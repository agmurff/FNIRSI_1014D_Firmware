//******************************************************************************
/* 
 * File:   PC_interface.c
 * Author: Atlan
 * 
 * Created on November 2, 2025, 2:52 PM
 */
//******************************************************************************
//----------------------------------------------------------------------------------------------------------------------------------
#include "types.h"
#include "menu.h"
#include "test.h"
#include "scope_functions.h"
#include "statemachine.h"
#include "touchpanel.h"
#include "timer.h"
#include "fpga_control.h"
#include "spi_control.h"
#include "sd_card_interface.h"
#include "display_lib.h"
#include "ff.h"
#include "DS3231.h"

#include "usb_interface.h"
#include "cdc_class.h"
#include "variables.h"
#include "menu_1014d.h"

#include "PC_interface.h"

//#include "sin_cos_math.h"

//sinx
//#include <stdio.h>
//#include <math.h>
//#include <stdlib.h>

//endsinx

//#include <stdint.h>
//#include <stddef.h>

//#include <string.h>

/* Buffers and indices */
extern uint8 usb_rx[1024];
extern volatile uint32 usb_rx_in_idx;
extern volatile uint32 usb_rx_out_idx;

extern uint8 usb_tx[32768];
extern volatile uint32 usb_tx_in_idx;
extern volatile uint32 usb_tx_out_idx;

//------------------------------------------------------------------------------
sysparam SysParam;

//******************************************************************************
void ini_SysParam(void)
{
    uint8 i = 0;

    // Vynuluj celú štruktúru pre istotu
    memset(&SysParam, 0, sizeof(SysParam));

    // --- Základné systémové stavy ---
    SysParam.run_state       = 1;     // RUN (0=STOP,1=RUN,2=SINGLE/WAIT)
    SysParam.reserved1       = 0;
    SysParam.ch2_enabled     = 1;     // CH2 zapnutý (0=OFF,1=ON)

    for (i = 0; i < 17; i++) SysParam.reserved2[i] = 0;

    SysParam.time_zoom       = 16;    // Time base zoom (2=5ns ... 30=10s)

    for (i = 0; i < 35; i++) SysParam.reserved3[i] = 0;

    // --- Horizontálna pozícia (3 bajty little-endian, stred = 0x00124F80 = 1200000) ---
    SysParam.horiz_position[0] = 0x80;
    SysParam.horiz_position[1] = 0x4F;
    SysParam.horiz_position[2] = 0x12;

    for (i = 0; i < 5; i++) SysParam.reserved4[i] = 0;

    // --- Trigger ---
    SysParam.trigger_channel = 0;     // CH1 trigger
    SysParam.trigger_mode    = 0;     // AUTO
    SysParam.trigger_edge    = 0;     // UP
    SysParam.trigger_source  = 0;     // AUTO
    //for (i = 0; i < 4; i++) SysParam.reserved5[i] = 0;

    SysParam.trigger_level   = 128;   // Stredná úroveň
    SysParam.reserved6       = 0;

    // --- CH1 nastavenia ---
    SysParam.ch1_volt_zoom   = 10;    // 10 = cca 0.5V/div (4–13)
    //for (i = 0; i < 5; i++) SysParam.reserved7[i] = 0;

    SysParam.ch1_vert_position[0] = 0;
    SysParam.ch1_vert_position[1] = 0;

    //for (i = 0; i < 34; i++) SysParam.reserved8[i] = 0;

    SysParam.ch1_coupling    = 0;     // DC
    SysParam.ch1_probe       = 0;     // 1x

   // for (i = 0; i < 22; i++) SysParam.reserved9[i] = 0;

    // --- CH2 nastavenia ---
    SysParam.ch2_volt_zoom   = 10;    // 10 = rovnaký zoom ako CH1
   // for (i = 0; i < 7; i++) SysParam.reserved10[i] = 0;

    //SysParam.ch2_vert_position = 0;   // stred obrazovky
    SysParam.ch1_vert_position[0] = 0;
    SysParam.ch1_vert_position[1] = 0;
    
    //for (i = 0; i < 30; i++) SysParam.reserved11[i] = 0;

    SysParam.ch2_coupling    = 0;     // DC
    SysParam.ch2_probe       = 0;     // 1x

    //for (i = 0; i < 67; i++) SysParam.reserved12[i] = 0;

    // --- Doplnkové režimy ---
    SysParam.xy_mode         = 0;     // XY mode OFF
    SysParam.signal_gen      = 0;     // Signal generator OFF

    //for (i = 0; i < 33; i++) SysParam.reserved13[i] = 0;

    // --- Menu / výber kanála ---
    SysParam.selected_channel = 0;    // CH1
    SysParam.trigger_edit     = 0;    // OFF
    SysParam.menu_flags       = 1;    // normal

    //for (i = 0; i < 32; i++) SysParam.reserved14[i] = 0;
}
/*

void ini_SysParam(void) 
{
  uint8 i = 0;
  
  //﻿Inicializácia SysParam so všetkými reserved na 0 a predvolenými hodnotami
  SysParam.run_state = 1;         //STOP(0), RUN(1), SINGLE SHOT WAIT(2)      [uint8]
  SysParam.reserved1         = 0;        // reserved byte                             [uint8]
  SysParam.ch2_enabled            = 0;        // CH2 OFF(0), ON(1)                         [uint8]

 for( i=0; i<17; i++) SysParam.reserved2[i] = 0;// [uint8]

  SysParam.time_zoom         = 16;       // Time base zoom (2=5ns ... 30=10s)        [uint8]

  for( i=0; i<35; i++) SysParam.reserved3[i] = 0;   // [uint8]

  //SysParam.horiz_position    = 1200000;  // Horizontal position, center               [uint32_t]
  SysParam.horiz_position[0]    = 0x80;
  SysParam.horiz_position[1]    = 0x4F;
  SysParam.horiz_position[2]    = 0x12;

  for( i=0; i<5; i++) SysParam.reserved4[i] = 0;    // [uint8]

  SysParam.trigger_channel   = 0;        // Trigger CH1(0), CH2(1)                     [uint8]
  SysParam.trigger_mode      = 0;        // AUTO(0), NORMAL(1)                         [uint8]
  SysParam.trigger_edge      = 0;        // UP(0), DOWN(1)                             [uint8]
  SysParam.trigger_source    = 0;        // AUTO(0), MANUAL(1)                         [uint8]

  for( i=0; i<4; i++) SysParam.reserved5[i] = 0;    // [uint8]

  SysParam.trigger_level     = 128;      // Trigger level (0–255, center=128)         [uint8]
  SysParam.reserved6         = 0;        //[uint8]
  SysParam.ch1_volt_zoom     = 10;        // CH1 volts zoom (4–13)                      [uint8]

  for( i=0; i<5; i++) SysParam.reserved7[i] = 0;    // [uint8]

  SysParam.ch1_vert_position[0] = 0;        // CH1 vertical position                       [int16_t]
  SysParam.ch1_vert_position[1] = 0;

  for( i=0; i<34; i++) SysParam.reserved8[i] = 0;   //[uint8]

  SysParam.ch1_coupling      = 0;        //CH1 DC(0), AC(1)                           [uint8]
  SysParam.ch1_probe         = 0;        // CH1 probe 1x(0), 10x(1), 100x(2)         [uint8]

  for( i=0; i<22; i++) SysParam.reserved9[i] = 0;   //[uint8]

  for( i=0; i<33; i++) SysParam.reserved13[i] = 0;  // [uint8]

  SysParam.selected_channel  = 0;        // Selected channel CH1(0), CH2(1)           [uint8]
  SysParam.trigger_edit      = 0;        // Trigger edit OFF(0), ON(1)                 [uint8]
  SysParam.menu_flags        = 1;        // Menu flags: 0=no menu, 1=normal, 4=gen, 8=50% [uint8]

  for( i=0; i<32; i++) SysParam.reserved14[i] = 0;  // [uint8]
}
*/
//******************************************************************************



