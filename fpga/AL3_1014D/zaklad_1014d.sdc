# zaklad_1014d.sdc — timing constraints for the 1014D retarget.
# Baseline kept IDENTICAL to Atlan4's zaklad.sdc so first builds compare directly
# against his shipped FPGA_phy.timing (flow validation). The commented block below
# completes STA coverage — sample_write_clock / clk_50MHz / i_mcu_clk are otherwise
# invisible to timing analysis (FPGA_NOTES.md §TD rebuild) — enable it only AFTER the
# first successful build/bring-up, one line at a time.

create_clock -name clk_200MHz -period 5 -waveform {0 2} [get_nets clk_200MHz]
create_clock -name i_xtal -period 20 -waveform {0 10}  [get_ports i_xtal]
set_clock_latency  -source 1 [get_clocks {i_xtal}]

# --- full-coverage additions (TD dialect unverified; enable after first build) -------
#create_generated_clock -name sample_write_clock -source [get_nets clk_200MHz] -divide_by 2 [get_nets sample_write_clock]
#create_generated_clock -name clk_50MHz -source [get_nets clk_200MHz] -divide_by 4 [get_nets clk_50MHz]
#create_clock -name i_mcu_clk -period 100 [get_ports i_mcu_clk]
# + set_input_delay on i_adc*_d vs the encode outputs (AD9288 tCO + board flight time)
