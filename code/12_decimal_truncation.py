"""
TASK 1.1 SUPPLEMENT: HOW MUCH OF THE APPARENT SHARE MOVEMENT IS DECIMAL PRECISION?

WHY THIS EXISTS
---------------
GEM truncated the ownership file to one decimal place between March 2025 and
August 2026. A naive vintage diff reads every one of those truncations as an
ownership change.

The finding was originally computed as an ad-hoc snippet during task 1.3 and
recorded as "74.9% of all value changes". That number could not be reproduced
later: a like-for-like recomputation on 3 September 2026 returned 80.0% against
the pinned V1 endpoint and 78.5% against V2, and neither matched 74.9%. The
snippet's exact rule was never written down, so there is no way to tell whether
the gap is the release, a dedup difference, or a different definition of
"explained by rounding".

An unreproducible number cannot go in a public note. This script replaces it.
It is deliberately explicit about the two things the ad-hoc version left
implicit: how duplicate edge keys are handled, and what "explained by rounding"
means. It reports the answer under a strict and a broad reading so the
sensitivity to that definition is visible rather than buried in a choice.

WHAT IT MEASURES
----------------
1. The decimal-place distribution of the share column in each release. This is
   the underlying fact: 26.9% of March 2025 values need two decimals, and zero
   of the August values do, under either August file.

2. Of the edges carrying a numeric share in BOTH releases, how many changed at
   all, and of those, how many are explained by nothing more than the March
   value being rounded to one decimal place.

   STRICT: the March value has more than one decimal place AND rounding it to
   one decimal reproduces the August value exactly. This is the defensible
   reading and it is the one to quote.

   BROAD: strict, plus edges where the absolute change is smaller than half a
   unit in the last retained place (0.05) and so could not survive truncation
   either way. Reported to show the answer is not sensitive to the edge case.

3. How many changes the pre-committed 0.06 threshold in
   08_event_validation_sample.py suppresses, and how many survive into the
   restatement bucket. This is the check that R is unaffected: the truncated
   edges were already filtered before task 1.1 ran.

DEDUPLICATION, STATED BECAUSE IT MOVES THE ANSWER
-------------------------------------------------
An edge is keyed on (Subject Entity ID, Interested Party ID). A small number of
keys appear more than once in a release. The rule here is FIRST occurrence, and
the count of dropped duplicates is printed. Silently keeping all of them would
double-count; silently dropping them without saying so is how the original
number became unreproducible.

Run:  python 12_decimal_truncation.py
Out:  outputs/decimal_truncation.txt
      outputs/RUN_PROVENANCE_12_decimal_truncation.json
"""

import os

import pandas as pd

# Release resolution is pinned in _release.py, not matched against whatever is
# in the data folder. See that module's docstring for why.
import _release

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)

OLD_KEY = "March 2025"
NEW_KEY = "August 2026"          # PINNED to V1 on 3 Sep 2026
ALSO_REPORT = "August 2026 V2"   # reported alongside, never the default

SHARE = "% Share of Ownership"
SUBJ = "Subject Entity ID"
PARTY = "Interested Party ID"

# The pre-committed threshold in 08_event_validation_sample.py.
THRESHOLD = 0.06

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def decimals(v):
    """Number of significant decimal places in the value as WRITTEN.

    Trailing zeros do not count: "51.30" is one decimal place, because the
    question is how much precision the file actually carries, not how it was
    formatted. Returns None for anything not parseable as a number.
    """
    s = str(v).strip().rstrip("%").strip()
    if s in ("", "nan", "None"):
        return None
    try:
        float(s)
    except ValueError:
        return None
    if "." not in s:
        return 0
    return len(s.split(".")[1].rstrip("0"))


def load(path, label):
    df = pd.read_excel(path, sheet_name="Entity Ownership", dtype=str).fillna("")
    for c in (SUBJ, PARTY, SHARE):
        _release.require_col(df, c, f"Entity Ownership in {label}")
    df["k"] = df[SUBJ].str.strip() + "|" + df[PARTY].str.strip()
    df["raw"] = df[SHARE].astype(str).str.strip().str.rstrip("%").str.strip()
    n_all = len(df)
    df = df[df["raw"] != ""]
    n_num = len(df)
    before = len(df)
    df = df.drop_duplicates(subset="k", keep="first")
    dupes = before - len(df)
    say(f"  {label}")
    say(f"    rows {n_all:,} | carrying a share value {n_num:,} "
        f"| duplicate edge keys dropped {dupes:,}")
    dp = df["raw"].map(decimals)
    two_plus = int((dp >= 2).sum())
    parseable = int(dp.notna().sum())
    say(f"    values needing 2+ decimal places: {two_plus:,} of {parseable:,} "
        f"({100 * two_plus / max(parseable, 1):.1f}%)")
    return df.set_index("k")["raw"]