//extern sysparam SysParam;
/*
void usb_CDC_send_data(uint8 *data, uint32 length)
{
    if (!usb_connect || data == NULL || length == 0)
        return;

    uint32 i = 0;

    while (i < length)
    {
        // vypočítaj počet voľných bajtov v TX buffri
        uint32 free_space = circular_buffer_free(usb_tx_in_idx, usb_tx_out_idx, sizeof(usb_tx));

        // ak nie je miesto, spusti odosielanie a čakaj
        if (free_space == 0)
        {
            usb_CDC_in_ep_callback();  // odošli čo sa dá
            continue;                  // počkaj, kým sa buffer uvoľní
        }

        // koľko bajtov môžeme teraz zapísať
        uint32 to_copy = length - i;
        if (to_copy > free_space)
            to_copy = free_space;

        // zapíš dáta do TX kruhového bufferu
        for (uint32 n = 0; n < to_copy; n++)
        {
            usb_tx[usb_tx_in_idx++] = data[i++];
            usb_tx_in_idx %= sizeof(usb_tx);
        }

        // spusti prenos
        usb_CDC_in_ep_callback();
    }
*/
    // po

    /*
     // Pomocná funkcia na odoslanie dát cez TX buffer
void usb_CDC_send_data(uint8 *data, uint32 length)
{
    for(uint32 i = 0; i < length; i++)
    {
        uint32 next = (usb_tx_in_idx + 1) % sizeof(usb_tx);
        if(next == usb_tx_out_idx)
            break; // buffer full
        usb_tx[usb_tx_in_idx] = data[i];
        usb_tx_in_idx = next;
    }
}
*/

//==============================================================================
// Line-oriented command dispatcher -- main-loop serviced
//==============================================================================
// Framing contract (follows the #END / #ERR convention already used in this tree):
//   every command emits zero or more response lines, then exactly one "#END" line.
//   Setters that succeed emit "#OK" first. Failures emit "#ERR <reason>".
//   A host can therefore always read until "#END".
//
// Values on the wire are raw firmware indices / struct values, NOT engineering units:
// the firmware works in table indices throughout (time_div_texts[35] etc.) and has no
// printf. Unit conversion belongs on the host, where it can be done properly.
//
// This runs from the main loop, not from the EP2 interrupt callback, so a reply is free
// to be slow. Bulk waveform transfer (:WAV:DATA?) belongs here too, for the same reason.

#define CDC_CMD_BUF_SIZE   128

//------------------------------------------------------------------------------
static void cdc_end(void)
{
    usb_CDC_send_text("#END\n");
}

static void cdc_ok(void)
{
    usb_CDC_send_text("#OK\n");
    cdc_end();
}

static void cdc_err(const char *reason)
{
    usb_CDC_send_text("#ERR ");
    usb_CDC_send_text(reason);
    usb_CDC_send_text("\n");
    cdc_end();
}

