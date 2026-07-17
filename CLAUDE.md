# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. Rewritten 2026-07-09 after the Atlan4-base overhaul — if an older doc (notably
`PORT_A.md`, or the stale copy of this file at `~/src/CLAUDE.md`) contradicts this one or the
code, trust the code.

## What this repository is (current reality)

Bare-metal firmware for the **FNIRSI 1013D** (tablet) and **1014D** (benchtop) oscilloscopes.
SoC is an Allwinner F1C100s "suniv" (ARM926EJ-S, 32 MB DRAM at `0x80000000`, peripherals in
the `0x01C2xxxx` sunxi range). The analog front end is an FPGA driven over a bit-banged
parallel bus on Port E (`fpga_control.c`) — sampling, trigger, and backlight PWM all live
there. No RTOS, no libc (`-nostdlib`, hand-written `mem*.s`, tiny `malloc.c`).

**Active branch `atlan4-base`:** the repo root is **Atlan4's much-evolved 1013D fork
(v1.00o5)** with a **1014D port grafted on**, selected by one build switch in
`fnirsi_1013d_scope/port_config.h`:

- `#define PORT_1014D 1` (default) — 1014D: external Si5351 clock gen on PA0/PA1 I²C,
  UART1 key-controller input on PA2/PA3, no touch/RTC/battery.
- `#define PORT_1014D 0` — 1013D: GT911 touch, DS3231 RTC, battery (guard bugs that gutted
  this variant were fixed 2026-07-09 — PORT_AUDIT.md F3/F4 — but it has never been
  hardware-tested on a 1013D).

The 1014D-specific modules were imported nearly verbatim from **pecostm32's official 1014D
firmware** and bridged to Atlan4 APIs:

| In this tree | Imported from `FNIRSI_1014D_Firmware/fnirsi_1014d_scope/` |
|---|---|
| `menu_1014d.c/.h` | `user_interface_functions.c/.h` (button-driven UI) |
| `sm_1014d.c` | `statemachine.c` (key/rotary state machine) |
| `clock_synthesizer.c/.h` | same names (Si5351/MS5351M I²C) |
| `uart.c/.h` | same names (UART1 key controller) |
| `font_1.c` | one 13 px VW font out of `1014D_fonts.c` |
| `fonts_1014d.c` | `font_0/2/3/4` out of `1014D_fonts.c` (2026-07-10 — the P14 layout needs P14 glyph metrics; Atlan4's `font_0/2/3/4.c` are `#if !PORT_1014D`-guarded) |

Deliberately **not** imported: pecostm32's new 1014D FPGA design (stock FPGA `0x1432` is
used; Atlan4 also supports PECO FPGAs `0x1532`/`0x1632` via `fpgasettings.fw_FPGA`), his
`fnirsi_1014d_scope.c` main, and his USB stack (Atlan4's are kept). The SD bootloader for the
1014D **is** pecostm32's `fnirsi_1014d_startup`, committed as
`fnirsi_1013d_scope/bootloader_1014d_base.bin` (hash-verified local rebuild).

History: `main` = pristine pecostm32 1013D upstream; `PORT_A` = first-generation port
(`port_a.c`, superseded and deleted); `9daa91f` on this branch vendors pristine Atlan4.

## Reference trees at repo root (untracked vendor checkouts — read, don't edit)

- `Atlan4-1.00o5/` — pristine Atlan4 v1.00o5 scope source (diff base for the port).
- `FNIRSI_1013D_Firmware/` — pecostm32's 1013D GitHub repo (upstream reference).
- `FNIRSI_1014D_Firmware/` — pecostm32's official 1014D GitHub repo, locally rebuilt; origin
  of all imported 1014D code and the behavior reference for anything 1014D.
- `Bootloader fw0.02 and fw0.03 and fw0.04/` — Atlan4's bootloader source snapshots
  (user-extracted zip): pecostm32's `fnirsi_1014d_startup` modified for the 1013D — the
  reference for the sector-710 boot-byte contract (BOOT_NOTES.md). Their shipped v0.8
  loader exists only as a binary — it **is** the committed `bootloader_base.bin`, and its
  FPGA-version wait is dead code (BOOT_NOTES.md, 2026-07-10).
- `Atlan4-FPGA/` — Atlan4's replacement-FPGA sources, AL3 family only (matches this unit's
  Anlogic AL3_10), fetched file-by-file from GitHub 2026-07-10: full Anlogic TD project
  (`zaklad.v`, reports version `0x1532` → `fw_FPGA=2`), prebuilt bitstreams, stock-1013D
  SPI-flash dump, and `FPGA commands.txt` (stock-FPGA protocol reference). See
  FPGA_NOTES.md §migration before touching.