def compare(old, new, label):
    k = old.index.intersection(new.index)
    a_raw, b_raw = old.loc[k], new.loc[k]
    fa = pd.to_numeric(a_raw, errors="coerce")
    fb = pd.to_numeric(b_raw, errors="coerce")
    ok = fa.notna() & fb.notna()
    a_raw, b_raw, fa, fb = a_raw[ok], b_raw[ok], fa[ok], fb[ok]
    matched = len(fa)

    differs = fa.round(6) != fb.round(6)
    n_diff = int(differs.sum())

    old_dp = a_raw.map(decimals)
    strict = differs & (old_dp > 1) & (fa.round(1).round(6) == fb.round(6))
    broad = strict | (differs & ((fa - fb).abs() < 0.05))

    small = differs & ((fa - fb).abs() <= THRESHOLD)
    survives = differs & ~small

    say()
    say(f"  {label}")
    say(f"    edges with a numeric share in BOTH releases      {matched:>7,}")
    say(f"    value differs at all                             {n_diff:>7,}  "
        f"({100 * n_diff / max(matched, 1):.1f}% of matched)")
    say(f"    STRICT: explained by 1dp rounding alone          {int(strict.sum()):>7,}  "
        f"({100 * strict.sum() / max(n_diff, 1):.1f}% of all changes)")
    say(f"    BROAD:  strict, or below half the last place     {int(broad.sum()):>7,}  "
        f"({100 * broad.sum() / max(n_diff, 1):.1f}% of all changes)")
    say(f"    suppressed by the {THRESHOLD} threshold in 08         {int(small.sum()):>7,}  "
        f"({100 * small.sum() / max(n_diff, 1):.1f}% of all changes)")
    say(f"    survives into the restatement bucket             {int(survives.sum()):>7,}  "
        f"({100 * survives.sum() / max(n_diff, 1):.1f}% of all changes)")
    return {
        "matched_edges": matched,
        "changed": n_diff,
        "strict_rounding_only": int(strict.sum()),
        "broad_rounding_only": int(broad.sum()),
        "suppressed_by_threshold": int(small.sum()),
        "survives_as_restatement": int(survives.sum()),
    }


def main():
    old_f = _release.resolve(OLD_KEY, DATA)
    new_f = _release.resolve(NEW_KEY, DATA)
    alt_f = _release.resolve(ALSO_REPORT, DATA)

    say("TASK 1.1 SUPPLEMENT  DECIMAL-PRECISION TRUNCATION")
    say("  replaces the ad-hoc 74.9% figure, which could not be reproduced")
    say()
    say("DECIMAL PLACES CARRIED BY EACH RELEASE")
    old = load(old_f, f"{OLD_KEY}  ({os.path.basename(old_f)})")
    new = load(new_f, f"{NEW_KEY}  ({os.path.basename(new_f)})  PINNED")
    alt = load(alt_f, f"{ALSO_REPORT}  ({os.path.basename(alt_f)})  reported alongside")

    say()
    say("=" * 74)
    say("MATCHED EDGES: HOW MUCH OF THE MOVEMENT IS PRECISION AND NOTHING ELSE")
    res_v1 = compare(old, new, f"{OLD_KEY} against {NEW_KEY} (PINNED, quote this)")
    res_v2 = compare(old, alt, f"{OLD_KEY} against {ALSO_REPORT} (reported alongside)")

    say()
    say("=" * 74)
    say("WHAT THIS MEANS")
    pct = 100 * res_v1["strict_rounding_only"] / max(res_v1["changed"], 1)
    say(f"  {pct:.1f}% of all apparent share-value changes between the pinned")
    say("  vintages are a change in the file's decimal precision and nothing else.")
    say("  That is a formatting decision, not research, not a correction, and")
    say("  certainly not an ownership event.")
    say()
    say("  R IS UNAFFECTED. The 0.06 threshold in 08_event_validation_sample.py")
    say(f"  already suppressed {res_v1['suppressed_by_threshold']:,} of the "
        f"{res_v1['changed']:,} changes before task 1.1 ran, so the 36.0%")
    say("  figure never contained them. Anyone rerunning this with a tighter")
    say(f"  threshold will manufacture roughly {res_v1['strict_rounding_only']:,} spurious changes.")
    say()
    say("  DO NOT QUOTE 74.9%. It was an ad-hoc calculation with an unrecorded")
    say("  rule and it is not reproducible. Quote the STRICT figure above and")
    say("  cite this script.")

    path = os.path.join(OUT, "decimal_truncation.txt")
    with open(path, "w") as fh:
        fh.write("\n".join(_lines) + "\n")
    _release.write_provenance(
        OUT, "12_decimal_truncation",
        {"old": old_f, "new_pinned": new_f, "also_reported": alt_f},
        extra={"results_pinned": res_v1, "results_v2": res_v2,
               "threshold": THRESHOLD})
    say()
    say(f"  written to {os.path.abspath(OUT)}")
    with open(path, "w") as fh:
        fh.write("\n".join(_lines) + "\n")


if __name__ == "__main__":
    main()