//Unsigned scalar reply
static void cdc_uval(uint32 v)
{
    usb_send_uint("", v);
    cdc_end();
}

//Signed scalar reply (measurements and the horizontal position can be negative)
static void cdc_send_int(const char *label, int32 v)
{
    usb_CDC_send_text(label);

    if(v < 0)
    {
        usb_CDC_send_text("-");
        v = -v;
    }

    usb_send_uint("", (uint32)v);
}

static void cdc_ival(int32 v)
{
    cdc_send_int("", v);
    cdc_end();
}

//------------------------------------------------------------------------------
//Per-channel queries. Returns 1 if the tail was recognised, 0 otherwise.
static int cdc_channel_query(const char *tail, CHANNELSETTINGS *ch)
{
    if(my_strcasecmp(tail, "STAT?")    == 0) { cdc_uval(ch->enable);             return 1; }
    if(my_strcasecmp(tail, "VOLTDIV?") == 0) { cdc_uval(ch->displayvoltperdiv);  return 1; }
    if(my_strcasecmp(tail, "SAMPDIV?") == 0) { cdc_uval(ch->samplevoltperdiv);   return 1; }
    if(my_strcasecmp(tail, "COUPL?")   == 0) { cdc_uval(ch->coupling);           return 1; }
    if(my_strcasecmp(tail, "PROBE?")   == 0) { cdc_uval(ch->magnification);      return 1; }
    if(my_strcasecmp(tail, "POS?")     == 0) { cdc_uval(ch->traceposition);      return 1; }
    if(my_strcasecmp(tail, "INV?")     == 0) { cdc_uval(ch->invert);             return 1; }

    //Measurements from the most recent completed acquisition
    if(my_strcasecmp(tail, "MIN?")     == 0) { cdc_ival(ch->min);                return 1; }
    if(my_strcasecmp(tail, "MAX?")     == 0) { cdc_ival(ch->max);                return 1; }
    if(my_strcasecmp(tail, "AVG?")     == 0) { cdc_ival(ch->average);            return 1; }
    if(my_strcasecmp(tail, "CENTER?")  == 0) { cdc_ival(ch->center);             return 1; }
    if(my_strcasecmp(tail, "PP?")      == 0) { cdc_ival(ch->peakpeak);           return 1; }
    if(my_strcasecmp(tail, "RMS?")     == 0) { cdc_uval(ch->rms);                return 1; }

    return 0;
}

//------------------------------------------------------------------------------
static void cdc_system_status_body(void)
{
    usb_send_uint("runstate: ",     scopesettings.runstate);
    usb_send_uint("timeperdiv: ",   scopesettings.timeperdiv);
    usb_send_uint("samplerate: ",   scopesettings.samplerate);
    usb_send_uint("long_mode: ",    scopesettings.long_mode);
    usb_send_uint("samplecount: ",  scopesettings.samplecount);
    usb_send_uint("nofsamples: ",   scopesettings.nofsamples);
    usb_send_uint("totalsamples: ", fpgasettings.totalsamples);
    usb_send_uint("acq_trace: ",    scopesettings.ACQ_trace);
    usb_send_uint("average_mode: ", scopesettings.average_mode);

    usb_send_uint("trig_channel: ", scopesettings.triggerchannel);
    usb_send_uint("trig_mode: ",    scopesettings.triggermode);
    usb_send_uint("trig_edge: ",    scopesettings.triggeredge);
    usb_send_uint("trig_level: ",   scopesettings.triggerlevel);
    cdc_send_int("trig_hpos: ",     scopesettings.triggerhorizontalposition);

    usb_send_uint("ch1_enable: ",   scopesettings.channel1.enable);
    usb_send_uint("ch1_voltdiv: ",  scopesettings.channel1.displayvoltperdiv);
    usb_send_uint("ch1_coupling: ", scopesettings.channel1.coupling);
    usb_send_uint("ch1_probe: ",    scopesettings.channel1.magnification);
    usb_send_uint("ch1_pos: ",      scopesettings.channel1.traceposition);

    usb_send_uint("ch2_enable: ",   scopesettings.channel2.enable);
    usb_send_uint("ch2_voltdiv: ",  scopesettings.channel2.displayvoltperdiv);
    usb_send_uint("ch2_coupling: ", scopesettings.channel2.coupling);
    usb_send_uint("ch2_probe: ",    scopesettings.channel2.magnification);
    usb_send_uint("ch2_pos: ",      scopesettings.channel2.traceposition);

    //What a remote renderer needs to reproduce the on-screen mapping exactly
    //(scope_get_y_sample: px = (adc-128)*input_calibration[samplevoltperdiv] >> 21,
    // y = 448 - (traceposition + px + dcoff), position space clamped 0..399):
    usb_send_uint("ch1_cal: ",      scopesettings.channel1.input_calibration[scopesettings.channel1.samplevoltperdiv]);
    usb_send_uint("ch2_cal: ",      scopesettings.channel2.input_calibration[scopesettings.channel2.samplevoltperdiv]);
    cdc_send_int("ch1_dcoff: ",     (scopesettings.channel1.dc_shift_size != 0) ? ((scopesettings.channel1.dcoffset * 100) / scopesettings.channel1.dc_shift_size) : 0);
    cdc_send_int("ch2_dcoff: ",     (scopesettings.channel2.dc_shift_size != 0) ? ((scopesettings.channel2.dcoffset * 100) / scopesettings.channel2.dc_shift_size) : 0);
    usb_send_uint("trig_vpos: ",    scopesettings.triggerverticalposition);

    usb_send_uint("xymode: ",       scopesettings.xymodedisplay);
    usb_send_uint("fw_fpga: ",      fpgasettings.fw_FPGA);
}

