"""
TASK 1.2: DOES THE BUILD-OUT SHARE DECAY, AND DOES RESTATEMENT STAY FLAT?

WHY THIS EXISTS
---------------
Task 1.1 decomposed one vintage pair, March 2025 against August 2026, and found
64% build-out, 20% restatement, 16% methodology change. That answers Carlo's age
objection once. It does not answer it as a trend.

The objection in its strongest form is that a young database is mostly adding
coverage, and that this says nothing about mature data. The decisive reply is
not an argument, it is a curve. If the build-out share falls across successive
releases while the restatement share stays flat, then the part of the problem
that persists has been separated from the part that resolves itself, and the
note can say when the dataset becomes usable as a panel.

PRE-COMMITTED PREDICTION, written before this script was run
-------------------------------------------------------------
    Build-out share:                DECLINING across the sequence
    Restatement share:              FLAT or rising
    Methodology share:              SPIKES at specific releases, not a trend

If build-out does not decline, say so. Eighteen months may be too short a window
to see it, which is a limitation rather than a contradiction, and reporting a
flat curve honestly is worth more than not looking.

ONE PREDICTION IS ALREADY ALMOST CERTAIN, AND IT IS THE POINT
---------------------------------------------------------------
The `Share Imputed?` column first appears in the DECEMBER 2025 release. It is
absent from November 2025 and every release before it. So share imputation was
introduced in exactly one release transition, and the November to December 2025
pair should show a methodology spike that no other pair shows.

That is the note's cleanest single exhibit. A user diffing those two releases
sees ownership percentages appear across thousands of relationships on one date,
with no announcement, and would read it as GEM having done a large research
push. It is a rule change.

A HONEST LIMITATION IN THE METHOD
----------------------------------
Before December 2025 there is no imputation flag, so for those pairs a blank
that becomes a number cannot be attributed to either research or imputation.
Those are reported in a separate "unattributable" bucket rather than being
silently counted as build-out, which would understate methodology in exactly the
period where we cannot see it.

RUN
    python 07_decay_curves.py

Writes: outputs/decay_curves.csv
        outputs/decay_curves.txt
"""

import os
import re
import glob
import datetime
import warnings

import pandas as pd

# Release resolution is pinned in _release.py, not matched against whatever is
# in the data folder. See that module's docstring for why.
import _release


warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def release_date(name):
    """Parse the release month out of the filename. Returns None if absent."""
    m = re.search(r"(" + "|".join(MONTHS) + r")[-_](\d{4})", name)
    if not m:
        return None
    return datetime.date(int(m.group(2)), MONTHS[m.group(1)], 1)


