# ROADMAP.md — proposed improvements (suggestions, not commitments)

Written 2026-07-09 after the port audit + fix pass (PORT_AUDIT.md). Ordered roughly by
(value ÷ effort) within each section. Strike items as they land or get rejected.

## Now / next bench session

1. **Hardware-verify the fix passes** — PORT_AUDIT.md §4 (timebase sweep incl. long/roll
   mode, compositing, version string, FPGA-wait soak) plus the 2026-07-09 evening fixes:
   AUTO (no touch chrome, sane rate after), Position trim pans the trace (indicator = bottom
   time-offset text + top pointer), no flat-trace/scroller flash on timebase changes, and the
   Factory settings menu (defaults/reboot/FEL direct jump).
1b. **Sawtooth at ≤200 ns/div** — run Base calibration first, then the P14-binary A/B test
   (FPGA_NOTES.md §sawtooth); fix direction depends on the outcome. A dedicated trace
   scrollbar/locator for the benchtop UI is a follow-on idea once panning is verified.
2. ~~Decide the boot-source switch's fate~~ **Done 2026-07-09**: the hidden F1×2/F2 binding
   was removed and replaced by the **Factory settings menu** (Restore defaults / Reboot /
   FEL direct jump); the sector-710 garbage write is guarded. Hardware-verify all three
   actions (FEL jump especially — first direct-from-firmware BROM entry on this unit).
   Optional follow-up: persistent boot default via the loader byte contract (BOOT_NOTES.md).

## Refactors that pay for themselves

3. **Finish the file-level UI swap** (plan already in AGENTS.md): compile `menu.c`,
   `statemachine.c`, `generator.c`, `PC_interface.c`, `touchpanel.c` only for the 1013D
   variant and `menu_1014d.c`/`sm_1014d.c`/`uart.c`/`clock_synthesizer.c` only for the
   1014D. Kills the whole class of "1013D chrome reachable on 1014D" bugs (audit found
   several), shrinks the image, and makes `scope_setup_main_screen()`-style ambiguity
   impossible. Needs conditional object lists in `nbproject/Makefile-Debug.mk` (or item 6).
4. **Non-blocking key input** — `uart1_get_user_input()` busy-waits on the key controller
   every main-loop pass, gating the frame rate on UART turnaround. Move UART1 RX to the
   interrupt controller (interrupt.c infra exists) or a poll-without-wait design; add rotary
   acceleration using the existing `movespeed`.
5. **Warning cleanup → then `-Werror`** — the 234 `-Wpointer-sign` warnings are mechanical
   `int8*`/`char*` mismatches from the (correct) signed-int8 fix; unify the string types
   (`char*` for text, `int8` only for numeric bytes). Real bugs hide badly in 260-line
   warning spew.
6. **Escape the NetBeans makefiles** — a hand-written flat Makefile (or CMake) for the four
   projects. The generated `Makefile-Debug.mk` silently drops local edits on regen (already
   bitten: `-fcommon`, variant objects). This also unlocks item 3 cleanly.
7. **Dead weight removal** — `strcpy.s` (never compiled, wrong-semantics trap),
   `compile.sh`/`burn.sh`/`debug.sh` (stale STM32 leftovers), stray
   `dist/.../scope-1014D.bin`, and a decision on `test.c` (debug scaffolding).
8. **Repo hygiene for the reference trees** — `Atlan4-1.00o5/`, `FNIRSI_1013D_Firmware/`,
   `FNIRSI_1014D_Firmware/` are untracked local-only checkouts the docs now depend on; make
   them submodules or add a `fetch-refs.sh` + note so a fresh clone can reproduce the
   workspace.
9. **CI** — a GitHub Action that builds both variants (arm-none-eabi-gcc is apt-installable),
   fails on new warnings, and publishes the packed images as artifacts. The repo has zero
   automated checks today; this is the cheapest one that matters.

## Features (1014D as an instrument)

10. **Finish key coverage** — F3–F6 soft keys, cursor keys (H_CUR/V_CUR states exist in
    `sm_1014d.c`), measurements-menu slots; audit `sm_handle_user_input()` against the full
    `UIC_*` table for unhandled codes.
11. **Calibration track** — wire/verify the imported calibration UI (`menu_1014d.c` has
    CALIBRATION_STATE screens) against sector-708 input-calibration storage; per-ADC
    compensation on this unit's front end.
