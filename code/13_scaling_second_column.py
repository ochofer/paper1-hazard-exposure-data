"""
TASK 1.5 SUPPLEMENT: DOES SCALING CHANGE THE RANKING, AND CAN IT BE DONE AT ALL?

WHY THIS EXISTS
---------------
The research design chat ruled on 3 September 2026 that the note should report a
second exposure column beside raw attributable MW, and should treat the scaling
choice itself as a finding measured the same way as the blank-share convention.
The ruling's proposed second column was "fossil share of owned fleet, computed
inside GEM", chosen so the public repository stays self-contained and CC BY 4.0
without needing FMP fundamentals.

The motivation is the dispute between Aswani, Raghunandan and Rajgopal (Review of
Finance 2024) and Bolton and Kacperczyk. Raw attributable MW is the analogue of
unscaled emissions and ranks large utilities top by construction. Emissions
intensity is the analogue of a size-scaled measure.

WHAT THE WORKBOOKS ACTUALLY CONTAIN, CHECKED BEFORE WRITING THIS
----------------------------------------------------------------
GEM's Ownership Tracker has no wind, solar, hydro, nuclear or geothermal sheets.
The only power-generation sheets are coal plant, gas plant and bioenergy power.
So the only fleet share computable inside GEM is

    (coal + gas) / (coal + gas + bioenergy)

whose denominator is already almost entirely fossil. The expectation, stated
before running, is that this is near 1.0 for nearly every firm.

That is not merely a weak measure. It is a misleading one: a reader seeing
"fossil share of owned fleet = 0.97" will take it to mean the firm is
overwhelmingly fossil, when it in fact says nothing about renewables, nuclear or
hydro because GEM does not track them here. This script measures the degeneracy
rather than asserting it, so the answer to the ruling is evidence rather than an
opinion.

PRE-COMMITTED BEFORE RUNNING, recorded in PROJECT_STATUS.md
------------------------------------------------------------
1. DEGENERACY TEST. Median fossil share above 0.95 AND interquartile range below
   0.10 on the active panel means the measure cannot serve as a scaler. It does
   not become the note's second column and that is reported as the answer.
2. Otherwise compute the between-vintage Spearman and top-quintile overlap as
   for raw MW. If the two rankings correlate above 0.95 it drops to a footnote.
3. Report the WITHIN-vintage rank correlation between fossil share and raw MW
   regardless. If they order firms nearly identically the column adds nothing.
4. Also compute coal share of coal plus gas as a candidate alternative. It is a
   fuel-mix measure, not a size scaler, so it does not answer the intensity
   question, but its vintage stability is a legitimate finding in its own right.
5. Report whatever comes out.

HOW THE TRAVERSAL IS REUSED RATHER THAN REIMPLEMENTED
------------------------------------------------------
This script imports 09_exposure_proxy and calls its own load_vintage, build and
make_parents. Nothing about the attribution rule is reimplemented here, because
a second copy of a nearest-listed-parent walk is a second copy that can drift
from the first. The only thing this script does differently is load three sector
sheets instead of two and then run build once per sector on a filtered copy of
the loaded data, so the per-sector totals come out of exactly the same code path
that produces the headline measure.

Run:  python 13_scaling_second_column.py
Out:  outputs/scaling_second_column.txt
      outputs/scaling_by_firm.csv
      outputs/RUN_PROVENANCE_13_scaling_second_column.json
"""

import importlib.util
import os

import pandas as pd

import _release

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
PANEL = os.path.join(OUT, "cross_section.csv")
os.makedirs(OUT, exist_ok=True)

SHEETS = ["Coal Plant Ownership", "Gas Plant Ownership", "Bioenergy Power Ownership"]