def as_num(x):
    try:
        return float(str(x).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def load(path):
    """Return (edges, imputed_set, has_flag, schema) for one release, or None.

    The entity table is read only to record its schema. Column names are NOT
    stable across releases: July 2025 V2 calls the key `GEM Entity ID` where
    every other release calls it `Entity ID`. That is itself a finding, so the
    loader records schema rather than assuming it.
    """
    xl = pd.ExcelFile(path)
    if "Entity Ownership" not in xl.sheet_names:
        return None
    eo = pd.read_excel(xl, sheet_name="Entity Ownership", dtype=str).fillna("")
    has_flag = "Share Imputed?" in eo.columns

    schema = {"sheets": len(xl.sheet_names),
              "entity_key": None,
              "ownership_cols": len(eo.columns)}
    if "All Entities" in xl.sheet_names:
        ae = pd.read_excel(xl, sheet_name="All Entities", dtype=str, nrows=1)
        for cand in ("Entity ID", "GEM Entity ID"):
            if cand in ae.columns:
                schema["entity_key"] = cand
                break

    # Access columns BY NAME, never by position. December 2025 inserts a
    # "Last Review Date" column at index 6, which shifts "Share Imputed?" from
    # 6 to 7. An earlier version of this script read index 6 and silently
    # classified 3,860 imputed values as new research. That failure mode is
    # precisely what the note is about, so it would be careless to reproduce it.
    subj = eo["Subject Entity ID"].astype(str).str.strip()
    party = eo["Interested Party ID"].astype(str).str.strip()
    share = eo["% Share of Ownership"].astype(str).str.strip()
    flag = (eo["Share Imputed?"].astype(str).str.strip() if has_flag
            else pd.Series([""] * len(eo)))

    edges, imputed = {}, set()
    for sj, pt, sh, fl in zip(subj, party, share, flag):
        k = (sj, pt)
        edges[k] = sh
        if fl == "imputed value":
            imputed.add(k)
    schema["has_last_review_date"] = "Last Review Date" in eo.columns
    return edges, imputed, has_flag, schema


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    # -- pick one file per release month, preferring V2 where a month was
    # reissued, since V2 is the corrected version of that month.
    #
    # As of 22 August 2026 there is exactly ONE file per release month except
    # July 2025 and May 2026, which shipped V1 and V2. The three duplicate
    # August 2026 files that previously sat here were reduced to one, keeping
    # the copy carrying `newest_update` under GEM's canonical filename.
    best = {}
    for f in glob.glob(os.path.join(DATA, "*.xlsx")):
        b = os.path.basename(f)
        d = release_date(b)
        if d is None:
            continue
        # "Prefer V2" is CORRECT for July 2025 and May 2026, the two months
        # GEM reissued with a corrected file, and WRONG for August 2026,
        # whose V2_External reissue is not the pinned endpoint. So the
        # exception is named rather than the rule rewritten.
        pin = _release.MONTH_PIN.get((d.year, d.month))
        if pin is not None:
            if b != pin:
                continue
            best[d] = (99, f)
            continue
        rank = 2 if "V2" in b else 1
        if d not in best or rank > best[d][0]:
            best[d] = (rank, f)
    seq = [(d, best[d][1]) for d in sorted(best)]
    _release.write_provenance(
        OUT, '07_decay_curves',
        {f'release_{d:%Y-%m}': p for d, p in seq})

    say("TASK 1.2  DECAY CURVES ACROSS CONSECUTIVE GEM RELEASES")
    say("  pre-committed prediction: build-out declining, restatement flat,")
    say("  methodology spiking at specific releases rather than trending")
    say()
    say(f"  {len(seq)} releases found:")
    for d, f in seq:
        say(f"    {d.strftime('%Y-%m')}  {os.path.basename(f)[:58]}")
    say()

    remap_f = glob.glob(os.path.join(DATA, "*entity IDs to map*.xlsx"))
    DEDUP = set()
    if remap_f:
        mp = pd.read_excel(remap_f[0], sheet_name="data", dtype=str).fillna("")
        DEDUP = {v.strip() for v in mp["ID to be replaced"] if v.strip()}
    say(f"  deduplication ground truth: {len(DEDUP):,} entity IDs "
        "(cumulative, so it over-attributes in early pairs)")
    say()

    prev = None
    prev_d = None
    out = []
    schemas = []
    for d, f in seq:
        cur = load(f)
        if cur is None:
            say(f"  {d.strftime('%Y-%m')}: no Entity Ownership sheet, skipped "
                "(this is the June 2024 entity-only release)")
            continue
        schemas.append({"release": d.strftime("%Y-%m"), **cur[3]})
        if prev is None:
            prev, prev_d = cur, d
            continue

        A, _, _, _ = prev
        B, IMP, HAS, _ = cur

        # FLAG-BLIND vs FLAG-AWARE, and this is not cosmetic.
        #
        # The `Share Imputed?` flag first appears in December 2025. Before that,
        # changes that are actually imputation get classified as build-out or
        # restatement, because nothing marks them. From December 2025 the same
        # changes are classified as methodology. So the CLASSIFICATION RULE
        # changes in the middle of the series.
        #
        # An earlier version of this script split the pairs at n // 2 to test
        # the build-out trend. That split landed exactly on the flag boundary:
        # all six early pairs flag-absent, all six late pairs flag-present.
        # Build-out share was therefore mechanically lower in the second half
        # whether or not a real trend existed, and the verdict could not be read
        # as evidence for the prediction. Caught by the Project A scaffolding and
        # blocking tests chat on 22 August.
        #
        # The fix: compute every pair BOTH ways. The blind pass applies the
        # pre-December rule throughout, so the trend test is comparable across
        # the whole series. The aware pass is the richer view and is reported
        # separately. The headline trend comes from the blind series.
        row = {}
        for use_flag in (False, True):
            HAS_eff = HAS and use_flag
            build = rest = meth = unattr = 0
            for k in set(B) - set(A):
                build += 1
            for k in set(A) - set(B):
                if k[0] in DEDUP or k[1] in DEDUP:
                    meth += 1
                else:
                    rest += 1
            for k in set(A) & set(B):
                a, b = as_num(A[k]), as_num(B[k])
                if a is None and b is not None:
                    if not HAS_eff:
                        unattr += 1      # cannot tell research from imputation
                    elif k in IMP:
                        meth += 1
                    else:
                        build += 1
                    continue
                if a is None or b is None:
                    continue
                if abs(a - b) <= 0.06:
                    continue
                if HAS_eff and k in IMP:
                    meth += 1
                else:
                    rest += 1

            t = build + rest + meth + unattr
            sfx = "" if use_flag else "_blind"
            row[f"changed_edges{sfx}"] = t
            if t:
                row[f"build_pct{sfx}"] = round(build / t * 100, 1)
                row[f"restate_pct{sfx}"] = round(rest / t * 100, 1)
                row[f"method_pct{sfx}"] = round(meth / t * 100, 1)
                row[f"unattr_pct{sfx}"] = round(unattr / t * 100, 1)

        tot = row["changed_edges"]
        if tot == 0:
            # Two consecutive releases with identical ownership edges. Worth
            # reporting rather than swallowing: it means GEM reissued a file
            # without changing the ownership layer.
            say(f"  {prev_d.strftime('%Y-%m')} to {d.strftime('%Y-%m')}: "
                "ZERO ownership change, releases are identical on this layer")
            prev, prev_d = cur, d
            continue
        out.append({
            "from": prev_d.strftime("%Y-%m"),
            "to": d.strftime("%Y-%m"),
            "months": (d.year - prev_d.year) * 12 + d.month - prev_d.month,
            "imputation_flag_present": HAS,
            **row,
        })
        prev, prev_d = cur, d

    df = pd.DataFrame(out)
    say("PER-PAIR DECOMPOSITION, FLAG-BLIND, one classification rule throughout")
    say("  This is the series the trend verdict uses. The flag-aware series is")
    say("  richer but is not comparable across December 2025, so it is reported")
    say("  separately below.")
    say(f"  {'pair':<18}{'mth':>4}{'edges':>8}{'build':>8}{'restate':>9}"
        f"{'method':>8}{'unattr':>8}")
    for r in df.itertuples(index=False):
        say(f"  {r[0]+' to '+r[1]:<18}{r.months:>4}{r.changed_edges_blind:>8,}{r.build_pct_blind:>7.1f}%"
            f"{r.restate_pct_blind:>8.1f}%{r.method_pct_blind:>7.1f}%"
            f"{r.unattr_pct_blind:>7.1f}%")
    say()

    # -- normalise for gap length, since pairs are not equally spaced --------
    say("PER-MONTH RATES, because the gaps are uneven")
    say(f"  {'pair':<18}{'build/mth':>11}{'restate/mth':>13}")
    # NAMED access. Positional indices broke here once already: adding
    # `imputation_flag_present` shifted every column and the arithmetic silently
    # started reading a boolean as an edge count. Same failure mode this script
    # documents in GEM's own data.
    for r in df.itertuples(index=False):
        say(f"  {r[0] + ' to ' + r[1]:<18}"
            f"{r.changed_edges_blind * r.build_pct_blind / 100 / r.months:>11,.0f}"
            f"{r.changed_edges_blind * r.restate_pct_blind / 100 / r.months:>13,.0f}")
    say()

    # -- verdict against the pre-commitment ---------------------------------
    say("VERDICT AGAINST THE PRE-COMMITTED PREDICTION")
    n = len(df)
    if n >= 4:
        h1, h2 = df.iloc[:n // 2], df.iloc[n // 2:]
        say("  FLAG-BLIND, comparable across the whole series:")
        say(f"    build-out share:   first half {h1['build_pct_blind'].mean():.1f}%  "
            f"second half {h2['build_pct_blind'].mean():.1f}%")
        say(f"    restatement share: first half {h1['restate_pct_blind'].mean():.1f}%  "
            f"second half {h2['restate_pct_blind'].mean():.1f}%")
        say(f"    methodology share: first half {h1['method_pct_blind'].mean():.1f}%  "
            f"second half {h2['method_pct_blind'].mean():.1f}%")
        say()
        say("  flag-aware, for contrast only. NOT a valid trend test, because the")
        say("  flag arrives in Dec 2025 and the split lands on that boundary:")
        say(f"    build-out share:   first half {h1['build_pct'].mean():.1f}%  "
            f"second half {h2['build_pct'].mean():.1f}%")
        say(f"    methodology share: first half {h1['method_pct'].mean():.1f}%  "
            f"second half {h2['method_pct'].mean():.1f}%")
        say()
        say()
        if h2["build_pct_blind"].mean() < h1["build_pct_blind"].mean():
            say("  Build-out share DECLINED as predicted.")
        else:
            say("  Build-out share did NOT decline. Report this plainly. Eighteen")
            say("  months may be too short a window, which is a limitation and")
            say("  not a contradiction.")
        # The pre-commitment was "flat OR rising", so a rise is a confirmation
        # rather than a surprise. An earlier version of this check tested only
        # for flatness and reported a rise as a failure, which was a bug in the
        # test rather than in the prediction.
        delta = h2["restate_pct_blind"].mean() - h1["restate_pct_blind"].mean()
        if delta >= -5:
            say(f"  Restatement share is flat or rising ({delta:+.1f} points), "
                "as predicted.")
        else:
            say(f"  Restatement share FELL by {-delta:.1f} points, against the "
                "prediction. Investigate before writing.")

        # SENSITIVITY. Even flag-blind, one pair dominates. November to December
        # 2025 is 96.4% unattributable under the blind rule, because that is
        # where thousands of blanks were filled and the blind rule cannot say by
        # what. And build-out correlates with gap length, so the three two-month
        # pairs pull upward. Both are reported rather than argued away.
        say()
        say("  SENSITIVITY, flag-blind throughout")
        d2 = df[df["to"] != "2025-12"]
        n2 = len(d2); a2, b2 = d2.iloc[:n2 // 2], d2.iloc[n2 // 2:]
        say(f"    excluding the Nov-Dec 2025 pair: build {a2['build_pct_blind'].mean():.1f}% "
            f"to {b2['build_pct_blind'].mean():.1f}%")
        d3 = df[df["months"] == 1]
        n3 = len(d3); a3, b3 = d3.iloc[:n3 // 2], d3.iloc[n3 // 2:]
        say(f"    one-month pairs only, n={n3}: build {a3['build_pct_blind'].mean():.1f}% "
            f"to {b3['build_pct_blind'].mean():.1f}%")
        d4 = d3[d3["to"] != "2025-12"]
        n4 = len(d4); a4, b4 = d4.iloc[:n4 // 2], d4.iloc[n4 // 2:]
        say(f"    one-month pairs, Nov-Dec excluded, n={n4}: build "
            f"{a4['build_pct_blind'].mean():.1f}% to {b4['build_pct_blind'].mean():.1f}%")
        say(f"    correlation of build-out share with gap length: "
            f"{df['build_pct_blind'].corr(df['months']):+.2f}")
        say("    Report whichever of these the note quotes, and say which it is.")

    say()
    say("METHODOLOGY SPIKES, the datable rule changes")
    top = df.nlargest(3, "method_pct")   # flag-aware, which is where spikes show
    for r in top.itertuples(index=False):
        say(f"  {r[0]} to {r[1]}: methodology {r.method_pct:.1f}% of change "
            f"({int(r.changed_edges*r.method_pct/100):,} edges)")
    say()
    say("  The imputation flag first appears in the December 2025 release, so a")
    say("  spike on the pair ending 2025-12 is the introduction of the 100/n")
    say("  rule, dated to a single release and announced nowhere.")

    # Schema drift is a finding in its own right: a user diffing two releases
    # can have their join silently break on a renamed key.
    say()
    say("SCHEMA DRIFT ACROSS RELEASES")
    sdf = pd.DataFrame(schemas)
    say(f"  {'release':<10}{'sheets':>8}{'own cols':>10}  {'entity key':<14} extras")
    for r in sdf.itertuples(index=False):
        say(f"  {r[0]:<10}{r[1]:>8}{r[3]:>10}  {r[2]:<14} "
            f"LastReviewDate={r[4]}")
    say()
    say(f"  distinct sheet counts   : {sorted(sdf['sheets'].unique())}")
    say(f"  distinct entity keys    : {sorted(x for x in sdf['entity_key'].unique() if x)}")
    say(f"  distinct ownership widths: {sorted(sdf['ownership_cols'].unique())}")
    sdf.to_csv(os.path.join(OUT, "schema_drift.csv"), index=False)

    df.to_csv(os.path.join(OUT, "decay_curves.csv"), index=False)
    with open(os.path.join(OUT, "decay_curves.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    say()
    say(f"written to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
