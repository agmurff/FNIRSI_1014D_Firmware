# PORT_AUDIT.md — audit of the 1014D graft onto Atlan4 v1.00o5

**Audited:** commit `4a5fa61` ("working state", 2026-07-09) on branch `atlan4-base`.
**Audit date:** 2026-07-09 (Claude, static analysis + build verification; no hardware in the loop).
**What was audited:** the port that grafts pecostm32's official 1014D firmware modules onto
Atlan4's 1013D fork v1.00o5, authored largely via opencode ("Big Pickle") and documented in
`AGENTS.md`.

## Method

Four trees were cross-compared file-by-file and hunk-by-hunk:

| Tree | Path | Role |
|---|---|---|
| **W** | `fnirsi_1013d_scope/` (repo root) | the working port |
| **A4** | `Atlan4-1.00o5/fnirsi_1013d_scope/` | pristine base (also vendored at commit `9daa91f`) |
| **P14** | `FNIRSI_1014D_Firmware/fnirsi_1014d_scope/` | pecostm32 official 1014D (origin of imports) |
| **P13** | `FNIRSI_1013D_Firmware/fnirsi_1013d_scope/` | pecostm32 upstream 1013D (context only) |

Checks: import fidelity (W's 1014D files vs their P14 origins, accounting for renames),
seam integrity (every W-vs-A4 change classified as guarded/additive/bring-up-fix),
table/index-space coherence, both build variants compiled with object-level symbol
verification, bootloader binary provenance by hash.

## Verdict

The graft is **structurally sound**. Imports are near-byte-faithful with a small number of
deliberate, correct API bridges; all shared-core modifications are `#if PORT_1014D`-guarded or
additive; persistence stays on Atlan4's single config path; the committed 1014D bootloader is
byte-identical to a local rebuild of pecostm32's `fnirsi_1014d_startup`. The known-broken
timebase has a precise mechanical explanation (F1). The **1013D variant** did not deliver on
its "reproduces upstream Atlan4" claim (F3, F4). All actionable findings were fixed the same
day — see §5 for outcomes (F2 was retracted on link-level verification).

## 1. Verified good

- **Import fidelity.** `clock_synthesizer.c/.h` and `uart.c` are byte-identical to P14 modulo
  blank lines; `uart.h` = P14 + an added (now unreferenced) `GD_KEY_*` table.
  `menu_1014d.c` ← P14 `user_interface_functions.c` (5083 lines, 29 diff lines);
  `sm_1014d.c` ← P14 `statemachine.c` (2538 lines, 50 diff lines). Every deviation was read:
  include renames, whole-file `#if PORT_1014D` guards (correctly placed **after** includes),
  the F1/F2 boot-source switch, and four API bridges:
  - `settings->triggeronchannel` (field absent in Atlan4) → pointer-compare against
    `scopesettings.triggerchannel`: semantically equivalent to P14's `1^ch`/`0^ch` assignment.
  - `scope_set_50_percent_trigger()` → Atlan4's `scope_do_50_percent_trigger_setup()`
    (real function, `scope_functions.c:1512`; equivalence assumed, not line-verified).
  - `display_top_pointer(x, c)` → Atlan4's `(x, TRACE_VERTICAL_START, c)` signature.
  - `MEASUREMENTFUNCTION` → `UI_MEASUREMENTFUNCTION` typedef rename (both exist in W).
- **Seam integrity.** All W-vs-A4 changes in shared core are `#if PORT_1014D`-guarded or
  benign-additive: `main()` (Si5351 before FPGA — same order as P14; touch setup/restore
  screen skipped; `ui_setup_main_screen()`; `sm_init()`/`sm_handle_user_input()`),
  `scope_functions.c` (1014D chrome redraw inside the copy-rect, `ui_draw_grid`,
  `#if !PORT_1014D` around 1013D cursor/measurement chrome), `fpga_control.c`
  (bounded ready-wait: converts a hard hang into a timeout; `tp_i2c_read_status()` skip that
  fixes the PA2/PA3 UART mux clobber), `variables.h`/`statemachine.h`/`fnirsi_1013d_scope.h`
  (additive defines/structs; `CHANNELSETTINGS`/`SCOPESETTINGS` 1014D fields appended at the
  **end** of the structs, guarded), `display_lib` (P14 draw functions added), `icons.c`
  (append-only, 0 removals), `ccu_control.h` (UART1 gate/reset bits — bit 21, correct for
  F1C100s).
- **Index-space coherence (tables).** Both `sm_set_time_base()` and `menu_1014d.c` bound and
  index `timeperdiv` against W's tables (`time_div_texts[35]`,
  `time_per_div_sample_rate[35]`, `screen_time_calc_data[35]`), so UI and core agree on
  Atlan4's 35-entry space (0 = 50 s/div). No 24-vs-35 offset bug exists — the timebase
  breakage is F1 below. FPGA rate encodings in `sample_rate_settings[]` are identical between
  A4 and P14 for all common entries (0, 1, 3, 9, 19 …), i.e. both target the same stock-FPGA
  command encoding.
