//----------------------------------------------------------------------------------------------------------------------------------
// Build variant: 1=1014D (Si5351 clock gen + UART1 keys), 0=1013D (GT911 touch + RTC + battery)
//----------------------------------------------------------------------------------------------------------------------------------

#ifndef PORT_CONFIG_H
#define PORT_CONFIG_H

#define PORT_1014D 1

//Set to 1 for boot-stage boxes and heartbeat/FPGA status overlay during bring-up
#define PORT_A_KEYDEBUG 0

//Bench bring-up only: force USB into CDC/serial mode (USB_CH340=1) at boot.
//The 1014D has no UI path to the MSC<->CDC toggle (menu.c's toggle is touch-gated and
//tp_i2c_read_status() is a 1014D stub), and scope_load_configuration_data() restores
//USB_CH340 from the saved config sector *before* usb_device_init() runs -- so changing
//only the reset default in scope_reset_config_data() does NOT survive an existing saved
//config. This overrides after the config load. Costs USB mass storage while set.
//Set back to 0 once the Factory-settings USB-mode entry exists (ROADMAP item 13).
#define FORCE_USB_CDC 0

#if PORT_A_KEYDEBUG
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
