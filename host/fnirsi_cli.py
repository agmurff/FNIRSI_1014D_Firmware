#!/usr/bin/env python3
"""
JSON command-line front end for the FNIRSI 1014D CDC interface.

Intended for driving the scope from a remote shell (e.g. over the nobgp MCP), where a
structured result is far more useful than formatted text. Every subcommand prints one
JSON object to stdout; failures print {"error": ...} and exit non-zero.

    ./fnirsi_cli.py ports
    ./fnirsi_cli.py identify
    ./fnirsi_cli.py status
    ./fnirsi_cli.py run | stop
    ./fnirsi_cli.py measure --channel CH1
    ./fnirsi_cli.py capture --channel CH1 --max-points 32
    ./fnirsi_cli.py set-timebase 20
    ./fnirsi_cli.py set-trigger --mode 0 --edge 0 --level 128
    ./fnirsi_cli.py set-channel --channel CH1 --voltdiv 3 --coupling 0
    ./fnirsi_cli.py raw ':SYST:STAT?'

Port defaults to auto-detection of USB 0483:5740, or $FNIRSI_PORT.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fnirsi_scope import (  # noqa: E402
    FnirsiScope,
    ScopeError,
    find_scope_port,
    TIMEBASE_LABELS,
    timebase_seconds,
)


def emit(obj, code=0):
    json.dump(obj, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(code)


def list_ports():
    from serial.tools import list_ports as lp
    return [
        {
            "device": p.device,
            "vid": f"{p.vid:04x}" if p.vid is not None else None,
            "pid": f"{p.pid:04x}" if p.pid is not None else None,
            "description": p.description,
            "is_scope": (p.vid == 0x0483 and p.pid == 0x5740),
        }
        for p in lp.comports()
    ]


def main():
    ap = argparse.ArgumentParser(description="FNIRSI 1014D remote control")
    ap.add_argument("--port", default=os.environ.get("FNIRSI_PORT"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ports")
    sub.add_parser("identify")
    sub.add_parser("status")
    sub.add_parser("run")
    sub.add_parser("stop")

    p = sub.add_parser("measure")
    p.add_argument("--channel", default="CH1")

    p = sub.add_parser("capture")
    p.add_argument("--channel", default="CH1")
    p.add_argument("--max-points", type=int, default=64,
                   help="decimate to at most this many samples; 0 omits samples")

    p = sub.add_parser("set-timebase")
    p.add_argument("index", type=int)

    p = sub.add_parser("set-trigger")
    p.add_argument("--source", type=int)
    p.add_argument("--mode", type=int)
    p.add_argument("--edge", type=int)
    p.add_argument("--level", type=int)

    p = sub.add_parser("set-channel")
    p.add_argument("--channel", default="CH1")
    p.add_argument("--voltdiv", type=int)
    p.add_argument("--coupling", type=int)
    p.add_argument("--enabled", type=int, choices=[0, 1])

    p = sub.add_parser("raw")
    p.add_argument("command")

    args = ap.parse_args()

    if args.cmd == "ports":
        emit({"ports": list_ports()})

    port = args.port or find_scope_port()
    if not port:
        emit({"error": "no scope found (looked for USB 0483:5740)",
              "hint": "is it plugged in and in CDC mode? On the scope: "
                      "Factory settings -> USB mode",
              "ports": list_ports()}, 1)

    try:
        with FnirsiScope(port) as s:
            if args.cmd == "identify":
                emit({"port": port, **s.identify()})

            if args.cmd == "status":
                emit({"port": port, **s.status()})

            if args.cmd in ("run", "stop"):
                s.run() if args.cmd == "run" else s.stop()
                emit({"runstate": "RUNNING" if s.running else "STOPPED"})

            if args.cmd == "measure":
                emit({"channel": args.channel.upper(), **s.measure(args.channel)})

            if args.cmd == "capture":
                wf = s.capture(args.channel)
                samples = wf.samples
                out = {
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
                }
                if args.max_points and samples:
                    step = max(1, len(samples) // args.max_points)
                    out["samples"] = samples[::step][:args.max_points]
                    out["decimation"] = step
                emit(out)

            if args.cmd == "set-timebase":
                actual = s.set_timebase(args.index)
                emit({
                    "requested": args.index,
                    "actual": actual,
                    "label": TIMEBASE_LABELS[actual] if 0 <= actual < 35 else None,
                    "seconds_per_div": timebase_seconds(actual),
                    "roll_mode": actual <= 10,
                })

            if args.cmd == "set-trigger":
                out = {}
                if any(v is not None for v in (args.source, args.mode, args.edge)):
                    s.set_trigger(source=args.source, mode=args.mode, edge=args.edge)
                if args.level is not None:
                    out["level_actual"] = s.set_trigger_level(args.level)
                st = s.status()
                out.update({
                    "source": st.get("trig_channel"),
                    "mode": st.get("trig_mode_label"),
                    "edge": st.get("trig_edge_label"),
                    "level": st.get("trig_level"),
                })
                emit(out)

            if args.cmd == "set-channel":
                s.configure_channel(
                    args.channel,
                    voltdiv=args.voltdiv,
                    coupling=args.coupling,
                    enabled=None if args.enabled is None else bool(args.enabled),
                )
                st = s.status()
                key = "ch1" if args.channel.upper() == "CH1" else "ch2"
                emit({
                    "channel": args.channel.upper(),
                    "enabled": bool(st.get(f"{key}_enable")),
                    "voltdiv_index": st.get(f"{key}_voltdiv"),
                    "voltdiv_label": st.get(f"{key}_voltdiv_label"),
                    "volts_per_div": st.get(f"{key}_volts_per_div"),
                    "coupling": st.get(f"{key}_coupling_label"),
                    "probe": st.get(f"{key}_probe_label"),
                })

            if args.cmd == "raw":
                emit({"command": args.command, "response": s.command(args.command)})

    except ScopeError as e:
        emit({"error": str(e), "type": "ScopeError", "port": port}, 1)
    except Exception as e:  # noqa: BLE001
        emit({"error": str(e), "type": type(e).__name__, "port": port}, 1)


if __name__ == "__main__":
    main()
