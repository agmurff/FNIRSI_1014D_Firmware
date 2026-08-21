# PORT_A — 1014D port notes (reconstructed)

> **⚠️ SUPERSEDED (2026-07-09).** This documents the *first-generation* port (`port_a.c/.h`
> on the `PORT_A` branch). The active work is now on `atlan4-base`, where `port_a.*` were
> deleted and replaced by modules imported from pecostm32's official 1014D firmware
> (`clock_synthesizer.*`, `uart.*`, `menu_1014d.*`, `sm_1014d.c`). See `CLAUDE.md`,
> `AGENTS.md`, and `PORT_AUDIT.md` for the current state. Kept for provenance and hardware
> notes (pin mapping, Si5351 registers, key-controller protocol) that remain valid.

This branch (`PORT_A`) adapts pecostm32's **1013D** replacement firmware to run on the
**FNIRSI 1014D**. This file reconstructs what the port does, where it came from, and how it
was being worked on, so the effort can be picked back up. It is a lab notebook, not a spec —
verify against the code before relying on any detail.

## Provenance

- **Upstream:** `pecostm32/FNIRSI_1013D_Firmware` (targets the 1013D). Upstream explicitly
  disclaims the 1014D — commit `85d2ab8` (2023-09-30) literally added *"Not suited for 1014D"*.
  This fork exists to close that gap.
- **Author of the port:** donwulff / Jukka Santala.
- **Fork point:** upstream v0.006, commit `9b37203` (2023-01-12).
- **Port work:** three commits, all **2023-01-19**:
  | commit | message | what it did |
  |--------|---------|-------------|
  | `25a517c` | "Saving my current work: ClockGen & UART configuration, some keys bound to correct functions. Not really useful yet." | The actual port: `port_a.c/.h`, `touchpanel_disable.c`, main() hooks, Makefile swap |
  | `46b80c9` | "Rewrote missing port_a.h; included mksunxi.c and flashfilepacker.c as well as their Windows mingw builds." | Made the scope folder self-contained: added tool **sources** + Windows `.exe` builds |
  | `18c597f` | "Use defines for command bytes, skip missing header in flashfilepacker.c, hide ugly output behind DEBUG." | Cleanup; introduced the `GD_KEY_*` defines and `DEBUG`-gated diagnostics |
- **2025-08-10** (`baf5005`): merged upstream `main` (then at `51f4872`, 2025-02-27) into
  `PORT_A`. This pulled ~2 years of upstream 1013D fixes but added **no new port code**.
- Working tree currently matches `origin/PORT_A` (clean — no uncommitted WIP to recover).

Net: the port is ~2.5 years old, was left at an early "boots and reads some keys" stage, and
was recently only re-synced with upstream.

## What the port actually changes (9 files vs. upstream)

Only `fnirsi_1013d_scope/` was touched. The three startup loaders
(`sd_card_bootloader`, `startup_screen`, `startup_from_sd_card`) are **unmodified 1013D code**.

- **`port_a.c` / `port_a.h`** (new) — the port itself: clock generator + UART keyboard.
- **`touchpanel_disable.c`** (new) — drop-in replacement for `touchpanel.c`; every `tp_i2c_*`
  function is an empty stub. Its header comment documents the old 1013D pinout.
- **`fnirsi_1013d_scope.c`** (+8 lines) — `#include "port_a.h"`, and three calls in `main()`:
  `cg_i2c_setup()` (after interrupts), `uart1_setup()` (before the main loop),
  `uart1_handler()` (inside the loop, next to `touch_handler()`).
- **`nbproject/Makefile-Debug.mk`** — swaps `touchpanel.o` → `touchpanel_disable.o`, adds
  `port_a.o`, and **changes optimisation from `-O3` to `-Og -g`** (i.e. a debug build).
- **`mksunxi.c`, `flashfilepacker.c`, `mksunxi.exe`, `flashfilepacker.exe`** — added. The
  prebuilt *Linux* `mksunxi`/`flashfilepacker` binaries already existed upstream; the port
  added their source and Windows builds.

