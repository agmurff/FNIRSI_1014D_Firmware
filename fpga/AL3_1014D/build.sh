#!/bin/bash
# Headless TD build of the 1014D retarget (see README.md). Needs the TD 5.0.3 Linux
# install plus the GTK2 stub libs (FPGA_NOTES.md §TD rebuild for the one-time setup).
set -e
TD=${TD_HOME:-/home/jsantala/tools/anlogic-td/TD_5.0.3_28716_NL}
SHIM=${TD_SHIM:-/home/jsantala/tools/anlogic-td/shim}
HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=${1:-$HERE/build}

mkdir -p "$BUILD"
cat "$HERE/al_ip/pll.v" "$HERE/al_ip/sample_memory.v" "$HERE/zaklad.v" > "$BUILD/all_1014d.v"
cp "$HERE/zaklad_1014d.adc" "$HERE/zaklad_1014d.sdc" "$BUILD/"
sed "s|@TD@|$TD|" "$HERE/build.tcl" > "$BUILD/flow.tcl"

cd "$BUILD"
# "sh: Bad fd number" lines in the log are TD shelling bashisms at dash — cosmetic.
LD_LIBRARY_PATH="$SHIM:$TD/lib" "$TD/bin/td" flow.tcl > build.log 2>&1 || {
  echo "BUILD FAILED — errors:"; grep -iE 'ERROR' build.log | grep -v 'Bad fd' | head -20; exit 1; }
grep -iE 'ERROR' build.log | grep -v 'Bad fd' | head -10 || true
grep -A8 'Timing group' timing_1014d.rpt | head -11
ls -la FPGA_1014D.bit FPGA_1014D.bin
echo "OK — review reports in $BUILD, then curate into out/ manually."