- **FPGA compatibility.** Atlan4's three-FPGA support is intact (`0x1432` stock / `0x1532`
  PECO-AL3 / `0x1632` PECO-EF2 → `fw_FPGA` 1/2/3). Stock 1014D reports `0x1432` → `fw_FPGA=1`,
  the path all timebase writes assume. pecostm32's *new 1014D FPGA design* was deliberately
  not imported.
- **Persistence.** Single config path in both variants: Atlan4's
  `scope_load_configuration_data()` at boot + `scope_save_configuration_data()` on the key
  controller's `UIC_BUTTON_OFF` (0xC8) power-down notification (`sm_1014d.c:100`). The
  imported `ui_save_setup`/`ui_prepare_setup_for_file` only serialize in-memory snapshots and
  waveform-file headers, not a second flash/SD config.
- **Boot-source switch contract.** F1 double-tap → `*0x81BFFC1F = 2` (FEL), F2 → `1` (SD),
  then `sd_card_write(DISPLAY_CONFIG_SECTOR=710, …)` + watchdog reset — matches the
  pecostm32-1014D bootloader's startup-menu byte in the display-config sector staging area.
- **Builds.** 1014D variant: clean end-to-end (`EXIT 0`), correct `[port_config.h variant:
  v1.00o5-1014D]` and `BOOTLOADER: bootloader_1014d_base.bin at offset 0x8000` echoes,
  variant-named artifacts produced. `sm_1014d.o` (65 functions) and `menu_1014d.o`
  (102) fully compiled in the 1014D build and **empty** in the 1013D build (guards after
  includes — the AGENTS.md gotcha is respected).
- **Bootloader provenance.** `fnirsi_1013d_scope/bootloader_1014d_base.bin` is
  **md5-identical** to the locally rebuilt
  `FNIRSI_1014D_Firmware/fnirsi_1014d_startup/dist/.../fnirsi_sd_card_bootloader.bin`
  (`a281ab70…`). It differs from the GitHub-committed binary only because ours is a local
  GCC-14 rebuild.
- **`types.h` int8 fix.** `typedef signed char int8` is exactly P14's own definition, required
  by the imported UI (`setvalue = -1`). The 234 `-Wpointer-sign` warnings are fallout, not
  bugs.
- **font_1 swap.** `font_1` is now P14's 13 px variable-width font (defined in `font_1.c`,
  removed from `font_0.c`). No Atlan4-side file references `font_1`, so the 1013D variant is
  unaffected; only the imported UI uses it (26 references).

## 2. Findings (severity-ordered)

### F1 — `sm_set_time_base()` is missing Atlan4's timebase choreography → **the** broken-timebase root cause. (HIGH)

`sm_1014d.c:1401` (imported from P14) only does: bounds-check → `timeperdiv = newvalue` →
`samplerate = time_per_div_sample_rate[tpd]` (when running) → `fpga_set_sample_rate()` →
redraw. That is all P14 hardware needs because pecostm32's 1014D has **no long timebases**
(24-entry space starting at 200 ms/div).

Atlan4's reference flow (`scope_set_timebase()`, `scope_functions.c:190`) additionally:
1. remaps 9→11 / 10→8 in scope mode (skips 50/20 ms) and flips `scopesettings.long_mode`;
2. sends `fpga_set_long_timebase(tpd)` when `tpd < 11`, else `fpga_set_time_base(tpd)` and
   sets `display_data_done`;
3. re-derives `samplerate` + `fpga_set_sample_rate()`;
4. handles single-trigger-mode restart and calls `scope_preset_values()`.

