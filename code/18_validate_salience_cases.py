"""
VALIDATE THE SALIENCE EVIDENCE FILE, AND COMPUTE THE LAGS FROM IT

WHY THIS EXISTS
---------------
The gate 5 register of 7 September found exactly one number in the note that is
not traceable to any output file: the lag table, the six datable cases and the
delay between each transaction and the first release carrying it.

It cannot be computed. The transaction dates come from exchange filings, company
press releases and EDINET, read by hand. Presenting a hand-verified table as a
script output would dress up human work as computation, which is a version of
what the note criticises elsewhere.

So the split, agreed on 7 September: the dates and sources are a CURATED INPUT,
`evidence/salience_lag_cases.csv`, checked into the repository as evidence. The
arithmetic over them is computed here, and this script also refuses to let the
evidence drift away from the verified sample.

WHAT IT CHECKS
--------------
1. Every case in the evidence file exists in event_validation_sample.csv, matched
   on subject_id AND party_id, never on case number. Case numbers are positions
   in a draw, not identities; restoring verdicts by case number onto different
   companies has already happened twice in this project.
2. The verdict recorded in the evidence file matches the verified sample.
3. The evidence file contains exactly the cases whose verdict is REAL or REAL BUT
   MISDATED, no more and no fewer, so a case cannot be quietly added or dropped.
4. Where the file records a newest_update stamp, it matches the sample.

WHAT IT COMPUTES
----------------
The lag, on one uniform rule stated in the output: from the transaction date to
the FIRST DAY OF THE MONTH of the first GEM release carrying the change. That is
the delay a researcher differencing vintages would actually experience. Where a
newest_update stamp exists it is reported beside the lag as an independent
cross-check, not substituted for it.

Added 19 November 2026, after the results were known: what the sampling frame fixes.
The cases are edges that differ between the March 2025 and the August 2026
releases, so a change absent from March 2025 cannot be carried before the next
release held, May 2025, and a transaction inside the window cannot be carried
after August 2026. For each case the script prints the first release that could
have carried the change (May 2025 for a transaction before March 2025, the first
release after the transaction's month otherwise), the days from that release
to the carrying one, and the carrying release's position in the sequence of
releases from that first one.

Run:  python 18_validate_salience_cases.py
Out:  outputs/salience_lag.txt
      outputs/salience_lag.csv
      outputs/RUN_PROVENANCE_18_salience_lag.json
"""

import os
import sys

import pandas as pd

import _release

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
EVIDENCE = os.path.join(HERE, "..", "evidence", "salience_lag_cases.csv")
SAMPLE = os.path.join(OUT, "event_validation_sample.csv")

REAL_VERDICTS = {"REAL", "REAL BUT MISDATED"}

# The releases held, by month, as outputs/decay_curves.txt lists them, and the
# month of the earlier release of the pair the cases were drawn from.
RELEASES_HELD = ["2025-03", "2025-05", "2025-07", "2025-08", "2025-09", "2025-10",
                 "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-05",
                 "2026-07", "2026-08"]
BASE_RELEASE = "2025-03"


