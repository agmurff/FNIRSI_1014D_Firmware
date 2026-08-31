"""
Automated noise-floor characterisation of the FNIRSI 1014D.

Sweeps CH1 through every volts-per-division setting, captures the raw acquisition
buffer at each, and reports the noise in both ADC counts and input-referred volts.

With nothing connected this measures the instrument's own noise floor. The interesting
question it answers: is the noise dominated by the ADC (constant in counts, so scaling
with V/div when referred to the input) or by the analog front end (constant in volts)?
"""
import sys, time, math
sys.path.insert(0, r'C:\Fnirsi_Oscilloscope\host')
from fnirsi_scope import FnirsiScope, VOLTDIV_LABELS, voltdiv_volts, find_scope_port

# The 1014D screen is 8 vertical divisions; the ADC spans those with mid-scale at 128.
# That gives roughly 25 counts per division -- enough to refer counts back to volts.
COUNTS_PER_DIV = 25.0


def stats(xs):
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / n
    return mean, math.sqrt(var), min(xs), max(xs)


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_scope_port()
    if not port:
        raise SystemExit("no scope found")

    with FnirsiScope(port) as s:
        base = s.status()
        original_vd = base["ch1_voltdiv"]
        original_cp = base["ch1_coupling"]
        probe_row = base["ch1_probe"]

        print(f"scope     : {s.identify()['raw']}")
        print(f"timebase  : {base['timebase_label']}/div")
        print(f"probe     : {base.get('ch1_probe_label')}")
        print(f"coupling  : DC (forced for this sweep)")
        print()

        # DC coupling so we see the real offset, not an AC-blocked one
        s.configure_channel("CH1", coupling=0)

        print(f"{'idx':>3}  {'V/div':>8}  {'mean':>7}  {'sd':>6}  {'p-p':>4}  "
              f"{'sd (mV in)':>11}  {'p-p (mV in)':>12}")
        print("-" * 68)

        rows = []
        for vd in range(7):
            s.configure_channel("CH1", voltdiv=vd)
            time.sleep(0.35)                      # let the front end settle
            s.stop()                              # freeze so the buffer is coherent
            time.sleep(0.25)
            wf = s.capture("CH1", with_scaling=False)
            s.run()

            mean, sd, lo, hi = stats(wf.samples)
            vpd = voltdiv_volts(probe_row, vd)
            volts_per_count = vpd / COUNTS_PER_DIV

            sd_mv = sd * volts_per_count * 1000.0
            pp_mv = (hi - lo) * volts_per_count * 1000.0

            label = VOLTDIV_LABELS[probe_row][vd]
            print(f"{vd:>3}  {label:>8}  {mean:>7.2f}  {sd:>6.2f}  {hi-lo:>4}  "
                  f"{sd_mv:>11.1f}  {pp_mv:>12.1f}")

            rows.append(dict(idx=vd, label=label, volts_per_div=vpd, mean=mean,
                             sd_counts=sd, pp_counts=hi - lo,
                             sd_mv=sd_mv, pp_mv=pp_mv))

        # restore
        s.configure_channel("CH1", voltdiv=original_vd, coupling=original_cp)
        s.run()

        print()
        sds = [r["sd_counts"] for r in rows]
        print(f"noise in ADC counts : {min(sds):.2f} .. {max(sds):.2f} sd  "
              f"(spread {max(sds)-min(sds):.2f})")
        mvs = [r["sd_mv"] for r in rows]
        print(f"input-referred      : {min(mvs):.1f} .. {max(mvs):.1f} mV sd  "
              f"({max(mvs)/max(min(mvs), 1e-9):.0f}x across the range)")
        print()
        if (max(sds) - min(sds)) < 1.0:
            print("Counts are near-constant across sensitivity -> the noise floor is")
            print("dominated by the digitiser, not the analog front end. Input-referred")
            print("noise therefore scales directly with V/div, so the most sensitive")
            print("range is the one to use for small signals.")
        else:
            print("Counts vary with sensitivity -> the analog front end contributes;")
            print("the noise is not purely a digitiser artefact.")

        import json
        with open(r'C:\Fnirsi_Oscilloscope\host\noise_sweep.json', 'w') as f:
            json.dump(rows, f, indent=2)
        print("\nraw results -> host/noise_sweep.json")


if __name__ == '__main__':
    main()
