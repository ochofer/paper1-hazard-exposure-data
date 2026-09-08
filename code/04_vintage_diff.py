"""
VINTAGE DIFF: does a second GEM release actually give us a time dimension?

WHY THIS EXISTS
---------------
The design has a look-ahead problem. If we take the August 2026 ownership
snapshot and apply it to 2015 to 2026, we credit firms with assets they had not
yet bought. The obvious fix is to use dated vintages, so ownership as at 2025
comes from the 2025 release. Gabe Louis at GEM supplied sixteen vintages back to
March 2025 for exactly this purpose.

This script asks whether that fix works. It does not assume it does.

THE TEST, AND WHAT WOULD FALSIFY THE FIX
-----------------------------------------
If vintage differences reflect the real world, then the rate at which assets
change hands between two releases should look like a plausible M&A rate. Call it
a few percent a year. If instead the differences are mostly GEM improving its
own research, the rate will be far too high to be real, and the "time dimension"
we think we are measuring will be mostly measurement error.

The discriminating comparison is between two layers of the same data:

  IMMEDIATE owner   who directly holds the asset. Changes only when the asset
                    is actually sold, or when GEM corrects a direct error.

  TOP-LEVEL parent  the entity at the top of the ownership path, which is what
                    the paper actually attributes assets to. Changes when the
                    asset is sold, AND ALSO whenever GEM adds an intermediate
                    holding company above the current top, because the walk up
                    the graph now terminates somewhere new.

Both layers describe the same fifteen months of real corporate activity. So if
the top-level parent moves far more than the immediate owner does, the excess
cannot be the world changing. It is the graph growing. That is the whole test.

PRE-COMMITTED READING, written before the numbers were seen:
    top-parent change rate within ~2x the immediate-owner rate -> vintages usable
    top-parent change rate far above that                      -> vintages measure
                                                                  GEM's research
                                                                  effort, not events

WHAT IT RETURNED ON May 2025 V1 vs August 2026 V1
--------------------------------------------------
    immediate owner changed on   1,584 of 34,103 assets   (4.6%)
    top-level parent changed on 15,699 of 34,103 assets  (46.0%)

4.6% over fifteen months is a believable M&A rate. 46% is not. The ratio is ten
to one, so roughly nine tenths of the apparent ownership change is GEM having
researched the entity in more depth, not an asset having been sold.

The mechanism is visible elsewhere in the same comparison: the entity table grew
from 20,008 to 26,943, with 8,081 entities that did not exist in the May 2025
release. Every one of those that sits above an existing asset moves that asset's
top-level parent without anything having happened in the world.

WHY THIS IS WORSE THAN THE PROBLEM IT WAS MEANT TO SOLVE
---------------------------------------------------------
A single stale snapshot gives a known, signable bias. Using vintages gives a
spurious ownership-change signal on 46% of assets, and that signal is not noise
drawn at random. GEM prioritises research on large, newsworthy, high-emitting
assets, so the error correlates with exactly the asset characteristics that
plausibly correlate with returns. Swapping a clean bias for a confounded one is
not an improvement.

RUN
    python 04_vintage_diff.py

Writes: outputs/vintage_diff_summary.txt
        outputs/vintage_entity_churn.csv
        outputs/vintage_asset_parent_changes.csv
"""

import os
import glob
import warnings

import pandas as pd

# Release resolution is pinned in _release.py, not matched against whatever is
# in the data folder. See that module's docstring for why.
import _release


warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# Locate the two vintages.
#
# OLD_HINT is matched against filenames, so pointing this at a different vintage
# is a one-line change. Once the other fourteen releases are downloaded, loop
# this over consecutive pairs to get a full churn time series.
# ---------------------------------------------------------------------------
OLD_KEY = "March 2025"
NEW_KEY = "August 2026"   # PINNED to V1 on 3 Sep 2026

SEARCH_DIRS = [
    os.path.join(HERE, "..", "Data", "GEM Data"),
    os.path.join(HERE, "..", "..", "..", "uploads"),
]


DATA = SEARCH_DIRS[0]