def first_release_that_could_carry(t):
    """The first release after BASE_RELEASE and after the transaction's month."""
    m = t.strftime("%Y-%m")
    for r in RELEASES_HELD:
        if r > BASE_RELEASE and r > m:
            return r
    return None

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def main():
    ev = pd.read_csv(EVIDENCE, dtype=str).fillna("")
    sm = pd.read_csv(SAMPLE, dtype=str).fillna("")

    say("SALIENCE LAG  CURATED EVIDENCE, VALIDATED AND MEASURED")
    say("  evidence/salience_lag_cases.csv is a hand-verified INPUT, not an output.")
    say("  Transaction dates come from exchange filings, company press releases and")
    say("  EDINET. This script validates it against the verified sample and computes")
    say("  the arithmetic over it.")
    say()

    # ---- 1 to 4, the guards ------------------------------------------------
    sm["k"] = sm.subject_id.str.strip() + "|" + sm.party_id.str.strip()
    ev["k"] = ev.subject_id.str.strip() + "|" + ev.party_id.str.strip()
    smk = dict(zip(sm.k, sm.verdict.str.strip().str.upper()))
    smu = dict(zip(sm.k, sm.newest_update.str.strip()))

    problems = []
    for _, r in ev.iterrows():
        if r.k not in smk:
            problems.append(f"case {r['case']} ({r['subject_name']} / {r['party_name']}) "
                            f"is not in the verified sample on subject_id + party_id")
            continue
        if smk[r.k] != r.verdict.strip().upper():
            problems.append(f"case {r['case']} verdict '{r['verdict']}' does not match "
                            f"the sample's '{smk[r.k]}'")
        stamp = r["gem_newest_update_stamp"].strip()
        if stamp and smu.get(r.k, ""):
            if not smu[r.k].startswith(stamp):
                problems.append(f"case {r['case']} stamp '{stamp}' does not match the "
                                f"sample's '{smu[r.k]}'")

    expected = {k for k, v in smk.items() if v in REAL_VERDICTS}
    got = set(ev.k)
    for k in expected - got:
        row = sm[sm.k == k].iloc[0]
        problems.append(f"MISSING from the evidence file: {row['subject_name']} / "
                        f"{row['party_name']}, verdict {smk[k]}")
    for k in got - expected:
        problems.append(f"EXTRA in the evidence file, not a real transaction in the "
                        f"sample: {k}")

    say(f"VALIDATION against {os.path.basename(SAMPLE)}, matched on subject_id + party_id")
    say(f"  cases in the evidence file                {len(ev)}")
    say(f"  cases in the sample verdicted REAL or REAL BUT MISDATED   {len(expected)}")
    if problems:
        say()
        for p in problems:
            say(f"  FAIL  {p}")
        with open(os.path.join(OUT, "salience_lag.txt"), "w") as fh:
            fh.write("\n".join(_lines) + "\n")
        sys.exit("validation failed, see outputs/salience_lag.txt")
    say("  all cases present, matched and verdict-consistent. No case added or dropped.")

    # ---- the arithmetic ----------------------------------------------------
    ev["t"] = pd.to_datetime(ev.transaction_date)
    ev["r"] = pd.to_datetime(ev.gem_release_date_used)
    ev["lag_days"] = (ev.r - ev.t).dt.days
    # Added 19 November 2026: the frame's floor or ceiling and the lag counted
    # from the first release that could have carried the change.
    ev["first_release_that_could_carry"] = [first_release_that_could_carry(t) for t in ev.t]
    first_dates = pd.to_datetime(ev.first_release_that_could_carry + "-01")
    ev["days_after_first_possible"] = (ev.r - first_dates).dt.days
    ev["release_position_from_first_possible"] = [
        RELEASES_HELD.index(c) - RELEASES_HELD.index(f) + 1
        for c, f in zip(ev.gem_first_release_carrying_change, ev.first_release_that_could_carry)]
    base_date = pd.Timestamp(BASE_RELEASE + "-01")
    last_date = pd.Timestamp(RELEASES_HELD[-1] + "-01")
    ev["before_first_release"] = ev.t < base_date
    ev["lag_floor_or_ceiling_days"] = [
        (fd - t).days if t < base_date else (last_date - t).days
        for t, fd in zip(ev.t, first_dates)]
    ev = ev.sort_values("lag_days").reset_index(drop=True)

    say()
    say("=" * 78)
    say("THE LAG. Transaction date to the first day of the month of the first GEM")
    say("release carrying the change. One uniform rule, stated because the choice")
    say("of endpoint moves the number.")
    say()
    say(f"  {'case':<5}{'subject':<34}{'transaction':<13}{'release':<9}{'lag days':>9}  stamp")
    for _, r in ev.iterrows():
        say(f"  {r['case']:<5}{r['subject_name'][:32]:<34}{r['transaction_date']:<13}"
            f"{r['gem_first_release_carrying_change']:<9}{r['lag_days']:>9,}  "
            f"{r['gem_newest_update_stamp'] or '-'}")

    fast = ev[ev.lag_days <= 120]
    slow = ev[ev.lag_days > 120]
    say()
    say(f"  fast, within four months: {len(fast)} cases, "
        f"{fast.lag_days.min():,} to {fast.lag_days.max():,} days")
    say(f"  slow, beyond four months: {len(slow)} cases, "
        f"{slow.lag_days.min():,} to {slow.lag_days.max():,} days "
        f"({slow.lag_days.min()/365.25:.1f} to {slow.lag_days.max()/365.25:.1f} years)")

    # Added 19 November 2026, after the results were known. The frame fixes the
    # groups, as the figures below show.
    say()
    say("=" * 78)
    say("WHAT THE FRAME FIXES, added 19 November 2026. A change sampled from the")
    say("difference between March 2025 and August 2026 cannot be carried before May")
    say("2025, the first release after March, nor after August 2026.")
    say()
    say(f"  {'case':<5}{'transaction':<13}{'frame':<17}{'first release that could carry':<32}"
        f"{'carried':<9}{'days after it':>14}{'position':>10}")
    for _, r in ev.iterrows():
        frame = (f"at least {r['lag_floor_or_ceiling_days']:,}" if r["before_first_release"]
                 else f"at most {r['lag_floor_or_ceiling_days']:,}")
        say(f"  {r['case']:<5}{r['transaction_date']:<13}{frame:<17}"
            f"{r['first_release_that_could_carry']:<32}{r['gem_first_release_carrying_change']:<9}"
            f"{r['days_after_first_possible']:>14,}{r['release_position_from_first_possible']:>10}")
    pre = ev[ev.before_first_release]
    inw = ev[~ev.before_first_release]
    ordinal = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth"}
    months = sorted(set(pre.gem_first_release_carrying_change))
    month_names = " and ".join(pd.Timestamp(m + "-01").strftime("%B %Y") for m in months)
    say()
    say(f"  the {len(pre)} cases with transactions before March 2025, "
        f"{pd.Timestamp(pre.t.min()).strftime('%B %Y')} to {pd.Timestamp(pre.t.max()).strftime('%B %Y')}: "
        f"carried {pre.days_after_first_possible.min():,} to "
        f"{pre.days_after_first_possible.max():,} days after the first release that")
    say(f"  could have carried them, {pd.Timestamp(pre.first_release_that_could_carry.iloc[0] + '-01').strftime('%B %Y')}, "
        f"in {month_names}; their lags could not be under "
        f"{pre.lag_floor_or_ceiling_days.min():,} to {pre.lag_floor_or_ceiling_days.max():,} days")
    pos = " and ".join(ordinal.get(int(p), str(p))
                       for p in sorted(inw.release_position_from_first_possible))
    ceil = " and ".join(f"{c:,}" for c in sorted(inw.lag_floor_or_ceiling_days))
    say(f"  the {len(inw)} cases with transactions inside the window: carried in the {pos} "
        f"release after the transaction; their lags could not exceed {ceil} days")
    say()
    say("  Six cases cannot establish a correlation, and every case from before the")
    say("  first release is also a less visible one, so whether the lag varies with")
    say("  how visible the event was cannot be told from them.")

    ev.drop(columns=["k", "t", "r", "before_first_release"]).to_csv(
        os.path.join(OUT, "salience_lag.csv"), index=False)
    _release.write_provenance(
        OUT, "18_salience_lag",
        {"evidence": EVIDENCE, "verdicts": SAMPLE},
        extra={"rule": "lag = transaction date to first day of the month of the "
                       "first GEM release carrying the change",
               "n_cases": len(ev),
               "fast_threshold_days": 120,
               "n_fast": len(fast), "n_slow": len(slow),
               "releases_held": RELEASES_HELD, "base_release": BASE_RELEASE,
               "days_after_first_possible": {str(r['case']): int(r['days_after_first_possible'])
                                             for _, r in ev.iterrows()},
               "lag_days": {str(r['case']): int(r['lag_days']) for _, r in ev.iterrows()}})
    say()
    say(f"  written to {os.path.relpath(OUT, os.path.join(HERE, '..'))}")
    with open(os.path.join(OUT, "salience_lag.txt"), "w") as fh:
        fh.write("\n".join(_lines) + "\n")


if __name__ == "__main__":
    main()
