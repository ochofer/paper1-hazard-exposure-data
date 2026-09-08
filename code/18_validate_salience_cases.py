"""
VALIDATE THE SALIENCE EVIDENCE FILE, AND COMPUTE THE LAGS FROM IT

WHY THIS EXISTS
---------------
The gate 5 register of 7 September found exactly one number in the note that is
not traceable to any output file: the salience lag table, the six datable cases
whose recording delay correlates with how visible the underlying event was. It
is the finding the note leads on, after the hand verification that earns it.

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
    say()
    say("  A PHRASING CORRECTION FOR THE NOTE. The slow group has been described as")
    say("  'two to four and a half years'. The shortest of the four is "
        f"{slow.lag_days.min():,} days,")
    say(f"  which is {slow.lag_days.min()/365.25:.1f} years, not two. The accurate phrase is")
    say(f"  '{slow.lag_days.min()/365.25:.1f} to {slow.lag_days.max()/365.25:.1f} years', "
        f"or the days themselves.")
    say()
    say("  The two fast cases are the recent, heavily covered transactions: a")
    say("  statutory disclosure by a listed Japanese issuer, and a 1.9bn USD")
    say("  acquisition by a listed US utility. The four slow ones are older or reach")
    say("  the affected entity only through a perimeter. Salience note per case is in")
    say("  the evidence file.")
    say()
    say("  WHAT THIS IS NOT. Six cases cannot establish a correlation. The claim the")
    say("  note makes is that the lag is not a constant, which one fast case and one")
    say("  slow case would establish, and that its variation lines up with salience,")
    say("  which is offered as the reading of six hand-checked cases and labelled as")
    say("  such. An offset cannot fix a lag that is not constant, and that is the")
    say("  consequence that matters.")

    ev.drop(columns=["k", "t", "r"]).to_csv(
        os.path.join(OUT, "salience_lag.csv"), index=False)
    _release.write_provenance(
        OUT, "18_salience_lag",
        {"evidence": EVIDENCE, "verdicts": SAMPLE},
        extra={"rule": "lag = transaction date to first day of the month of the "
                       "first GEM release carrying the change",
               "n_cases": len(ev),
               "fast_threshold_days": 120,
               "n_fast": len(fast), "n_slow": len(slow),
               "lag_days": {str(r['case']): int(r['lag_days']) for _, r in ev.iterrows()}})
    say()
    say(f"  written to {os.path.abspath(OUT)}")
    with open(os.path.join(OUT, "salience_lag.txt"), "w") as fh:
        fh.write("\n".join(_lines) + "\n")


if __name__ == "__main__":
    main()