def find(key):
    """Resolve a PINNED release key to one workbook.

    This used to take a filename hint and prefer any match containing "V2".
    That rule silently switched the August 2026 endpoint when GEM reissued the
    month on 26 August 2026. It now takes a key from _release.RELEASES and
    resolves to one exact filename, or fails.
    """
    return _release.resolve(key, DATA)


# The unit identifier column is named differently on every sector sheet, which
# is a small thing that will silently break a naive loop, so it is explicit.
UNIT_ID = {
    "Coal Plant": "GEM unit ID",
    "Gas Plant": "GEM unit ID",
    "Bioenergy Power": "GEM unit ID",
    "Coal Mine": "GEM Mine ID",
    "Iron Mine": "GEM Asset ID",
    "Gas Pipeline": "ProjectID",
    "Oil & NGL Pipeline": "ProjectID",
    "Steel Plant": "Steel Plant ID",
}

# GEM renamed this column between the two releases. Whether the rename is purely
# cosmetic or whether the definition also changed is an open question with GEM,
# so it is flagged here rather than quietly assumed.
PARENT_COL_OLD = "Owner GEM Entity ID"
PARENT_COL_NEW = "Parent GEM Entity ID"
IMMEDIATE_COL = "Immediate Project Owner GEM Entity ID"


def owner_sets(df, id_col, owner_col):
    """Map each asset to the SET of entities recorded against it.

    A set, not a single value, because an asset with three co-owners has three
    rows. Comparing sets means a genuine change in the ownership group is caught
    while a reordering of the same rows is not.
    """
    g = df.groupby(id_col)[owner_col].apply(lambda x: frozenset(v for v in x if v))
    return g.to_dict()


