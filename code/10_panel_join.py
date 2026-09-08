"""
TASK 1.5 SETUP: JOIN THE EXPOSURE PROXY TO THE REGIONAL CROSS-SECTION

WHY THIS IS A SEPARATE SCRIPT
------------------------------
09_exposure_proxy.py measures attributable operating coal and gas capacity for
every listed firm in the world: 666 firms in March 2025, 765 in August 2026.
That is the right universe for describing the dataset, but it is not the panel
the paper is about. The paper's cross-section is 328 listed firms headquartered
in Ken French's developed Europe plus the United States, built by
00_coverage_and_crosswalk.py and frozen in outputs/cross_section.csv.

Task 1.5 asks whether sorting THAT panel on the exposure proxy gives a
different answer depending on the vintage. So the two have to be joined first,
and the join itself turns out to be informative.

THE JOIN IS EXACT, WHICH IS WORTH SAYING
------------------------------------------
Both sides are keyed on the GEM entity ID, so there is no fuzzy name matching
and no crosswalk loss. Any firm that fails to join is genuinely absent, not a
matching failure.

A SELECTION PROBLEM THAT MUST BE STATED, NOT SOLVED SILENTLY
--------------------------------------------------------------
cross_section.csv was built from the AUGUST 2026 release. So the panel is
defined on the later vintage and then looked at backwards. That conditions on
being present, listed and identified in August 2026, which is exactly the kind
of look-ahead the note is about.

This script does NOT try to fix that. It measures it: how many of the 328 were
listed and identified in March 2025 at all, and how much of the measured change
is firms entering the panel rather than firms changing.

Fixing it properly means rebuilding the panel separately under each vintage,
which changes what "the 328" means and would break the figure that is already
public in Carlo's CV, cover letter and website. That is a task 1.6 decision, not
something to do here.

MISSING MEANS ZERO, DELIBERATELY
----------------------------------
A panel firm with no row in the exposure file has no attributable coal or gas
capacity in that vintage. That is a real zero, not missing data, and it is set
to 0.0 rather than dropped. Dropping it would hide entry and exit, which is
precisely what task 1.5 needs to see.

BOTH BLANK-SHARE CONVENTIONS, ALWAYS
--------------------------------------
Task 1.4 measured that the blank-share convention alone moves the cross-vintage
rank correlation by about 0.05 and halves the apparent growth. Every number
here is therefore reported under both. Collapsing to one would hide that
finding inside the result.

RUN
    python 10_panel_join.py

Reads:  outputs/cross_section.csv
        outputs/exposure_proxy_by_firm.csv
Writes: outputs/panel_exposure.csv        328 firms x vintage x blank rule
        outputs/panel_join_summary.txt    the run log
"""

import os

import pandas as pd

# Provenance. Scripts 10, 11 and 05 were the last three with no RUN_PROVENANCE
# record, found by the gate 5 register on 7 September 2026. See _release.py.
import _release


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")

PANEL = os.path.join(OUT, "cross_section.csv")
EXPO = os.path.join(OUT, "exposure_proxy_by_firm.csv")

VINTAGES = ["March 2025", "August 2026"]
RULES = ["zero", "impute"]
QUANTILE = 5          # quintiles for the portfolio-overlap test


def spearman(a, b):
    """Pearson on average ranks. scipy is unavailable (no egress) and pandas
    .rank() uses average ranks for ties, which is Spearman's definition."""
    return a.rank().corr(b.rank())


def overlap(a, b, k):
    """Share of the top-k set under a that is also in the top-k set under b."""
    sa = set(a.sort_values(ascending=False).head(k).index)
    sb = set(b.sort_values(ascending=False).head(k).index)
    return len(sa & sb) / k, sa, sb


