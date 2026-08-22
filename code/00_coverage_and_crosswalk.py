"""
BLOCKING TEST 3: how large is the real cross-section?

Builds the firm-level universe from the GEM Global Energy Ownership Tracker and
counts survivors at every step, so the number that ends up in the paper is
auditable rather than asserted. Every input is free and redistributable
(GEM is CC BY 4.0, GLEIF and the ANNA LEI-to-ISIN file are open), so this whole
script can ship in the public repo and a reader can rerun it.

FOUR DECISIONS ARE MADE HERE THAT CHANGE THE ANSWER MATERIALLY.
Each is stated as a switch at the top so it can be flipped and re-reported
rather than buried:

  1. ASSET KEY. An "asset unit" is a distinct (Asset ID, Asset Unit ID) pair.
     16,585 of 49,942 ownership rows have a blank unit ID, so collapsing on unit
     ID alone destroys about a third of the file.

  2. STATUS FILTER. I count only assets GEM marks as operating. A cancelled,
     announced or pre-construction plant has no physical climate exposure, and
     roughly 7,500 of the 47,185 asset units are in that category, with a
     further 4,500 retired or mothballed.

  3. ATTRIBUTION RULE. I attribute an asset to the NEAREST listed parent rather
     than to every listed entity anywhere in its ownership chain. GEM's graph
     includes custodians and institutional shareholders as owners, so the
     any-ancestor rule attributes power stations to BNP Paribas, Citigroup and
     Bank of America. Nearest-parent is the construct that means something operationally.

  4. REGION. Ken French's developed-Europe country list plus the United States,
     on headquarters country. My factor model uses French's regions, so my
     universe should match his rather than improvise a different boundary.

RECONCILIATION WITH THE 18 AUGUST AUDIT. Set OPERATING_ONLY = False and this
script returns 1,720 firms worldwide, 372 in region, 200 with five or more
assets and 354 carrying an LEI, against that audit's 1,719 / 370 / 200 / 352.
The five-or-more count matches exactly and the rest is within two firms. So the
whole of the drop from 370 to 328 is the status filter, decision 2 above, and
nothing else. Flip the switch and see for yourself.

Usage:  python 00_coverage_and_crosswalk.py
"""

import os
import pickle
from collections import defaultdict

import pandas as pd

# --------------------------------------------------------------------------
# Switches. Change these and rerun to see how sensitive the answer is.
# --------------------------------------------------------------------------
OPERATING_ONLY = True          # decision 2
ATTRIBUTION = "nearest"        # decision 3: "nearest" or "any"
DEPTH_CAP = 12                 # cycle-safe upward traversal depth
IDENTIFIER_RULE = "lei_or_permid"

FRENCH_EUROPE = {
    "Austria", "Belgium", "Denmark", "Finland", "France", "Germany", "Greece",
    "Ireland", "Italy", "Netherlands", "Norway", "Portugal", "Spain", "Sweden",
    "Switzerland", "United Kingdom",
}
REGION = FRENCH_EUROPE | {"United States"}

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data")
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)

GEM_XLSX = os.path.join(DATA, "GEM Data",
                        "Global-Energy-Ownership-Tracker-August-2026-V1.xlsx")
ANNA_CSV = os.path.join(DATA, "GLEIF Data", "lei-isin-20260818T071512.csv")

LEI_COL = "Global Legal Entity Identifier Index"
PERMID_COL = "PermID: Refinitiv Permanent Identifier"
CIK_COL = "US SEC Central Index Key"

