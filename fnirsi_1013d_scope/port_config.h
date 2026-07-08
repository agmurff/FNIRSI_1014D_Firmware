//----------------------------------------------------------------------------------------------------------------------------------
// Build-variant selector for the 1013D-touch vs 1014D-keys port.
//
//   PORT_1014D == 1  -> FNIRSI 1014D bench model. Port A drives the Si5351-compatible clock
//                       generator (bit-banged I2C, PA0/PA1) and the UART1 key controller
//                       (PA2/PA3). There is NO touch panel; input comes from physical keys via
//                       uart1_handler(). cg_i2c_setup() supplies the external FPGA/ADC sample
//                       clock (also fixes the backlight-PWM flashing seen without it).
//
//   PORT_1014D == 0  -> original 1013D tablet model. Port A is the GT911 touch panel; input
//                       comes from touch_handler(). This reproduces the pristine Atlan4 build.
//
// Only main()'s init/dispatch differ between the two; everything else is shared. Keep this the
// single source of truth for the variant so both builds come from one codebase.
//----------------------------------------------------------------------------------------------------------------------------------

#ifndef PORT_CONFIG_H
#define PORT_CONFIG_H

#define PORT_1014D 1

// On-screen bring-up diagnostics (boot-stage boxes, green UART/FPGA status stack, proof-of-life
// flash). Off for normal builds; flip to 1 to re-enable when working on init/GUI. All uses are
// guarded by this flag, so 0 removes them entirely from the build.
#define PORT_A_KEYDEBUG 0

#if PORT_A_KEYDEBUG
//Font-independent boot progress marker: draws (n) cyan squares at the top-left of the trace area
//(to the visible framebuffer). Count the boxes = last milestone reached before a hang. Last-wins;
//cleared once real trace rendering runs. Usable from any .c that includes display_lib.h + variables.h.
#define DBG_STAGE(n) do { int _dbgi; \
    display_set_screen_buffer((uint16 *)maindisplaybuffer); \
    display_set_fg_color(0x00000000); display_fill_rect(10, 55, 470, 44); \
    display_set_fg_color(0x0000FFFF); \
    for(_dbgi=0;_dbgi<(n);_dbgi++) display_fill_rect(14 + _dbgi*46, 59, 36, 36); \
  } while(0)
#else
#define DBG_STAGE(n) do {} while(0)
#endif

#endif /* PORT_CONFIG_H */
