"""
Live dashboard for the FNIRSI 1014D.

Polls the scope's MCP server (running on whichever machine the scope is physically
attached to) and serves a single-page view of what the instrument is doing.

Deliberately READ-ONLY. It observes; it does not drive. Adding setters here would mean
two things could change the scope's state at once with no coordination between them,
and a monitoring view that silently reconfigures the instrument is a bad trade.

Config via environment:
    FNIRSI_MCP_URL     MCP endpoint            (default http://10.0.20.172:8765/mcp)
    POLL_INTERVAL      seconds between polls   (default 2.0)
    CAPTURE_CH2        also poll CH2           (default 1)
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = os.environ.get("FNIRSI_MCP_URL", "http://10.0.20.172:8765/mcp")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "2.0"))
CAPTURE_CH2 = os.environ.get("CAPTURE_CH2", "1") not in ("0", "false", "False")
WAVE_POINTS = int(os.environ.get("WAVE_POINTS", "600"))

app = FastAPI(title="FNIRSI 1014D dashboard")

STATE: dict[str, Any] = {
    "connected": False,
    "error": None,
    "updated_at": None,
    "updated_ago": None,
    "poll_ms": None,
    "mcp_url": MCP_URL,
    "identity": None,
    "status": None,
    "ch1": None,
    "ch2": None,
    "measure_ch1": None,
    "measure_ch2": None,
    "consecutive_failures": 0,
}


def _unwrap(result) -> Any:
    """MCP tool results arrive as content parts; ours are single JSON objects."""
    import json
    for part in result.content:
        text = getattr(part, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except ValueError:
            return {"raw": text}
    return None


def _stats(wave: dict | None) -> dict | None:
    """
    Summary for a captured trace.

    The firmware's own `measure` tool costs SIX serial round trips per channel, which
    dominated the poll cycle and would monopolise the scope's single serial link --
    starving anything else talking to it. capture_waveform already returns min/max/mean/
    peak-to-peak computed over the FULL sample set, so those come free; RMS is derived
    here from the decimated samples, which is ample for a dashboard.
    """
    if not wave or wave.get("error") or not wave.get("samples"):
        return None

    samples = wave["samples"]
    mean = wave.get("mean")
    if mean is None:
        mean = sum(samples) / len(samples)

    # AC RMS: deviation about the mean, which is what matters with the trace centred
    # near mid-scale. Reported in ADC counts, like everything else.
    ac_rms = (sum((s - mean) ** 2 for s in samples) / len(samples)) ** 0.5

    return {
        "min": wave.get("min"),
        "max": wave.get("max"),
        "mean": round(mean, 2),
        "pp": wave.get("peak_to_peak"),
        "ac_rms": round(ac_rms, 2),
    }


async def _poll_once(session: ClientSession) -> None:
    started = time.monotonic()

    status = _unwrap(await session.call_tool("get_status", {}))

    # A tool that reports an error still returns 200; treat that as not-connected
    # rather than showing stale values as if they were live.
    if isinstance(status, dict) and status.get("error"):
        raise RuntimeError(status["error"])

    ch1 = _unwrap(await session.call_tool(
        "capture_waveform", {"channel": "CH1", "max_points": WAVE_POINTS}))

    ch2 = None
    if CAPTURE_CH2 and status and status.get("ch2_enable"):
        ch2 = _unwrap(await session.call_tool(
            "capture_waveform", {"channel": "CH2", "max_points": WAVE_POINTS}))

    STATE.update(
        connected=True,
        error=None,
        updated_at=time.time(),
        poll_ms=int((time.monotonic() - started) * 1000),
        status=status,
        ch1=ch1,
        ch2=ch2,
        measure_ch1=_stats(ch1),
        measure_ch2=_stats(ch2),
        consecutive_failures=0,
    )


async def poller() -> None:
    backoff = 1.0
    while True:
        try:
            async with streamable_http_client(MCP_URL) as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    STATE["identity"] = _unwrap(
                        await session.call_tool("identify", {}))
                    backoff = 1.0
                    while True:
                        await _poll_once(session)
                        await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            STATE.update(
                connected=False,
                error=f"{type(exc).__name__}: {exc}",
                consecutive_failures=STATE["consecutive_failures"] + 1,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


@app.on_event("startup")
async def _startup() -> None:
    app.state.task = asyncio.create_task(poller())


@app.on_event("shutdown")
async def _shutdown() -> None:
    app.state.task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await app.state.task


@app.get("/api/state")
async def api_state() -> JSONResponse:
    out = dict(STATE)
    out["updated_ago"] = (
        round(time.time() - STATE["updated_at"], 1)
        if STATE["updated_at"] else None
    )
    return JSONResponse(out)


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"ok": True, "scope_connected": STATE["connected"]})


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