static void cdc_system_status(void)
{
    cdc_system_status_body();
    cdc_end();
}

//------------------------------------------------------------------------------
// Waveform dump. Hex, not raw binary, for two reasons: usb_CDC_send_text() measures its
// argument with a NUL scan so it cannot carry arbitrary bytes, and hex survives a plain
// terminal. Cost is 2 chars/sample, which is irrelevant next to the USB link.
//
// The 32 KB TX ring SILENTLY TRUNCATES when full (usb_CDC_send_text clamps to free space),
// so the ring is flushed every line rather than queueing the whole trace and hoping.
#define CDC_WAV_PER_LINE   32

static void cdc_wave_emit(const uint8 *buf, const char *name, uint32 decim);

static void cdc_wave_dump(const char *tail)
{
    const uint8 *buf;
    const char  *name;
    uint32 n, i, sent, decim = 1;

    while(*tail == ' ')
        tail++;

    //Both trace buffers are declared uint32[] but are addressed as bytes throughout the
    //firmware -- scope_save_view_item_file() writes them as (uint8 *) too.
    if(my_strncasecmp(tail, "CH1", 3) == 0)
    {
        buf  = (const uint8 *)channel1tracebuffer;
        name = "CH1";
    }
    else if(my_strncasecmp(tail, "CH2", 3) == 0)
    {
        buf  = (const uint8 *)channel2tracebuffer;
        name = "CH2";
    }
    else
    {
        cdc_err("usage: :WAV:DATA? CH1|CH2 [decimation]");
        return;
    }

    //Optional decimation: send every Nth sample. The full 3000-sample hex dump is what
    //bounds a live-view poll cycle (the serial link is only serviced once per acquisition
    //loop), so letting the host ask for every 5th sample cuts the transfer by that factor.
    tail += 3;
    while(*tail == ' ')
        tail++;

    if((*tail >= '0') && (*tail <= '9'))
    {
        decim = my_atoul(tail);

        if(decim < 1)
            decim = 1;

        if(decim > 64)
            decim = 64;
    }
    else if(*tail != 0)
    {
        cdc_err("usage: :WAV:DATA? CH1|CH2 [decimation]");
        return;
    }

    cdc_wave_emit(buf, name, decim);
    cdc_end();
}

//Emit one channel's header + hex block, no terminator -- shared by :WAV:DATA? and :LIVE?
static void cdc_wave_emit(const uint8 *buf, const char *name, uint32 decim)
{
    uint32 n, i, sent;

    n = scopesettings.samplecount;

    if(n > MAX_SAMPLE_BUFFER_SIZE)
        n = MAX_SAMPLE_BUFFER_SIZE;

    sent = (n + decim - 1) / decim;

    //Header first, so the host knows how many samples to expect before the hex starts:
    //"#WAV <ch> <count>" then a "decim: N" line
    usb_CDC_send_text("#WAV ");
    usb_CDC_send_text(name);
    usb_CDC_send_text(" ");
    usb_send_uint("", sent);
    usb_send_uint("decim: ", decim);
    usb_CDC_in_ep_callback();

    sent = 0;

    for(i = 0; i < n; i += decim)
    {
        send_hex_byte(buf[i]);
        sent++;

        if((sent % CDC_WAV_PER_LINE) == 0)
        {
            usb_CDC_send_text("\n");
            usb_CDC_in_ep_callback();
        }
    }

    //Terminate a partial final line
    if((sent % CDC_WAV_PER_LINE) != 0)
    {
        usb_CDC_send_text("\n");
        usb_CDC_in_ep_callback();
    }
}

//------------------------------------------------------------------------------
// :LIVE? [decimation] -- the whole live view in ONE round trip: the status block,
// then a decimated wave block per enabled channel. Exists because the per-command
// latency floor (the serial link is serviced once per acquisition loop, ~350 ms)
// dominates a poll cycle, not the transfer: status + two captures as separate
// commands costs three loop periods, this costs one.
static void cdc_live(const char *arg)
{
    uint32 decim = 5;

    while(*arg == ' ')
        arg++;

    if((*arg >= '0') && (*arg <= '9'))
    {
        decim = my_atoul(arg);

        if(decim < 1)
            decim = 1;

        if(decim > 64)
            decim = 64;
    }
    else if(*arg != 0)
    {
        cdc_err("usage: :LIVE? [decimation]");
        return;
    }

    cdc_system_status_body();

    if(scopesettings.channel1.enable)
        cdc_wave_emit((const uint8 *)channel1tracebuffer, "CH1", decim);

    if(scopesettings.channel2.enable)
        cdc_wave_emit((const uint8 *)channel2tracebuffer, "CH2", decim);

    cdc_end();
}

//==============================================================================
// Setters
//==============================================================================
// Every setter drives the firmware's OWN handler rather than writing scopesettings
// directly, because each setting has side effects that must reach the FPGA: a raw struct
// write leaves the hardware on the previous value and silently desynchronises the scope.
//
// The dial handlers (sm_set_time_base, sm_set_channel_sensitivity) take a *delta* through
// the global 'setvalue', so absolute commands compute the delta, drive the handler once,
// then restore the dial default.
//
// The bodies sit behind PORT_1014D because those sm_/ui_ handlers live in the
// whole-file-guarded 1014D modules, while PC_interface.c itself is always compiled.

