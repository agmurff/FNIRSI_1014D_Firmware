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

#endif /* PORT_CONFIG_H */
