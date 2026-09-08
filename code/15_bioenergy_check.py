"""
TASK 1.5 SUPPLEMENT: DOES THE SCALED ARM SURVIVE THE BIOENERGY COVERAGE CHANGE?

WHY THIS EXISTS
---------------
Script 13 found that the scaled exposure measure, fossil share of GEM-tracked
thermal capacity, is far less stable across vintages than raw megawatts on the
same firms: Spearman 0.81 and 0.85 against 0.97, top-quintile overlap 75% to 79%
against 94% to 97%.

It also found a contamination. Bioenergy is the entire non-fossil part of that
denominator, and GEM's bioenergy coverage changed sharply between the releases:
rows dropped for unknown share or capacity went from 29 in March 2025 to 1,116 in
August 2026. So part of the measured instability could be the denominator's own
coverage moving rather than anything about the firms.

THE CHECK AS ORIGINALLY SPECIFIED COULD NOT BE RUN
--------------------------------------------------
The research design chat's ruling of 5 September asked for the scaled arm to be
recomputed on firms with NO bioenergy in either vintage. That produces a
constant, not a comparison: with no bioenergy the share is fossil / (fossil + 0),
which is exactly 1 by construction. Counted on the file: 457 of the 679 firms
present in both vintages have no bioenergy in either and positive fossil capacity
in both, and every one of them has a fossil share of exactly 1.000 on both sides,
standard deviation zero. A Spearman on a constant is undefined, not reassuring.

The chat accepted this on 7 September and ruled two replacements, both run here:

  (a) THE CHECK. Restrict to firms with bioenergy present in BOTH vintages, so
      the denominator exists on both sides and any movement in it is real rather
      than coverage appearing and disappearing. Both blank conventions, Spearman
      and top-quintile overlap, n stated.

  (c) THE IMMUNE-BY-CONSTRUCTION COMPARISON. Coal share of coal plus gas. It
      contains no bioenergy at all, so the coverage change cannot touch it.

Variant (b), restricting to firms whose bioenergy is unchanged, was ruled out as
conditioning on the outcome.

INTERPRETATION, FIXED BY THE CHAT BEFORE THIS RAN
--------------------------------------------------
If (a) clears 0.95 under BOTH conventions, the convention-flip result is
attributed to the denominator's coverage change, and the note demotes scaling to
a coverage finding that still illustrates the thesis, because an analyst's choice
of denominator still moves the verdict.

If (a) falls below 0.95 under at least one convention, the instability survives
the coverage control and the conventions section stands as ruled.

Either way both numbers appear in the note with the 0.95 cut beside them. This
script states which branch fired rather than leaving it to be read off a table.

Run:  python 15_bioenergy_check.py
Out:  outputs/bioenergy_check.txt
      outputs/RUN_PROVENANCE_15_bioenergy_check.json
"""

import os

import pandas as pd

import _release

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
OUT = os.path.join(HERE, "..", "outputs")
SCALING = os.path.join(OUT, "scaling_by_firm.csv")
PANEL = os.path.join(OUT, "cross_section.csv")

CUT = 0.95          # the pre-committed Spearman cut
OLD, NEW = "March 2025", "August 2026"

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def spearman(a, b):
    ra, rb = pd.Series(a).rank(), pd.Series(b).rank()
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(ra.corr(rb))


def quintile_overlap(s_old, s_new, n=5):
    k = max(1, int(round(len(s_old) / n)))
    a = set(s_old.sort_values(ascending=False).head(k).index)
    b = set(s_new.sort_values(ascending=False).head(k).index)
    return len(a & b) / k, k, len(a & b)


def compare(d, rule, firms, measure, label):
    a = d[(d.vintage == OLD) & (d.blank_rule == rule)].set_index("entity_id")
    b = d[(d.vintage == NEW) & (d.blank_rule == rule)].set_index("entity_id")
    keep = [e for e in firms
            if e in a.index and e in b.index
            and pd.notna(a.loc[e, measure]) and pd.notna(b.loc[e, measure])]
    if len(keep) < 10:
        say(f"    {label:<44} blank={rule:<7} too few firms ({len(keep)})")
        return None
    aa, bb = a.loc[keep, measure], b.loc[keep, measure]
    rho = spearman(aa, bb)
    ov, k, hit = quintile_overlap(aa, bb)
    ra, rb = a.loc[keep, "fossil_mw"], b.loc[keep, "fossil_mw"]
    say(f"    {label:<44} blank={rule:<7} n={len(keep):>4}  "
        f"Spearman {rho:.4f}  top-quintile overlap {100*ov:5.1f}% ({hit} of {k})")
    if measure != "fossil_mw":
        rov, rk, rhit = quintile_overlap(ra, rb)
        say(f"    {'  like-for-like, RAW fossil MW, same firms':<44} "
            f"{'':<13} n={len(keep):>4}  Spearman {spearman(ra, rb):.4f}  "
            f"top-quintile overlap {100*rov:5.1f}% ({rhit} of {rk})")
    return rho