//Parse an unsigned decimal, requiring at least one digit. Returns 0 on a malformed argument.
static int cdc_parse_uint(const char *s, uint32 *out)
{
    while(*s == ' ')
        s++;

    if((*s < '0') || (*s > '9'))
        return 0;

    *out = my_atoul(s);

    return 1;
}

//------------------------------------------------------------------------------
static void cdc_set_timebase(const char *arg)
{
    uint32 target;

    if(!cdc_parse_uint(arg, &target))
    {
        cdc_err("expected a timebase index");
        return;
    }

    if(target > 34)
    {
        cdc_err("timebase index out of range (0-34)");
        return;
    }

#if PORT_1014D
    {
        int32 delta = (int32)target - (int32)scopesettings.timeperdiv;

        if(delta != 0)
        {
            int8 saved = setvalue;

            //sm_set_time_base() is the dial handler and does the whole job: long/short regime
            //selection, the FPGA timebase command, sample rate, re-arm in single mode, and
            //the display. Writing scopesettings.timeperdiv here would leave the FPGA behind.
            setvalue = (int8)delta;
            sm_set_time_base();
            setvalue = saved;
        }

        //It deliberately remaps indices 7..10 (the roll/sweep overlap where
        //200ms/100ms/50ms/20ms appear in both blocks), so report what actually stuck rather
        //than echoing back what was asked for.
        usb_send_uint("timeperdiv: ", scopesettings.timeperdiv);
        cdc_ok();
    }
#else
    cdc_err("not supported on this build variant");
#endif
}

//------------------------------------------------------------------------------
static void cdc_set_trigger_level(const char *arg)
{
    uint32 target;

    if(!cdc_parse_uint(arg, &target))
    {
        cdc_err("expected a level");
        return;
    }

    if(target > 255)
    {
        cdc_err("trigger level out of range (0-255)");
        return;
    }

#if PORT_1014D
    {
        uint32 voltperdiv;
        int32  traceposition;
        int32  dcoffset;

        //fpga_set_trigger_level() derives the ADC level from the on-screen marker position,
        //so solve its formula backwards for the position that yields the requested level.
        //Assigning scopesettings.triggerlevel directly would just be recomputed over.
        if(scopesettings.triggerchannel == 0)
        {
            voltperdiv    = scopesettings.channel1.samplevoltperdiv;
            traceposition = scopesettings.channel1.traceposition;
            dcoffset      = (scopesettings.channel1.dcoffset * 100) / scopesettings.channel1.dc_shift_size;
        }
        else
        {
            voltperdiv    = scopesettings.channel2.samplevoltperdiv;
            traceposition = scopesettings.channel2.traceposition;
            dcoffset      = (scopesettings.channel2.dcoffset * 100) / scopesettings.channel2.dc_shift_size;
        }

        scopesettings.triggerverticalposition =
            (uint16)(((((int32)target - 128) * signal_adjusters[voltperdiv]) >> VOLTAGE_SHIFTER)
                     + traceposition + dcoffset);

        ui_display_trigger_vertical_position();
        fpga_set_trigger_level();

        //Report what the FPGA actually took: the marker is quantised to screen pixels, so the
        //achieved level can sit a count or two off the requested one.
        usb_send_uint("trig_level: ", scopesettings.triggerlevel);
        cdc_ok();
    }
#else
    cdc_err("not supported on this build variant");
#endif
}

//------------------------------------------------------------------------------
//which: 0 = source/channel, 1 = mode, 2 = edge
static void cdc_set_trigger_field(const char *arg, int which)
{
    uint32 v;
    uint32 limit = (which == 1) ? 2 : 1;

    if(!cdc_parse_uint(arg, &v))
    {
        cdc_err("expected a value");
        return;
    }

    if(v > limit)
    {
        cdc_err("value out of range");
        return;
    }

#if PORT_1014D
    switch(which)
    {
        case 0:
            if(scopesettings.triggerchannel != v)
            {
                scopesettings.triggerchannel = v;
                ui_display_trigger_channel();
                fpga_set_trigger_channel();

                //The level maps through the new channel's position and sensitivity, so
                //re-derive the marker and push it (mirrors UIC_BUTTON_TRIG_CHX)
                scope_calculate_trigger_vertical_position();
                fpga_set_trigger_level();
            }
            break;

        case 1:
            scopesettings.triggermode = v;
            ui_display_trigger_mode();
            fpga_set_trigger_mode();
            break;

        case 2:
            scopesettings.triggeredge = v;
            ui_display_trigger_edge();
            fpga_set_trigger_edge();
            break;
    }

    cdc_ok();
#else
    cdc_err("not supported on this build variant");
#endif
}

