"""
TASK 1.4: ATTRIBUTABLE OPERATING FOSSIL GENERATING CAPACITY, ON TWO VINTAGES

WHAT THIS BUILDS
----------------
For each listed firm, the megawatts of operating coal and gas generating
capacity attributable to it through the ownership graph, computed separately
on the March 2025 and August 2026 releases.

This is the transition exposure proxy. Task 1.5 then asks whether sorting firms
on it gives a different answer depending on which vintage you happened to
download, which is the Berg, Fabisik and Sautner move.

PRE-COMMITTED CHOICES, made with Carlo on 2 September 2026 BEFORE anything ran
-----------------------------------------------------------------------------
    sectors      Coal Plant Ownership and Gas Plant Ownership only. One unit
                 throughout (MW), so no conversion assumptions. Both sheets
                 exist in both vintages.

                 DELIBERATELY EXCLUDED and why: coal mines are in Mtpa,
                 pipelines in Bcm/y or BOEd, steel in ttpa; summing them needs
                 contestable conversion factors. Bioenergy, iron and steel are
                 not fossil. Oil & NGL Pipeline and Cement and Concrete are
                 excluded for a harder reason: THEY DO NOT EXIST IN THE MARCH
                 2025 WORKBOOK. Including a sector present in only one vintage
                 would manufacture an increase that is pure sector addition.

    status       operating only. Announced and pre-permit projects are where
                 GEM's build-out is fastest, so including them would import the
                 artefact this track is measuring.

    attribution  nearest listed parent, depth cap 12, cycle-safe. Same rule as
                 00_coverage_and_crosswalk.py, so the firm panel is comparable
                 to the 328-firm cross-section.

    listed       PubliclyListed is true AND an LEI or PermID is present.

    unit key     GEM unit ID.

THE BLANK-SHARE PROBLEM, AND WHY THIS SCRIPT REPORTS TWO NUMBERS
------------------------------------------------------------------
This was found by verification, not by design, and it is the most consequential
thing in the script.

    March 2025    18,807 ownership edges, 2,492 with a BLANK share  (13.3%)
    August 2026   25,206 ownership edges,     0 with a blank share  ( 0.0%)
                  of which 4,465 are flagged `imputed value`        (17.7%)

GEM filled every blank between the two releases. So the choice of what a blank
share means is not a technicality: it applies to a large slice of the earlier
vintage and to none of the later one, which means a careless choice creates
apparent exposure growth out of nothing.

The first version of this script did `fillna(0.0)`. That silently zeroed 2,492
real edges in March 2025 and none in August 2026. It was caught because DTE
Energy came out at 0 MW in March 2025 while GEM's own sheet listed it as the
parent of 24 operating units. The edge DTE Energy -> DTE Electric exists in
March 2025 with a blank share, and GEM's own Ownership Path renders it as
"DTE Electric Co [unknown %]". Multiplying by zero deleted a real utility's
entire coal fleet.

So the script now computes the measure under BOTH conventions and reports both:

    zero      a blank share contributes nothing. Understates the earlier
              vintage. This is what a user doing the obvious thing gets, so it
              is worth reporting rather than hiding.
    impute    a blank share is filled using GEM's own documented convention:
              the owners of a subject split whatever is not already accounted
              for by known shares. Where every owner of a subject is blank,
              they split 100 equally. 65% of March 2025's blanks are
              sole-owner subjects, so they become 100%.

Neither is "correct". The gap between them is a measurement of how much the
answer depends on a convention the vendor never states, and that gap is the
finding. It must be reported in the note, not resolved silently.

WHY WE DO NOT JUST USE GEM'S OWN "Share" COLUMN
------------------------------------------------
The per-sector sheets carry a Share column, so it looks as though GEM has done
this work. It has, under a different rule. GEM emits one row per (ancestor,
unit) for EVERY ancestor in the chain, not just the nearest listed one:

    Aboitiz Equity Ventures Inc -> Aboitiz Power Corp [53.09%]
        -> Pagbilao power station Unit 2 [100.0%]

Both Aboitiz entities get a row for Pagbilao Unit 2. Summing GEM's Share column
by parent counts the unit twice. Measured: the operating coal fleet in the
August 2026 release is 2,200 GW, which matches the known global figure; summing
GEM's own attributable shares over all parents gives 7,730 GW across coal and
gas against an actual 4,351 GW, an over-count of 78%. The script reports this
ratio for both vintages because it got WORSE over time, which is itself a
result.

RECONSTRUCTING ASSET OWNERSHIP FOR MARCH 2025
-----------------------------------------------
March 2025 has no "Asset Ownership" sheet; it was added later. But the
Ownership Path column encodes the whole chain with percentages, and the final
hop is the immediate owner's stake in the unit:

    A -> B [53.09%] -> C [100.0%] -> D [70.0%] -> Unit [100.0%]

Verified: multiplying the bracketed shares reproduces GEM's own Share column
exactly (0.5309 x 1.0 x 0.70 = 0.3716, and GEM writes 37.16). So the last
bracket paired with "Immediate Project Owner GEM Entity ID" gives the
asset-level table March 2025 lacks. Reconstructed identically for BOTH vintages
so the comparison is like for like.

Some paths end "[unknown %]" and yield no number. Those rows are dropped and
counted in the run log rather than being silently coerced to zero, which is the
same mistake as the blank shares above.

SCHEMA DRIFT, AGAIN
-------------------
March 2025 names the column "Owner GEM Entity ID"; August 2026 names it
"Parent GEM Entity ID". Resolved by name, never by position. Third schema
change found in this dataset, after the December 2025 "Last Review Date"
insertion and the disappearance of "newest_update" in the August 2026 V2
file.

RUN
    python 09_exposure_proxy.py

Writes: outputs/exposure_proxy_by_firm.csv   firm x vintage x blank-rule
        outputs/exposure_proxy_summary.txt   the run log
"""

