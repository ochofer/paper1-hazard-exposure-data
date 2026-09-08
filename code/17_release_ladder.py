"""
BOTH RELEASES SIDE BY SIDE: THE V-REVISED R LADDER, COMPUTED NOT TRANSCRIBED

WHY THIS EXISTS
---------------
The ruling of 6 September requires a section reporting both August 2026 releases
side by side, with R and the worst case for each in the same table as the
pre-committed 25% bar. The gate 5 register of 7 September found that three of
those numbers, R on V2 and the worst-case pair 25.2% and 24.3%, existed only in
RELEASE_COMPARISON_outputs_2026-09-02.txt, a hand-assembled bundle rather than a
script output, with no provenance record behind them. A headline of the section
cannot rest on a file somebody typed.

WHAT IT DOES
------------
Everything from source, nothing carried over:

1. V is DERIVED from the verdicts in event_validation_sample.csv rather than
   hard-coded. Two readings, because the pre-committed rule predates the
   REAL BUT MISDATED category and does not say which side those fall on:
     in-window   REAL and in window only
     strict      any real datable transaction, whenever it happened
   Wilson score intervals at 95% for each, because at n = 19 a point estimate
   of V overstates what the sample supports and the note must never quote V
   without its interval.

2. The three buckets are recomputed for EACH release by running script 06's own
   code path, once per release, into a scratch directory. Nothing is
   reimplemented here and nothing is read out of a summary.

   Reading both releases is NOT a repin. The pin governs the note's endpoint and
   remains V1; the ruling separately requires V2 to be reported beside it, and
   _release.RELEASES carries the V2 key for exactly this purpose.

3. The ladder: R with the restatement bucket revised down by V at each reading,
   denominator held at total apparent change, which is the construction task 1.3
   pre-committed to.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not choose between the readings and it does not decide which release the
note leads with. Both are settled: the endpoint is V1, and both columns are
reported including the worst case that fails on V2. This script exists so those
numbers have a provenance record, not to reopen the decision.

Run:  python 17_release_ladder.py
Out:  outputs/release_ladder.txt
      outputs/RUN_PROVENANCE_17_release_ladder.json
"""

import importlib.util
import math
import os
import shutil
import tempfile

import pandas as pd

import _release

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
OUT = os.path.join(HERE, "..", "outputs")
SAMPLE = os.path.join(OUT, "event_validation_sample.csv")

GO_THRESHOLD = 0.25
Z = 1.96

RELEASES = [("V1 (PINNED)", "August 2026"), ("V2_External", "August 2026 V2")]

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def wilson(k, n, z=Z):
    """Wilson score interval. At n = 19 the normal approximation is not usable
    and the note must not quote V without an interval."""
    if n == 0:
        return (float("nan"), float("nan"))
    d = n + z * z
    centre = (k + z * z / 2) / d
    half = z / d * math.sqrt(k * (n - k) / n + z * z / 4)
    return max(0.0, centre - half), min(1.0, centre + half)