- `donwulff-notes.md` — text copy (2026-07-17, images not vendored) of the user's own
  hardware/theory notes from github.com/Donwulff/FNIRSI-1013D-1014D-Hack `notes.md`:
  bandwidth/sensitivity analysis, hardware-mod queue sources, FPGA flash/bitstream findings.
  Content incorporated into FPGA_NOTES.md / ROADMAP.md 2026-07-17.
- `pecostm32-RE/` — pecostm32's 1014D reverse engineering, fetched 2026-07-10 from his
  `Anlogic_AL3-10_Analyzing` + `FNIRSI-1013D-1014D-Hack` repos: stock 1014D FPGA flash dump
  + decompiled netlist + authoritative 1014D pinout (`Original_1014D_fpga_generated.adc`),
  full 1014D board schematics, and per-timebase MCU↔FPGA bus captures ("FPGA explained").
  Pinout diff vs the Atlan4 project and flashing routes: FPGA_NOTES.md §pecostm32-RE.

## Key documents

- **`PORT_AUDIT.md`** — 2026-07-09 full audit of the graft: method, verified-good list,
  findings F1–F9, the same-day **fix pass (§5)** with outcomes (timebase root cause fixed,
  dead `#ifndef` guards fixed, 1013D-variant make failure fixed, F2/strcpy retracted as a
  false alarm, overlay-menu compositing added), AGENTS.md errata, and a hardware-verify
  checklist. **Read it before touching acquisition, timebase, or variant guards.**
- **`FPGA_NOTES.md`** — FPGA command inventory, `fw_FPGA` 1/2/3 paths, how long-timebase
  (roll) mode really works, and the new-FPGA migration assessment. Read before touching
  `fpga_control.c` or planning the bitstream swap.
- **`BOOT_NOTES.md`** — boot chain, SD sector map (16/80/708/709/710), loader contracts
  (the 1014D loader has **no persistent boot byte** — its menu is key-hold at power-on),
  recovery paths, bootloader migration assessment.
- **`ROADMAP.md`** — proposed improvements/refactors/features (dated suggestions).
- **`AGENTS.md`** — opencode's context file for the same tree: module layout, display
  double-buffering architecture, hard-earned gotchas (guard placement, `int8` signedness,
  non-ISO `strcpy`, UART polling, buffer adjacency). Mostly accurate; see PORT_AUDIT.md §3
  for corrections.
- **`PORT_A.md`** — historical reconstruction of the superseded first-generation port.

## Building

Requires `arm-none-eabi-gcc` (plus host `gcc` to rebuild `mksunxi`/`flashfilepacker` if
needed). NetBeans-generated makefiles; config `Debug` is the ARM target (`Release` is an
unused host target).

```bash
cd fnirsi_1013d_scope
make            # compile → link → objcopy → mksunxi → bootloader overlay via flashfilepacker
make clean
```

The Makefile echoes `[port_config.h variant: …]` first and `>>> BOOTLOADER: …` near the end.
**Always confirm both before flashing**: 1014D must say `v1.00o5-1014D` and
`bootloader_1014d_base.bin at offset 0x8000`; 1013D says `bootloader_base.bin at 0x5BC00`.
**Never leave a wrong-variant build as the last artifact** — rebuild the intended variant
last.

Artifacts in `dist/Debug/GNU_ARM-Linux/`: `fnirsi_1013d.bin` (bootable SD image — same
filename in both variants), `fnirsi_1013d_scope.bin` (scope program only), plus variant-named
copies (`fnirsi_1014d*.bin` on 1014D builds).

Gotchas:
- Fresh checkout: `chmod +x fnirsi_1013d_scope/mksunxi fnirsi_1013d_scope/flashfilepacker`
  (committed non-executable), or rebuild from the checked-in `.c` sources.