## The hardware differences driving the port

The 1014D reuses the same four Port A pins as the 1013D but for **completely different
peripherals**. This single remap is the crux of the port (from the header comments of
`touchpanel_disable.c` (1013D) and `port_a.c` (1014D)):

| Pin | 1013D — capacitive touch (GT911/GT9157) | 1014D — this port |
|-----|------------------------------------------|-------------------|
| PA0 | touch RESET | **SDA** — clock-generator I²C (bit-banged) |
| PA1 | touch INT   | **SCL** — clock-generator I²C (bit-banged) |
| PA2 | touch SDA   | **UART1_RX** — physical-key controller |
| PA3 | touch SCL   | **UART1_TX** — physical-key controller |

Consequences:
1. **Touch panel is gone** on the 1014D → `touchpanel.c` replaced by stubs. `main()` and
   `fpga_do_conversion()` still *call* `tp_*`/`touch_handler`, so the stubs must exist.
2. **Input is physical buttons/knobs** read from a controller over **UART1**.
   `uart1_handler()` polls it (write `0xFF`, read a `GD_KEY_*` / `GD_TRIM_*` code) and
   dispatches. Key codes are defined in `port_a.h`.
3. **The sampling clock is now generated externally** by a **Si5351-compatible clock
   generator** on the bit-banged I²C (device addr `0xC0`). `cg_i2c_setup()` programs
   PLLA ≈ 800 MHz, CLK0 = 200 MHz, CLK1 = 50 MHz (with 66/75/80 MHz alternatives commented
   out), CLK2 off. On the 1013D this clock was not software-programmed here.

### Deeper hardware facts (confirmed in the [notes repo](https://github.com/Donwulff/FNIRSI-1013D-1014D-Hack/blob/main/notes.md))

- **SoC:** Allwinner **F1C100s** (ARM9 / ARM926EJ-S). The stock 1014D firmware clocks the core
  at **575 MHz**; this open firmware uses 600 MHz. That 575-vs-600 ratio is exactly why
  `uart1_setup()` sets the UART1 divisor to `0x4E` instead of the stock `0x51`
  (`0x51 × 24/25 ≈ 0x4E`) — that's what the cryptic comment in `port_a.c` means. UART runs
  ~115200 baud.
- **Clock generator:** an **MS5351M** (an Si5351 clone), configured per Skyworks AN619 — one
  clock for the signal generator (up to 200 MHz), one for the scope logic (50 MHz), matching
  `cg_i2c_setup()`.
- **FPGA — different silicon and bitstream.** The 1014D uses an **Anlogic AL3_10**; the 1013D
  used an Altera Cyclone IV EP4CE6 (old units) or Gowin EF2L45 (newer). Bitstream header
  version differs (1013D `001c0000` vs 1014D `00e40000`). **The MCU has no JTAG or SPI link to
  the FPGA** — reflashing means ISP over the shared data bus (FPGA SPI flash = ZB25VQ80ATIG,
  writable with BusPirate + flashrom; Anlogic IDE 5.0.4 builds AL3 bitstreams). Even so, the
  reused 1013D `fpga_control.c` command set **evidently works on the real 1014D FPGA** (the
  firmware boots and acquires), so the MCU-facing protocol is compatible; the likely remaining
  FPGA-side work is calibration/timing. Atlan4 maintains the AL3 (1014D) and EF2 (1013D) FPGA
  logic in parallel from one base design (`zaklad.v`) — consistent with a common command interface.
- **ADC:** ~**200 MSa/s** per channel from two interleaved 100 MSPS converters (likely an
  MXT2088, an AD9288-100 clone) — this is the interleave that `fpga_read_sample_data()` splits
  into even/odd ADC halves.

## Reconstructed workflow

- **Build:** debug config (`-Og -g`), on-device diagnostics via `DEBUG` (see
  `display_stage()` painting a number top-left, and the UART register dump in
  `uart1_handler()`).