Without (1)/(2), stepping below index 11 leaves the FPGA in short-timebase mode with a
long-timebase sample rate and a stale `long_mode`, and even in the short region the FPGA
never receives an updated `0x0E` timebase/sample-count command nor a `scope_preset_values()`
reset. **Fix recipe:** rebuild `sm_set_time_base()` around `scope_set_timebase()`'s logic
(the function is in shared core and compiled in both variants). Caveat: `scope_set_timebase()`
reads `previousytouch` in its rate-update condition — on 1014D that global is stale/0 (the
condition then degenerates to true), so either call it as-is knowingly, or lift its body minus
the touch dependency. Keep `scope_calculate_sample_range_properties()` at the end (see F8).

### F2 — `strcpy` return-semantics mismatch. **(RETRACTED — false alarm, verified at link level)**

Initial version of this finding blamed Atlan4's `strcpy.s` (which returns one **past** the
terminator) for breaking the imported `buffer = strcpy(buffer, …)` chains
(`menu_1014d.c:1795, 2183, 2230, 2913`). Wrong: **`strcpy.s` is vestigial and never
compiled** — it is absent from `nbproject/Makefile-Debug.mk` in Atlan4 upstream and in this
tree. The `strcpy` that actually links is a C function in `scope_functions.c:4208`
(pecostm32-mainline, adopted by Atlan4) that returns a pointer **at** the terminator —
byte-for-byte the same semantics as the copy Big Pickle deleted from
`user_interface_functions.c` (that deletion avoided a duplicate-symbol link error, not a
behavior change). Atlan4's own code chains it the same way (`scope_functions.c:4257, 4304`).
The imported UI strings were never broken.

**Residual (real) risk in this family:** GCC treats `strcpy` as a builtin and, for calls it
can fold (e.g. literal/known-length sources), substitutes **ISO** dst-return semantics —
which would silently break the terminator-chaining contract. All six chained sites currently
use variable sources (not foldable), but `-fno-builtin-strcpy` was added to CFLAGS to close
the class permanently.

### F3 — `#ifndef PORT_1014D` guards are dead: the 1013D variant loses touch, battery, and RTC. (MEDIUM)

`port_config.h` **always** defines `PORT_1014D` (as 1 or 0), and `touchpanel.c`,
`power_and_battery.c`, `DS3231.c` all see it via `variables.h → port_config.h`. So their
`#ifndef PORT_1014D` function-body guards are **always false**: bodies are compiled out in
*both* variants. Verified on 1013D-variant objects: `tp_i2c_setup`, `tp_i2c_read_status`,
`battery_check_status`, and all DS3231 functions are 4-byte `bx lr` stubs. The 1014D build is
unaffected (stubs are what it wants), but the "PORT_1014D 0 reproduces upstream Atlan4" claim
in AGENTS.md is currently false — that build would boot with **no input at all**.
**Fix recipe:** change every `#ifndef PORT_1014D` in those three files to `#if !PORT_1014D`
(guards are already after the includes, so the macro is defined at that point).

### F4 — 1013D-variant `make` exits with an error at the final packaging step. (MEDIUM)

`Makefile:132-137`: for the 1013D variant `VARIANT_PREFIX=fnirsi_1013d`, so the variant-copy
becomes `cp fnirsi_1013d_scope.bin fnirsi_1013d_scope.bin` → "same file" → **make error 1**
(after all real artifacts were already produced). Breaks scripted builds and the "both
variants build" claim. **Fix recipe:** wrap the two `cp`s in
`if [ "$(VARIANT_PREFIX)" != "fnirsi_1013d" ]; then …; fi` (or `cp` to a temp name).

### F5 — NAV_LEFT / NAV_RIGHT key codes disagree between the two tables. (LOW — hardware check)

`uart.h` (from the original port_a bring-up): `GD_KEY_NAV_LEFT=0x08`, `GD_KEY_NAV_RIGHT=0x0C`.
`statemachine.h` (from P14): `UIC_BUTTON_NAV_RIGHT=8`, `UIC_BUTTON_NAV_LEFT=12`. All other 50
codes agree numerically. Dispatch uses only `UIC_*` (the `GD_*` table is now completely
unreferenced), so behavior follows pecostm32's mapping.
**Resolved 2026-07-09:** user confirmed pecostm32's mapping is the correct one (the original
port_a probing labels were the confused ones — the raw codes were probed on this unit and
shared with pecostm32). The `GD_*` labels in `uart.h` were corrected to match and marked
documentation-only.