- CFLAGS (in `nbproject/Makefile-Debug.mk`) carry `-fcommon` and
  `-Wno-error=implicit-*`/`int-conversion` for GCC 14, and are `-O2` (not `-O3`, not `-Og`).
- **No automated tests** (`test` targets are empty NetBeans stubs). Verification is
  build + on-device.
- Ignore `compile.sh`, `burn.sh`, `debug.sh` — stale leftovers from an unrelated STM32
  project.
- FPGA command bytes and register magic values are silicon-tied — match existing patterns,
  never invent values.

## Loading onto the device

The user builds on this Linux server and flashes from a Windows laptop (sunxi-fel / SD).

- **SD image:** `dd` `fnirsi_1013d.bin` to the raw SD device at 8 KB offset
  (`bs=1024 seek=8`); FAT32 partition must start ≥1 MB in. Display-config sector for
  per-model LCD timing is SD sector 710 (`configuration_file.txt`).
- **FEL:** enter it via Factory settings → "FEL firmware update" (direct BROM jump from the
  running scope), or by holding any extra key at power-on → loader menu → F3. Then
  `sunxi-fel -p write 0x7FFFFFE0 fnirsi_1013d_scope.bin exe 0x80000000` (skips all loaders
  and their FPGA version check). The old sector-710 byte poke does not work with the current
  1014D bootloader.
- **Factory settings menu** (main menu, last item; added 2026-07-09): Restore defaults /
  Reboot / FEL firmware update / Sampling clock. FEL is a direct BROM jump (`0xFFFF0020`);
  Reboot + holding a key reaches the loader's own menu (F1 PECO / F2 stock firmware / F3
  FEL). This replaced a hidden F1×2/F2 binding that stole the measurement-menu F-keys and
  wrote a boot byte the 1014D loader ignores (BOOT_NOTES.md). Sampling clock (2026-07-10)
  opens a submenu for manual Si5351 selection (50 stock/57/67/80 MHz, live A/B with traces
  updating under the menu) plus the auto clock search — which no longer runs inside Base
  calibration (FPGA_NOTES.md §clock search).
- On-screen bring-up diagnostics: set `PORT_A_KEYDEBUG 1` in `port_config.h` (boot-stage
  squares, heartbeat/FPGA-version overlay).

## Architecture orientation (1014D build)

`main()` in `fnirsi_1013d_scope.c`: clocks/caches → timer/IRQ → **`clock_synthesizer_setup()`
(Si5351, must precede FPGA init)** → SPI flash → `fpga_init()` → display → SD/FatFs → USB →
`scope_load_configuration_data()` (Atlan4 SD-sector config) → settings to FPGA →
`ui_setup_main_screen()` → `uart1_init()` + `sm_init()` → loop:
`scope_acquire_trace_data()` → `sm_handle_user_input()` → `scope_display_trace_data()` (gated
on `enabletracedisplay` OR `ui_menu_composite_active()` — open overlay menus are re-drawn
into the offscreen buffer each frame by `ui_redraw_active_menu()`, so traces stay live under
them). Config is saved on the key controller's power-off code (`UIC_BUTTON_OFF`).

Input flow: `uart1_get_user_input()` returns a raw key byte (blocking poll — write `0xFF`,
wait for response) that is dispatched directly against `UIC_BUTTON_*`/`UIC_ROTARY_*` codes in
`sm_1014d.c` (the `GD_KEY_*` table in `uart.h` is documentation only; pecostm32's UIC mapping
is the confirmed-correct one — PORT_AUDIT.md F5).

Shared core (both variants): `scope_functions.c`, `fpga_control.c`, `variables.c/.h`,
storage/USB. 1013D-only UI: `menu.c`, `statemachine.c`, `touchpanel.c`, `DS3231.c`,
`power_and_battery.c`, `generator.c`, `PC_interface.c`. 1014D-only: the imported table above.
Whole-file variant guards must come **after** the includes (`variables.h` pulls in
`port_config.h`; a guard before includes silently compiles the file out).

Timing tables (`time_div_texts[35]`, `time_per_div_sample_rate[35]`,
`sample_rate_settings[29]`, `timebase_settings[35]`, …) are Atlan4's 35-entry space
(index 0 = 50 s/div; indices <11 are "long timebase" mode with separate FPGA handling via
`long_mode`/`fpga_set_long_timebase()`). pecostm32's 1014D used a 24-entry space without long
timebases — that difference was the root cause of the broken timebase keys, fixed by making
`sm_set_time_base()` mirror `scope_set_timebase()` (PORT_AUDIT.md F1/§5).