//------------------------------------------------------------------------------
//Per-channel setters. Returns 1 if the tail was recognised.
static int cdc_channel_set(const char *tail, CHANNELSETTINGS *ch)
{
    uint32 v;

    if(my_strncasecmp(tail, "VOLTDIV ", 8) == 0)
    {
        if(!cdc_parse_uint(&tail[8], &v)) { cdc_err("expected an index");          return 1; }
        if(v > 6)                         { cdc_err("voltdiv out of range (0-6)"); return 1; }
#if PORT_1014D
        {
            int32 delta = (int32)v - (int32)ch->displayvoltperdiv;

            if(delta != 0)
            {
                //sm_set_channel_sensitivity() pushes volts/div and the DC offset, re-maps the
                //trigger level when the trigger is on this channel, and settles 50ms.
                int8 saved = setvalue;
                setvalue = (int8)delta;
                sm_set_channel_sensitivity(ch);
                setvalue = saved;
            }

            usb_send_uint("voltdiv: ", ch->displayvoltperdiv);
            cdc_ok();
        }
#else
        cdc_err("not supported on this build variant");
#endif
        return 1;
    }

    if(my_strncasecmp(tail, "COUPL ", 6) == 0)
    {
        if(!cdc_parse_uint(&tail[6], &v)) { cdc_err("expected 0 (DC) or 1 (AC)"); return 1; }
        if(v > 1)                         { cdc_err("coupling must be 0 or 1");   return 1; }
#if PORT_1014D
        if(ch->coupling != v)
        {
            ch->coupling = v;

            //On a switch to AC the DC offset trim no longer applies (mirrors the channel menu)
            if(ch->coupling)
                ch->dcoffset = 0;

            fpga_set_channel_coupling(ch);
            fpga_set_channel_offset(ch);

            //Zeroing the offset shifts the trigger level mapping
            if(((ch == &scopesettings.channel1) && (scopesettings.triggerchannel == 0)) ||
               ((ch == &scopesettings.channel2) && (scopesettings.triggerchannel == 1)))
            {
                fpga_set_trigger_level();
            }

            ui_display_channel_coupling(ch);
        }

        cdc_ok();
#else
        cdc_err("not supported on this build variant");
#endif
        return 1;
    }

    if(my_strncasecmp(tail, "STAT ", 5) == 0)
    {
        if(!cdc_parse_uint(&tail[5], &v)) { cdc_err("expected 0 or 1");      return 1; }
        if(v > 1)                         { cdc_err("state must be 0 or 1"); return 1; }
#if PORT_1014D
        //sm_toggle_channel_enable() also moves the trigger source off a channel being
        //disabled, so toggle through it rather than assigning enable directly.
        if(ch->enable != v)
            sm_toggle_channel_enable(ch);

        cdc_ok();
#else
        cdc_err("not supported on this build variant");
#endif
        return 1;
    }

    return 0;
}

//------------------------------------------------------------------------------
static void cdc_dispatch(char *cmd)
{
    //--- identity ---------------------------------------------------------------
    if(my_strcasecmp(cmd, "*IDN?") == 0)
    {
        usb_CDC_send_text("FNIRSI,");
#if PORT_1014D
        usb_CDC_send_text("1014D,");
#else
        usb_CDC_send_text("1013D,");
#endif
        usb_CDC_send_text(VERSION_STRING);
        usb_send_uint(",FPGA", fpgasettings.fw_FPGA);
        cdc_end();
        return;
    }

    //--- ping -------------------------------------------------------------------
    if(my_strcasecmp(cmd, "*PING") == 0) { cdc_ok(); return; }

    //--- whole-system snapshot --------------------------------------------------
    if(my_strcasecmp(cmd, ":SYST:STAT?") == 0) { cdc_system_status(); return; }

    //--- live view: status + enabled channels' traces, one round trip ------------
    if(my_strncasecmp(cmd, ":LIVE?", 6) == 0) { cdc_live(&cmd[6]); return; }

    //--- run control ------------------------------------------------------------
    //Mirrors the RUN/STOP key in sm_1014d.c: set the flag, then repaint the label.
    if(my_strcasecmp(cmd, ":RUN?") == 0) { cdc_uval(scopesettings.runstate); return; }

    if((my_strcasecmp(cmd, ":RUN") == 0) || (my_strcasecmp(cmd, ":STOP") == 0))
    {
        scopesettings.runstate = (my_strcasecmp(cmd, ":RUN") == 0)
                                   ? RUN_STATE_RUNNING : RUN_STATE_STOPPED;
#if PORT_1014D
        ui_display_run_stop_text();
#endif
        cdc_ok();
        return;
    }

    //--- acquisition ------------------------------------------------------------
    if(my_strcasecmp(cmd, ":ACQ:POINTS?") == 0) { cdc_uval(scopesettings.samplecount);  return; }
    if(my_strcasecmp(cmd, ":ACQ:NOFS?")   == 0) { cdc_uval(scopesettings.nofsamples);   return; }
    if(my_strcasecmp(cmd, ":ACQ:TOTAL?")  == 0) { cdc_uval(fpgasettings.totalsamples);  return; }
    if(my_strcasecmp(cmd, ":ACQ:MODE?")   == 0) { cdc_uval(scopesettings.ACQ_trace);    return; }
    if(my_strcasecmp(cmd, ":ACQ:AVG?")    == 0) { cdc_uval(scopesettings.average_mode); return; }

    //--- timebase ---------------------------------------------------------------
    //Index into Atlan4 35-entry space (0 = 50 s/div; below 11 = long/roll mode).
    if(my_strcasecmp(cmd, ":TIM:SCALE?") == 0) { cdc_uval(scopesettings.timeperdiv);  return; }
    if(my_strcasecmp(cmd, ":TIM:RATE?")  == 0) { cdc_uval(scopesettings.samplerate);  return; }
    if(my_strcasecmp(cmd, ":TIM:LONG?")  == 0) { cdc_uval(scopesettings.long_mode);   return; }
    if(my_strcasecmp(cmd, ":TIM:POS?")   == 0) { cdc_ival(scopesettings.triggerhorizontalposition); return; }

    //--- trigger ----------------------------------------------------------------
    if(my_strcasecmp(cmd, ":TRIG:SOUR?") == 0) { cdc_uval(scopesettings.triggerchannel); return; }
    if(my_strcasecmp(cmd, ":TRIG:MODE?") == 0) { cdc_uval(scopesettings.triggermode);    return; }
    if(my_strcasecmp(cmd, ":TRIG:EDGE?") == 0) { cdc_uval(scopesettings.triggeredge);    return; }
    if(my_strcasecmp(cmd, ":TRIG:LEV?")  == 0) { cdc_uval(scopesettings.triggerlevel);   return; }

    //--- setters ----------------------------------------------------------------
    if(my_strncasecmp(cmd, ":TIM:SCALE ", 11) == 0) { cdc_set_timebase(&cmd[11]);         return; }
    if(my_strncasecmp(cmd, ":TRIG:LEV ",  10) == 0) { cdc_set_trigger_level(&cmd[10]);    return; }
    if(my_strncasecmp(cmd, ":TRIG:SOUR ", 11) == 0) { cdc_set_trigger_field(&cmd[11], 0); return; }
    if(my_strncasecmp(cmd, ":TRIG:MODE ", 11) == 0) { cdc_set_trigger_field(&cmd[11], 1); return; }
    if(my_strncasecmp(cmd, ":TRIG:EDGE ", 11) == 0) { cdc_set_trigger_field(&cmd[11], 2); return; }

    //--- waveform ---------------------------------------------------------------
    //Note: with average_mode on, the displayed trace comes from channelXtracebufferAVG;
    //this dumps the raw acquisition buffer, same as the on-scope waveform file does.
    if(my_strncasecmp(cmd, ":WAV:DATA?", 10) == 0)
    {
        cdc_wave_dump(&cmd[10]);
        return;
    }

    //--- per-channel ------------------------------------------------------------
    if(my_strncasecmp(cmd, ":CH1:", 5) == 0)
    {
        if(cdc_channel_query(&cmd[5], &scopesettings.channel1)) return;
        if(cdc_channel_set(&cmd[5], &scopesettings.channel1))   return;
        cdc_err("unknown CH1 subcommand");
        return;
    }

    if(my_strncasecmp(cmd, ":CH2:", 5) == 0)
    {
        if(cdc_channel_query(&cmd[5], &scopesettings.channel2)) return;
        if(cdc_channel_set(&cmd[5], &scopesettings.channel2))   return;
        cdc_err("unknown CH2 subcommand");
        return;
    }

    cdc_err("unknown command");
}

