"""
MCP server exposing the FNIRSI 1014D over its custom CDC command interface.

Run directly for stdio transport:
    python fnirsi_mcp.py

Register with Claude Code:
    claude mcp add fnirsi -- python C:/Fnirsi_Oscilloscope/host/fnirsi_mcp.py

Environment:
    FNIRSI_PORT   serial port to use (default: auto-detect USB 0483:5740)

The connection is opened lazily and held open between calls, because the scope's
reply latency is bound by its main loop (~200 ms per round trip) and reopening the
port per call would add a further ~300 ms of settling.

Requires: pyserial, mcp
"""

from __future__ import annotations

import os
import threading
from typing import Optional

# The SDK renamed FastMCP -> MCPServer in mcp 2.x. Same decorator/run shape either way,
# so support both rather than pinning the caller to one generation.
try:
    from mcp.server.mcpserver import MCPServer as _Server   # mcp >= 2
except ImportError:                                          # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server        # mcp 1.x

from fnirsi_scope import (
    FnirsiScope,
    ScopeError,
    find_scope_port,
)

mcp = _Server("fnirsi-1014d")

_scope: Optional[FnirsiScope] = None
_lock = threading.Lock()


def _get_scope() -> FnirsiScope:
    """Open (or reuse) the connection. Callers must hold _lock."""
    global _scope
    if _scope is None:
        port = os.environ.get("FNIRSI_PORT") or find_scope_port()
        if not port:
            raise ScopeError(
                "No scope found. Looked for USB 0483:5740. Is it connected and in "
                "CDC mode? Set it via Factory settings -> USB mode on the scope, or "
                "set FNIRSI_PORT explicitly."
            )
        _scope = FnirsiScope(port).open()
    return _scope


def _reset() -> None:
    """Drop the cached connection so the next call reconnects."""
    global _scope
    if _scope is not None:
        try:
            _scope.close()
        except Exception:
            pass
        _scope = None


def _guarded(fn):
    """Serialise access and turn a dead link into one clean retry."""
    def wrapper(*args, **kwargs):
        with _lock:
            try:
                return fn(_get_scope(), *args, **kwargs)
            except (ScopeError, OSError) as first:
                _reset()
                try:
                    return fn(_get_scope(), *args, **kwargs)
                except Exception as second:
                    return {"error": f"{type(second).__name__}: {second}",
                            "first_attempt": str(first)}
    return wrapper


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def identify() -> dict:
    """Identify the connected oscilloscope: model, firmware version, FPGA variant."""
    return _guarded(lambda s: s.identify())()


@mcp.tool()
def get_status() -> dict:
    """
    Full settings snapshot: timebase, trigger, both channels, acquisition state.

    Returns raw firmware indices plus decoded labels (e.g. timeperdiv 20 alongside
    timebase_label "200us"). Prefer this single call over many individual queries --
    each round trip costs roughly 200 ms.
    """
    return _guarded(lambda s: s.status())()


@mcp.tool()
def set_run_state(running: bool) -> dict:
    """Start (running=true) or stop (running=false) acquisition."""
    def go(s, running):
        s.run() if running else s.stop()
        return {"runstate": "RUNNING" if s.running else "STOPPED"}
    return _guarded(go)(running)


@mcp.tool()
def measure(channel: str = "CH1") -> dict:
    """
    Measurements from the most recent acquisition on CH1 or CH2:
    min, max, avg, center, peak-to-peak, rms.

    These are the firmware's internal values; their absolute scaling is unverified
    on this unit, so treat them as relative rather than calibrated readings.
    """
    return _guarded(lambda s, c: s.measure(c))(channel)