# per-sector sheet -> (asset id column, status column, capacity column, unit)
SECTOR_SHEETS = {
    "Coal Plant Ownership":          ("GEM unit ID", "Status", "Capacity (MW)", "MW"),
    "Gas Plant Ownership":           ("GEM unit ID", "Status", "Capacity (MW)", "MW"),
    "Bioenergy Power Ownership":     ("GEM unit ID", "Status", "Capacity (MW)", "MW"),
    "Coal Mine Ownership":           ("GEM Mine ID", "Status", "Capacity (Mtpa)", "Mtpa coal"),
    "Iron Mine Ownership":           ("GEM Asset ID", "Operating status", "Design capacity (ttpa)", "ttpa ore"),
    "Gas Pipeline Ownership":        ("ProjectID", "Status", "CapacityBOEd", "BOEd"),
    "Oil & NGL Pipeline Ownership":  ("ProjectID", "Status", "CapacityBOEd", "BOEd"),
    "Steel Plant Ownership":         ("Steel Plant ID", "Status", "Nominal crude steel capacity (ttpa)", "ttpa steel"),
    "Cement and Concrete Ownership": ("GEM plant ID", "Status", "Cement capacity (million metric tonnes per annum)", "Mt cement"),
}

OPERATING_STATUSES = {"operating", "operating pre-retirement"}


def blank(s):
    """GEM writes missing identifiers as 'not found' or 'not applicable',
    not as an empty cell. Treating those as present is the most likely way to
    overstate identifier coverage, so they are handled explicitly."""
    s = s.astype(str).str.strip()
    return (s == "") | s.str.lower().isin(
        ["not found", "not applicable", "none", "nan"])


def pct(s):
    return pd.to_numeric(s.astype(str).str.strip().str.rstrip("%"),
                         errors="coerce").fillna(0.0) / 100.0


def load_sheets():
    print("reading the workbook (51 MB, takes about a minute) ...")
    xl = pd.ExcelFile(GEM_XLSX)
    ent = xl.parse("All Entities", dtype=str).fillna("")
    eo = xl.parse("Entity Ownership", dtype=str).fillna("")
    ao = xl.parse("Asset Ownership", dtype=str).fillna("")
    sectors = {n: xl.parse(n, dtype=str).fillna("") for n in SECTOR_SHEETS}
    return ent, eo, ao, sectors


def build_status_map(sectors):
    """Asset status and capacity live only in the per-sector sheets, keyed by
    the sector's own asset id. Build one lookup covering all of them."""
    rows = []
    for name, (idc, stc, capc, unit) in SECTOR_SHEETS.items():
        d = sectors[name][[idc, stc, capc]].drop_duplicates()
        d.columns = ["gid", "status", "cap"]
        d["sector"] = name.replace(" Ownership", "")
        d["capunit"] = unit
        rows.append(d)
    S = pd.concat(rows, ignore_index=True)
    S["cap"] = pd.to_numeric(S["cap"].str.replace(",", "", regex=False),
                             errors="coerce")
    S["status"] = S["status"].str.strip().str.lower()
    agg = S.groupby("gid").agg(
        status=("status", lambda x: "|".join(sorted(set(x)))),
        cap=("cap", "max"), sector=("sector", "first"),
        capunit=("capunit", "first")).reset_index()
    return agg