//------------------------------------------------------------------------------
// Drains the RX ring the EP2 interrupt fills (usb_CDC_out_ep_callback in cdc_class.c),
// assembles whole lines, and dispatches them. Called once per main-loop iteration.
void usb_CDC_process_rx(void)
{
    static char   cmd_buf[CDC_CMD_BUF_SIZE];
    static uint16 idx = 0;
    static uint8  overflow = 0;

    while(usb_rx_out_idx != usb_rx_in_idx)
    {
        char c = usb_rx[usb_rx_out_idx++];
        usb_rx_out_idx %= sizeof(usb_rx);

        if((c != '\n') && (c != '\r'))
        {
            //Truncate rather than overrun, and remember that we did so, so the caller
            //gets an error instead of a silently mangled command. (The old code stopped
            //storing but never reset idx, so an over-long line merged into the next one.)
            if(idx < (CDC_CMD_BUF_SIZE - 1))
                cmd_buf[idx++] = c;
            else
                overflow = 1;

            continue;
        }

        //Line terminator. Ignore empty lines so CRLF does not dispatch twice.
        if((idx == 0) && (overflow == 0))
            continue;

        cmd_buf[idx] = 0;

        if(overflow)
            cdc_err("command too long");
        else
            cdc_dispatch(cmd_buf);

        idx      = 0;
        overflow = 0;

        //Push the queued reply out of the TX ring. Safe here: main-loop context.
        usb_CDC_in_ep_callback();
    }
}

/*
 if(strcmp(cmd_buf, "#ECHO") == 0)
{
    char msg[64];
    sprintf(msg, "Run state: %d, CH2: %d, TimeZoom: %d\r\n",
            SysParam.run_state, SysParam.ch2_on, SysParam.time_zoom);
    usb_ch340_send_data((uint8*)msg, strlen(msg));
}
 */

/*
 
 void gini_Sys1Param(void) 
{
    display_set_fg_color(BLACK_COLOR);
    display_fill_rect(488, 420, 250, 50); // Vyčistí priestor na zobrazenie textu

    // Nastavenie farby textu a fontu
    display_set_fg_color(WHITE_COLOR);
    display_set_font(&font_0);

    // Zobrazenie textu
    display_text(488, 440, message);
    display_decimal(600, 440, value);
    display_text(495, 455, viewfilename);

    timer0_delay(3000); // Počká 3 sekundy
}
 */
//*********************************************
// prevod bajtu na dva hex znaky
/*
 void send_hex_byte(uint8 b)
{
    char out[2];
    const char hex[] = "0123456789ABCDEF";
    out[0] = hex[(b >> 4) & 0x0F];
    out[1] = hex[b & 0x0F];
    usb_ch340_send_data((uint8*)out, 2);
}
 */