@mcp.tool()
def capture_waveform(channel: str = "CH1", max_points: int = 512,
                     decimation: int = 1) -> dict:
    """
    Capture the raw trace buffer for CH1 or CH2.

    decimation asks the firmware to transmit every Nth sample (1-64), cutting the
    serial transfer time by that factor -- use ~5 for a fast live view, 1 for full
    resolution. Older firmware ignores it via an automatic fallback.

    Samples are raw ADC bytes (0-255, mid-scale ~128); no voltage axis is fabricated,
    because the per-channel calibration is not exposed by the firmware. Returns
    summary statistics always, and the samples themselves decimated to at most
    max_points so a full 16382-sample trace does not flood the conversation. Set
    max_points to 0 to omit the samples entirely.
    """
    def go(s, channel, max_points, decimation):
        wf = s.capture(channel, decimation=decimation)
        samples = wf.samples
        result = {
            "channel": wf.channel,
            "sample_count": len(samples),
            "timebase_label": wf.timebase_label,
            "seconds_per_div": wf.seconds_per_div,
            "volts_per_div_label": wf.voltdiv_label,
            "duration_seconds": wf.duration_seconds,
            "min": min(samples) if samples else None,
            "max": max(samples) if samples else None,
            "mean": round(sum(samples) / len(samples), 2) if samples else None,
            "peak_to_peak": (max(samples) - min(samples)) if samples else None,
            "units": "raw ADC counts (0-255, mid-scale 128)",
            "wire_decimation": wf.decimation,
        }
        if max_points and samples:
            step = max(1, len(samples) // max_points)
            result["samples"] = samples[::step][:max_points]
            result["decimation"] = step
        return result

    return _guarded(go)(channel, max_points, decimation)


@mcp.tool()
def live_view(decimation: int = 5) -> dict:
    """
    The whole live view in one scope round trip: full status plus a decimated trace
    for each enabled channel. This is the cheapest way to watch the instrument --
    prefer it over separate get_status/capture_waveform calls when polling.

    decimation: firmware sends every Nth sample (1-64, default 5 -> 600 points).
    On firmware predating :LIVE? it falls back to the separate calls automatically.
    """
    def go(s, decimation):
        try:
            status, waves = s.live(decimation)
        except ScopeError:
            status = s.status()
            waves = {}
            if status.get("ch1_enable"):
                waves["CH1"] = s.capture("CH1", with_scaling=False,
                                         decimation=decimation)
            if status.get("ch2_enable"):
                waves["CH2"] = s.capture("CH2", with_scaling=False,
                                         decimation=decimation)

        def pack(wf):
            if wf is None:
                return None
            ss = wf.samples
            return {
                "channel": wf.channel,
                "samples": ss,
                "sample_count": len(ss),
                "min": min(ss) if ss else None,
                "max": max(ss) if ss else None,
                "mean": round(sum(ss) / len(ss), 2) if ss else None,
                "peak_to_peak": (max(ss) - min(ss)) if ss else None,
                "wire_decimation": wf.decimation,
                "units": "raw ADC counts (0-255, mid-scale 128)",
            }

        return {"status": status,
                "ch1": pack(waves.get("CH1")),
                "ch2": pack(waves.get("CH2"))}

    return _guarded(go)(decimation)


@mcp.tool()
def set_timebase(index: int) -> dict:
    """
    Set the horizontal timebase by index into the firmware's 35-entry table
    (0 = 50 s/div ... 34 = 5 ns/div; indices 0-10 are roll mode).

    Returns the index actually reached and its label. The firmware deliberately remaps
    indices 7-10 -- the roll/sweep overlap where 200ms/100ms/50ms/20ms appear in both
    blocks -- so the result can differ from what was requested.
    """
    def go(s, index):
        actual = s.set_timebase(index)
        from fnirsi_scope import TIMEBASE_LABELS, timebase_seconds
        return {
            "requested": index,
            "actual": actual,
            "label": TIMEBASE_LABELS[actual] if 0 <= actual < 35 else None,
            "seconds_per_div": timebase_seconds(actual),
            "roll_mode": actual <= 10,
        }
    return _guarded(go)(index)


@mcp.tool()
def set_trigger(source: int = None, mode: int = None,
                edge: int = None, level: int = None) -> dict:
    """
    Configure the trigger. All arguments optional; only those given are changed.

    source: 0=CH1, 1=CH2
    mode:   0=AUTO, 1=SINGLE, 2=NORMAL
    edge:   0=RISING, 1=FALLING
    level:  ADC counts 0-255 (mid-scale 128)

    Setting SINGLE mode is how you arm a one-shot capture.
    """
    def go(s, source, mode, edge, level):
        out = {}
        if source is not None or mode is not None or edge is not None:
            s.set_trigger(source=source, mode=mode, edge=edge)
        if level is not None:
            out["level_actual"] = s.set_trigger_level(level)
        st = s.status()
        out.update({
            "source": st.get("trig_channel"),
            "mode": st.get("trig_mode_label"),
            "edge": st.get("trig_edge_label"),
            "level": st.get("trig_level"),
        })
        return out
    return _guarded(go)(source, mode, edge, level)


@mcp.tool()
def configure_channel(channel: str = "CH1", voltdiv: int = None,
                      coupling: int = None, enabled: bool = None) -> dict:
    """
    Configure CH1 or CH2. All arguments optional; only those given are changed.

    voltdiv:  index 0-6 into the channel's volts-per-div row, where 0 is the LARGEST
              V/div and 6 the smallest (the firmware table is in descending order).
    coupling: 0=DC, 1=AC
    enabled:  channel on/off

    Returns the resulting channel state with decoded labels.
    """
    def go(s, channel, voltdiv, coupling, enabled):
        s.configure_channel(channel, voltdiv=voltdiv,
                            coupling=coupling, enabled=enabled)
        st = s.status()
        key = "ch1" if channel.upper() == "CH1" else "ch2"
        return {
            "channel": channel.upper(),
            "enabled": bool(st.get(f"{key}_enable")),
            "voltdiv_index": st.get(f"{key}_voltdiv"),
            "voltdiv_label": st.get(f"{key}_voltdiv_label"),
            "volts_per_div": st.get(f"{key}_volts_per_div"),
            "coupling": st.get(f"{key}_coupling_label"),
            "probe": st.get(f"{key}_probe_label"),
        }
    return _guarded(go)(channel, voltdiv, coupling, enabled)


@mcp.tool()
def raw_command(command: str) -> dict:
    """
    Send a raw protocol command and return its response lines.

    Escape hatch for commands not yet wrapped as tools. Every response ends with a
    "#END" line, which is stripped; errors surface as "#ERR <reason>".

    Implemented: *IDN? *PING :SYST:STAT? :RUN :STOP :RUN? :ACQ:*? :TIM:SCALE[?]
    :TIM:RATE? :TIM:LONG? :TIM:POS? :TRIG:{SOUR,MODE,EDGE,LEV}[?] :WAV:DATA? and the
    per-channel :CH1:/:CH2: queries and setters (VOLTDIV, COUPL, STAT).
    """
    return _guarded(lambda s, c: {"command": c, "response": s.command(c)})(command)


if __name__ == "__main__":
    # stdio by default (local use). Set FNIRSI_MCP_TRANSPORT=streamable-http to serve over
    # HTTP instead -- which is how this runs on a remote host such as a Pi with the scope
    # attached, with the port then published to the outside world by whatever tunnel or
    # proxy fronts that machine.
    transport = os.environ.get("FNIRSI_MCP_TRANSPORT", "stdio")

    if transport == "stdio":
        mcp.run()
    else:
        host = os.environ.get("FNIRSI_MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("FNIRSI_MCP_PORT", "8765"))
        try:
            mcp.run(transport=transport, host=host, port=port)
        except TypeError:
            # Older SDKs take host/port from settings rather than run() kwargs.
            for attr, value in (("host", host), ("port", port)):
                if hasattr(mcp, "settings"):
                    setattr(mcp.settings, attr, value)
            mcp.run(transport=transport)
