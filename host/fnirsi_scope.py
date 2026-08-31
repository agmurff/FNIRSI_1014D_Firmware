"""
Host-side client for the FNIRSI 1014D running the custom CDC command interface.

Protocol (implemented in PC_interface.c, usb_CDC_process_rx):
    every command returns zero or more response lines followed by exactly one "#END".
    Setters that succeed return "#OK" first; failures return "#ERR <reason>".

Values on the wire are raw firmware table indices, not engineering units -- the firmware
works in indices throughout and has no printf. The index -> unit tables below are
transcribed from the firmware's own variables.c so the conversion happens here, once.

Requires: pyserial
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import serial  # pyserial
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pyserial is required:  pip install pyserial") from exc


# ---------------------------------------------------------------------------
# Tables transcribed from fnirsi_101xd_scope/variables.c
# ---------------------------------------------------------------------------

# time_div_texts[35] (variables.c:518, PORT_1014D branch).
# Indices 0..10 are the "long timebase" / roll-mode entries, which the firmware
# handles through a separate FPGA path (scopesettings.long_mode).
TIMEBASE_LABELS = [
    "50s", "20s", "10s", "5s", "2s", "1s", "500ms", "200ms", "100ms", "50ms", "20ms",
    "200ms", "100ms", "50ms", "20ms", "10ms", "5ms", "2ms", "1ms", "500us",
    "200us", "100us", "50us", "20us", "10us", "5us", "2us", "1us", "500ns",
    "200ns", "100ns", "50ns", "20ns", "10ns", "5ns",
]
LONG_TIMEBASE_MAX_INDEX = 10  # indices <= this are roll mode

# volt_div_texts[7][7] (variables.c:679 -- the LIVE definition; the ascending-order
# copy at :641 is inside a block comment). Rows are probe/magnification settings,
# columns are the volts-per-div index. Note the DESCENDING order.
PROBE_LABELS = ["0.5x", "1x", "10x", "20x", "50x", "100x", "1000x"]
VOLTDIV_LABELS = [
    ["2.5V", "1.25V", "500mV", "250mV", "100mV", "50mV", "25mV"],      # 0.5
    ["5V", "2.5V", "1V", "500mV", "200mV", "100mV", "50mV"],           # 1
    ["50V", "25V", "10V", "5V", "2V", "1V", "500mV"],                  # 10
    ["100V", "50V", "20V", "10V", "4V", "2V", "1V"],                   # 20
    ["250V", "125V", "50V", "25V", "10V", "5V", "2.5V"],               # 50
    ["500V", "250V", "100V", "50V", "20V", "10V", "5V"],               # 100
    ["5kV", "2.5kV", "1kV", "500V", "200V", "100V", "50V"],            # 1000
]

COUPLING_LABELS = {0: "DC", 1: "AC"}
TRIGGER_MODE_LABELS = {0: "AUTO", 1: "SINGLE", 2: "NORMAL"}
TRIGGER_EDGE_LABELS = {0: "RISING", 1: "FALLING"}
RUN_STATE_LABELS = {0: "STOPPED", 1: "RUNNING"}

_SI = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9}
_VOLT = {"kV": 1e3, "V": 1.0, "mV": 1e-3}


def _parse_scaled(text: str, units: dict) -> Optional[float]:
    m = re.fullmatch(r"([0-9.]+)\s*([a-zA-Z]+)", text)
    if not m:
        return None
    value, unit = m.group(1), m.group(2)
    if unit not in units:
        return None
    return float(value) * units[unit]


def timebase_seconds(index: int) -> Optional[float]:
    """Seconds per division for a timebase index, or None if out of range."""
    if not 0 <= index < len(TIMEBASE_LABELS):
        return None
    return _parse_scaled(TIMEBASE_LABELS[index], _SI)


def voltdiv_volts(probe_index: int, voltdiv_index: int) -> Optional[float]:
    """Volts per division, or None if either index is out of range."""
    if not (0 <= probe_index < 7 and 0 <= voltdiv_index < 7):
        return None
    return _parse_scaled(VOLTDIV_LABELS[probe_index][voltdiv_index], _VOLT)


class ScopeError(RuntimeError):
    """The scope returned #ERR, or the response was malformed."""


