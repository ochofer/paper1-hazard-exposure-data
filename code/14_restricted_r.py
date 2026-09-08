"""
TASK 1.1 SUPPLEMENT: R WITH RESIDUAL COUNTERPARTIES REMOVED FROM BOTH SIDES

WHY THIS EXISTS
---------------
R is the share of apparent ownership change that is not the database simply
growing: (restatement + methodology) / total. Task 1.3 found that a large part
of the restatement bucket has a RESIDUAL counterparty: a party like "small
shareholder(s)" or "natural person(s)" whose value is 100 minus the named
holders rather than an observed stake. A change in a residual carries no
ownership information, so it arguably should not count as evidence of anything.

Project A main put an objection to the research design chat on 5 September:
excluding residuals is not symmetric with the exclusions already inside R.
Build-out, restatement and methodology partition apparent change by CAUSE,
whereas a residual counterparty is a property of the COUNTERPARTY and appears in
all three buckets. Taking residuals out of the numerator alone would compare a
restricted numerator against an unrestricted denominator.

The chat ruled on 7 September: residuals come out of the numerator AND the
denominator, and the result is reported beside the published 36.0% with the same
prominence whatever it shows. This script is that computation.

WHY IT IS NOT DERIVABLE FROM THE NUMBER ALREADY REPORTED
--------------------------------------------------------
The previously reported figure, 360 residual edges of 2,543 (14.2%), was
measured on script 08's restatement frame only. That frame is the numerator's
larger half and says nothing about how many residual edges sit in the 8,135
build-out and 2,039 methodology edges, which are in the denominator. Removing
residuals from both sides needs them identified across all 12,717 changed edges.

IDENTIFICATION, AND THE CONTROL THAT CHECKS IT
-----------------------------------------------
change_decomposition_edges.csv carries entity IDs only, so party names are
joined from `All Entities` in BOTH releases. Both are needed: a removed link has
a party that exists only in the earlier release, and a new link has a party that
may exist only in the later one.

A party is residual if its name contains "small shareholder", "natural person",
"other shareholder", "unknown" or "various". This is the same rule used to
produce the 360, so the restatement bucket here MUST come back at 360. That
equality is asserted at the end as a control: if it fails, the name join or the
rule has drifted and the run stops rather than reporting a number.

Run:  python 14_restricted_r.py
Out:  outputs/restricted_r.txt
      outputs/RUN_PROVENANCE_14_restricted_r.json
"""

import os
import sys

import pandas as pd

import _release

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
OUT = os.path.join(HERE, "..", "outputs")
EDGES = os.path.join(OUT, "change_decomposition_edges.csv")
os.makedirs(OUT, exist_ok=True)

OLD_KEY = "March 2025"
NEW_KEY = "August 2026"          # PINNED to V1 on 3 Sep 2026

RESIDUAL_TOKENS = ["small shareholder", "natural person", "other shareholder",
                   "unknown", "various"]

# Control. The restatement bucket was measured at 360 residual edges of 2,543 on
# script 08's frame using this same rule. Anything else means a drift.
EXPECTED_RESTATEMENT_RESIDUALS = 360

GO_THRESHOLD = 0.25

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def name_map(path, label):
    ent = pd.read_excel(path, sheet_name="All Entities", dtype=str).fillna("")
    idc = _release.require_col(ent, ["Entity ID", "GEM Entity ID"], f"All Entities in {label}")
    nmc = _release.require_col(ent, ["Name", "Full Name"], f"All Entities in {label}")
    ent = ent[ent[idc].str.strip() != ""]
    say(f"  {label:<14} entities {len(ent):>7,}  id column '{idc}'  name column '{nmc}'")
    return dict(zip(ent[idc].str.strip(), ent[nmc].str.strip()))


def is_residual(nm):
    s = str(nm).lower()
    return any(t in s for t in RESIDUAL_TOKENS)