### F6 — `tagThumbnailData` gained an **unguarded** `tracedisplaymode` field → saved-file format break. (LOW)

`variables.h` (thumbnail struct): `tracedisplaymode` inserted mid-struct (P14's layout),
unguarded, in both variants. Thumbnail/waveform files written by pristine Atlan4 firmware
misparse in this tree and vice versa (fields after the insertion shift by one byte, including
both 100-byte trace arrays). Within this tree the two variants agree with each other.
Acceptable if declared intentional — document it, or guard + provide a legacy reader if
cross-firmware file exchange matters.

### F7 — Implicit function declarations. (LOW)

- `sm_1014d.c` boot-switch calls `sd_card_write()` without `#include "sd_card_interface.h"`
  (port-introduced). Benign on ARM32 EABI, but add the include.
- `PC_interface.c` calls `usb_CDC_in_ep_callback()` without including `cdc_class.h` —
  **pre-existing upstream Atlan4 wart**, not port-introduced.
- These are why `-Wno-error=implicit-function-declaration -Wno-error=implicit-int
  -Wno-error=int-conversion` were added to CFLAGS for GCC 14. After fixing the first item,
  only the pre-existing one remains.

### F8 — Imported `scope_calculate_sample_range_properties()` ignores `long_mode`. (INFO)

The imported helper (`scope_functions.c:2561`) always uses the `50.0 *` short-mode formula,
while Atlan4's per-frame recompute inside `scope_display_trace_data()`
(`scope_functions.c:2610`) switches to `5.0 *` in long mode. Harmless today because the
display path recomputes every frame and overwrites it — but keep in mind when fixing F1
(don't let the un-scaled value be consumed between keypress and next frame).

### F9 — Build/config drift worth knowing. (INFO)

- CFLAGS changed `-O3` → `-O2` (plus `-fcommon` and the F7 warning demotions). Older docs
  saying the debug build is `-Og -g` are stale.
- The battery icon on 1014D persists because `batterychargelevel` is preset to 20 (max) at
  init and chrome draws it unconditionally while `battery_check_status()` is a stub —
  already in AGENTS.md's known issues; mechanism confirmed.
- `dist/Debug/GNU_ARM-Linux/scope-1014D.bin` (416768 B) is a stray manual artifact, not
  produced by the current Makefile.

## 3. AGENTS.md errata (as of its 2026-07-09 state)

- "Key dispatch — Inline in `main()` loop" → superseded: dispatch is `sm_init()` +
  `sm_handle_user_input()` from `sm_1014d.c`.
- "`menu_1014d.c` + `sm_1014d.c` … as untracked files … Makefile picks them up via the
  wildcard" → they are committed, and `nbproject/Makefile-Debug.mk` lists all objects
  **explicitly** (menu_1014d.o, sm_1014d.o, clock_synthesizer.o, uart.o, font_1.o, strlen.o).
- "Key code values are identical … no translation layer" → true **except** NAV_LEFT/NAV_RIGHT
  are swapped between the GD_* and UIC_* tables (F5); GD_* is dead code.
- "touchpanel.c … empty stubs on 1014D" → true, but they are (unintentionally) empty stubs on
  the 1013D variant too (F3).

## 4. Hardware-verify checklist (can't be settled statically)

1. Timebase behavior after the F1 fix: step through the full range with the TIME rotary in
   run and stop, across the long/short boundary (the 20/50 ms skip at indices 8↔11), and in
   single-trigger mode (should re-arm and show RUN).
2. Overlay-menu compositing (fix pass §6): with the main menu, channel menus, sliders, and
   on/off panels open, traces should keep updating beneath the menu; the grid-brightness
   slider should now live-preview again. File view/item view must still suppress traces.
3. Version string no longer overlaps (suffix removed; both variants display `v1.00o5`).
4. ~~F1-double-tap → FEL and F2 → SD boot-source switching~~ — settled statically instead
   (2026-07-09, BOOT_NOTES.md): the switch targets the Atlan4-loader byte contract, which
   the current pecostm32-1014D bootloader never reads, so it is **inert on SD boots**. Don't
   burn bench time on it; decide port-the-contract vs drop-the-feature (ROADMAP.md item 2).
5. Long-soak: the bounded FPGA ready-wait (2 000 000 iterations) — confirm no spurious
   timeouts at the slowest rates on real hardware. NOTE: after F1, long timebases
   (50 s/div … 20 ms/div) are reachable from the keys for the first time on this hardware —
   exercise them specifically (Atlan4's `scope_get_long_timebase_data()` roll-mode path).
6. 1013D variant on a 1013D unit, if ever needed: touch/battery/RTC restored by the F3 fix
   have never been hardware-tested in this tree.

## 5. Fix pass (2026-07-09, same session — all applied, both variants rebuilt clean)

| Finding | Outcome |
|---|---|
| F1 timebase | **Fixed.** `sm_set_time_base()` now mirrors `scope_set_timebase()`: wave-view regime clamp, 9/11–10/8 skip, `long_mode` + `fpga_set_long_timebase()`/`fpga_set_time_base()` + `display_data_done`, conditional samplerate + `scope_preset_values()`, single-mode re-arm with `ui_display_run_stop_text()`. |
| F2 strcpy | **Retracted** (see F2). `strcpy.s` edit reverted; `-fno-builtin-strcpy` added to CFLAGS as insurance against GCC builtin folding. |
| F3 dead guards | **Fixed.** All 35 `#ifndef PORT_1014D` → `#if !PORT_1014D` (touchpanel.c, power_and_battery.c, DS3231.c). Verified by nm: 1013D objects have real bodies again (`tp_i2c_setup` 472 B, `battery_check_status` 192 B), 1014D still stubs. |
| F4 Makefile | **Fixed.** Variant-copy step skipped when the prefix equals the base name; 1013D-variant `make` now exits 0. |
| F5 key labels | **Resolved.** pecostm32 mapping confirmed correct by user; `GD_KEY_NAV_RIGHT`=0x08 / `GD_KEY_NAV_LEFT`=0x0C in uart.h, marked documentation-only. |
| F6 thumbnail format | Left as-is (deliberate P14 format adoption; documented). |
| F7 implicit decls | **Fixed.** `sm_1014d.c` includes `sd_card_interface.h`; `menu.c` includes `cdc_class.h` (pre-existing upstream wart). Zero implicit-declaration warnings remain. |
| F8 range properties | **Fixed.** `scope_calculate_sample_range_properties()` is long_mode-aware (5.0 vs 50.0 factor, same as the display path). |
| Battery icon (AGENTS known issue) | **Confirmed stale.** Nothing on the 1014D path draws it since the `ui_setup_main_screen()` swap: `menu_1014d.c`/`sm_1014d.c` contain no battery drawing, `battery_check_status()` is a stub, and `scope_setup_main_screen()`'s only shared-core caller is Atlan4's wave-file loader, unreachable from the 1014D UI. |
| Version string overlap | **Fixed.** `-1014D` suffix removed from the displayed `VERSION_STRING` (user: the 1014D is recognizable by its UI); build artifacts stay variant-named via the Makefile. |

**Enhancement — overlay-menu compositing (user request):** menus that are plain overlays
(main menu, channel menu, slider, on/off panel — `ui_menu_composite_active()` /
`ui_redraw_active_menu()` in `menu_1014d.c`) are now redrawn into `displaybuffertmp` at the
end of `scope_display_trace_data()`'s 1014D chrome pass, and the display gates
(`fnirsi_1013d_scope.c` main loop + the early return in `scope_display_trace_data()`) let
those states through. Result: traces keep updating live beneath open overlay menus (the main
loop never stopped acquiring — `enablesampling` is not consulted by the Atlan4 loop), menus
render flicker-free because they land in the offscreen buffer before the atomic blit, and the
grid-brightness slider's live preview (which calls `scope_display_trace_data()` mid-menu and
was dead under the old blanket gate) works again. Full-screen states (file view, item view)
are unchanged — traces stay suppressed there.

## 5b. Bench-feedback fix pass (2026-07-10 — F10/F11, both variants rebuilt clean)

**F10 — the 1014D UI was rendering with Atlan4's 1013D fonts (root cause of a whole class
of text glitches).** Only `font_1` was imported from pecostm32's `1014D_fonts.c`;
`menu_1014d.c` also uses `font_0/2/3/4`, which resolved to Atlan4's fonts with different
glyphs, widths and spacing (P14 `font_2/3` have per-char spacing 1 vs Atlan4's 0; P14
`font_4` is 32 px vs Atlan4's 16 px). Bench symptoms: measurement slots showing "nax"
(clipped "Vmax"), assorted misfit text. **Fixed:** P14's `font_0/2/3/4` imported as
`fonts_1014d.c` (`#if PORT_1014D`), Atlan4's `font_0/2/3/4.c` guarded `#if !PORT_1014D`,
object registered in `Makefile-Debug.mk`. Verified by nm: the 1014D build takes all four
from `fonts_1014d.o`, Atlan4's font objects compile empty.

**F11 — 1014D F-key measurement slots were never defaulted nor persisted.** Atlan4's
`scope_reset_config_data()`/config sector predate the P14 `measurementitems[6]` model, so
the zeroed globals left every slot "Vmax" with a NULL `channelsettings` pointer (same class
as the earlier movespeed finding: P14 defaults not carried into Atlan4's reset). **Fixed:**
P14 defaults (Vpp/Vavg/Freq × CH1/CH2) added to the reset; slots persisted at new config
offset `MEASUREMENT_SLOT_SETTING_OFFSET` (208) as 6×(channel,index); restore clamps the
channel, range-checks the index (≥12 → per-slot default) and rebuilds the `channelsettings`
pointer (pointers are never persisted). `SETTING_SECTOR_VERSION_LOW` bumped 0x0015→0x0016 —
**first boot of the new binary reloads defaults once** (old sectors lack the slot fields).

Smaller items, same pass: version string moved to P14's top-bar spot (233,4 — Atlan4's
698,24 sat on the F1 slot text in the P14 layout) and now carries a **build stamp**
`MMDD.HHMM` from `build_time.h` (regenerated every make — flash verification at a glance);
1014D `time_div_texts` lost their "/div" suffix (P14's bottom bar has its own "DIV :"
label; the suffixed strings right-aligned over it for anything longer than "5ns/div"); the
auto-clock-search summary now lingers 3 s (was unreadably fast). The Grok clock-search
repair earlier the same day is documented in FPGA_NOTES.md §"Auto clock search".

## 5c. Screenshot-driven fix pass (2026-07-10 night — F12–F15, both variants rebuilt clean)

Root material: 12 bench BMPs (shorted inputs, before/after Base cal), analyzed
pixel-level; the sawtooth findings from the same set are in FPGA_NOTES.md §"Screenshot
analysis". All items below verified against pecostm32's reference source.

**F12 — sidebar measurement values never update.** pecostm32 calls
`ui_update_measurements()` from `scope_display_trace_data()` every frame; the graft never
called it, so the six slots kept their setup-time garbage (average=0 → −128 counts →
bogus "22.0v", itself left-clipped by F13). **Fixed:** called at the end of the 1014D
trace flow — *after* the trace copy, because the value fields (x≥717) overlap the trace
copy rect (2..729) and the later copy must win; the function now sets its own source
buffer (`displaybuffer1` — this tree's trace flow leaves source on `displaybuffertmp`,
P14's default assumption doesn't hold) and the caller restores the screen buffer to
`maindisplaybuffer` afterwards.

**F13 — P14 sidebar coordinates collide with Atlan4's wider trace window.** P14's trace
window ends at x=706; Atlan4's per-frame copy rect is x=2..729. The measurement labels
(`MEASUREMENT_LABEL_X` 719) lost their leading glyphs every frame ("Vavg"→"avg",
"Freq"→"eq", "Vpp"→clipped "pp") — except slot 1, whose label row sits above the rect's
y=48. **Fixed:** labels moved to x=731 (they are only redrawn on slot changes); values
stay at 719 and survive via the F12 copy ordering. Full-width narrowing of the trace
window to P14 geometry was considered and rejected for now (touches the whole trace
pipeline; 800-px row wrap risk if values move right instead).

**F14 — probe magnification semantic clash (wrong ×10/×100 scaling).** P14 UI treats
`magnification` as probe index 0/1/2 = 1:1/10:1/100:1; Atlan4's tables
(`volt_div_texts[7][7]`, `volt_calc_data[7][7]`) use rows 0.5×,1×,10×,20×,50×,100×,1000×.
The graft mixed them: default 1 displayed as "10 : 1" while scaling 1× (the bench unit's
"10:1" chip with correct 50 mV math), and cycling probe set 0.5×/1×/10× while displaying
1:1/10:1/100:1. **Fixed:** probe UI now cycles rows {1,2,5} via
`probe_magnification_from_index[]`/`ui_probe_index_from_magnification()`; the 3-entry
icon/text arrays are indexed by probe index, magnification stays in Atlan4 space
everywhere else (volt math untouched).

**F15 — top-bar sensitivity field overflow.** The P14 "DIV :" field is 57 px with a
clear rect the same size; Atlan4's `volt_div_texts` carry a "/div" suffix and overflow it
to the left, leaving stale leading characters on change (bench: "150mV/div" hybrid of old
"100mV/div" + new "50mV/div"). Same class as the F10-pass `time_div_texts` fix, missed
then. **Fixed:** new `volt_div_texts_short[7][7]` (values only, `const char *` to stay
warning-neutral) used by `ui_display_channel_sensitivity()`.

Also in this pass (see FPGA_NOTES §Screenshot analysis for rationale): Base calibration
persists its results via `scope_save_configuration_data()` on success (F-class: results
previously lived in RAM until soft-off — hard power cycle silently reverted them), and
displays the measured interleave comps (`C1:/C2:` lines, 2.5 s) for the ongoing sawtooth
work. Builds: 1013D exit 0 / 257 warnings (baseline); 1014D **built last**, exit 0 /
266 warnings (baseline 267 — the removed always-false `magnification < 0` compare),
`>>> BOOTLOADER: bootloader_1014d_base.bin at offset 0x8000`.

**F16 — normal/single trigger mode deadlocks when the level leaves the signal (bench,
same night).** Atlan4's acquisition is non-blocking: `scope_acquire_trace_data()` only
sends `fpga_set_trigger_level()` when *arming* a conversion (gated on
`display_data_done == 1`). The 1014D rotary handler `sm_set_trigger_level()` updated
`triggerverticalposition` but never pushed the level. So in normal/single mode (FPGA
trigger mode 0x01, no auto timeout): conversion armed with a level outside the waveform →
never completes → `display_data_done` never returns to 1 → moving the level back is never
sent to the FPGA → permanent freeze (trace *and* measurements — nothing new is acquired).
The 1013D touch flow was immune because `menu.c` pushes the level directly while dragging.
**Fixed** by pushing `fpga_set_trigger_level()` from every 1014D place the level mapping
changes outside the acquire loop: `sm_set_trigger_level()` (rotary), the trigger-channel
toggle (level maps through the new channel's position/sensitivity), the 50 % button, and
trigger-origin-with-level. Writing cmd 0x17 while a conversion is armed is the established
1013D pattern. Note Auto mode always self-healed (FPGA times out and completes) — that is
why only Normal showed it.

**F17 — per-frame trace copy narrowed to the P14 trace window (bench round 2, same
night).** Bench confirmed the F13 analysis visibly: the x=707..729 strip has no grid (P14
grid ends at 704) and the trace copy there flash-fought the measurement-value fronts and
wiped the slot dividers. Root fix instead of the F13 label workaround: the 1014D per-frame
copy is now `(2, 48, 705, 432)` (ends x=706 = P14 window edge; trace drawn beyond simply
isn't shown, matching where the grid ends), `MEASUREMENT_LABEL_X` restored to P14-native
719, and `ui_update_measurements()` no longer depends on copy ordering (kept after the
copy anyway). The y-range is intentionally NOT narrowed to P14's 59..458: the composited
factory/clock menus (to y=472) and the waiting/triggered text live in the 48..479 band.
Also: version string + build stamp split onto two font_1 lines at (233, 4)/(233, 16) —
the single font_2 line ran into the move-speed icon/text at x=330. Open from the same
bench round: "a bit of chrome" visible below the PECO logo and below the version area
(y≈48–58 strip) — identified and fixed as F18. F16 (trigger deadlock) bench-verified
fixed.

**F18 — orphaned shade tops above the trace window (bench 13/14.bmp, 2026-07-11).** The
"chrome fragments" under the PECO logo (x≈60–100) and under the version text (x≈237–482)
are the *tops* of `ui_draw_outline()`'s decorative shade trapezoids (rows 44..47): the
per-frame trace copy rect starts at y=48, so each frame wiped rows 48..57 (shade bottoms
+ window border) while the rows above y=48 survived from setup — not touch chrome after
all, and present in every build; visibility depended on screen state. **Fixed** by adding
`ui_draw_outline()` to the 1014D pre-copy chrome refresh in `scope_display_trace_data()`
(border/shades/cutouts rebuilt into displaybuffertmp each frame; its sidebar lines at
x711+ fall outside the copied columns, harmless), plus clamping the trace x range to the
P14 window (6..704 instead of Atlan4's 3..727) so traces don't paint over the restored
border columns.

**F19 — Base calibration reverted on every hard power cycle (bench 13/14.bmp,
2026-07-11).** The 77af34b persistence fix was only half the story: the save side works
(`scope_save_config_data()` writes `dc_calibration_offset[]` + the 4 ADC comps into the
settings sector), but stock Atlan4's `scope_load_input_calibration_data()` only restores
those settings-sector values when the **INPUT_CALIBRATION_SECTOR** checksum validates —
a sector written solely by the 1013D input-calibration procedure, never on a 1014D. So
the gate always failed and every boot loaded the 860/0 defaults (zero level off by the
uncompensated amount, comps gone). **Fixed** by splitting the function into two
independent blocks: settings-sector cal values restore on their own plausibility check
(all 12 offsets in 100..1600, all 4 comps |x|≤100 — needed because
`scope_reset_config_data()` calls in with a settingsworkbuffer that may have failed the
settings checksum), while `input_calibration[]`/dc_shift stay gated on the input-cal
sector checksum + `reload_cal_data` as before. Side effect (matches stock 1013D intent):
calibration now also survives Factory settings → Restore defaults, since the workbuffer
still holds valid data on that path.

## 5d. GUI-glue audit (2026-07-10 night) — why the GUI "felt rewritten", quantified

Concern: the port was supposed to carry pecostm32's 1014D GUI over, yet placement and
functionality kept differing. Mechanical audit: extracted every `ui_*` call made by the
pecostm32 core files we deliberately did NOT import (`scope_functions.c`,
`statemachine.c`, `fnirsi_1014d_scope.c`, `fpga_control.c` — 49 distinct functions) and
checked each against this tree. Result after F12: **all 49 are hooked up**; exactly two
P14 UI functions exist here but are never called, both deliberately superseded —
`ui_setup_display_lib()` (Atlan4's own display init does the same) and
`ui_show_open_slider()` (P14 redraws the open slider per frame from its trace loop; this
tree's overlay compositing redraws it via `ui_redraw_active_menu()` instead). So the GUI
*code* is verbatim P14; every bench difference so far has been a **seam** where that code
meets Atlan4's engine: fonts (F10), config/reset defaults (F11), core call-site hooks
(F12, F16), trace-window geometry (F13), data tables (F14, F15). The seam classes are now
each audited; remaining risk is per-call-site behavioral drift, found only on the bench.

## 6. Reproduction appendix

```bash
# file-by-file classification of the working tree against the three references
for f in $(ls fnirsi_1013d_scope | grep -E '\.(c|h|s|ld)$'); do ...cmp/diff per tree...; done

# import fidelity
diff FNIRSI_1014D_Firmware/fnirsi_1014d_scope/user_interface_functions.c fnirsi_1013d_scope/menu_1014d.c
diff FNIRSI_1014D_Firmware/fnirsi_1014d_scope/statemachine.c            fnirsi_1013d_scope/sm_1014d.c

# guard truth (F3): bodies gone in both variants
arm-none-eabi-gcc -E -DNO_STDLIB=1 -I fnirsi_1013d_scope fnirsi_1013d_scope/touchpanel.c | awk '/tp_i2c_setup/,/^}/'
arm-none-eabi-nm -S build/Debug/GNU_ARM-Linux/touchpanel.o   # 4-byte T symbols

# variant builds (always finish on the 1014D variant!)
sed -i 's/PORT_1014D 1/PORT_1014D 0/' fnirsi_1013d_scope/port_config.h && make clean && make  # F4 error
sed -i 's/PORT_1014D 0/PORT_1014D 1/' fnirsi_1013d_scope/port_config.h && make clean && make  # exit 0

# bootloader provenance
md5sum fnirsi_1013d_scope/bootloader_1014d_base.bin \
       FNIRSI_1014D_Firmware/fnirsi_1014d_startup/dist/Debug/GNU_ARM-Linux/fnirsi_sd_card_bootloader.bin
```