# Pre-committed thresholds. See the docstring and PROJECT_STATUS.md.
DEGENERATE_MEDIAN = 0.95
DEGENERATE_IQR = 0.10
FOOTNOTE_SPEARMAN = 0.95

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def load_nine():
    """Import 09_exposure_proxy by path, because the module name starts with a
    digit and cannot be imported normally."""
    p = os.path.join(HERE, "09_exposure_proxy.py")
    spec = importlib.util.spec_from_file_location("exposure_proxy", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def spearman(a, b):
    """Pearson on average ranks, which is the definition. scipy is unavailable
    in this environment and cannot be installed: there is no network egress."""
    ra, rb = pd.Series(a).rank(), pd.Series(b).rank()
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(ra.corr(rb))


def quintile_overlap(s_old, s_new, n=5):
    """Share of the top-quintile names common to both, on the union index."""
    k = max(1, int(round(len(s_old) / n)))
    top_old = set(s_old.sort_values(ascending=False).head(k).index)
    top_new = set(s_new.sort_values(ascending=False).head(k).index)
    return len(top_old & top_new) / k, k, len(top_old & top_new)


def main():
    nine = load_nine()
    nine.SECTORS = SHEETS          # three sheets, not two
    nine.DATA = DATA

    old_f = _release.RELEASES["March 2025"]
    new_f = _release.RELEASES["August 2026"]

    say("TASK 1.5 SUPPLEMENT  SCALING: CAN A SECOND COLUMN BE BUILT INSIDE GEM?")
    say("  ruling (d), research design chat, 3 September 2026")
    say("  thresholds pre-committed before this ran; see PROJECT_STATUS.md")
    say()
    say("  GEM's ownership tracker carries NO wind, solar, hydro, nuclear or")
    say("  geothermal sheets. The only generation sheets are coal, gas and")
    say("  bioenergy, so any fleet share computed here has an almost entirely")
    say("  fossil denominator. That is the thing being tested.")

    loaded = {lbl: nine.load_vintage(lbl, fn, say)
              for lbl, fn in [("March 2025", old_f), ("August 2026", new_f)]}

    # sector labels are derived inside 09 as sheet.replace(" Plant Ownership","").lower()
    labels = sorted({v[2] for V in loaded.values() for v in V["units"].values()})
    say()
    say(f"  sector labels seen in the loaded units: {labels}")
    say()
    say("  NOTE THE BIOENERGY DROP ASYMMETRY in the load log above. Rows dropped for")
    say("  unknown share or capacity: 29 in March 2025 against 1,116 in August 2026.")
    say("  Bioenergy is the whole of the denominator's non-fossil part, so its data")
    say("  quality changing between vintages feeds straight into any fleet share.")

    def subset(V, keep):
        W = dict(V)
        W["units"] = {k: v for k, v in V["units"].items() if v[2] in keep}
        return W

    coal_l = [l for l in labels if l.startswith("coal")]
    gas_l = [l for l in labels if l.startswith("gas")]
    bio_l = [l for l in labels if l.startswith("bio")]
    if not (coal_l and gas_l and bio_l):
        raise SystemExit(f"sector labels not as expected: {labels}")

    frames = []
    for lbl, V in loaded.items():
        for rule in ("zero", "impute"):
            parts = {}
            for nm, keep in (("coal", coal_l), ("gas", gas_l), ("bio", bio_l)):
                df, _ = nine.build(f"{lbl} [{nm}]", subset(V, keep), rule,
                                   lambda *_a, **_k: None)
                parts[nm] = df.set_index("entity_id")["attributable_mw"]
            idx = parts["coal"].index.union(parts["gas"].index).union(parts["bio"].index)
            t = pd.DataFrame(index=idx)
            for nm in ("coal", "gas", "bio"):
                t[nm + "_mw"] = parts[nm].reindex(idx).fillna(0.0)
            t["vintage"] = lbl
            t["blank_rule"] = rule
            t["name"] = [V["name"].get(i, "") for i in idx]
            t["fossil_mw"] = t.coal_mw + t.gas_mw
            t["thermal_mw"] = t.fossil_mw + t.bio_mw
            t["fossil_share"] = (t.fossil_mw / t.thermal_mw).where(t.thermal_mw > 0)
            t["coal_share"] = (t.coal_mw / t.fossil_mw).where(t.fossil_mw > 0)
            frames.append(t.reset_index().rename(columns={"index": "entity_id"}))
    allf = pd.concat(frames, ignore_index=True)
    allf.to_csv(os.path.join(OUT, "scaling_by_firm.csv"), index=False)

    panel = set(pd.read_csv(PANEL, dtype={"entity_id": str})["entity_id"])
    say()
    say("=" * 74)
    say("TEST 1 (PRE-COMMITTED). IS FOSSIL SHARE DEGENERATE?")
    say(f"  degenerate if median > {DEGENERATE_MEDIAN} AND interquartile range < {DEGENERATE_IQR}")

    verdicts = {}
    for scope, keep in (("worldwide", None), ("the 328 panel", panel)):
        for rule in ("zero", "impute"):
            d = allf[(allf.blank_rule == rule) & (allf.vintage == "August 2026")]
            if keep is not None:
                d = d[d.entity_id.isin(keep)]
            fs = d.fossil_share.dropna()
            if len(fs) == 0:
                continue
            q1, med, q3 = fs.quantile(.25), fs.median(), fs.quantile(.75)
            iqr = q3 - q1
            deg = (med > DEGENERATE_MEDIAN) and (iqr < DEGENERATE_IQR)
            verdicts[(scope, rule)] = deg
            say(f"    {scope:<14} blank={rule:<7} n={len(fs):>4}  "
                f"median {med:.3f}  IQR {iqr:.3f} ({q1:.3f} to {q3:.3f})  "
                f"share at exactly 1.000 {100*(fs >= 0.9995).mean():.1f}%  "
                f"-> {'DEGENERATE' if deg else 'usable'}")

    say()
    say("TEST 3 (PRE-COMMITTED). DOES FOSSIL SHARE ORDER FIRMS DIFFERENTLY FROM RAW MW?")
    say("  within one vintage. If these agree, the second column adds nothing.")
    for rule in ("zero", "impute"):
        d = allf[(allf.blank_rule == rule) & (allf.vintage == "August 2026")]
        d = d[d.entity_id.isin(panel) & d.fossil_share.notna()]
        say(f"    the 328 panel, blank={rule:<7} n={len(d):>4}  "
            f"Spearman(fossil share, raw fossil MW) = {spearman(d.fossil_share, d.fossil_mw):.4f}")

    say()
    say("TEST 2 (PRE-COMMITTED). DOES EACH MEASURE MOVE BETWEEN VINTAGES?")
    say(f"  drops to a footnote if the between-vintage Spearman exceeds {FOOTNOTE_SPEARMAN}")
    for measure in ("fossil_mw", "fossil_share", "coal_share"):
        say(f"    --- {measure} ---")
        for rule in ("zero", "impute"):
            a = allf[(allf.vintage == "March 2025") & (allf.blank_rule == rule)] \
                .set_index("entity_id")[measure]
            b = allf[(allf.vintage == "August 2026") & (allf.blank_rule == rule)] \
                .set_index("entity_id")[measure]
            common = [e for e in a.index.intersection(b.index)
                      if e in panel and pd.notna(a[e]) and pd.notna(b[e])]
            if len(common) < 10:
                say(f"      blank={rule:<7} too few firms ({len(common)}) to compare")
                continue
            aa, bb = a.loc[common], b.loc[common]
            rho = spearman(aa, bb)
            ov, k, hit = quintile_overlap(aa, bb)
            flag = "footnote" if rho > FOOTNOTE_SPEARMAN else "reportable"
            say(f"      blank={rule:<7} n={len(common):>4}  Spearman {rho:.4f}  "
                f"top-quintile overlap {100*ov:.1f}% ({hit} of {k})  -> {flag}")
            if measure != "fossil_mw":
                # Same firms, unscaled. A scaled measure is undefined where the
                # denominator is zero, so the firms that enter or leave the
                # universe drop out of the scaled comparison but not the raw
                # one. Quoting 0.81 against a raw figure computed on a larger
                # set would compare two different samples.
                ra = allf[(allf.vintage == "March 2025") & (allf.blank_rule == rule)] \
                    .set_index("entity_id")["fossil_mw"].loc[common]
                rb = allf[(allf.vintage == "August 2026") & (allf.blank_rule == rule)] \
                    .set_index("entity_id")["fossil_mw"].loc[common]
                rov, rk, rhit = quintile_overlap(ra, rb)
                say(f"        like-for-like, RAW fossil MW on those same {len(common)} "
                    f"firms: Spearman {spearman(ra, rb):.4f}, "
                    f"top-quintile overlap {100*rov:.1f}% ({rhit} of {rk})")

    path = os.path.join(OUT, "scaling_second_column.txt")
    _release.write_provenance(
        OUT, "13_scaling_second_column",
        {"old": os.path.join(DATA, old_f), "new_pinned": os.path.join(DATA, new_f)},
        extra={"sheets": SHEETS,
               "precommitted": {"degenerate_median": DEGENERATE_MEDIAN,
                                "degenerate_iqr": DEGENERATE_IQR,
                                "footnote_spearman": FOOTNOTE_SPEARMAN},
               "degeneracy_verdicts": {f"{k[0]}|{k[1]}": bool(v) for k, v in verdicts.items()}})
    say()
    say(f"  written to {os.path.abspath(OUT)}")
    with open(path, "w") as fh:
        fh.write("\n".join(_lines) + "\n")


if __name__ == "__main__":
    main()
