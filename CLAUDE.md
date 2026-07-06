# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Bare-metal firmware for the **FNIRSI 1013D / 1014D** handheld tablet oscilloscope. The
code originates from pecostm32's reverse-engineered replacement firmware for the **1013D**;
this fork (branch `PORT_A`) is an in-progress effort to **port it to the 1014D hardware**.
Everything is still named `fnirsi_1013d_*` even where it now targets the 1014D.

- **SoC:** Allwinner "suniv" (ARM926EJ-S core, ~600 MHz, DRAM based at `0x80000000`,
  32 MB). Peripheral registers live in the `0x01C2xxxx` sunxi range.
- **Analog front end** is an **FPGA** the MCU drives over a parallel command protocol
  (`fpga_control.c`); it does the sampling, trigger, and backlight PWM.
- **No RTOS, no libc.** Built `-nostdlib` with `-DNO_STDLIB=1`; `memcpy`/`memset`/etc. are
  hand-written in `.s` files, and `malloc.c` is a tiny custom allocator.

Branch note: `main` tracks upstream 1013D firmware; **`PORT_A` is the 1014D port** and is
where active work happens. The port-specific code is almost entirely in `port_a.c` / `port_a.h`.
**`PORT_A.md` reconstructs the port in full** (provenance, exact file delta, workflow, status,
and what to verify before changing acquisition) — read it before working on the port.

## The four projects and the boot chain

The Allwinner BROM loads a first-stage image from a fixed SD-card offset (via the `eGON.EXE`
header), which initializes hardware and then loads the real scope program into DRAM at
`0x80000000` and jumps to it. Two boot paths exist:

- **With splash screen (3 stages):** `fnirsi_1013d_sd_card_bootloader` → `fnirsi_1013d_startup_screen` → `fnirsi_1013d_scope`
- **Without splash (2 stages, faster but not kept up to date):** `fnirsi_1013d_startup_from_sd_card` → `fnirsi_1013d_scope`

`fnirsi_1013d_scope/` is the actual oscilloscope application and is where ~all meaningful
work happens. The startup projects are small loaders (clock + DRAM + FPGA init, SD read,
jump). `fnirsi_1013d_startup_from_sd_card.c` is the clearest illustration of the handoff.

## Building

Requires the **`arm-none-eabi-gcc`** bare-metal toolchain (target) plus host **`gcc`** (for the
two helper tools). A full `make` in `fnirsi_1013d_scope/` is confirmed to build cleanly
end-to-end: compile → link → `objcopy` → `mksunxi` → `flashfilepacker`.

Each project builds independently with NetBeans-generated makefiles. Default config `Debug`
is the ARM firmware target (the `Release` config targets host GNU-Linux and is not used):

```bash
cd fnirsi_1013d_scope
make            # builds Debug (ARM); runs objcopy + mksunxi + flashfilepacker in .build-post
make clean
```