12. **Roll-mode/long-timebase UX** — newly reachable from keys after the F1 fix; verify,
    then polish (it's trigger-off streaming; the UI should say so).
13. **PC interface on the 1014D** — USB CDC (`cdc_class.c`/`PC_interface.c`) is compiled but
    only reachable from touch UI; wire a key/menu item to toggle MSC↔CDC (`USB_CH340`).
14. **Signal generator decision** — Atlan4's `0x50/0x51/0x52` FPGA commands have unverified
    stock-FPGA support and the 1014D panel entry hung on fresh flash (still unexplained);
    either verify on stock FPGA and wire to a key, or fence it to fw_FPGA ≥ 2.
15. **Si5351 as a feature** — the clock generator is programmable at runtime; alternate ADC
    clocks (66/75/80 MHz were sketched in the old port; user ran 75 MHz → "300 MSa/s"
    apparently-working in 2023, unvalidated — FPGA_NOTES.md §frequency) or a cal-frequency
    output on CLK2 are cheap experiments once calibration exists. Experimental tier.
    **Order matters:** fix interleave calibration at stock rate first (item 11, the
    sawtooth suspect); only then consider vetted overclock presets. An "auto-calibrate
    clock" loop (search for max stable rate at runtime) needs a pass/fail oracle the
    hardware doesn't really offer — fixed validated presets from a debug menu are the
    sane shape. For interleave itself, the cheap software approach: even/odd sample
    statistics (means/variances of the two ADC streams should match on any live signal)
    → auto-trim per-ADC offset/gain until they do; phase skew needs fast edges, not the
    1 kHz cal output.

## FPGA + bootloader migration (tracked in FPGA_NOTES.md / BOOT_NOTES.md)

16. ~~Vendor the replacement FPGA project; determine its version word~~ **Done 2026-07-10**:
    Atlan4's AL3-family sources vendored at `Atlan4-FPGA/`; version word is **0x1532** →
    `fw_FPGA=2`; the "bootloader v0.8" prerequisite decoded (v0.8 = our
    `bootloader_base.bin`, FPGA wait dead code). Also vendored `pecostm32-RE/` (stock 1014D
    FPGA flash dump = the back-out path, decompiled netlist, authoritative 1014D pinout,
    board schematics, bus captures). Real remaining work before any flash: **retarget
    `zaklad.v` to the 1014D pinout** (`Original_1014D_fpga_generated.adc`; same die
    AL3A10LG144C7, MCU bus identical, analog side fully reshuffled) and decide handling of
    the 1014D-only DAC bus / I²C EEPROM / second clock input; flashing = CH341A on the
    board's `FPGA_FLASH` header J2 (or TD JTAG on J5) — the scope CPU has no path to the
    FPGA flash. Details: FPGA_NOTES.md §pecostm32-RE. Toolchain downloaded 2026-07-10 to
    `~/tools/anlogic-td/` (TD 5.0.3 Linux + 4.6.4 + licenses), not yet installed — setup
    notes + headless-flow validation plan in FPGA_NOTES.md §"Synthesis environment".
17. **Patch `fnirsi_1014d_startup` first**: relax the `0x1432` spin (bricks the boot path
    under any other bitstream — Atlan4's v0.8 simply never calls it; follow that precedent),
    optionally adopt the boot byte (item 2), rebuild `bootloader_1014d_base.bin`,
    hardware-test, only then flash a new bitstream.
18. After a fw≥2 bitstream boots: exercise the `fw_FPGA==2` acquisition path (0x0B/0x0C
    geometry, recalibrated constants — all Atlan4-1013D-tuned today) and re-derive
    calibration on the 1014D.

## Docs

19. **Single-source the agent docs** — CLAUDE.md and AGENTS.md overlap and will drift;
    either make one a thin pointer to the other or symlink them. The deep content now lives
    in PORT_AUDIT.md / FPGA_NOTES.md / BOOT_NOTES.md, so both entry docs can shrink.

## Measurement precision & calibration (2026-07-12, PORT_AUDIT F28/F30)

20. **Honest measurement/trigger precision (F28, Tier 1 — cheap, display-only, both variants).**
    Trigger level and single-sample measurements (Vpp/Vmax/Vmin) show **integer mV** — kill the
    fake `X.00` hundredths (trigger is *set* in 1 mV steps; those measurements resolve ~1 ADC
    code ≈ 1.5 mV, so decimals are fiction). `ui_print_value`/`ui_display_voltage` in menu_1014d.c.
    *Done in code 2026-07-12 (PORT_AUDIT F28 implementation; hardware-verify pending).*
21. **Recover the average's oversampling resolution (F28, Tier 2).** Defer the `/samplecount`
    division in `fpga_read_sample_data` until *after* mV scaling so Vavg/Vrms keep the sub-mV
    resolution that averaging 1500 samples provides (~11–12-bit DC via dither). Keep the integer
    `average` for control paths (50 %/autoset), add a high-res display value; then Vavg decimals
    mean something.
    *Done in code for Vavg 2026-07-12 (`averagesum` + hi-res `ui_display_vavg`; hardware-verify
    pending). Vrms still integer-divides then integer-`isqrt`s — open.*
22. **Zero a shorted channel in Base calibration (F30).** Root-cause and fix the non-repeatable
    +7–10 mV residual on a grounded input (trace above 0 V). Gate on the pecostm32 shorted-input
    A/B first (his ~0 vs ours +7 ⇒ our cal; both +7 ⇒ inherent front-end).
23. **Guard disabled-channel measurements (F29).** `ui_display_measurements` draws every slot
    unconditionally; blank/dash slots whose channel is disabled (fixes CH2 showing −22 V).