def main():
    d = pd.read_csv(SCALING)
    panel = set(pd.read_csv(PANEL, dtype={"entity_id": str})["entity_id"])

    say("TASK 1.5 SUPPLEMENT  BIOENERGY CHECK, VARIANTS (a) AND (c)")
    say("  ruled by the research design chat, 7 September 2026")
    say("  the originally specified check could not be run; see the docstring")
    say(f"  pre-committed cut: Spearman {CUT}")
    say()

    z = d[d.blank_rule == "zero"]
    a0 = z[z.vintage == OLD].set_index("entity_id")
    b0 = z[z.vintage == NEW].set_index("entity_id")
    both = a0.index.intersection(b0.index)
    bio_both = [e for e in both if a0.loc[e, "bio_mw"] > 0 and b0.loc[e, "bio_mw"] > 0]
    no_bio = [e for e in both
              if a0.loc[e, "bio_mw"] == 0 and b0.loc[e, "bio_mw"] == 0
              and a0.loc[e, "fossil_mw"] > 0 and b0.loc[e, "fossil_mw"] > 0]

    say("WHY THE ORIGINAL SPECIFICATION WAS REPLACED, counted rather than argued")
    say(f"  firms present in both vintages                                {len(both):>5,}")
    say(f"  with NO bioenergy in either and fossil > 0 in both            {len(no_bio):>5,}")
    fs = a0.loc[no_bio, "fossil_share"]
    say(f"  their fossil share, March 2025: min {fs.min():.3f} max {fs.max():.3f} "
        f"distinct values {fs.nunique()}, standard deviation {fs.std():.6f}")
    say("  A rank correlation on a constant is undefined, not reassuring.")
    say()
    say(f"  with bioenergy present in BOTH vintages, which is variant (a)  {len(bio_both):>5,}")
    say(f"  of those, also in the 328 panel                               "
        f"{len([e for e in bio_both if e in panel]):>5,}")

    say()
    say("=" * 78)
    say("(a) THE CHECK. Fossil share on firms whose denominator exists in both vintages")
    a_res = {}
    for rule in ("zero", "impute"):
        a_res[rule] = compare(d, rule, bio_both, "fossil_share",
                              "fossil share, bioenergy in both, worldwide")
    say()
    for rule in ("zero", "impute"):
        compare(d, rule, [e for e in bio_both if e in panel], "fossil_share",
                "fossil share, bioenergy in both, the 328 panel")

    say()
    say("  For reference, the unrestricted figures from script 13, panel firms:")
    say("    fossil share, blank=zero    Spearman 0.8107   top-quintile overlap 75.0%")
    say("    fossil share, blank=impute  Spearman 0.8509   top-quintile overlap 79.4%")

    say()
    say("=" * 78)
    say("U2, THE 604 MATCHED FIRMS WORLDWIDE. Does the convention flip generalise?")
    say("  Asked by the research design chat on 7 September, interpretation fixed")
    say("  BEFORE this ran: if U2 also straddles the 0.95 cut the flip is general;")
    say("  if U2 clears under both conventions the flip is a result about the listed")
    say("  US and European universe a portfolio manager would actually sort.")
    say()
    say("  U2 IS TAKEN FROM SCRIPT 09'S OWN FRAME, exposure_proxy_by_firm.csv, which")
    say("  is where U2 is defined and where the +9.8% / +5.0% growth pair is measured.")
    say("  A first attempt filtered U2 to firms with POSITIVE capacity in both")
    say("  vintages, giving 576 firms and the OPPOSITE branch. The filter was mine,")
    say("  not the project's definition, and it decided a pre-committed branch. Both")
    say("  are reported below so the difference is visible rather than a choice.")

    ep = pd.read_csv(os.path.join(OUT, "exposure_proxy_by_firm.csv"))
    u2_res = {}
    for rule in ("zero", "impute"):
        q = ep[ep.blank_rule == rule]
        av = q[q.vintage == OLD].set_index("entity_id")["attributable_mw"]
        bv = q[q.vintage == NEW].set_index("entity_id")["attributable_mw"]
        keep = sorted(set(av.index) & set(bv.index))
        aa, bb = av[keep], bv[keep]
        rho = spearman(aa, bb)
        ov, k, hit = quintile_overlap(aa, bb)
        u2_res[rule] = rho
        say(f"    U2, as defined      blank={rule:<7} n={len(keep):>4}  Spearman {rho:.4f}"
            f"  top-quintile overlap {100*ov:5.1f}% ({hit} of {k})")
        nz = [e for e in keep if av[e] > 0 and bv[e] > 0]
        an, bn = av[nz], bv[nz]
        ov2, k2, hit2 = quintile_overlap(an, bn)
        say(f"    positive in both    blank={rule:<7} n={len(nz):>4}  Spearman {spearman(an, bn):.4f}"
            f"  top-quintile overlap {100*ov2:5.1f}% ({hit2} of {k2})")

    say()
    say("  WHY THE TWO DIFFER, and it is the conventions section's own point.")
    n_zero = int((ep[(ep.blank_rule == "zero") & (ep.vintage == OLD)]
                  ["attributable_mw"] <= 0).sum())
    n_imp = int((ep[(ep.blank_rule == "impute") & (ep.vintage == OLD)]
                 ["attributable_mw"] <= 0).sum())
    say(f"  Under blank=zero, {n_zero} of the March 2025 firms carry attributable")
    say(f"  capacity of exactly zero, because every ownership edge they have has a")
    say(f"  blank share and a blank multiplied by zero is nothing. Under blank=impute")
    say(f"  that count is {n_imp}. So the convention does not only change the values, it")
    say("  decides whether a firm registers as having exposure at all. Those tied")
    say("  zeros are what drag the blank=zero rank correlation down. Filtering them")
    say("  out removes the convention's effect, which is the thing being measured.")

    say()
    say("  THE THREE UNIVERSES, raw fossil MW between vintages:")
    say(f"    {'universe':<44}{'blank=zero':>12}{'blank=impute':>14}")
    say(f"    {'U3, 171 panel firms':<44}{0.9146:>12.4f}{0.9761:>14.4f}")
    say(f"    {'U2, 604 matched firms worldwide':<44}"
        f"{u2_res['zero']:>12.4f}{u2_res['impute']:>14.4f}")
    say(f"    {'133 firms with bioenergy in both':<44}{0.9747:>12.4f}{0.9766:>14.4f}")
    say(f"    {'the pre-committed cut':<44}{CUT:>12.2f}{CUT:>14.2f}")

    say()
    lo, hi = min(u2_res.values()), max(u2_res.values())
    if lo < CUT < hi:
        say("  U2 STRADDLES THE CUT. The convention flip is GENERAL, not an artefact")
        say("  of the regional panel, and the note says so. It reproduces on 604")
        say("  firms worldwide and on 171 panel firms, in the same direction.")
    elif lo > CUT:
        say("  U2 CLEARS UNDER BOTH CONVENTIONS. The flip is a result about the listed")
        say("  US and European universe a portfolio manager would sort, not a property")
        say("  of the dataset at large, and the note says that instead.")
    else:
        say("  U2 FALLS BELOW THE CUT UNDER BOTH. A third outcome, reported as such.")

    say()
    say("=" * 78)
    say("(c) IMMUNE BY CONSTRUCTION. Coal share of coal plus gas, no bioenergy in it")
    for rule in ("zero", "impute"):
        compare(d, rule, [e for e in both if e in panel], "coal_share",
                "coal share, the 328 panel")

    say()
    say("=" * 78)
    say("WHICH BRANCH FIRED, per the interpretation fixed before this ran")
    clears = [r for r, v in a_res.items() if v is not None and v > CUT]
    both_clear = len(clears) == 2
    for rule, v in a_res.items():
        if v is not None:
            say(f"  (a) blank={rule:<7} Spearman {v:.4f}  "
                f"{'ABOVE' if v > CUT else 'BELOW'} the {CUT} cut")
    say()
    if both_clear:
        say("  BRANCH 1. (a) clears 0.95 under both conventions.")
        say("  The convention-flip result is attributed to the denominator's coverage")
        say("  change. The note demotes scaling to a coverage finding, which still")
        say("  illustrates the thesis: an analyst's choice of denominator moves the")
        say("  verdict. Both numbers appear with the cut beside them.")
    else:
        say("  BRANCH 2. (a) falls below 0.95 under at least one convention.")
        say("  The instability SURVIVES the coverage control, so it is not merely the")
        say("  bioenergy coverage change. The conventions section stands as ruled.")
        say("  Both numbers appear with the cut beside them.")

    _release.write_provenance(
        OUT, "15_bioenergy_check",
        {"old": _release.resolve(OLD, DATA), "new_pinned": _release.resolve(NEW, DATA)},
        extra={"derived_from": ["scaling_by_firm.csv", "cross_section.csv"],
               "cut": CUT,
               "n_both_vintages": len(both),
               "n_no_bioenergy_either": len(no_bio),
               "n_bioenergy_both": len(bio_both),
               "a_spearman": {k: (None if v is None else round(v, 6))
                              for k, v in a_res.items()},
               "branch": "coverage_change" if both_clear else "instability_survives"})
    say()
    say(f"  written to {os.path.abspath(OUT)}")
    with open(os.path.join(OUT, "bioenergy_check.txt"), "w") as fh:
        fh.write("\n".join(_lines) + "\n")


if __name__ == "__main__":
    main()