import os
import re
from collections import defaultdict

import pandas as pd

# Release resolution is pinned in _release.py, not matched against whatever is
# in the data folder. See that module's docstring for why.
import _release


HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)

# PINNED 3 September 2026. This dict previously named the V2_External
# file while scripts 00, 04, 06 and 07 were on V1, which is how task
# 1.5 came to join a V1 cross-section to a V2 exposure measure. The
# filenames now come from the single pin in _release.py.
VINTAGES = {
    "March 2025":  _release.RELEASES["March 2025"],
    "August 2026": _release.RELEASES["August 2026"],
}

SECTORS = ["Coal Plant Ownership", "Gas Plant Ownership"]
OPERATING = {"operating", "operating pre-retirement"}
DEPTH_CAP = 12
BLANK_RULES = ["zero", "impute"]

LEI_COL = "Global Legal Entity Identifier Index"
PERMID_COL = "PermID: Refinitiv Permanent Identifier"
PARENT_ID = ["Parent GEM Entity ID", "Owner GEM Entity ID"]

_PCT = re.compile(r"\[([0-9.]+)%\]")


def col(df, candidates):
    """Resolve a column by name across schema versions. Never by position:
    see the December 2025 column-shift bug recorded in 07_decay_curves.py."""
    for c in candidates:
        if c in df.columns:
            return c
    raise SystemExit(f"none of {candidates} in {list(df.columns)[:12]}")


def blank(s):
    """GEM writes missing identifiers as 'not found', not as an empty cell."""
    s = s.astype(str).str.strip()
    return (s == "") | s.str.lower().isin(
        ["not found", "not applicable", "none", "nan"])


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False)
                         .str.rstrip("%").str.strip(), errors="coerce")


def last_hop_share(path):
    """The immediate owner's stake in the unit is the LAST bracketed percent."""
    m = _PCT.findall(str(path))
    if not m:
        return None
    try:
        return float(m[-1]) / 100.0
    except ValueError:
        return None