def main():
    lines = []

    def log(s=""):
        print(s)
        lines.append(s)

    panel = pd.read_csv(PANEL, dtype={"entity_id": str})
    expo = pd.read_csv(EXPO, dtype={"entity_id": str})
    expo["attributable_mw"] = pd.to_numeric(expo["attributable_mw"])

    log("TASK 1.5 SETUP  PANEL JOIN")
    log(f"  panel      {len(panel):,} firms from cross_section.csv")
    log(f"  exposure   {expo.entity_id.nunique():,} distinct firms worldwide")
    log(f"  join key   GEM entity ID, exact, no name matching")

    ids = list(panel.entity_id)
    wide = panel[["entity_id", "name", "hq"]].copy()
    for v in VINTAGES:
        for r in RULES:
            s = (expo[(expo.vintage == v) & (expo.blank_rule == r)]
                 .set_index("entity_id")["attributable_mw"])
            # missing means a real zero, not missing data. See the docstring.
            wide[f"mw_{v.split()[1]}_{r}"] = [float(s.get(i, 0.0)) for i in ids]
    wide.to_csv(os.path.join(OUT, "panel_exposure.csv"), index=False)

    log(f"\n{'='*74}\nHOW MUCH OF THE PANEL THE PROXY ACTUALLY COVERS")
    log("  the proxy is coal and gas POWER only, so a panel firm whose only")
    log("  fossil assets are pipelines, mines, steel or cement scores zero")
    for v in VINTAGES:
        c = wide[f"mw_{v.split()[1]}_impute"]
        log(f"  {v:<13} firms with any exposure {int((c > 0).sum()):>4} of {len(wide)}"
            f"   total {c.sum()/1000:>7,.1f} GW")
    never = int(((wide.mw_2025_impute == 0) & (wide.mw_2026_impute == 0)).sum())
    log(f"  never exposed in either vintage      {never:>4} of {len(wide)}"
        f"  ({never/len(wide)*100:.0f}%)")
    log(f"  the EFFECTIVE panel for task 1.5 is therefore "
        f"{len(wide)-never} firms, not {len(wide)}")

    log(f"\n{'='*74}\nSELECTION: THE PANEL IS DEFINED ON THE LATER VINTAGE")
    a2025 = set(expo[expo.vintage == "March 2025"].entity_id)
    a2026 = set(expo[expo.vintage == "August 2026"].entity_id)
    inp = set(ids)
    log(f"  of the {len(inp)} panel firms, appearing in the exposure universe:")
    log(f"    March 2025  {len(inp & a2025):>4}")
    log(f"    August 2026 {len(inp & a2026):>4}")
    log(f"    entered between the two vintages {len((inp & a2026) - a2025):>4}")
    log(f"    left between the two vintages    {len((inp & a2025) - a2026):>4}")
    log("  panel membership itself is conditioned on August 2026. Not fixed")
    log("  here, by design. See the docstring and the task 1.6 note.")

    log(f"\n{'='*74}\nDOES THE SORT MOVE? {QUANTILE}-QUANTILE PORTFOLIOS")
    active = wide[(wide.mw_2025_impute > 0) | (wide.mw_2026_impute > 0)].copy()
    active = active.set_index("entity_id")
    nm = active["name"]
    log(f"  computed on the {len(active)} firms with exposure in either vintage")
    k = max(1, len(active) // QUANTILE)
    log(f"  top quintile = {k} firms")

    res = {}
    for r in RULES:
        A = active[f"mw_2025_{r}"]
        B = active[f"mw_2026_{r}"]
        rho_all = spearman(wide[f"mw_2025_{r}"], wide[f"mw_2026_{r}"])
        rho_act = spearman(A, B)
        ov, sa, sb = overlap(A, B, k)
        res[r] = (A, B, sa, sb)
        log(f"\n  --- blank={r} ---")
        log(f"    Spearman, all {len(wide)} panel firms incl. zeros   {rho_all:.4f}")
        log(f"    Spearman, {len(active)} active firms                {rho_act:.4f}")
        log(f"    Pearson,  {len(active)} active firms                {A.corr(B):.4f}")
        log(f"    total GW  2025 {A.sum()/1000:>7,.1f}   2026 {B.sum()/1000:>7,.1f}"
            f"   ({(B.sum()/A.sum()-1)*100:+.1f}%)")
        log(f"    TOP-QUINTILE OVERLAP  {ov*100:.1f}%  "
            f"({len(sa & sb)} of {k} firms in common)")
        # DETERMINISM, third instance of this trap in this codebase. `sa - sb`
        # is a set difference, and set iteration order for strings varies
        # between processes because string hashing is randomised. The names and
        # values are identical run to run; only their order moves. Sorted by
        # the size of the move, largest first, which is also more useful to a
        # reader than an arbitrary order.
        def _ordered(s_):
            return sorted(s_, key=lambda e: (-abs(B.get(e, 0) - A.get(e, 0)), str(e)))

        log(f"    dropped out of the top quintile: {len(sa - sb)}")
        for e in _ordered(sa - sb)[:6]:
            log(f"       {str(nm.get(e, e))[:34]:<36} "
                f"{A.get(e, 0):>9,.0f} -> {B.get(e, 0):>9,.0f} MW")
        log(f"    entered the top quintile:        {len(sb - sa)}")
        for e in _ordered(sb - sa)[:6]:
            log(f"       {str(nm.get(e, e))[:34]:<36} "
                f"{A.get(e, 0):>9,.0f} -> {B.get(e, 0):>9,.0f} MW")

    log(f"\n{'='*74}\nHOW MUCH THE BLANK-SHARE CONVENTION ALONE MOVES THE SORT")
    _, _, sa_z, sb_z = res["zero"]
    _, _, sa_i, sb_i = res["impute"]
    log(f"  March 2025 top quintile, zero vs impute: "
        f"{len(sa_z & sa_i)} of {k} in common "
        f"({len(sa_z & sa_i)/k*100:.1f}%)")
    log(f"  August 2026 top quintile, zero vs impute: "
        f"{len(sb_z & sb_i)} of {k} in common "
        f"({len(sb_z & sb_i)/k*100:.1f}%)")
    log("  the August figure should be 100%: August 2026 has no blank shares,")
    log("  so the two conventions are identical there. It is a self-check.")

    log(f"\n{'='*74}\nLARGEST PANEL MOVES (blank=impute)")
    A, B = active["mw_2025_impute"], active["mw_2026_impute"]
    j = pd.DataFrame({"a": A, "b": B})
    j["chg"] = j.b - j.a
    log(f"  {'firm':<34}{'2025':>11}{'2026':>11}{'change':>11}")
    for row in j.reindex(j.chg.abs().sort_values(ascending=False).index).head(14).itertuples():
        log(f"  {str(nm.get(row.Index, row.Index))[:32]:<34}"
            f"{row.a:>11,.0f}{row.b:>11,.0f}{row.chg:>+11,.0f}")

    # The release behind these numbers is not read here: it arrives through
    # 09's exposure proxy. Checksumming 09's own provenance record is what makes
    # the chain traceable rather than asserted.
    _prov = {"panel": PANEL, "exposure": EXPO}
    _up = os.path.join(OUT, "RUN_PROVENANCE_09_exposure_proxy.json")
    if os.path.exists(_up):
        _prov["upstream_provenance_09"] = _up
    _release.write_provenance(
        OUT, "10_panel_join", _prov,
        extra={"release_reaches_this_script_via":
               "09_exposure_proxy, which resolves the pin in _release.RELEASES"})

    with open(os.path.join(OUT, "panel_join_summary.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"\n  written to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
