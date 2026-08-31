# Host tooling for the FNIRSI 1014D CDC command interface

Companion to the firmware on this branch, which exposes a line-oriented command
interface over USB CDC. See `fnirsi_101xd_scope/PC_interface.c` for the firmware side.

## Getting the scope onto the command interface

The scope boots into **USB mass storage**. To reach the command interface, on the scope:

> main menu → **Factory settings** → **USB mode**  (toggles `MSC` ⇄ `CDC`)

It then enumerates as USB `0483:5740` — `/dev/ttyACM0` on Linux, a COM port on Windows.

Note that the config sector lives inside the span the SD image occupies, so **every
firmware flash resets the USB mode back to MSC** and it has to be re-selected.

## Files

| File | Purpose |
|---|---|
| `fnirsi_scope.py` | Client library. Protocol framing, index→unit tables, waveform decode. |
| `fnirsi_cli.py` | JSON command line — for driving the scope from a remote shell. |
| `fnirsi_mcp.py` | MCP server, so an agent can drive the bench directly. |
| `noise_sweep.py` | Example: automated noise-floor characterisation across sensitivities. |

## Install

```bash
pip install -r requirements.txt      # pyserial; mcp only needed for the MCP server
```

`pyserial` alone is enough for the library and the CLI.

## CLI

```bash
./fnirsi_cli.py ports                                   # what serial devices exist
./fnirsi_cli.py identify
./fnirsi_cli.py status                                  # full snapshot, decoded
./fnirsi_cli.py capture --channel CH1 --max-points 32
./fnirsi_cli.py set-timebase 20
./fnirsi_cli.py set-trigger --mode 0 --edge 0 --level 128
./fnirsi_cli.py set-channel --channel CH1 --voltdiv 3 --coupling 0
./fnirsi_cli.py raw ':SYST:STAT?'
```

Every subcommand prints one JSON object. Port is auto-detected by VID:PID, or set
`FNIRSI_PORT`.

## MCP server

```bash
claude mcp add fnirsi -- python3 /path/to/fnirsi_mcp.py
```

Tools: `identify`, `get_status`, `set_run_state`, `set_timebase`, `set_trigger`,
`configure_channel`, `measure`, `capture_waveform`, `raw_command`.

The server holds the serial port open between calls to avoid ~300 ms of reconnect
latency per operation, so **the CLI and the MCP server cannot both use the scope at
once** — the second one gets a permission error on the port.

## Things worth knowing

**Values on the wire are raw firmware table indices, not engineering units.** The
firmware works in indices throughout and has no `printf`, so unit conversion happens
here. The tables in `fnirsi_scope.py` are transcribed from the firmware's `variables.c`.

**Volts-per-div indices are in descending order** — index 0 is the *largest* V/div,
index 6 the smallest. (`variables.c` contains two `volt_div_texts` definitions in
opposite orders; the ascending one is inside a block comment.)

**Timebase indices 7–10 are unreachable** — they are the roll/sweep overlap where
200 ms…20 ms appear in both blocks, and the firmware remaps them. `set_timebase()`
returns the index actually reached, which is why it is worth reading the result.

**Trigger level is pixel-quantised.** The level derives from the on-screen marker
position, so the achieved level can differ from the request by a count or two;
`set_trigger_level()` returns what was actually achieved.

**Waveform samples are raw ADC counts (0–255, mid-scale ≈128).** No voltage axis is
fabricated, because the per-channel calibration is not exposed by the firmware.

**Measurements** (`measure`) are the firmware's own internal values; their absolute
scaling is unverified, so treat them as relative. Note also that PORT_AUDIT F31 records
that AC/DC coupling was historically never pushed to the FPGA, so reported coupling is
the setting rather than a guaranteed hardware state.

**Round-trip latency is ~200 ms**, bound by the scope's acquisition main loop. Prefer a
single `status` call over many individual queries.