def load_vintage(label, fname, log):
    """Read one workbook once. Both blank-share rules are applied later, to the
    same loaded data, so the two runs cannot drift apart."""
    path = os.path.join(DATA, fname)
    if not os.path.exists(path):
        raise SystemExit(f"missing workbook: {path}")
    xl = pd.ExcelFile(path)
    log(f"\n{'-'*74}\nloading {label}   ({fname})")
    log(f"  sheets present: {len(xl.sheet_names)}")
    absent = [s for s in ("Oil & NGL Pipeline Ownership",
                          "Cement and Concrete Ownership",
                          "Asset Ownership") if s not in xl.sheet_names]
    if absent:
        log(f"  NOT in this vintage: {', '.join(absent)}")
    missing = [s for s in SECTORS if s not in xl.sheet_names]
    if missing:
        raise SystemExit(f"{label} is missing {missing}")

    ent = xl.parse("All Entities", dtype=str).fillna("")
    ent["listed"] = ent["PubliclyListed"].str.strip().str.lower() == "true"
    ent["ident"] = ~blank(ent[LEI_COL]) | ~blank(ent[PERMID_COL])
    listed = set(ent.loc[ent.listed & ent.ident, "Entity ID"])
    name = dict(zip(ent["Entity ID"], ent["Name"]))
    hq = dict(zip(ent["Entity ID"], ent["Headquarters Country"]))
    log(f"  entities {len(ent):,} | listed {int(ent.listed.sum()):,} | "
        f"listed and identified {len(listed):,}")

    eo = xl.parse("Entity Ownership", dtype=str).fillna("")
    raw = num(eo["% Share of Ownership"])
    n_blank = int(raw.isna().sum())
    log(f"  entity ownership edges {len(eo):,} | "
        f"BLANK share {n_blank:,} ({n_blank/len(eo)*100:.1f}%)")
    if "Share Imputed?" in eo.columns:
        vc = eo["Share Imputed?"].str.strip().value_counts()
        imp = int(vc.get("imputed value", 0))
        log(f"  flagged `imputed value` by GEM: {imp:,} "
            f"({imp/len(eo)*100:.1f}%)")
    edges = [(s, p, (None if pd.isna(v) else v / 100.0))
             for s, p, v in zip(eo["Subject Entity ID"],
                                eo["Interested Party ID"], raw) if s and p]

    units = {}
    gem_rows = []
    for sh_name in SECTORS:
        d = xl.parse(sh_name, dtype=str).fillna("")
        pid = col(d, PARENT_ID)
        d = d[d["Status"].str.strip().str.lower().isin(OPERATING)].copy()
        d["cap"] = num(d["Capacity (MW)"])
        d["gemsh"] = num(d["Share"]) / 100.0
        d["hop"] = d["Ownership Path"].map(last_hop_share)
        sector = sh_name.replace(" Plant Ownership", "").lower()
        # pd.isna, NOT "is None". Series.map turns a returned None into a float
        # NaN, so `hop is None` never fires and the NaN propagates into the firm
        # totals. That produced an attributable total of "nan GW" on the first
        # run of this script.
        dropped = 0
        for u, own, cap, hop in zip(d["GEM unit ID"],
                                    d["Immediate Project Owner GEM Entity ID"],
                                    d["cap"], d["hop"]):
            if not u or not own or pd.isna(cap) or pd.isna(hop):
                dropped += 1
                continue
            units.setdefault((u, own), (cap, hop, sector))
        gem_rows.append(d[["cap", "gemsh"]])
        log(f"  {sh_name:<24} operating rows {len(d):>8,}  "
            f"units {d['GEM unit ID'].nunique():>6,}"
            + (f"  DROPPED {dropped:,} (unknown share or capacity)"
               if dropped else ""))

    return dict(listed=listed, name=name, hq=hq, edges=edges, units=units,
                gem=pd.concat(gem_rows, ignore_index=True), n_blank=n_blank)


def make_parents(edges, rule):
    """Build the ownership graph under one blank-share convention.

    impute: the owners of a subject split whatever the known shares leave
            unaccounted for. Where every owner is blank they split 100 equally.
            This is GEM's own documented imputation convention, applied by us
            to the earlier vintage because GEM had not yet applied it there.
    zero:   a blank contributes nothing.
    """
    by_subject = defaultdict(list)
    for s, p, v in edges:
        by_subject[s].append((p, v))
    parents = defaultdict(list)
    for s, lst in by_subject.items():
        known = sum(v for _, v in lst if v is not None)
        nb = sum(1 for _, v in lst if v is None)
        fill = 0.0
        if rule == "impute" and nb:
            fill = max(0.0, 1.0 - known) / nb
        for p, v in lst:
            parents[s].append((p, v if v is not None else fill))
    return parents


