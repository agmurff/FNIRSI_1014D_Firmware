# Headless TD build flow for the 1014D retarget — run via build.sh (which fills @TD@
# and stages sources into the build dir). Verified working with TD 5.0.3 Linux
# 2026-07-18. Quirks this encodes (FPGA_NOTES.md §TD rebuild): read_verilog takes ONE
# -file, so build.sh concatenates the sources; al3_macro.v goes in via -lib;
# import_device without -package defaults to LQFP144 (the die's only package);
# bitgen -bin emits the flashable image for the FPGA's SPI flash.
import_device al3_10.db
read_verilog -lib @TD@/arch/al3_macro.v -file all_1014d.v -top fnirsi_1013D
read_adc zaklad_1014d.adc
optimize_rtl
read_sdc zaklad_1014d.sdc
map_macro
map
pack
place
route
report_area -file area_1014d.rpt
report_io -file io_1014d.rpt
report_timing -file timing_1014d.rpt
bitgen -bit FPGA_1014D.bit -bin FPGA_1014D.bin
exit