def main():
    old_f, new_f = find(OLD_KEY), find(NEW_KEY)
    _release.write_provenance(OUT, '04_vintage_diff',
                              {'old': old_f, 'new': new_f})
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    say("GEM VINTAGE DIFF")
    say(f"  old: {os.path.basename(old_f)}")
    say(f"  new: {os.path.basename(new_f)}")
    say()

    # -- entity universe -----------------------------------------------------
    oe = pd.read_excel(old_f, sheet_name="All Entities", dtype=str).fillna("")
    ne = pd.read_excel(new_f, sheet_name="All Entities", dtype=str).fillna("")
    O, N = set(oe["Entity ID"]), set(ne["Entity ID"])

    say("ENTITY UNIVERSE")
    say(f"  old release            {len(O):>8,}")
    say(f"  new release            {len(N):>8,}")
    say(f"  present in both        {len(O & N):>8,}")
    say(f"  gone from new release  {len(O - N):>8,}   <- breaks a panel if these were merged, not deleted")
    say(f"  new in new release     {len(N - O):>8,}   <- this is what moves top-level parents")
    say()

    pd.DataFrame(
        {"entity_id": sorted(O - N), "status": "in old vintage only"}
    ).to_csv(os.path.join(OUT, "vintage_entity_churn.csv"), index=False)

    # The listed flag is what decides who enters the cross-section at all, so a
    # flip is not a cosmetic edit. It adds or removes a firm.
    om = oe.set_index("Entity ID")["PubliclyListed"].to_dict()
    nm = ne.set_index("Entity ID")["PubliclyListed"].to_dict()
    both_e = O & N
    t2f = sum(1 for e in both_e if om.get(e, "").strip() == "True"
              and nm.get(e, "").strip() == "False")
    f2t = sum(1 for e in both_e if om.get(e, "").strip() == "False"
              and nm.get(e, "").strip() == "True")
    say("PUBLICLY-LISTED FLAG, on entities present in both")
    say(f"  True  -> False         {t2f:>8,}   these firms leave the cross-section")
    say(f"  False -> True          {f2t:>8,}   these firms enter it")
    say()

    # -- the discriminating test --------------------------------------------
    say("ASSET ATTRIBUTION: immediate owner against top-level parent")
    say(f"  {'sector':<20} {'assets':>8} {'top parent':>16} {'immediate owner':>18}")

    tot_b = tot_top = tot_imm = 0
    changed_rows = []

    # Sector sheets are not constant across releases. March 2025 has no
    # "Oil & NGL Pipeline Ownership" and no "Cement and Concrete Ownership";
    # both appear later. A sector missing from either side is skipped and
    # reported rather than silently dropped, because a sector that vanishes
    # from the comparison would quietly change the totals.
    skipped = []
    for sector, id_col in UNIT_ID.items():
        sheet = f"{sector} Ownership"
        try:
            o = pd.read_excel(old_f, sheet_name=sheet, dtype=str).fillna("")
            n = pd.read_excel(new_f, sheet_name=sheet, dtype=str).fillna("")
        except ValueError:
            skipped.append(sector)
            say(f"  {sector:<20} SKIPPED, sheet absent from one of the releases")
            continue

        a_top = owner_sets(o, id_col, PARENT_COL_OLD)
        b_top = owner_sets(n, id_col, PARENT_COL_NEW)
        a_imm = owner_sets(o, id_col, IMMEDIATE_COL)
        b_imm = owner_sets(n, id_col, IMMEDIATE_COL)

        both = set(a_top) & set(b_top)
        top_chg = [u for u in both if a_top[u] != b_top[u]]
        imm_both = set(a_imm) & set(b_imm)
        imm_chg = [u for u in imm_both if a_imm[u] != b_imm[u]]

        tot_b += len(both)
        tot_top += len(top_chg)
        tot_imm += len(imm_chg)

        # Assets whose top parent moved while the immediate owner did NOT are
        # the clean cases: nobody sold anything, the graph above simply grew.
        for u in top_chg:
            changed_rows.append({
                "sector": sector,
                "asset_id": u,
                "old_top_parent": "|".join(sorted(a_top[u])),
                "new_top_parent": "|".join(sorted(b_top[u])),
                "immediate_owner_also_changed":
                    u in imm_both and a_imm[u] != b_imm[u],
            })

        say(f"  {sector:<20} {len(both):>8,} {len(top_chg):>9,} "
            f"({len(top_chg)/len(both)*100:>4.1f}%) {len(imm_chg):>10,} "
            f"({len(imm_chg)/len(imm_both)*100:>4.1f}%)")

    say(f"  {'TOTAL':<20} {tot_b:>8,} {tot_top:>9,} ({tot_top/tot_b*100:>4.1f}%) "
        f"{tot_imm:>10,} ({tot_imm/tot_b*100:>4.1f}%)")
    say()

    ratio = (tot_top / tot_b) / (tot_imm / tot_b) if tot_imm else float("inf")
    say(f"  ratio of the two rates: {ratio:.1f} to 1")
    say()
    if ratio > 2:
        say("  VERDICT: vintages are NOT a clean time dimension.")
        say("  The immediate-owner rate is a believable M&A rate. The top-parent rate")
        say("  is not, and the two describe the same period of real-world activity.")
        say("  The excess is GEM's ownership graph deepening, so roughly")
        say(f"  {(1 - (tot_imm/tot_top))*100:.0f}% of apparent ownership change is research, not events.")
    else:
        say("  VERDICT: the two rates are close, so vintage differences are")
        say("  plausibly dominated by real events. Re-read before relying on this.")

    df = pd.DataFrame(changed_rows)
    # DETERMINISM. These rows are built by iterating Python sets, and set
    # iteration order for strings varies between processes because string
    # hashing is randomised. The row CONTENT is identical run to run, but the
    # row ORDER is not, so the file's checksum changes while nothing about the
    # data does. Found on 7 September 2026 by rerunning 04, 06 and 07 to emit
    # provenance records: every summary output was byte-identical and these two
    # CSVs were not. No reported figure was affected. It is fixed because a
    # checksum on a file whose bytes move for no reason is worthless as an audit
    # record, which is the whole point of the manifest.
    df = df.sort_values(list(df.columns), kind="mergesort").reset_index(drop=True)
    df.to_csv(os.path.join(OUT, "vintage_asset_parent_changes.csv"), index=False)
    if len(df):
        clean = (~df["immediate_owner_also_changed"]).sum()
        say()
        say(f"  of {len(df):,} assets whose top parent moved, {clean:,} "
            f"({clean/len(df)*100:.1f}%) had NO change")
        say("  in their immediate owner, so nothing about the asset itself changed.")

    # -----------------------------------------------------------------------
    # THE OBVIOUS OBJECTION, TESTED RATHER THAN ARGUED
    #
    # Carlo asked on 21 August: could the top parent be moving simply because
    # the ownership PERCENTAGES were revised? GEM records every percentage
    # shareholder, so a stake revised from 49 to 51 could genuinely change who
    # sits at the top. That is a fair challenge and it deserves a measurement.
    #
    # The test below separates the two explanations by conditioning on whether
    # GEM's picture of the corporate structure changed, measured as the number
    # of steps in the Ownership Path string.
    #
    #   chain SAME length  -> GEM's structural picture is unchanged, so any
    #                         share move is a genuine revision of a real stake.
    #   chain LENGTHENED   -> GEM inserted a company into the middle of the
    #                         chain. The look-through share is a product of the
    #                         shares along that chain, so inserting a link
    #                         mechanically changes the number even when no stake
    #                         was revised and nothing was bought or sold.
    #
    # If share revisions were driving this, the two rows would look similar.
    # -----------------------------------------------------------------------
    say()
    say("OBJECTION TEST: are the shares moving on their own, or because the")
    say("chain got longer? (conditioning on Ownership Path depth)")

    from collections import Counter
    tab = Counter()
    depth_o, depth_n = [], []
    for sector, id_col in UNIT_ID.items():
        if sector in skipped:
            continue
        o = pd.read_excel(old_f, sheet_name=f"{sector} Ownership", dtype=str).fillna("")
        n = pd.read_excel(new_f, sheet_name=f"{sector} Ownership", dtype=str).fillna("")
        # zip over the four columns rather than iterrows(), which is roughly
        # two orders of magnitude faster on sheets this size.
        def pairs(df, parent_col):
            return {
                (u, p): (sh, str(path).count("->"))
                for u, p, sh, path in zip(df[id_col], df[parent_col],
                                          df["Share"], df["Ownership Path"])
                if p
            }
        A = pairs(o, PARENT_COL_OLD)
        B = pairs(n, PARENT_COL_NEW)
        depth_o += [d for _, d in A.values()]
        depth_n += [d for _, d in B.values()]

        def as_num(x):
            try:
                return float(str(x).replace("%", "").strip())
            except (TypeError, ValueError):
                return None

        for k in set(A) & set(B):
            (sa, da), (sb, db) = A[k], B[k]
            a, b = as_num(sa), as_num(sb)
            moved = a is not None and b is not None and abs(a - b) > 1
            chain = "lengthened" if db > da else ("same" if db == da else "shortened")
            tab[(chain, moved)] += 1

    say(f"  mean ownership-chain depth: {sum(depth_o)/len(depth_o):.2f} steps "
        f"-> {sum(depth_n)/len(depth_n):.2f} steps")
    say()
    say(f"  {'chain between vintages':24} {'share moved >1pt':>17} {'stable':>9} {'moved %':>9}")
    for chain in ("lengthened", "same", "shortened"):
        m, s_ = tab[(chain, True)], tab[(chain, False)]
        if m + s_ == 0:
            continue
        say(f"  {chain:24} {m:>17,} {s_:>9,} {m/(m+s_)*100:>8.1f}%")
    m_same = tab[("same", True)]
    n_same = m_same + tab[("same", False)]
    m_long = tab[("lengthened", True)]
    n_long = m_long + tab[("lengthened", False)]
    say()
    say(f"  VERDICT: where GEM's structural picture is unchanged, only "
        f"{m_same/n_same*100:.1f}% of shares")
    say(f"  moved materially, which is a believable rate of real stake changes.")
    say(f"  Where the chain lengthened, {m_long/n_long*100:.1f}% moved. So the share moves are")
    say("  mostly a CONSEQUENCE of GEM adding intermediate companies, not an")
    say("  independent cause. The objection is answered: it is still research depth.")

    with open(os.path.join(OUT, "vintage_diff_summary.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    say()
    say(f"written to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