def build(label, V, rule, log):
    listed, units = V["listed"], V["units"]
    parents = make_parents(V["edges"], rule)
    memo = {}

    def nearest(e, depth, stack):
        """Look-through economic interest of the nearest listed parents.
        Stops at the first listed entity on each path. Cycle-safe via stack."""
        key = (e, depth)
        if key in memo:
            return memo[key]
        acc = defaultdict(float)
        if depth < DEPTH_CAP and e not in stack:
            stack = stack | {e}
            for p, sh in parents.get(e, ()):
                if p in listed:
                    acc[p] += sh
                else:
                    for a, v in nearest(p, depth + 1, stack).items():
                        acc[a] += sh * v
        memo[key] = dict(acc)
        return memo[key]

    unit_cap, firm_mw, firm_units = {}, defaultdict(float), defaultdict(set)
    for (u, own), (cap, hop, sector) in units.items():
        unit_cap[u] = (cap, sector)
        contrib = {own: 1.0} if own in listed else nearest(own, 0, frozenset())
        for a, v in contrib.items():
            firm_mw[a] += hop * v * cap
            firm_units[a].add(u)

    by_sector = defaultdict(float)
    for u, (cap, sector) in unit_cap.items():
        by_sector[sector] += cap
    fleet = sum(by_sector.values())
    attributable = sum(firm_mw.values())

    log(f"\n  [{label} | blank={rule}]")
    log(f"    fleet {fleet/1000:,.1f} GW  "
        f"(coal {by_sector['coal']/1000:,.1f}, gas {by_sector['gas']/1000:,.1f})"
        if "coal" in by_sector else f"    fleet {fleet/1000:,.1f} GW")
    log(f"    attributed to listed firms  {attributable/1000:>9,.1f} GW  "
        f"({attributable/fleet*100:.1f}% of fleet)")
    log(f"    listed firms with exposure  {len(firm_mw):>9,}")

    rows = [{"vintage": label, "blank_rule": rule, "entity_id": a,
             "name": V["name"].get(a, ""), "hq_country": V["hq"].get(a, ""),
             "attributable_mw": round(v, 2), "units": len(firm_units[a])}
            for a, v in firm_mw.items()]
    return pd.DataFrame(rows).sort_values("attributable_mw", ascending=False), fleet


def compare(a, b, A, B, rule, log, names):
    both = A.index.intersection(B.index)
    log(f"\n  --- blank={rule} ---")
    log(f"    firms in {a:<12}{len(A):>7,}      "
        f"only here {len(A.index.difference(B.index)):>5,}")
    log(f"    firms in {b:<12}{len(B):>7,}      "
        f"only here {len(B.index.difference(A.index)):>5,}")
    log(f"    in both      {len(both):>7,}")
    if len(both) < 2:
        return None
    j = pd.DataFrame({"a": A[both], "b": B[both]})
    j["chg"] = j.b - j.a
    # Spearman as Pearson on ranks. scipy is not installed and cannot be
    # (no egress). pandas .rank() uses average ranks for ties, which is
    # Spearman's own definition, so this is the statistic, not an approximation.
    log(f"    Spearman rank correlation   {j.a.rank().corr(j.b.rank()):.4f}")
    log(f"    Pearson correlation         {j.a.corr(j.b):.4f}")
    log(f"    total {a}  {j.a.sum()/1000:>9,.1f} GW")
    log(f"    total {b}  {j.b.sum()/1000:>9,.1f} GW  "
        f"({(j.b.sum()/j.a.sum()-1)*100:+.1f}%)")
    unch = int((j.chg.abs() < 1e-6).sum())
    log(f"    unchanged to within 1 kW    {unch:,} ({unch/len(j)*100:.1f}%)")
    log(f"    changed                     {len(j)-unch:,} "
        f"({(len(j)-unch)/len(j)*100:.1f}%)")
    log(f"\n    largest 12 absolute moves (MW):")
    log(f"      {'firm':<34}{a:>12}{b:>12}{'change':>12}")
    for r in j.reindex(j.chg.abs().sort_values(ascending=False).index).head(12).itertuples():
        log(f"      {str(names.get(r.Index, r.Index))[:32]:<34}"
            f"{r.a:>12,.0f}{r.b:>12,.0f}{r.chg:>+12,.0f}")
    return j