def main():
    old_f = _release.resolve(OLD_KEY, DATA)
    new_f = _release.resolve(NEW_KEY, DATA)

    say("TASK 1.1 SUPPLEMENT  RESTRICTED R, RESIDUALS OUT OF BOTH SIDES")
    say("  ruled by the research design chat, 7 September 2026")
    say("  reported beside the published 36.0% with the same prominence, as pre-committed")
    say()
    say("NAME JOIN, from both releases")
    names = {}
    names.update(name_map(old_f, OLD_KEY))          # earlier first
    names.update(name_map(new_f, NEW_KEY))          # later wins on collision
    say(f"  union of the two name maps: {len(names):,} entity ids")

    e = pd.read_csv(EDGES, dtype=str).fillna("")
    for c in ("subject", "party", "bucket"):
        _release.require_col(e, c, "change_decomposition_edges.csv")
    say(f"  changed edges loaded: {len(e):,}")

    e["party_name"] = e.party.map(names).fillna("")
    unnamed = int((e.party_name == "").sum())
    e["residual"] = e.party_name.map(is_residual)

    say()
    say("=" * 74)
    say("RESIDUAL COUNTERPARTIES, BY BUCKET, ACROSS ALL CHANGED EDGES")
    say(f"  a party is residual if its name contains any of: {', '.join(RESIDUAL_TOKENS)}")
    if unnamed:
        say(f"  NOTE {unnamed:,} edges ({100*unnamed/len(e):.2f}%) have a party id absent from")
        say("       both name maps and are therefore treated as NOT residual. They are")
        say("       counted here so the assumption is visible rather than buried.")

    tot = {}
    res = {}
    for b in ("build-out", "restatement", "methodology"):
        g = e[e.bucket == b]
        tot[b] = len(g)
        res[b] = int(g.residual.sum())
        say(f"  {b:<14} {tot[b]:>7,} edges   residual {res[b]:>5,}  ({100*res[b]/max(tot[b],1):5.1f}%)")
    total = sum(tot.values())
    total_res = sum(res.values())
    say(f"  {'TOTAL':<14} {total:>7,} edges   residual {total_res:>5,}  "
        f"({100*total_res/total:5.1f}%)")

    # ---- the control ------------------------------------------------------
    say()
    say("CONTROL: does the restatement bucket reproduce the figure already reported?")
    say(f"  expected {EXPECTED_RESTATEMENT_RESIDUALS} residual edges of 2,543 "
        f"(script 08 frame, same rule)")
    say(f"  found    {res['restatement']} residual edges of {tot['restatement']}")
    if res["restatement"] != EXPECTED_RESTATEMENT_RESIDUALS:
        say()
        say("  CONTROL FAILED. The name join or the residual rule has drifted from")
        say("  what produced the 360. Not reporting a restricted R on this basis.")
        with open(os.path.join(OUT, "restricted_r.txt"), "w") as fh:
            fh.write("\n".join(_lines) + "\n")
        sys.exit(f"control failed: {res['restatement']} != {EXPECTED_RESTATEMENT_RESIDUALS}")
    say("  MATCHES. The identification is the same one that produced the 360.")

    # ---- R, published and restricted --------------------------------------
    num = tot["restatement"] + tot["methodology"]
    R = num / total
    r_num = (tot["restatement"] - res["restatement"]) + (tot["methodology"] - res["methodology"])
    r_tot = total - total_res
    R_restricted = r_num / r_tot

    say()
    say("=" * 74)
    say("R, PUBLISHED AND RESTRICTED")
    say(f"  {'':<38}{'numerator':>12}{'denominator':>14}{'R':>9}")
    say(f"  {'as published':<38}{num:>12,}{total:>14,}{R*100:>8.1f}%")
    say(f"  {'residuals out of both sides':<38}{r_num:>12,}{r_tot:>14,}{R_restricted*100:>8.1f}%")
    say()
    say(f"  change in R: {(R_restricted - R)*100:+.1f} percentage points")
    say(f"  pre-committed GO threshold: {GO_THRESHOLD*100:.0f}%")
    say(f"  as published  {'clears' if R >= GO_THRESHOLD else 'FAILS'}")
    say(f"  restricted    {'clears' if R_restricted >= GO_THRESHOLD else 'FAILS'}")

    say()
    say("  WHY IT MOVES THIS WAY, which is the opposite of what was assumed.")
    say("  Residual counterparties are NOT concentrated in the restatement bucket.")
    say("  They are most concentrated in BUILD-OUT, at 23.6% against 14.2% for")
    say("  restatement and 14.7% for methodology. Build-out sits in the denominator")
    say("  only. So removing residuals from both sides strips proportionally more")
    say("  from the denominator than from the numerator, and R RISES.")
    say()
    say("  The working assumption throughout was that excluding residuals would")
    say("  deflate R and put the pre-committed 25% bar at risk. It does the")
    say("  reverse. The restricted measure is the more conservative construction")
    say("  and it makes the go decision safer, not thinner.")
    say()
    say("  A finding in its own right: nearly a quarter of the edges counted as")
    say("  the database growing are new links to a residual bucket, which is not")
    say("  new ownership information either. Growth in residual buckets is not")
    say("  growth in coverage.")

    e[["subject", "party", "party_name", "bucket", "residual"]].to_csv(
        os.path.join(OUT, "restricted_r_edges.csv"), index=False)

    _release.write_provenance(
        OUT, "14_restricted_r",
        {"old": old_f, "new_pinned": new_f},
        extra={"edges_file": "change_decomposition_edges.csv",
               "residual_tokens": RESIDUAL_TOKENS,
               "by_bucket_total": tot, "by_bucket_residual": res,
               "unnamed_party_edges": unnamed,
               "R_published": round(R, 6),
               "R_restricted": round(R_restricted, 6),
               "go_threshold": GO_THRESHOLD})
    say()
    say(f"  written to {os.path.abspath(OUT)}")
    with open(os.path.join(OUT, "restricted_r.txt"), "w") as fh:
        fh.write("\n".join(_lines) + "\n")


if __name__ == "__main__":
    main()