## Known issues (state after the 2026-07-09 fix pass)

Working on hardware: SD boot via 1014D bootloader, Si5351 init, traces, UART keys (MENU→USB
mount), menu navigation. Fixed in code, **hardware verification pending** (checklist in
PORT_AUDIT.md §4): timebase keys incl. long timebases, overlay-menu compositing (traces keep
updating live under main/channel menus, sliders, on/off panels — full-screen views still
suppress traces), version-string overlap (variant suffix removed from display), 1013D-variant
touch/battery/RTC restoration; Factory settings menu (defaults/reboot/FEL, replaces the
hidden F-key boot-switch). From the 2026-07-09 bench observations, fixed in code (verify on
hardware): AUTO no longer paints touch chrome (menu.c's shared chrome functions now route to
their `ui_` equivalents on 1014D), no more false flat trace or touch-scroller flash on
timebase changes (`scope_preset_values()` guards), the Position trim works
(`scope_calculate_sample_range_properties()` was truncated — never set
`trigger_position_min/max`), and AUTO clears `long_mode`. **SOLVED (2026-07-12, F25):** the
≤200 ns/div sawtooth was Atlan4 commenting out the FPGA `0x28` mode-select in `fpga_do_conversion`
(wrong "not support" guess); restored on the stock `fw_FPGA==1` path, bench-confirmed gone
(PORT_AUDIT.md F25). Base calibration no longer changes the sampling
clock (2026-07-10 — it used to overclock first and then calibrate *at* the overclock, making
the sawtooth worse; clock experiments now live in Factory settings → Sampling clock).
2026-07-10 night screenshot-driven pass (PORT_AUDIT.md §5c, F12–F15; verify pending):
sidebar measurements now live-update every frame (`ui_update_measurements()` was never
called), measurement labels moved right of the trace copy rect that was clipping them,
probe 1:1/10:1/100:1 now maps to Atlan4 magnification rows 1/2/5 (was mislabeled + wrong
scaling), top-bar volt/div uses new short texts (`volt_div_texts_short`, the "/div" ones
overflowed the 57 px field), Base calibration persists its results (were RAM-only — a hard
power cycle silently reverted them, the "cal wears off" effect) and shows the measured
interleave comps (C1:/C2:, 2.5 s). Sawtooth status: cal *does* reduce it ~60 % (shorted-
input screenshots); bench comps stable −3/+3 both channels; residual is either v/div
dependence (averaged away) or a gain component (comp measured at ADC ~128, trace runs at
~178) — position-sweep test recipe in FPGA_NOTES.md §Screenshot analysis. Also fixed same
night (F16, bench-verified): normal/single trigger mode froze permanently once the level
left the waveform — the non-blocking acquire only pushes the trigger level when arming, so
the sm handlers now push `fpga_set_trigger_level()` directly (level rotary, trigger-channel
toggle, 50 %, origin). F17: the 1014D per-frame trace copy narrowed to the P14 window
(`(2,48,705,432)` — Atlan4's 728-wide copy wiped/flash-fought the sidebar edge; grid ends
at 704), labels back at P14-native x=719, version+build stamp split onto two lines clear
of the move-speed text. Interleave-mismatch verdicts: position sweep ruled out gain-type;
`d:` row came back uniform (~6 across all v/div) ruling out per-v/div comp — the averaged
offset comp is already optimal, so the cal diagnostic now measures the post-comp residual
(`r: score peak` per channel, waits for key press) to separate noise/outliers from any
real leftover structure (FPGA_NOTES.md §Screenshot analysis). GUI-glue audit (PORT_AUDIT.md §5d): all 49 `ui_*`
hooks that pecostm32's core makes are present in this tree; the GUI code is verbatim P14
and bench differences are seams (fonts/tables/geometry/hooks), each class now audited.
Remaining: "chrome" fragments below the PECO logo / version area (screenshot needed);
residual touch chrome (file-level UI swap plan); "Output browsing"/"Capture output"
main-menu items are null (null in pecostm32's fork too); backlog in ROADMAP.md.