def main():
    lines = []

    def log(s=""):
        print(s)
        lines.append(s)

    log("TASK 1.4  TRANSITION EXPOSURE PROXY ON TWO VINTAGES")
    log("  sectors: coal and gas power plants | status: operating only")
    log("  attribution: nearest listed parent, depth cap 12, cycle-safe")
    log("  blank shares: reported under BOTH conventions, see the docstring")

    _release.write_provenance(
        OUT, '09_exposure_proxy',
        {lbl: os.path.join(DATA, fn) for lbl, fn in VINTAGES.items()})
    loaded = {lbl: load_vintage(lbl, fn, log) for lbl, fn in VINTAGES.items()}

    log(f"\n{'='*74}\nGEM'S OWN Share COLUMN, SUMMED NAIVELY OVER ALL PARENTS")
    log("  what a user who takes the sector sheet at face value would get")
    for lbl, V in loaded.items():
        g = V["gem"].dropna()
        naive = (g["gemsh"] * g["cap"]).sum()
        fleet = sum(c for (c, _, _) in V["units"].values())
        fleet = sum({u: c for (u, _), (c, _, _) in V["units"].items()}.values())
        log(f"  {lbl:<13} {naive/1000:>9,.1f} GW  vs actual fleet "
            f"{fleet/1000:>8,.1f} GW  = {naive/fleet:.2f}x")

    log(f"\n{'='*74}\nTHE MEASURE")
    frames = {}
    for rule in BLANK_RULES:
        for lbl in VINTAGES:
            frames[(lbl, rule)], _ = build(lbl, loaded[lbl], rule, log)

    out = pd.concat(frames.values(), ignore_index=True)
    out.to_csv(os.path.join(OUT, "exposure_proxy_by_firm.csv"), index=False)

    a, b = list(VINTAGES)
    names = {**{r.entity_id: r.name for r in frames[(a, "impute")].itertuples()},
             **{r.entity_id: r.name for r in frames[(b, "impute")].itertuples()}}
    log(f"\n{'='*74}\nCROSS-VINTAGE COMPARISON")
    js = {}
    for rule in BLANK_RULES:
        A = frames[(a, rule)].set_index("entity_id")["attributable_mw"]
        B = frames[(b, rule)].set_index("entity_id")["attributable_mw"]
        js[rule] = compare(a, b, A, B, rule, log, names)

    log(f"\n{'='*74}\nHOW MUCH THE BLANK-SHARE CONVENTION MOVES THE ANSWER")
    for lbl in VINTAGES:
        z = frames[(lbl, "zero")]["attributable_mw"].sum() / 1000
        i = frames[(lbl, "impute")]["attributable_mw"].sum() / 1000
        log(f"  {lbl:<13} zero {z:>8,.1f} GW   impute {i:>8,.1f} GW   "
            f"gap {i-z:>+8,.1f} GW ({(i/z-1)*100:+.1f}%)")
    if all(js.get(r) is not None for r in BLANK_RULES):
        gz = js["zero"].b.sum() / js["zero"].a.sum() - 1
        gi = js["impute"].b.sum() / js["impute"].a.sum() - 1
        log(f"\n  APPARENT GROWTH {a} -> {b}, matched firms only:")
        log(f"    under blank=zero    {gz*100:+.1f}%")
        log(f"    under blank=impute  {gi*100:+.1f}%")
        log(f"  The difference between those two is not exposure. It is a "
            f"convention.")

    with open(os.path.join(OUT, "exposure_proxy_summary.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"\n  written to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