void send_hex_byte(uint8 byte)
{
    char hex[3];
    const char hexchars[] = "0123456789ABCDEF";
    hex[0] = hexchars[(byte >> 4) & 0x0F];
    hex[1] = hexchars[byte & 0x0F];
    hex[2] = 0;
    usb_CDC_send_text(hex);
}
//===================================================

// pomocná funkcia na odoslanie čísla
void usb_send_uint(const char *label, uint32_t v)
{
    char buf[32];
    usb_CDC_send_text(label);

    // konverzia cisla
    int pos = 0;
    if (v == 0) {
        buf[pos++] = '0';
    } else {
        char tmp[32];
        int t = 0;
        while (v > 0) {
            tmp[t++] = '0' + (v % 10);
            v /= 10;
        }
        // obrátiť poradie
        while (t--) buf[pos++] = tmp[t];
    }
    buf[pos] = 0;

    usb_CDC_send_text(buf);
    usb_CDC_send_text("\n");
        // 🔥 DÔLEŽITÉ: odoslať buffer do USB IN endpointu
    //usb_CDC_in_ep_callback();
}


//******************************************************************************

//Simple strstr replacement: find substring within string
const char *my_strstr(const char *haystack, const char *needle)
{
  if (!*needle) return haystack; // Empty substring always matches

  const char *p1 = haystack;
  while (*p1)
  {
    const char *p1_begin = p1;
    const char *p2 = needle;

    // Compare characters
    while (*p1 && *p2 && (*p1 == *p2))
    {
      p1++;
      p2++;
    }

    if (!*p2) return p1_begin; // Found match

    p1 = p1_begin + 1; // Move to next position
  }

  return 0; // Not found
}

//-----------------------------------------------------------------

int my_strcmp(const char *s1, const char *s2)
{
  while (*s1 && (*s1 == *s2)) 
  {
    s1++;
    s2++;
  }
  return *(const unsigned char *)s1 - *(const unsigned char *)s2;
}

char *my_strrchr(const char *s, int c)
{
    const char *last = 0;
    do {
        if (*s == (char)c)
            last = s;
    } while (*s++);
    return (char*)last;
}

char *my_strcpy(char *dest, const char *src)
{
    char *d = dest;
    while ((*d++ = *src++));
    return dest;
}

char *my_strncpy(char *dest, const char *src, int n)
{
    int i;
    for (i = 0; i < n && src[i]; i++) dest[i] = src[i];
    for (; i < n; i++) dest[i] = '\0';
    return dest;
}

// pripojí src na koniec dst
char *my_strcat(char *dst, const char *src)
{
    char *p = dst;

    // nájdi koniec dst
    while (*p) p++;

    // skopíruj src na koniec dst
    while (*src) {
        *p++ = *src++;
    }

    *p = 0; // null-terminátor
    return dst;
}


int my_strlen(const char *s)
{
    int len = 0;
    while (*s++) len++;
    return len;
}

// Simple sprintf for path joining (no formatting)
void my_sprintf_path(char *dst, const char *folder, const char *fname)
{
    while (*folder) *dst++ = *folder++;
    *dst++ = '/';
    while (*fname) *dst++ = *fname++;
    *dst = 0;
}
/*
// Case-insensitive compare
int my_strcasecmp(const char *s1, const char *s2)
{
    while (*s1 && *s2)
    {
        char c1 = *s1++;
        char c2 = *s2++;
        if (c1 >= 'A' && c1 <= 'Z') c1 += 32;
        if (c2 >= 'A' && c2 <= 'Z') c2 += 32;
        if (c1 != c2) return (unsigned char)c1 - (unsigned char)c2;
    }
    return (unsigned char)*s1 - (unsigned char)*s2;
}
*/
// jednoduchá funkcia na porovnanie reťazcov bez ohľadu na veľkosť písmen
int my_strcasecmp(const char *s1, const char *s2)
{
    while (*s1 && *s2)
    {
        char c1 = (*s1 >= 'a' && *s1 <= 'z') ? *s1 - 32 : *s1;
        char c2 = (*s2 >= 'a' && *s2 <= 'z') ? *s2 - 32 : *s2;
        if (c1 != c2)
            return c1 - c2;
        s1++;
        s2++;
    }
    return *s1 - *s2;
}

int my_strncasecmp(const char *s1, const char *s2, int n)
{
    for (int i = 0; i < n; i++) {
        char c1 = s1[i];
        char c2 = s2[i];
        if (c1 >= 'A' && c1 <= 'Z') c1 += 'a' - 'A';
        if (c2 >= 'A' && c2 <= 'Z') c2 += 'a' - 'A';
        if (c1 != c2 || c1 == '\0' || c2 == '\0')
            return (unsigned char)c1 - (unsigned char)c2;
    }
    return 0;
}

uint32_t my_atoul(const char *s)
{
    uint32_t v = 0;
    while (*s >= '0' && *s <= '9') {
        v = v * 10 + (*s - '0');
        s++;
    }
    return v;
}

void my_uint_to_str(char *dst, uint32 v)
{
    char tmp[12];
    int p = 0;

    if (v == 0) {
        dst[0] = '0';
        dst[1] = 0;
        return;
    }

    // ulož číslice odzadu
    while (v > 0) {
        tmp[p++] = '0' + (v % 10);
        v /= 10;
    }

    // otoč do správneho poradia
    for (int i = 0; i < p; i++)
        dst[i] = tmp[p - 1 - i];

    dst[p] = 0;
}




//******************************************************************************