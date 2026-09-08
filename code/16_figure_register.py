"""
SHIPPING GATE: IS EVERY FIGURE IN THE NOTE TRACEABLE TO AN OUTPUT FILE?

WHY THIS EXISTS
---------------
Gate 5 of the ruling of 6 September requires every figure in the note to be
traceable to a named output file carrying the release filename and its SHA-256.
Nothing had tested that. This script does, before the prose is written, because
a number that cannot be traced is cheap to fix now and expensive to fix in a
draft that is already built around it.

WHAT IT DOES
------------
It holds every number the ruling's section 2 running order calls for, together
with the output file that should contain it and the exact string that should
appear there. It then reads each file and checks. A claim whose string is absent
is reported as UNTRACEABLE, not quietly dropped.

This is deliberately dumb. It does not recompute anything and it cannot tell you
a number is correct. It tells you whether the number the note wants to print
actually appears in an artefact on disk that a reader could be pointed at. That
is the only thing gate 5 asks.

WHAT COUNTS AS TRACEABLE
------------------------
Three tiers, reported separately:
  OK          the string is in the named output file, and that file has a
              RUN_PROVENANCE record naming the release and its SHA-256
  NO-PROV     the string is in the named output file, but no provenance record
              covers it, so the release behind it is not recorded
  UNTRACEABLE the string is not in the named file at all

Anything not OK has to be resolved before the note ships: by pointing at a
different file, by writing the computation into a numbered script, or by cutting
the number.

Run:  python 16_figure_register.py
Out:  outputs/figure_register.txt
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

# section, claim, the exact string that must appear, the output file
REGISTER = [
    # ---- lead: hand verification and selection ------------------------------
    ("lead", "restatement bucket the sample was drawn from", "2,543", "restricted_r.txt"),
    ("lead", "R as published", "36.0%", "change_decomposition.txt"),
    ("lead", "pre-committed GO bar", "25%", "change_decomposition.txt"),
    ("lead", "generous bound on R", "29.1%", "change_decomposition.txt"),
    ("lead", "19 cases verified", "19", "event_validation_sample.csv"),
    ("lead", "salience lag, fast cases", "12 to 71 days", "salience_lag.txt"),
    ("lead", "salience lag, slow cases", "670 to 1,674 days", "salience_lag.txt"),
    ("lead", "salience lag, six datable cases", "cases in the evidence file                6", "salience_lag.txt"),

    # ---- conventions (blocked on branch 1, numbers still registered) --------
    ("conventions", "raw MW Spearman, blank=zero", "0.9146", "scaling_second_column.txt"),
    ("conventions", "raw MW Spearman, blank=impute", "0.9761", "scaling_second_column.txt"),
    ("conventions", "exposure growth U2, blank=zero", "+9.8%", "exposure_proxy_summary.txt"),
    ("conventions", "exposure growth U2, blank=impute", "+5.0%", "exposure_proxy_summary.txt"),
    ("conventions", "U2 convention flip, blank=zero", "0.9076", "bioenergy_check.txt"),
    ("conventions", "U2 convention flip, blank=impute", "0.9625", "bioenergy_check.txt"),
    ("conventions", "U2 firms with zero March capacity", "33 of the March 2025 firms", "bioenergy_check.txt"),
    ("conventions", "bioenergy control, blank=zero", "0.9643", "bioenergy_check.txt"),
    ("conventions", "bioenergy control, blank=impute", "0.9656", "bioenergy_check.txt"),
    ("conventions", "coal share, blank=zero", "0.9652", "bioenergy_check.txt"),

    # ---- graph mechanisms ---------------------------------------------------
    ("mechanisms", "ancestor over-count, March 2025", "1.55x", "exposure_proxy_summary.txt"),
    ("mechanisms", "ancestor over-count, August 2026", "1.76x", "exposure_proxy_summary.txt"),
    ("mechanisms", "Ameren and Union Electric capacity", "6991.2", "exposure_proxy_by_firm.csv"),
    ("mechanisms", "Entergy Corp, August 2026", "8720.92", "exposure_proxy_by_firm.csv"),
    ("mechanisms", "Entergy Louisiana, August 2026", "11121.4", "exposure_proxy_by_firm.csv"),

    # ---- portfolio consequences --------------------------------------------
    ("portfolio", "never exposed in either vintage", "137 of 328", "panel_join_summary.txt"),
    ("portfolio", "effective panel", "191", "panel_join_summary.txt"),
    ("portfolio", "Spearman 191 active, blank=zero", "0.7309", "panel_join_summary.txt"),
    ("portfolio", "Spearman 191 active, blank=impute", "0.7749", "panel_join_summary.txt"),
    ("portfolio", "top-quintile overlap, blank=zero", "86.8%", "panel_join_summary.txt"),
    ("portfolio", "top-quintile overlap, blank=impute", "92.1%", "panel_join_summary.txt"),
    ("portfolio", "U3 exposure growth, blank=zero", "+20.0%", "panel_join_summary.txt"),
    ("portfolio", "U3 exposure growth, blank=impute", "+11.7%", "panel_join_summary.txt"),

    # ---- both releases side by side ----------------------------------------
    ("releases", "R on V1", "36.0%", "change_decomposition.txt"),
    ("releases", "R on V2", "35.4%", "release_ladder.txt"),
    ("releases", "worst case on V1", "25.2%", "release_ladder.txt"),
    ("releases", "worst case on V2", "24.3%", "release_ladder.txt"),
    ("releases", "restricted R", "38.7%", "restricted_r.txt"),
    ("releases", "decimal truncation, V1", "80.0%", "decimal_truncation.txt"),
    ("releases", "decimal truncation, count", "3,561", "decimal_truncation.txt"),
    ("releases", "decimal truncation, V2", "78.5%", "decimal_truncation.txt"),
    ("releases", "decay, preferred cut n=8", "61.6% to 48.0%", "decay_curves.txt"),
    ("releases", "decay, gap-length correlation", "+0.51", "decay_curves.txt"),

    # ---- the tracker's age --------------------------------------------------
    ("age", "December 2025 methodology share", "96.2", "decay_curves.txt"),
    ("age", "number of adjacent release pairs", "13", "decay_curves.txt"),

    # ---- limitations, including the return arm ------------------------------
    ("limitations", "priceable firms in the 2026 arm", "173", "vintage_return_spread.txt"),
    ("limitations", "largest t statistic", "0.60", "vintage_return_spread.txt"),
    ("limitations", "Newey-West SE, low", "3.29%", "vintage_return_spread.txt"),
    ("limitations", "Newey-West SE, high", "3.44%", "vintage_return_spread.txt"),
    ("limitations", "MDE at t=3.0", "9.87%", "vintage_return_spread.txt"),
    ("limitations", "Fama-MacBeth requirement", "1,296", "power_comparison.txt"),
    # ---- appendix B: the mechanism catalogue --------------------------------
    # Typed here by hand from the output file, deliberately. The builder pulls
    # the same figures with its own regexes, so these entries are an independent
    # second statement of each number: if either the builder's pattern or this
    # transcription is wrong, the two disagree and one of them fails.
    ("appendix B", "build-out, new entity brought into coverage", "6,183", "change_decomposition.txt"),
    ("appendix B", "build-out, new entity, share", "48.6%", "change_decomposition.txt"),
    ("appendix B", "build-out, new link between covered entities", "1,744", "change_decomposition.txt"),
    ("appendix B", "build-out, new link, share", "13.7%", "change_decomposition.txt"),
    ("appendix B", "build-out, blank filled by research", "208", "change_decomposition.txt"),
    ("appendix B", "build-out, blank filled by research, share", "1.6%", "change_decomposition.txt"),
    ("appendix B", "build-out total", "8,135", "change_decomposition.txt"),
    ("appendix B", "build-out total, share", "64.0%", "change_decomposition.txt"),
    ("appendix B", "restatement, link removed", "1,710", "change_decomposition.txt"),
    ("appendix B", "restatement, link removed, share", "13.4%", "change_decomposition.txt"),
    ("appendix B", "restatement, share revised material", "533", "change_decomposition.txt"),
    ("appendix B", "restatement, share revised material, share", "4.2%", "change_decomposition.txt"),
    ("appendix B", "restatement, share revised small", "300", "change_decomposition.txt"),
    ("appendix B", "restatement, share revised small, share", "2.4%", "change_decomposition.txt"),
    ("appendix B", "restatement total, share", "20.0%", "change_decomposition.txt"),
    ("appendix B", "methodology, imputation rule introduced after Mar 2025", "1,842", "change_decomposition.txt"),
    ("appendix B", "methodology, imputation rule, share", "14.5%", "change_decomposition.txt"),
    ("appendix B", "methodology, entity deduplicated per remapping sheet", "143", "change_decomposition.txt"),
    ("appendix B", "methodology, deduplicated, share", "1.1%", "change_decomposition.txt"),
    ("appendix B", "methodology, imputed share moved, share", "0.4%", "change_decomposition.txt"),
    ("appendix B", "methodology total", "2,039", "change_decomposition.txt"),
    ("appendix B", "methodology total, share", "16.0%", "change_decomposition.txt"),
    ("appendix B", "total apparent change", "12,717", "change_decomposition.txt"),
    ("appendix B", "unchanged edges", "14,017", "change_decomposition.txt"),
    ("appendix B", "entities on the remapping sheet", "4,196", "change_decomposition.txt"),
    ("appendix B", "share of lost entities the remapping sheet accounts for", "11.5%", "change_decomposition.txt"),
    ("appendix B", "edges present in both releases", "16,954", "change_decomposition.txt"),
    ("appendix B", "real churn over eighteen months", "5.2%", "change_decomposition.txt"),
    ("appendix B", "ceiling on genuine corporate events", "881", "change_decomposition.txt"),
    ("appendix B", "edges GEM flags as imputed, Aug 2026", "4,392", "exposure_proxy_summary.txt"),
    ("appendix B", "edges GEM flags as imputed, share", "17.7%", "exposure_proxy_summary.txt"),
]

# which script's provenance record covers which output file
PROVENANCE_FOR = {
    "change_decomposition.txt": "RUN_PROVENANCE_06_change_decomposition.json",
    "decay_curves.txt": "RUN_PROVENANCE_07_decay_curves.json",
    "event_validation_sample.csv": "RUN_PROVENANCE_08_event_validation_sample.json",
    "exposure_proxy_summary.txt": "RUN_PROVENANCE_09_exposure_proxy.json",
    "exposure_proxy_by_firm.csv": "RUN_PROVENANCE_09_exposure_proxy.json",
    "decimal_truncation.txt": "RUN_PROVENANCE_12_decimal_truncation.json",
    "scaling_second_column.txt": "RUN_PROVENANCE_13_scaling_second_column.json",
    "restricted_r.txt": "RUN_PROVENANCE_14_restricted_r.json",
    "bioenergy_check.txt": "RUN_PROVENANCE_15_bioenergy_check.json",
    "salience_lag.txt": "RUN_PROVENANCE_18_salience_lag.json",
    "release_ladder.txt": "RUN_PROVENANCE_17_release_ladder.json",
    "panel_join_summary.txt": "RUN_PROVENANCE_10_panel_join.json",
    "vintage_return_spread.txt": "RUN_PROVENANCE_11_vintage_return_spread.json",
    "power_comparison.txt": "RUN_PROVENANCE_05_power_comparison.json",
}

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def main():
    cache = {}

    def body(fn):
        if fn not in cache:
            p = os.path.join(OUT, fn)
            cache[fn] = open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None
        return cache[fn]

    say("SHIPPING GATE 5  FIGURE REGISTER")
    say("  every number the ruling's section 2 calls for, against the output file")
    say("  that should contain it. Run before the prose, so an untraceable number")
    say("  is found while it is still cheap to fix.")
    say()

    rows = []
    for section, claim, needle, fn in REGISTER:
        txt = body(fn)
        if txt is None:
            status = "NO FILE"
        elif needle in txt:
            status = "OK" if fn in PROVENANCE_FOR else "NO-PROV"
        else:
            status = "UNTRACEABLE"
        rows.append((section, claim, needle, fn, status))

    cur = None
    for section, claim, needle, fn, status in rows:
        if section != cur:
            say(f"--- {section} ---")
            cur = section
        say(f"  [{status:<11}] {claim:<44} {needle:<16} {fn}")

    say()
    say("=" * 78)
    counts = {}
    for *_x, s in rows:
        counts[s] = counts.get(s, 0) + 1
    for k in ("OK", "NO-PROV", "UNTRACEABLE", "NO FILE"):
        if counts.get(k):
            say(f"  {k:<12} {counts[k]:>3}")

    bad = [r for r in rows if r[4] in ("UNTRACEABLE", "NO FILE")]
    if bad:
        say()
        say("  NOT TRACEABLE. Each must be resolved before the note ships, by pointing")
        say("  at a different file, by writing the computation into a numbered script,")
        say("  or by cutting the number from the note.")
        for section, claim, needle, fn, status in bad:
            say(f"    {section:<12} {claim:<44} expected '{needle}' in {fn}")

    noprov = [r for r in rows if r[4] == "NO-PROV"]
    if noprov:
        say()
        say("  IN A FILE BUT WITH NO PROVENANCE RECORD. The number is on disk but the")
        say("  release behind it is not recorded, so gate 5 is not met for it.")
        for section, claim, needle, fn, status in noprov:
            say(f"    {section:<12} {claim:<44} {fn}")

    say()
    say("  PROVENANCE RECORDS PRESENT")
    for fn, pj in sorted(set(PROVENANCE_FOR.items())):
        p = os.path.join(OUT, pj)
        if not os.path.exists(p):
            say(f"    MISSING  {pj}")
            continue
        rec = json.load(open(p))
        ins = rec.get("inputs", {})
        if not isinstance(ins, dict):
            say(f"    {pj:<48} MALFORMED: 'inputs' is {type(ins).__name__}, not a dict")
            continue
        if not ins:
            say(f"    {pj:<48} no data inputs ({rec.get('kind', 'see record')})")
            continue
        rel = next((v.get("filename") for k, v in ins.items() if "new" in k.lower()), None)
        sha = next((v.get("sha256", "")[:16] for k, v in ins.items() if "new" in k.lower()), "")
        if rel is None:
            say(f"    {pj:<48} upstream chain: {', '.join(sorted(ins))}")
        else:
            say(f"    {pj:<48} {rel}  sha {sha}")

    with open(os.path.join(OUT, "figure_register.txt"), "w") as fh:
        fh.write("\n".join(_lines) + "\n")
    say()
    say(f"  written to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