- **Fast iterate:** load over USB with **`sunxi-fel`** (Allwinner FEL/USB-recovery protocol,
  from the external `sunxi-tools` project), documented in
  `fnirsi_1013d_scope/dist/Debug/GNU_ARM-Linux/How_to_load_scope.txt`:
  ```
  sudo ./sunxi-fel version
  sudo ./sunxi-fel -p write 0x7FFFFFE0 fnirsi_1013d_scope.bin exe 0x80000000
  ```
  This writes the raw scope `.bin` straight into DRAM (`0x7FFFFFE0` = the linker `org`) and
  executes at `0x80000000`, **bypassing the SD card and all three startup loaders**. This is
  almost certainly the "USB update path via a sunxi protocol" — it avoids reflashing the SD
  card on every change. (It also sidesteps the loaders' FPGA version handshake; see below.)
  The in-tree `dist/.../readme` treats this FEL-to-DRAM load as the intended no-SD test path,
  and the author previously ran the firmware this way (both FEL and SD worked, barely usable).
  - **If** a stock `sunxi-fel` won't bring up DRAM on your build: the notes repo reports generic
    `sunxi-fel` doesn't know the FNIRSI DRAM config, and pecostm32 has a
    `Test code/fnirsi_1014d_startup_with_fel` DRAM-init stage for it.
- **Real install:** `dd` the packed `fnirsi_1013d.bin` to the SD card at 8 KB (see `README.md`
  / `CLAUDE.md`).

### USB mass storage (reflash over USB) — verified, with known descriptor bugs

A USB descriptor dump of the scope in USB mode (2026-07) shows standard USB Mass Storage
(Bulk-Only / SCSI, two 512-byte bulk endpoints). **The dump was taken from the stock firmware**,
but its strings match `mass_storage_class.c` byte-for-byte — our custom firmware copies the same
ST-derived descriptors, so the raw-disk MSC our code implements is the same one the dump shows.
As verified in code, it exposes the **raw whole card** (`READ_CAPACITY` = full `cardsectors`;
SCSI LBA → SD sector 1:1, no partition offset), so firmware can be `dd`'d over USB in place — no
card removal, no case opening (Linux-easy; the raw `seek=8` offset is awkward on Windows). The
SD-swapping the author recalls was most likely for **non-booting builds** (no firmware → no USB
mode → pull the card); FEL sidesteps that by loading DRAM regardless.

Known descriptor bugs (in our code — cosmetic/minor, they don't block MSC or reflash):
- **No Device Qualifier descriptor** → a USB-2.0-HighSpeed compliance error (hosts tolerate it).
- **Product string is transmitted scrambled.** `StringProduct` is *stored* correctly
  ("H2750  Usb Device") but the string-descriptor send path emits it with 16-bit chars
  transposed in pairs (plus a junk leading unit) — an alignment/stride bug in the string TX path
  (`usb_interface.c`). The interface string is garbled the same way.
- **Manufacturer string not served.** `iManufacturer = 1` / `StringVendor`
  ("HeroJe Scanners Drives - H2750") is declared but index 1 isn't answered by the
  string-descriptor handler → host reports "String descriptor not found".
- VID/PID `0x0483:0x5720` are STMicroelectronics' (a reused ST example descriptor), not FNIRSI's.

## Status — it works; the control tree is the gap

**The port runs on real 1014D hardware** — boots via **both SD card and FEL**, and is *barely
usable*. (The 2023 "not really useful yet" commit predates that.) So the FPGA command protocol,
clock generator, display, SD/USB, and UART key input are all functional enough to acquire and
display a trace.

**The main unfinished work is the control tree** (see next section). `uart1_handler()` today
wires only a handful of keys straight to actions — `AUTO`, `MENU` (→ USB), `CONF_CH1/2`
(magnification), `TRIG_MODE`, `TRIG_CHX`, `X_CH1 ±`/`Y_CH2 ±` (trace position, crude accel),
`SCALE_CH1/2 ±` (volts/div), `TIME ±` (timebase + rate) — leaving the rest of the mapped
`GD_KEY_*`/`GD_TRIM_*` codes unhooked. Touch is fully stubbed.

## Primary task — a unified control tree

**The #1 goal (and the first thing to use the LLM for): re-architect the control/input layer so
physical knobs (1014D, via `uart1_handler`) and touch + on-screen menus (1013D) both drive the
same scope actions — ideally one codebase that supports either model.** Today the two input
styles are tangled: `port_a.c` duplicates logic that otherwise lives inside the menu/touch
handlers (`scope_*_button(mode)` + `handle_*_menu_touch` in `statemachine.c`/`scope_functions.c`)
— hence its "code should be unified" comment. Do this on **Atlan4's current base (`Verzia 1.xxx`)**,
not the v0.006 base — see 'Related forks'.

## Open questions / verify before changing anything

- **FPGA version handshake `0x1432`** (`fpga_check_ready()`, only in the startup loaders):
  SD boot works on real 1014D hardware, so the 1014D FPGA **does** return the expected version —
  the MCU-facing command protocol is compatible. (The scope's `main()` doesn't call it anyway.)
- **Timing tables are 1013D-calibrated.** `sample_rate_settings[18]`, `timebase_settings[24]`,
  and `freq_calc_data[18]` (in `variables.c`) encode FPGA clock-divider values against the
  1013D sample clock. The 1014D now derives that clock from the Si5351 (50 MHz default), so
  these tables — plus per-channel `dc_calibration_offset[]` and `adc{1,2}compensation` — will
  need re-deriving before measurements read correctly.
- **Dual-ADC matching.** `fpga_read_adc_data()` interleaves two ADCs per channel and
  compensates to make them agree; `todo.txt` notes the two ADCs must be calibrated to match.
  Different silicon on the 1014D → recheck.
- **`port_a.c` has copy-paste leftovers** (e.g. the `cg_i2c_setup()` call is commented
  "Setup the touch panel interface"; magnification cycling is commented "Enable the channel").
  Don't trust the comments over the code.
- **Startup loaders are unmodified 1013D but evidently boot the 1014D** (the SD path works),
  so the SoC / DRAM / FPGA bring-up is compatible across both models. Remaining FPGA-side work is
  likely **calibration / timing** (the tables above), not basic compatibility.

## Related forks & merge landscape (next step — not started)

Recon of the two relevant downstreams (as of 2026-07):

- **[Atlan4/Fnirsi1013D](https://github.com/Atlan4/Fnirsi1013D)** — the *actively maintained*
  1013D line, at **~v0.28a / v0.27u** (2026) versus this repo's pecostm32 base at **v0.006**
  (2023). It is **~3 years and dozens of versions ahead.** Caveats for merging:
  - It's **not a git-mergeable history** — everything is uploaded as zip snapshots via the
    GitHub web UI ("Add files via upload"), so `git merge` is a non-starter; combining means a
    manual code-level diff/integration. Author writes in Slovak.
  - **It moves in the opposite direction to this port.** Its README says the bootloader was
    *"modified for the 1013d … removed uart for 1014"* — i.e. Atlan4 adapts 1014D hardware to
    run 1013D firmware (adds touch, drops the UART keyboard), the mirror image of PORT_A. Its
    bootloader/UART/touch work is therefore highly informative for us.
  - Structural divergence: refactored into **bootloader + updater + scope** with a migration
    path, split menus into `menu.c/.h`, and v0.28a added `PC_interface.c/.h` + `cdc_class`
    (USB-CDC PC remote control) — none of which exist in this repo's layout.
  - **FPGA:** ships an `FPGA.zip` and once had an `anlogic-usbjtag` programmer + `FPGA EF2`
    (Gowin) dirs that were later deleted. This is FPGA *programming tooling / bitstream
    backups*, oriented at the 1013D FPGAs — **not** a turnkey 1014D (AL3_10) bitstream rebuild.
    The real FPGA-to-Verilog reversing is pcprogrammer's work (see the notes repo), not Atlan4's.
- **[froloffw7/FNIRSI-1013D-1014D-Hack](https://github.com/froloffw7/FNIRSI-1013D-1014D-Hack)**
  — a QEMU-based desktop harness for running/reversing the ARM firmware without hardware.

**Proposed approach (to confirm):** the sensible "merge" is a **port-forward** — re-apply this
1014D port (`port_a.*`, touch-disable, the 575 MHz/UART-divisor bits) onto Atlan4's much newer
scope code — *not* pulling Atlan4 into the ancient v0.006 base. First concrete step: get a clean
copy of Atlan4's latest source (`Scope v0.28a/`) into a branch here so it can be diffed. The
hard part remains the FPGA: a different bitstream on the 1014D means neither base's
`fpga_control` command set is known to apply.

## Port-forward onto Atlan4 — status (branch `atlan4-base`, updated 2026-07-06)

> **⚠️ Snapshot of 2026-07-06**, before the modules-import overhaul — the flashing/FEL
> details below (0x5BC00 base, boot-config-byte FEL entry) are superseded; see `CLAUDE.md`
> and `BOOT_NOTES.md` for the current procedures. (Marker added 2026-08-21.)

The port-forward is underway on branch **`atlan4-base`**. The snapshot adopted is Atlan4
**v1.00o5** (not v0.28a — that estimate predated getting the real source); its scope source is
vendored into `fnirsi_1013d_scope/` and builds clean with this server's `arm-none-eabi-gcc`
14.2.1. FPGA is **not a blocker**: Atlan4 1.xxx is multi-FPGA and its `fw_FPGA==1` branch runs
the stock (0x1432) protocol this port already uses.

**Building a bootable image (the piece that was missing).** `flashfilepacker` is an *overlay*
tool (`-i` = "file to add to the output file at location"): it patches the freshly-built scope
into an existing packed image at `0x5BC00`, preserving the two boot stages already there. So a
standalone SD image needs a **bootloader base** to overlay into. That base is committed as
`fnirsi_1013d_scope/bootloader_base.bin` (the first `0x5BC00` bytes of Atlan4 v1.00o5's packed
`fnirsi_1013d.bin` = `eGON.BT0` SPL DRAM-init @0x0 + `eGON.EXE` splash loader @0x8000, scope slot
truncated off). The Makefile `.build-post` now `cp`s it to `dist/.../fnirsi_1013d.bin` before
`flashfilepacker`, so `make` produces a standalone, dd-able `fnirsi_1013d.bin` (~727 KB, three
eGON stages). Verify a build with: `xxd -s 0x5BC00 -l 8 dist/.../fnirsi_1013d.bin` → `eGON.EXE`.

**Flashing & self-update (no touch, no card-swap is the goal).**
- **Install (one-time / recovery):** `dd if=fnirsi_1013d.bin of=/dev/sdX bs=1024 seek=8`. SD boots
  before SPI-NOR, so the card wins over the unit's stock image. (FEL is *not* required and pulling
  the SD won't force FEL on this unit — it boots from SPI-NOR. pecostm32's prebuilt
  `startup_with_fel.bin` dd'd to SD did **not** enter FEL here — abandoned.)
- **USB-disk re-flash (persistent, no swap):** Atlan4's mass-storage class exposes the **whole raw
  card from sector 0** (`READ_CAPACITY_10` reports full size; `scsi_start_lba` → `sd_card_read/write`
  directly), so a host can re-`dd` a new `fnirsi_1013d.bin` at `seek=8` over USB. Default USB mode
  is mass storage (`USB_CH340=0`); entry = `scope_main_menu_usb_connection(1)`.
- **FEL (fast RAM dev loop):** boot-config value **2** at `STARTUP_CONFIG_ADDRESS` (0x81BFFC1F);
  the loader enters FEL on warm reboot when it reads it, then
  `sunxi-fel write 0x7FFFFFE0 fnirsi_1013d_scope.bin exe 0x80000000`.
- Both self-update entries currently reachable only by touch — Phase 3 binds a `port_a` key to
  each (ideally also a power-on key-hold as a recovery gate so a bad flash can't force a card-swap).

**HW-confirmed 2026-07-06:** the pristine Atlan4 packed image **boots from SD on the 1014D**
(load path + Atlan4 base both validated). It is **touch-only**, so it's uncontrollable on the
1014D (draws the "touch to calibrate" prompt and stops) — a boot/display smoke test only. The
display flashes, most likely because pristine Atlan4 never runs this port's external clock-gen
init (`cg_i2c_setup` → MS5351M, which feeds the FPGA that drives backlight PWM) — to confirm once
the port is grafted on.

### Phase 3 graft — DONE (first pass), 2026-07-06

The port is now grafted onto the Atlan4 v1.00o5 base and **both variants build clean** (exit 0,
0 gcc errors) from one codebase; the 1014D build packs to a bootable `fnirsi_1013d.bin` (730696 B,
`eGON.EXE` at 0x5BC00). Not yet hardware-tested — this is the "compiles + bootable image" milestone.

Delta (small and surgical — Atlan4's C source is otherwise untouched):
- **`port_a.c` / `port_a.h`** brought in verbatim from the `PORT_A` branch. Pleasant surprise:
  **all 14 scope/fpga functions and every `scopesettings`/`CHANNELSETTINGS` field the key handler
  pokes still exist in Atlan4 with matching signatures**, so `uart1_handler` compiled essentially
  unchanged (only added `#include "menu.h"` to kill implicit-declaration warnings for
  `scope_setup_usb_screen`/`scope_channel_settings`/`scope_run_stop_text`/
  `scope_trigger_channel_select`/`scope_acqusition_settings`).
- **`port_config.h`** — single build-variant switch. `PORT_1014D 1` = bench-key model (default),
  `0` = original 1013D touch build. All `main()` differences are `#if PORT_1014D` guarded, so the
  touch build still compiles (verified).
- **`fnirsi_1013d_scope.c` main()**, guarded by `PORT_1014D`: (a) `cg_i2c_setup()` inserted
  **before `fpga_init()`** (clock before FPGA — matches the PORT_A author's proven order; also the
  fix for the display flashing); (b) `tp_i2c_setup()` **skipped** on 1014D — running it would
  bit-bang GT911 init bytes onto PA0/PA1, which on the 1014D are the Si5351's SDA/SCL, and could
  corrupt the clock; (c) `uart1_setup()` added just before the main loop; (d) loop calls
  `uart1_handler()` instead of `touch_handler()`.
- **`nbproject/Makefile-Debug.mk`** — `port_a.o` added to `OBJECTFILES` + a compile rule.
- **Deliberately NOT swapped in: the old `touchpanel_disable.c`.** Atlan4's `touchpanel.c` `tp_i2c_*`
  functions are now **shared with the DS3231 RTC** (`DS3231.c`) and gained a device-address
  parameter, so the old empty-stub file no longer matches the callers. Atlan4's real `touchpanel.c`
  stays compiled (RTC needs it); on 1014D the touch *input* path is simply never driven.

**Known limitations of this first pass (not yet addressed):**
- **Key dispatch is still the old PORT_A subset** (AUTO, MENU→USB screen, CH mag, trigger mode/chan,
  a few trims/scale/time). It has NOT been re-targeted to Atlan4's richer `menu.c` action flow, and
  trigger-level FPGA writes are still commented out. Most keys do nothing yet.
- **No self-update key bindings yet** (FEL config-byte / USB-disk mode). Still touch-only entry.
- **Fresh-flash calibration prompt** (`calibrationfail=1` from `scope_load_configuration_data` when
  flash has no saved config) will draw its overlay and can't be dismissed without touch — but it is
  a non-blocking loop overlay, not a `while(1)`, so the scope still runs underneath.
- Fast-timebase sawtooth (50 MHz `sample_rate_settings`/`freq_calc_data` recalibration) untouched.

**Next:** flash to the 1014D and confirm (display no longer flashes; keys register); then re-target
key dispatch to Atlan4 menu/actions and bind FEL + USB-disk self-update to keys (+ power-on key-hold
recovery gate).
