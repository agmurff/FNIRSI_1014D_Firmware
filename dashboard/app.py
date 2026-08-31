"""
Live dashboard + control panel for the FNIRSI 1014D.

Polls the scope's MCP server (running on whichever machine the scope is physically
attached to), serves a scope-lookalike page, accepts control actions from it, and
reverse-proxies the MCP endpoint at /mcp so agents elsewhere can drive the same
instrument through this container's public URL.

Config via environment:
    FNIRSI_MCP_URL     MCP endpoint            (default http://10.0.20.172:8765/mcp)
    POLL_INTERVAL      seconds between polls   (default 0.2 -- effectively continuous)
    CAPTURE_CH2        also poll CH2           (default 1)
    WIRE_DECIMATION    firmware sends every Nth sample (default 5; 1 = full 3000)
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = os.environ.get("FNIRSI_MCP_URL", "http://10.0.20.172:8765/mcp")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "0.2"))
CAPTURE_CH2 = os.environ.get("CAPTURE_CH2", "1") not in ("0", "false", "False")
WIRE_DECIMATION = int(os.environ.get("WIRE_DECIMATION", "5"))

app = FastAPI(title="FNIRSI 1014D dashboard")

STATE: dict[str, Any] = {
    "connected": False,
    "error": None,
    "updated_at": None,
    "poll_ms": None,
    "identity": None,
    "status": None,
    "ch1": None,
    "ch2": None,
    "measure_ch1": None,
    "measure_ch2": None,
    "consecutive_failures": 0,
    "wire_decimation": WIRE_DECIMATION,
}

# One MCP session shared by the poller and the control endpoint; the scope end
# serialises on a single serial port anyway, so contention resolves there too.
MCP_LOCK = asyncio.Lock()
SESSION: ClientSession | None = None

CONTROL_TOOLS = {
    "set_run_state": {"running"},
    "set_timebase": {"index"},
    "set_trigger": {"source", "mode", "edge", "level"},
    "configure_channel": {"channel", "voltdiv", "coupling", "enabled"},
}


def _unwrap(result) -> Any:
    for part in result.content:
        text = getattr(part, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except ValueError:
            return {"raw": text}
    return None


def _stats(wave: dict | None, status: dict | None) -> dict | None:
    """
    Per-channel summary. min/max/mean/pp come free from capture_waveform (computed over
    the full transmitted set); AC RMS and a frequency ESTIMATE (zero crossings about the
    mean, with hysteresis) are derived here. The firmware's own frequency comes from FPGA
    counters that are not on the wire, so this is an estimate and is labelled as one.
    """
    if not wave or wave.get("error") or not wave.get("samples"):
        return None

    samples = wave["samples"]
    mean = wave.get("mean") or (sum(samples) / len(samples))
    ac_rms = (sum((s - mean) ** 2 for s in samples) / len(samples)) ** 0.5
    pp = wave.get("peak_to_peak") or 0

    freq = 0.0
    spd = (status or {}).get("seconds_per_div")
    total = (status or {}).get("samplecount")
    wire_decim = wave.get("wire_decimation") or 1
    if spd and total and pp >= 8:
        # dt per full-rate sample, assuming the buffer spans the 14-division screen;
        # crude, but matches the scope's own zero-crossing idea well enough for a readout
        dt = (spd * 14.0) / float(total) * wire_decim
        hyst = max(2.0, pp / 4.0)
        crossings = 0
        armed = samples[0] > mean + hyst
        for s in samples:
            if armed and s < mean - hyst:
                armed = False
            elif not armed and s > mean + hyst:
                armed = True
                crossings += 1
        span = dt * (len(samples) - 1)
        if span > 0 and crossings >= 2:
            freq = (crossings - 1) / span if crossings > 1 else 0.0

    return {
        "min": wave.get("min"),
        "max": wave.get("max"),
        "mean": round(mean, 2),
        "pp": pp,
        "ac_rms": round(ac_rms, 2),
        "freq_est_hz": round(freq, 1),
    }


async def _poll_once(session: ClientSession) -> None:
    started = time.monotonic()

    async with MCP_LOCK:
        status = _unwrap(await session.call_tool("get_status", {}))
        if isinstance(status, dict) and status.get("error"):
            raise RuntimeError(status["error"])

        ch1 = _unwrap(await session.call_tool("capture_waveform", {
            "channel": "CH1", "max_points": 3000, "decimation": WIRE_DECIMATION}))

        ch2 = None
        if CAPTURE_CH2 and status and status.get("ch2_enable"):
            ch2 = _unwrap(await session.call_tool("capture_waveform", {
                "channel": "CH2", "max_points": 3000, "decimation": WIRE_DECIMATION}))

    STATE.update(
        connected=True,
        error=None,
        updated_at=time.time(),
        poll_ms=int((time.monotonic() - started) * 1000),
        status=status,
        ch1=ch1,
        ch2=ch2,
        measure_ch1=_stats(ch1, status),
        measure_ch2=_stats(ch2, status),
        consecutive_failures=0,
    )


async def poller() -> None:
    global SESSION
    backoff = 1.0
    while True:
        try:
            async with streamable_http_client(MCP_URL) as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    SESSION = session
                    STATE["identity"] = _unwrap(
                        await session.call_tool("identify", {}))
                    backoff = 1.0
                    while True:
                        await _poll_once(session)
                        await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            SESSION = None
            raise
        except Exception as exc:  # noqa: BLE001
            SESSION = None
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
    app.state.proxy = httpx.AsyncClient(timeout=httpx.Timeout(None))


@app.on_event("shutdown")
async def _shutdown() -> None:
    app.state.task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await app.state.task
    await app.state.proxy.aclose()


@app.get("/api/state")
async def api_state() -> JSONResponse:
    out = dict(STATE)
    out["updated_ago"] = (
        round(time.time() - STATE["updated_at"], 1)
        if STATE["updated_at"] else None
    )
    return JSONResponse(out)


@app.post("/api/control")
async def api_control(request: Request) -> JSONResponse:
    """
    Drive the scope from the page. Only whitelisted tools and arguments pass,
    everything else is refused -- this is a control panel, not a generic RPC hole.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    tool = body.get("tool")
    args = body.get("args") or {}
    allowed = CONTROL_TOOLS.get(tool)
    if allowed is None:
        return JSONResponse({"error": f"tool not allowed: {tool}"}, status_code=400)
    if not isinstance(args, dict) or set(args) - allowed:
        return JSONResponse({"error": "argument not allowed"}, status_code=400)

    session = SESSION
    if session is None:
        return JSONResponse({"error": "scope link down"}, status_code=503)

    try:
        async with MCP_LOCK:
            result = _unwrap(await session.call_tool(tool, args))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=502)

    return JSONResponse({"ok": True, "result": result})


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"ok": True, "scope_connected": STATE["connected"]})