def load_06():
    p = os.path.join(HERE, "06_change_decomposition.py")
    spec = importlib.util.spec_from_file_location("change_decomposition", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def buckets_for(release_key, tmp):
    """Run script 06's own code path against one release, return bucket counts."""
    six = load_06()
    six.DATA = DATA
    six.OUT = tmp
    six.NEW_KEY = release_key
    six.main()
    e = pd.read_csv(os.path.join(tmp, "change_decomposition_edges.csv"), dtype=str)
    vc = e.bucket.value_counts()
    return {b: int(vc.get(b, 0)) for b in ("build-out", "restatement", "methodology")}


def main():
    s = pd.read_csv(SAMPLE, dtype=str).fillna("")
    v = s.verdict.str.strip().str.upper()
    n = len(s)
    in_window = int((v == "REAL").sum())
    misdated = int((v == "REAL BUT MISDATED").sum())
    strict = in_window + misdated

    say("BOTH RELEASES SIDE BY SIDE  THE V-REVISED R LADDER")
    say("  every number computed here; none transcribed from a summary")
    say()
    say("V, DERIVED FROM THE VERDICTS IN event_validation_sample.csv")
    say(f"  sample size                                        {n}")
    for lab, k in (("REAL and in window", in_window),
                   ("REAL BUT MISDATED", misdated),
                   ("NO EVENT", int((v == "NO EVENT").sum())),
                   ("UNCLEAR", int((v == "UNCLEAR").sum()))):
        say(f"    {lab:<48} {k}")
    say()
    readings = []
    for lab, k in (("in-window only", in_window), ("strict literal", strict)):
        lo, hi = wilson(k, n)
        say(f"  V, {lab:<20} {k}/{n} = {k/n:.3f}   95% Wilson {lo:.3f} to {hi:.3f}")
        readings.append((f"in-window V = {k/n:.3f}" if lab.startswith("in-window")
                         else f"strict V = {k/n:.3f}", k / n))
        if lab == "strict literal":
            readings.append((f"worst case, strict V at its 95% upper bound {hi:.3f}", hi))
    say()
    say("  Both intervals straddle a pre-committed branch boundary. At n = 19 the")
    say("  sample cannot separate the branches, and V is never quoted without its")
    say("  interval.")

    say()
    say("=" * 78)
    say("THE BUCKETS, RECOMPUTED PER RELEASE THROUGH SCRIPT 06'S OWN CODE PATH")
    tmp = tempfile.mkdtemp(prefix="ladder_")
    counts, files = {}, {}
    try:
        for label, key in RELEASES:
            counts[label] = buckets_for(key, tmp)
            files[label] = _release.resolve(key, DATA)
            b = counts[label]
            tot = sum(b.values())
            say(f"  {label:<14} {os.path.basename(files[label])}")
            say(f"  {'':<14} build-out {b['build-out']:>6,}   restatement {b['restatement']:>6,}"
                f"   methodology {b['methodology']:>6,}   total {tot:>7,}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    say()
    say("=" * 78)
    say(f"THE LADDER. R = (restatement + methodology) / total, restatement revised")
    say(f"down by V. Pre-committed GO bar {GO_THRESHOLD*100:.0f}%.")
    say()
    say(f"  {'reading':<46}{'V1 (PINNED)':>16}{'V2_External':>16}")
    rows = []
    for lab, vv in [("as published, V not applied", 0.0)] + readings:
        cells = []
        for rel, _ in RELEASES:
            b = counts[rel]
            tot = sum(b.values())
            r = (b["restatement"] * (1 - vv) + b["methodology"]) / tot
            cells.append(r)
        verdicts = ["clears" if c >= GO_THRESHOLD else "FAILS" for c in cells]
        say(f"  {lab:<46}{cells[0]*100:>9.1f}% {verdicts[0]:<6}{cells[1]*100:>9.1f}% {verdicts[1]:<6}")
        rows.append({"reading": lab, "V": round(vv, 4),
                     "R_V1": round(cells[0], 6), "R_V2": round(cells[1], 6),
                     "verdict_V1": verdicts[0], "verdict_V2": verdicts[1]})

    say()
    worst = rows[-1]
    say("  THE LINE THAT MATTERS. At the worst defensible reading the pre-committed")
    say(f"  decision {worst['verdict_V1']} on V1 at {worst['R_V1']*100:.1f}% and "
        f"{worst['verdict_V2']} on V2 at {worst['R_V2']*100:.1f}%.")
    say("  Both files are called August 2026 and neither is marked as a version.")
    say("  The endpoint is pinned to V1 because the 328-firm cross-section is itself")
    say("  a V1 artefact, never because V1 clears the bar.")

    pd.DataFrame(rows).to_csv(os.path.join(OUT, "release_ladder.csv"), index=False)
    _release.write_provenance(
        OUT, "17_release_ladder",
        {"old": _release.resolve("March 2025", DATA),
         "new_pinned": files["V1 (PINNED)"],
         "also_reported": files["V2_External"],
         "verdicts": SAMPLE},
        extra={"n_sample": n, "v_in_window": in_window, "v_strict": strict,
               "wilson_z": Z, "go_threshold": GO_THRESHOLD, "ladder": rows})
    say()
    say(f"  written to {os.path.abspath(OUT)}")
    with open(os.path.join(OUT, "release_ladder.txt"), "w") as fh:
        fh.write("\n".join(_lines) + "\n")


if __name__ == "__main__":
    main()