@dataclass
class Waveform:
    channel: str
    samples: list = field(default_factory=list)   # raw ADC bytes, 0..255
    decimation: int = 1                           # firmware sent every Nth sample
    seconds_per_div: Optional[float] = None
    volts_per_div: Optional[float] = None
    timebase_label: Optional[str] = None
    voltdiv_label: Optional[str] = None

    def __len__(self) -> int:
        return len(self.samples)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Total captured span, assuming the standard 12 horizontal divisions."""
        if self.seconds_per_div is None or not self.samples:
            return None
        return self.seconds_per_div * 12.0


class FnirsiScope:
    """
    Line-oriented client. Use as a context manager:

        with FnirsiScope("COM51") as scope:
            print(scope.identify())
            wf = scope.capture("CH1")
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0):
        self.port = port
        self._ser = serial.Serial()
        self._ser.port = port
        self._ser.baudrate = baudrate      # ignored by CDC, but pyserial wants it
        self._ser.timeout = timeout
        self._ser.dtr = True
        self._ser.rts = True

    # -- lifecycle ---------------------------------------------------------
    def open(self) -> "FnirsiScope":
        if not self._ser.is_open:
            self._ser.open()
            time.sleep(0.3)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        return self

    def close(self) -> None:
        if self._ser.is_open:
            self._ser.close()

    def __enter__(self) -> "FnirsiScope":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    # -- transport ---------------------------------------------------------
    def command(self, cmd: str, read_timeout: float = 10.0) -> list:
        """Send one command, return its response lines (excluding the #END)."""
        if not self._ser.is_open:
            raise ScopeError("port is not open")

        self._ser.reset_input_buffer()
        self._ser.write((cmd + "\n").encode("ascii"))
        self._ser.flush()

        lines: list = []
        deadline = time.monotonic() + read_timeout

        while time.monotonic() < deadline:
            raw = self._ser.readline()
            if not raw:
                continue
            line = raw.decode("ascii", errors="replace").strip()
            if line == "#END":
                break
            if line:
                lines.append(line)
        else:
            raise ScopeError(f"timed out waiting for #END after {cmd!r}")

        for line in lines:
            if line.startswith("#ERR"):
                raise ScopeError(f"{cmd!r} -> {line}")

        return lines

    def _query_int(self, cmd: str) -> int:
        lines = self.command(cmd)
        if not lines:
            raise ScopeError(f"{cmd!r} returned no value")
        return int(lines[0])

    # -- identity and status ----------------------------------------------
    def identify(self) -> dict:
        lines = self.command("*IDN?")
        if not lines:
            raise ScopeError("*IDN? returned nothing")
        parts = lines[0].split(",")
        return {
            "raw": lines[0],
            "manufacturer": parts[0] if len(parts) > 0 else None,
            "model": parts[1] if len(parts) > 1 else None,
            "firmware": parts[2] if len(parts) > 2 else None,
            "fpga": parts[3] if len(parts) > 3 else None,
        }

    def ping(self) -> bool:
        return self.command("*PING") == ["#OK"]

    def status(self) -> dict:
        """Full settings snapshot, with decoded labels alongside the raw indices."""
        out: dict = {}
        for line in self.command(":SYST:STAT?"):
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            try:
                out[key.strip()] = int(value.strip())
            except ValueError:
                out[key.strip()] = value.strip()

        tb = out.get("timeperdiv")
        if isinstance(tb, int):
            out["timebase_label"] = (TIMEBASE_LABELS[tb]
                                     if 0 <= tb < len(TIMEBASE_LABELS) else None)
            out["seconds_per_div"] = timebase_seconds(tb)
            out["roll_mode"] = tb <= LONG_TIMEBASE_MAX_INDEX

        for ch in ("ch1", "ch2"):
            probe = out.get(f"{ch}_probe")
            vdiv = out.get(f"{ch}_voltdiv")
            if isinstance(probe, int) and isinstance(vdiv, int):
                if 0 <= probe < 7 and 0 <= vdiv < 7:
                    out[f"{ch}_voltdiv_label"] = VOLTDIV_LABELS[probe][vdiv]
                    out[f"{ch}_volts_per_div"] = voltdiv_volts(probe, vdiv)
                    out[f"{ch}_probe_label"] = PROBE_LABELS[probe]
            coupling = out.get(f"{ch}_coupling")
            if isinstance(coupling, int):
                out[f"{ch}_coupling_label"] = COUPLING_LABELS.get(coupling)

        for key, table in (("runstate", RUN_STATE_LABELS),
                           ("trig_mode", TRIGGER_MODE_LABELS),
                           ("trig_edge", TRIGGER_EDGE_LABELS)):
            if isinstance(out.get(key), int):
                out[f"{key}_label"] = table.get(out[key])

        return out

    # -- run control -------------------------------------------------------
    def run(self) -> None:
        self.command(":RUN")

    def stop(self) -> None:
        self.command(":STOP")

    @property
    def running(self) -> bool:
        return self._query_int(":RUN?") == 1

    # -- configuration -----------------------------------------------------
    # Every setter takes a raw firmware index, matching the wire protocol. The firmware
    # routes each one through its own UI handler so the FPGA stays in sync, and echoes
    # back the value that actually stuck -- which is not always the one requested.

    def set_timebase(self, index: int) -> int:
        """
        Set the timebase by index into the 35-entry table. Returns the index actually
        reached: the firmware remaps 7..10 (the roll/sweep overlap) onto other entries.
        """
        if not 0 <= index <= 34:
            raise ValueError("timebase index must be 0..34")
        lines = self.command(f":TIM:SCALE {index}")
        for line in lines:
            if line.startswith("timeperdiv:"):
                return int(line.split(":", 1)[1])
        return index

    def set_trigger_level(self, level: int) -> int:
        """
        Set the trigger level in ADC counts (0..255, mid-scale 128). Returns the level
        actually achieved -- the on-screen marker is pixel-quantised, so it can land a
        count or two away from the request.
        """
        if not 0 <= level <= 255:
            raise ValueError("trigger level must be 0..255")
        lines = self.command(f":TRIG:LEV {level}")
        for line in lines:
            if line.startswith("trig_level:"):
                return int(line.split(":", 1)[1])
        return level

    def set_trigger(self, source=None, mode=None, edge=None) -> None:
        """source: 0=CH1 1=CH2   mode: 0=AUTO 1=SINGLE 2=NORMAL   edge: 0=RISING 1=FALLING"""
        if source is not None:
            self.command(f":TRIG:SOUR {int(source)}")
        if mode is not None:
            self.command(f":TRIG:MODE {int(mode)}")
        if edge is not None:
            self.command(f":TRIG:EDGE {int(edge)}")

    def configure_channel(self, channel: str = "CH1", voltdiv=None,
                          coupling=None, enabled=None) -> dict:
        """
        voltdiv: index 0..6 into the channel's row of VOLTDIV_LABELS (0 = largest V/div).
        coupling: 0=DC 1=AC.  enabled: bool.
        Returns the resulting per-channel state.
        """
        ch = channel.upper()
        if ch not in ("CH1", "CH2"):
            raise ValueError("channel must be CH1 or CH2")

        result: dict = {}

        if voltdiv is not None:
            if not 0 <= int(voltdiv) <= 6:
                raise ValueError("voltdiv index must be 0..6")
            lines = self.command(f":{ch}:VOLTDIV {int(voltdiv)}")
            for line in lines:
                if line.startswith("voltdiv:"):
                    result["voltdiv"] = int(line.split(":", 1)[1])
        if coupling is not None:
            self.command(f":{ch}:COUPL {int(coupling)}")
            result["coupling"] = int(coupling)
        if enabled is not None:
            self.command(f":{ch}:STAT {1 if enabled else 0}")
            result["enabled"] = bool(enabled)

        return result

    # -- measurements ------------------------------------------------------
    def measure(self, channel: str = "CH1") -> dict:
        """
        Measurements from the most recent completed acquisition.

        NOTE: these are the firmware's internal values. Their scaling has not been
        verified against a known input on this unit, so treat them as relative.
        """
        ch = channel.upper()
        if ch not in ("CH1", "CH2"):
            raise ValueError("channel must be CH1 or CH2")
        return {
            name.lower(): self._query_int(f":{ch}:{name}?")
            for name in ("MIN", "MAX", "AVG", "CENTER", "PP", "RMS")
        }

    # -- waveform ----------------------------------------------------------
    def capture(self, channel: str = "CH1", with_scaling: bool = True,
                decimation: int | None = None) -> Waveform:
        """
        Read the raw acquisition buffer for one channel.

        Samples are raw ADC bytes (0..255, mid-scale ~128). Converting these to volts
        needs the per-channel calibration the firmware holds but does not expose, so
        this deliberately does not fabricate a voltage axis.

        decimation asks the FIRMWARE to send every Nth sample (1..64), cutting the
        transfer time by that factor -- the full hex dump is what bounds a live-view
        poll. Older firmware without the argument gets one automatic retry without it.
        """
        ch = channel.upper()
        if ch not in ("CH1", "CH2"):
            raise ValueError("channel must be CH1 or CH2")

        cmd = f":WAV:DATA? {ch}"
        if decimation and int(decimation) > 1:
            cmd += f" {int(decimation)}"

        try:
            lines = self.command(cmd, read_timeout=30.0)
        except ScopeError:
            if decimation and int(decimation) > 1:
                # Firmware predating the decimation argument
                lines = self.command(f":WAV:DATA? {ch}", read_timeout=30.0)
            else:
                raise
        if not lines or not lines[0].startswith("#WAV"):
            raise ScopeError(f"unexpected waveform header: {lines[:1]}")

        header = lines[0].split()
        if len(header) < 3:
            raise ScopeError(f"malformed waveform header: {lines[0]!r}")
        expected = int(header[2])

        # Newer firmware follows the header with a "decim: N" line
        wire_decim = 1
        body = lines[1:]
        if body and body[0].startswith("decim:"):
            wire_decim = int(body[0].split(":", 1)[1])
            body = body[1:]

        hex_text = "".join(body)
        if len(hex_text) % 2:
            raise ScopeError("odd number of hex characters in waveform payload")

        samples = [int(hex_text[i:i + 2], 16) for i in range(0, len(hex_text), 2)]

        if len(samples) != expected:
            raise ScopeError(
                f"sample count mismatch: header said {expected}, decoded {len(samples)}"
            )

        wf = Waveform(channel=ch, samples=samples)
        wf.decimation = wire_decim

        if with_scaling:
            st = self.status()
            wf.seconds_per_div = st.get("seconds_per_div")
            wf.timebase_label = st.get("timebase_label")
            key = "ch1" if ch == "CH1" else "ch2"
            wf.volts_per_div = st.get(f"{key}_volts_per_div")
            wf.voltdiv_label = st.get(f"{key}_voltdiv_label")

        return wf


def find_scope_port() -> Optional[str]:
    """Return the first port whose VID:PID matches the firmware's CDC descriptors."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if p.vid == 0x0483 and p.pid == 0x5740:
            return p.device
    return None


if __name__ == "__main__":
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else find_scope_port()
    if not port:
        raise SystemExit("no scope found (looked for USB 0483:5740); pass a port explicitly")

    with FnirsiScope(port) as scope:
        print(f"port        : {port}")
        print(f"identify    : {scope.identify()['raw']}")
        st = scope.status()
        print(f"timebase    : {st.get('timebase_label')}/div  (index {st.get('timeperdiv')})")
        print(f"ch1         : {st.get('ch1_voltdiv_label')}/div  {st.get('ch1_coupling_label')}"
              f"  probe {st.get('ch1_probe_label')}")
        print(f"run state   : {st.get('runstate_label')}")
        wf = scope.capture("CH1")
        print(f"captured    : {len(wf)} samples, min={min(wf.samples)} max={max(wf.samples)}")