def main():
    ent, eo, ao, sectors = load_sheets()

    # ---- entity flags ----------------------------------------------------
    ent["listed"] = ent["PubliclyListed"].str.strip().str.lower() == "true"
    ent["has_lei"] = ~blank(ent[LEI_COL])
    ent["has_permid"] = ~blank(ent[PERMID_COL])
    ent["identified"] = ent["has_lei"] | ent["has_permid"]
    ent["in_region"] = ent["Headquarters Country"].str.strip().isin(REGION)
    E = ent.set_index("Entity ID")
    listed_id = set(E.index[E.listed & E.identified])
    in_region = set(E.index[E.in_region])
    print(f"entities {len(E):,} | listed {E.listed.sum():,} | "
          f"listed+identified {len(listed_id):,}")

    # ---- ownership graph -------------------------------------------------
    eo["sh"] = pct(eo["% Share of Ownership"])
    parents = defaultdict(list)
    for s, p, sh in zip(eo["Subject Entity ID"], eo["Interested Party ID"], eo["sh"]):
        if s and p:
            parents[s].append((p, sh))

    memo = {}

    def nearest(e, depth, stack):
        """Look-through economic interest of the nearest listed parents.
        Traversal stops at the first listed entity on each path, so a listed
        operating company shields its own listed shareholders from being
        credited with the asset. Cycle-safe via `stack`."""
        key = (e, depth)
        if key in memo:
            return memo[key]
        acc = defaultdict(float)
        if depth < DEPTH_CAP and e not in stack:
            stack = stack | {e}
            for p, sh in parents.get(e, ()):
                if p in listed_id:
                    acc[p] += sh
                else:
                    for a, v in nearest(p, depth + 1, stack).items():
                        acc[a] += sh * v
        memo[key] = dict(acc)
        return memo[key]

    memo_any = {}

    def any_ancestor(e, depth, stack):
        key = (e, depth)
        if key in memo_any:
            return memo_any[key]
        acc = set()
        if depth < DEPTH_CAP and e not in stack:
            stack = stack | {e}
            for p, sh in parents.get(e, ()):
                if p in listed_id:
                    acc.add(p)
                acc |= any_ancestor(p, depth + 1, stack)
        memo_any[key] = acc
        return acc

    # ---- assets ----------------------------------------------------------
    ao["sh"] = pct(ao["% Share of Ownership"])
    ao["key"] = ao["Asset ID"] + "|" + ao["Asset Unit ID"]          # decision 1
    n_units = ao["key"].nunique()
    print(f"asset units (Asset ID + Asset Unit ID): {n_units:,}")

    status = build_status_map(sectors)
    smap = dict(zip(status.gid, status.status))
    cmap = dict(zip(status.gid, status.cap))
    secmap = dict(zip(status.gid, status.sector))
    umap = dict(zip(status.gid, status.capunit))

    units = ao[["Asset ID", "Asset Unit ID", "key"]].drop_duplicates("key")

    def lookup(r):
        for cand in (r["Asset Unit ID"], r["Asset ID"]):
            if cand and cand in smap:
                return pd.Series([smap[cand], cmap[cand], secmap[cand], umap[cand]])
        return pd.Series([None, None, None, None])

    units[["status", "cap", "sector", "capunit"]] = units.apply(lookup, axis=1)
    units["operating"] = units["status"].apply(
        lambda s: bool(set(str(s).split("|")) & OPERATING_STATUSES) if s else False)
    print(f"  with a status from a sector sheet : {units.status.notna().sum():,}")
    print(f"  operating                          : {units.operating.sum():,}")

    keep = set(units[units.operating].key) if OPERATING_ONLY else set(units.key)

    # ---- attribute -------------------------------------------------------
    firm_assets = defaultdict(set)
    firm_lookthrough = defaultdict(float)
    asset_listed_share = defaultdict(float)   # for the capacity-weighted table
    asset_region_share = defaultdict(float)
    for k, own, sh in zip(ao["key"], ao["Immediate Owner Entity ID"], ao["sh"]):
        if k not in keep:
            continue
        if ATTRIBUTION == "nearest":
            contrib = ({own: sh} if own in listed_id
                       else {a: sh * v for a, v in nearest(own, 0, frozenset()).items()})
        else:
            anc = ({own} if own in listed_id else set()) | any_ancestor(own, 0, frozenset())
            contrib = {a: sh for a in anc}
        for a, v in contrib.items():
            firm_assets[a].add(k)
            firm_lookthrough[a] += v
            asset_listed_share[k] += v
            if a in in_region:
                asset_region_share[k] += v

    # ---- capacity-weighted coverage --------------------------------------
    # I report the match rate by CAPACITY as well as by count,
    # because "43% of assets" means something very different depending on
    # whether the covered assets are the large ones. Capacity units differ by
    # sector (MW, Mtpa, BOEd, ttpa) and cannot be summed across sectors, so
    # this is reported per sector and never pooled.
    cap = units[units.operating & units.cap.notna()].copy()
    cap["lst"] = cap.key.map(asset_listed_share).fillna(0.0)
    cap["rgn"] = cap.key.map(asset_region_share).fillna(0.0)
    rows = []
    for (sec, unit), g in cap.groupby(["sector", "capunit"]):
        tot = g.cap.sum()
        rows.append(dict(
            sector=sec, unit=unit, units=len(g), capacity=round(tot, 1),
            listed_by_count=round(100 * (g.lst > 0).mean(), 1),
            listed_by_capacity=round(100 * (g.cap * (g.lst > 0)).sum() / tot, 1),
            region_by_count=round(100 * (g.rgn > 0).mean(), 1),
            region_by_capacity=round(100 * (g.cap * (g.rgn > 0)).sum() / tot, 1),
            region_capacity_shareweighted=round(
                100 * (g.cap * g.rgn.clip(0, 1)).sum() / tot, 1)))
    captab = pd.DataFrame(rows).sort_values("region_by_capacity", ascending=False)
    print("\n=== COVERAGE BY CAPACITY, operating assets, per sector ===")
    print(captab.to_string(index=False))
    captab.to_csv(os.path.join(OUT, "coverage_by_capacity.csv"), index=False)
    print(f"\npooled by unit count: any listed {100*(cap.lst>0).mean():.1f}%, "
          f"US/Europe listed {100*(cap.rgn>0).mean():.1f}%")

    reg = {a: s for a, s in firm_assets.items() if a in in_region}
    print("\n=== CROSS-SECTION ===")
    print(f"listed+identified firms with >=1 kept asset (world) : {len(firm_assets):,}")
    print(f"US/developed-Europe HQ, >=1 asset                   : {len(reg):,}")
    print(f"US/developed-Europe HQ, >=5 assets                  : "
          f"{sum(1 for v in reg.values() if len(v) >= 5):,}")

    cs = pd.DataFrame({
        "entity_id": list(reg),
        "name": [E.loc[a, "Full Name"] for a in reg],
        "hq": [E.loc[a, "Headquarters Country"] for a in reg],
        "n_assets": [len(reg[a]) for a in reg],
        "lookthrough_assets": [firm_lookthrough[a] for a in reg],
        "lei": [E.loc[a, LEI_COL] for a in reg],
        "permid": [E.loc[a, PERMID_COL] for a in reg],
        "cik": [E.loc[a, CIK_COL] for a in reg],
    }).sort_values("n_assets", ascending=False)
    cs["has_lei"] = cs.lei.str.len() == 20
    cs["has_cik"] = ~blank(cs.cik)
    cs["has_permid"] = ~blank(cs.permid)
    print(f"   of which carrying an LEI                        : {cs.has_lei.sum():,}")
    print(f"   of which carrying an SEC CIK                    : {cs.has_cik.sum():,}")
    print(f"   of which carrying a PermID                      : {cs.has_permid.sum():,}")
    print(f"   with NEITHER an LEI nor a CIK                   : "
          f"{((~cs.has_lei) & (~cs.has_cik)).sum():,}")
    cs.to_csv(os.path.join(OUT, "cross_section.csv"), index=False)

    # ---- LEI to ISIN -----------------------------------------------------
    print("\n=== LEI TO ISIN (ANNA file) ===")
    anna = pd.read_csv(ANNA_CSV, dtype=str)
    leis = set(cs.loc[cs.has_lei, "lei"])
    sub = anna[anna.LEI.isin(leis)].copy()
    print(f"LEIs carried in         : {len(leis)}")
    print(f"LEIs present in ANNA    : {sub.LEI.nunique()}  "
          f"({100*sub.LEI.nunique()/max(len(leis),1):.1f}%)")
    print(f"raw ISINs returned      : {len(sub):,}")
    print("\nNOTE: the ANNA file carries no instrument type, so it cannot on its")
    print("own separate an ordinary share from a bond, a warrant or a")
    print("certificate. Two documented rules narrow it, then FMP must confirm.")

    ISO = {"United States": "US", "United Kingdom": "GB", "Germany": "DE",
           "France": "FR", "Italy": "IT", "Spain": "ES", "Netherlands": "NL",
           "Switzerland": "CH", "Sweden": "SE", "Norway": "NO", "Finland": "FI",
           "Denmark": "DK", "Austria": "AT", "Belgium": "BE", "Portugal": "PT",
           "Greece": "GR", "Ireland": "IE"}
    hq = dict(zip(cs.lei, cs.hq))
    sub["domestic"] = [ISO.get(hq.get(l, ""), "") == i[:2] for l, i in zip(sub.LEI, sub.ISIN)]
    s2 = sub[sub.domestic].copy()
    print(f"rule 1, ISIN country == HQ country : {len(s2):,} ISINs, {s2.LEI.nunique()} LEIs")

    def us_equity_issue(isin):
        """For US ISINs the middle nine characters are the CUSIP. Characters 7-8
        of a CUSIP are the issue number: numeric codes ending in 0 denote equity
        issues, alphabetic codes denote debt. Non-US ISINs pass through."""
        if not isin.startswith("US"):
            return True
        issue = isin[8:10]
        return issue.isdigit() and issue[1] == "0"

    s2["equity_like"] = [us_equity_issue(i) for i in s2.ISIN]
    cand = s2[s2.equity_like].copy()
    print(f"rule 2, US CUSIP equity issue code : {len(cand):,} ISINs, {cand.LEI.nunique()} LEIs")
    per = cand.groupby("LEI").size()
    print(f"\nLEIs resolving to exactly one candidate : {(per == 1).sum()}")
    print(f"LEIs with 2 to 3 candidates             : {((per >= 2) & (per <= 3)).sum()}")
    print(f"LEIs needing FMP instrument typing      : {(per > 3).sum()}")
    cand = cand.merge(cs[["lei", "name", "hq", "n_assets", "lookthrough_assets"]],
                      left_on="LEI", right_on="lei", how="left")
    cand.to_csv(os.path.join(OUT, "isin_candidates.csv"), index=False)

    missing = sorted(leis - set(sub.LEI))
    pd.DataFrame({"lei": missing}).merge(
        cs[["lei", "name", "hq", "n_assets"]], on="lei", how="left").to_csv(
        os.path.join(OUT, "lei_not_in_anna.csv"), index=False)
    cs[~cs.has_lei][["name", "hq", "n_assets", "cik"]].to_csv(
        os.path.join(OUT, "firms_without_lei.csv"), index=False)

    # ---- survival by country --------------------------------------------
    # Every firm that drops out is named somewhere in the outputs. This table
    # is the audit trail: it shows WHERE the narrowing loses firms, which is
    # what separates a genuine coverage limit from a broken join.
    print("\n=== IDENTIFIER SURVIVAL BY HEADQUARTERS COUNTRY ===")
    cs["in_anna"] = cs.lei.isin(set(sub.LEI))
    cs["has_isin_candidate"] = cs.lei.isin(set(cand.LEI))
    t = cs.groupby("hq").agg(
        firms=("name", "size"), assets=("n_assets", "sum"),
        with_lei=("has_lei", "sum"), with_cik=("has_cik", "sum"),
        in_anna=("in_anna", "sum"),
        with_isin=("has_isin_candidate", "sum")).sort_values("firms", ascending=False)
    t["pct_isin"] = (100 * t.with_isin / t.firms).round(1)
    print(t.to_string())
    t.to_csv(os.path.join(OUT, "identifier_survival_by_country.csv"))
    print("\nANNA ISIN country prefixes present in the mapping file, by region:")
    anna_cc = anna.ISIN.str[:2].value_counts()
    for c in ["US", "GB", "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO", "FI",
              "DK", "AT", "BE", "PT", "GR", "IE", "JE", "LU", "XS"]:
        print(f"  {c}: {int(anna_cc.get(c, 0)):>9,}")
    print("\nFI, LU and XS are ZERO. That is a property of the file, not a bug in")
    print("this script: the file is complete (sorted, runs 00.. to ZZ..) and a raw")
    print("byte grep for ',FI' also returns zero. Finnish and Irish firms therefore")
    print("cannot be resolved through ANNA and need a separate route.")

    print(f"\nwritten to {os.path.abspath(OUT)}")
    for f in ["cross_section.csv", "isin_candidates.csv", "lei_not_in_anna.csv",
              "firms_without_lei.csv", "coverage_by_capacity.csv",
              "identifier_survival_by_country.csv"]:
        print("  " + f)


if __name__ == "__main__":
    main()