The `make` post-build steps (see each project's top-level `Makefile`, target `.build-post`):
1. `objcopy` the `.elf` → raw `.bin`
2. `./mksunxi <bin>` — patches the Allwinner **eGON BROM header checksum** in place
3. (scope only) `./flashfilepacker -o fnirsi_1013d.bin -i ...scope.bin -l 0x9800` — packs the
   image and appends a custom check block at a fixed load offset

Final artifact: `fnirsi_1013d_scope/dist/Debug/GNU_ARM-Linux/fnirsi_1013d.bin`.

`mksunxi` and `flashfilepacker` are checked in twice: native x86-64 **Linux ELF** (no
extension, from upstream) and **Windows** `.exe` (mingw, added by the port). Gotcha: the Linux
ELF ones are committed **non-executable (mode 100644)** while the `.exe` are `100755`, so on a
fresh Linux checkout `make`'s `./mksunxi` fails with *Permission denied*. Fix per project with
`chmod +x mksunxi flashfilepacker`, or rebuild from source (host `gcc` required):
`gcc mksunxi.c -o mksunxi` and `gcc flashfilepacker.c -o flashfilepacker`.

**There are no automated tests.** The Makefile `test`/`build-tests` targets are empty
NetBeans stubs.

## Loading firmware onto the device

Two paths. **FEL is the fast dev loop and the primary way this port is loaded/tested.**

### FEL / USB (fast iteration, no SD reflash)

With the SoC in FEL (USB recovery) mode, `sunxi-fel` (from the external `sunxi-tools` project,
not included here) writes the scope image straight into DRAM and executes it, **bypassing the
SD card and all three startup loaders**:

```bash
sudo ./sunxi-fel version
sudo ./sunxi-fel -p write 0x7FFFFFE0 fnirsi_1013d_scope.bin exe 0x80000000
```

`0x7FFFFFE0` is the linker `org`; execution jumps to `0x80000000`. Documented in
`fnirsi_1013d_scope/dist/Debug/GNU_ARM-Linux/How_to_load_scope.txt`. Because it skips the
loaders, it also skips their FPGA `0x1432` version handshake (see below). The port's debug
build (`-Og -g`) plus on-screen `DEBUG` diagnostics are geared to this loop.

### SD card (persistent install)

`dd` the packed image to the **raw SD block device** (e.g. `/dev/sdc`, *not* `/dev/sdc1`);
the FAT32 partition must start ≥1 MB in, and you must `umount` the partition first:

```bash
sudo dd if=fnirsi_1013d.bin of=/dev/sdX bs=1024 seek=8        # firmware at 8 KB offset
sudo dd if=/dev/zero      of=/dev/sdX bs=1024 seek=8 count=1  # remove it again
```

Per-model LCD/touch timing is a **display configuration sector** at **SD sector 710**
(`dd ... bs=1024 seek=355`). See `configuration_file.txt` (byte layout, per-model timing
values, checksum rules) and `README.md` (full partitioning/backup/removal procedure).

## Scope application architecture (`fnirsi_1013d_scope/`)

`main()` in `fnirsi_1013d_scope.c` is the whole lifecycle: init clocks/caches → timer &
interrupts → power/battery → clock-gen I²C (`cg_i2c_setup`, was touch on 1013D) → SPI flash →
FPGA → display → touch stub → mount SD (FatFs) → USB → load saved config from flash → push
channel/trigger settings to FPGA → draw screen → `uart1_setup` → then an infinite loop of:
`battery_check_status` → `scope_acquire_trace_data` → `scope_display_trace_data` →
`touch_handler` (stubbed) → `uart1_handler`.

Layers (each is `*_control`/`*_interface` driver + higher-level logic):

- **FPGA (`fpga_control.c`)** — the analog front end; almost every acquisition or front-end
  change (channels, trigger, sample rate, timebase, sample readout, even backlight PWM) goes
  through it. See the **FPGA command protocol** section below.
- **Display** — `display_control.c` sets up the Allwinner DE/TCON and the framebuffer;
  `display_lib.c` is the graphics library (RGB565 16-bit buffers, fonts, icons, shapes,
  gradients, screen save/restore). Fonts (`font_*.c`) and `icons.c` are generated bitmap data.
- **Storage** — `sd_card_interface.c` (SD/MMC controller) under **FatFs** (`ff.c`,
  `ffunicode.c`, `diskio.c`); used for saved waveforms, bitmaps, and config.
- **USB (`usb_interface.c` + `mass_storage_class.c`)** — exposes the SD card as USB mass
  storage to a host PC.
- **Scope logic** — `scope_functions.c` (very large: all screens, menus, measurements,
  trace rendering, save/load) and `variables.c`/`variables.h` (global `scopesettings` state,
  channel structs, trace/sample buffers). `PCHANNELSETTINGS`/`PSCOPESETTINGS` are the
  central data structures, passed everywhere.
- **Input state machine (`statemachine.c`)** — `touch_handler` turns touch-panel gestures
  into actions (move traces, cursors, trigger point; open/close menus).

## FPGA command protocol

The analog front end is an FPGA on **Port E**, driven over a bit-banged parallel bus (macros
in `fpga_control.h`): 8-bit data on PE0–PE7, a clock on PE8 (`FPGA_PULSE_CLK`), and
command/data + read/write select on PE9/PE10. Every exchange asserts the control lines
(`FPGA_CMD_WRITE`/`FPGA_DATA_WRITE`/…), sets bus direction, then clocks bytes **MSB-first**.

A transaction is one **command byte** then zero or more data bytes (`fpga_write_cmd` +
`fpga_write_byte/short/int` or `fpga_read_byte/short`). Command bytes used in `fpga_control.c`:

| Cmd | Meaning |
|-----|---------|
| `0x01` | reset sample system (1 = assert, 0 = release) |
| `0x04` | enable system (data `0x01`) |
| `0x05` | read "conversion ready" flag (bit 0) |
| `0x06` | read FPGA version — **must be `0x1432`** (`fpga_check_ready`) |
| `0x0A` | read "triggered / buffer full" flag (bit 0) |
| `0x0D` / `0x0E` | set sample rate / time base (`int` from `sample_rate_settings[]` / `timebase_settings[]`) |
| `0x0F` | trigger system enable(0)/disable(1) |
| `0x14` | prepare transfer / read trigger point (`short & 0x0FFF, +2`) |
| `0x15` `0x16` `0x17` `0x1A` | trigger channel / edge / level / mode |
| `0x1F` | set read pointer to trigger point (`short`), before an ADC read |
| `0x28` | short-time-base mode |
| `0x38` | backlight brightness (`short`) — PWM lives in the FPGA |
| `0x3C` | "battery level" (`short 32431`) — purpose unclear, init-only |
| per-channel | `enablecommand`/`couplingcommand`/`voltperdivcommand`/`offsetcommand`/`adc1command`/`adc2command` (fields in `CHANNELSETTINGS`) |

**Acquisition** (`fpga_read_sample_data`): each channel is captured by **two time-interleaved
ADCs**, read (`0x1F` + `adc1command`/`adc2command`) into even/odd trace-buffer slots with
per-ADC `adcNcompensation` fixups so the halves match; min/max/RMS/average and zero-crossing
frequency are computed in the same pass.

**1014D caveats — verify before trusting acquisition (details in `PORT_A.md`):**
- The `0x1432` handshake runs only in the *startup loaders*, not the scope, so the **FEL path
  never checks it** — but an SD-booted 1014D with a different FPGA version would hang the loader.
- `sample_rate_settings` / `timebase_settings` / `freq_calc_data` (in `variables.c`) and each
  channel's `dc_calibration_offset[]` / `adcNcompensation` are calibrated for the **1013D
  sample clock**. The 1014D generates that clock externally (Si5351, 50 MHz default), so these
  tables and offsets need re-deriving.

## 1014D port specifics (`port_a.c` / `port_a.h`)

This is the heart of the port. The 1014D reuses the same four Port A pins as the 1013D but for
entirely different peripherals — so `touchpanel.c` is swapped for `touchpanel_disable.c` (empty
`tp_*` stubs, still called from `main()`/`fpga_do_conversion`) and input moves to physical keys:

| Pin | 1013D (touch) | 1014D (this port) |
|-----|---------------|-------------------|
| PA0 | touch RESET | **SDA** — clock-gen I²C |
| PA1 | touch INT   | **SCL** — clock-gen I²C |
| PA2 | touch SDA   | **UART1_RX** — key controller |
| PA3 | touch SCL   | **UART1_TX** — key controller |

- **Clock generator** (`cg_i2c_*`, `CG_*`): bit-banged I²C to a **Si5351-compatible** part
  (addr `0xC0`). `cg_i2c_setup()` sets PLLA ≈ 800 MHz, CLK0 = 200 MHz, CLK1 = 50 MHz (66/75/80
  MHz alternatives commented), CLK2 off — this feeds the FPGA/ADC sample clock.
- **UART keyboard** (`uart1_setup`/`uart1_handler`): polls the controller (write `0xFF`, read a
  `GD_KEY_*` / `GD_TRIM_*` code from `port_a.h`) and dispatches. Only a subset of keys is wired;
  trigger-level FPGA writes are still commented out. Author's own verdict: "not really useful yet."

Port A `*PORT_A_CFG_REG = 0xFFFF5511` and the FPGA/PE magic values encode per-pin
input/output/function modes — preserve them exactly. `cg_delay()` timing is calibrated against
the panel (see its comment). Don't trust `port_a.c`'s comments over its code — several are
copy-paste leftovers (e.g. `cg_i2c_setup()` is labelled "Setup the touch panel interface").

**Full reconstruction — provenance, the exact 9-file delta, workflow, status, and the
verify-before-you-change list — is in [`PORT_A.md`](PORT_A.md).**

## Gotchas

- **Ignore `compile.sh`, `burn.sh`, `debug.sh`.** They are stale leftovers from an unrelated
  STM32F103/OpenOCD project (`stm_usb.elf`, `stm32f103-64k.ld`, `cortex-m3` — none of which
  exist here). The real build is `make`.
- Hardware register values and FPGA command bytes are magic numbers tied to silicon —
  changing them blindly can misconfigure clocks/PLL/panel. Match existing patterns.
- `DEBUG`-gated code (e.g. `display_stage()`, UART register dumps in `uart1_handler`) prints
  diagnostics on-screen; it is off in normal builds.
- **Only `fnirsi_1013d_scope/` has been ported.** The three startup loaders are still
  unmodified 1013D code, so the SD-boot chain is not yet 1014D-ready — FEL is the working load
  path. Loading via FEL also means the `Debug` build is currently `-Og -g`, not `-O3`.
- The linker script `fnirsi_1013d.ld` places everything in a single DRAM region starting near
  `0x80000000`; `start.s` sets up the stack and clears BSS before `main`.