# ---------------------------------------------------------------------------
# MCP reverse proxy: this container's /mcp IS the scope's MCP endpoint, so one
# public URL serves both people (the page) and agents (the protocol).
#   claude mcp add --transport http fnirsi <public-url>/mcp
# Streamable HTTP is plain POST/GET/DELETE with optional SSE responses, so a
# byte-for-byte streaming proxy that preserves the session headers is enough.
# ---------------------------------------------------------------------------
_HOP = {"host", "content-length", "transfer-encoding", "connection", "keep-alive"}


@app.api_route("/mcp", methods=["POST", "GET", "DELETE"])
async def mcp_proxy(request: Request):
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP}
    body = await request.body()

    client: httpx.AsyncClient = app.state.proxy
    upstream = client.build_request(request.method, MCP_URL,
                                    headers=headers, content=body)
    try:
        resp = await client.send(upstream, stream=True)
    except httpx.HTTPError as exc:
        return JSONResponse({"error": f"scope MCP unreachable: {exc}"}, status_code=502)

    resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _HOP}

    async def body_iter():
        try:
            async for chunk in resp.aiter_raw():
                yield chunk
        finally:
            await resp.aclose()

    return StreamingResponse(body_iter(), status_code=resp.status_code,
                             headers=resp_headers,
                             media_type=resp.headers.get("content-type"))


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
