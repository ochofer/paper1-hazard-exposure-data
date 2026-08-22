"""
Cross-check: is the identifier my ownership data gives me actually the
listed parent company?

WHY I WROTE THIS
When a company drops out of my cross-section I need to know whether that is a
genuine coverage limit or a bug in the identifier. Global Energy Monitor's
identifier sometimes belongs to an operating subsidiary rather than to the
listed parent, and those two cases require opposite responses.

Their ownership data is a single source. GLEIF is the only free, independent
check on it, so I use GLEIF to audit the ownership data rather than to extend
it. Auditing a source against itself proves nothing.

WHAT AN LEI IS
A Legal Entity Identifier is a twenty-character code identifying a legally
distinct organisation. It is issued under a global system run by GLEIF, which
publishes the whole register free. Being a legal entity is not the same as
being a listed company, which is exactly the gap these checks probe.

I run three checks against the 328-company cross-section produced by
00_coverage_and_crosswalk.py:

  A. EXISTENCE.  Does GEM's LEI resolve to a real record in the GLEIF Level 1
     golden copy at all, and is that record ACTIVE?

  B. CATEGORY.   GLEIF classifies entities as GENERAL, FUND, BRANCH,
     SOLE_PROPRIETOR or RESIDENT_GOVERNMENT_ENTITY. Anything that is not
     GENERAL cannot be the listed operating parent of a power station.

  C. CONSOLIDATION. The Level 2 relationship file records
     IS_ULTIMATELY_CONSOLIDATED_BY edges. If GEM's LEI appears as the CHILD of
     such an edge, GLEIF is saying that entity is consolidated into someone
     else's accounts, which is the signature of a subsidiary LEI.

WHY THIS IS A SCREEN RATHER THAN A DELETION RULE
Accounting consolidation is a different thing from being unlisted. Snam, Endesa,
Buzzi and Associated British Foods are all genuinely listed and genuinely
consolidated by a controlling shareholder. So check C produces a list for me to audit by hand.
Three cases live inside it and only a human can separate them:

  1. listed firm with a controlling shareholder  -> keep, it trades
  2. non-traded subsidiary of a listed parent    -> replace with the parent
  3. not an equity at all (fund, municipal arm)  -> drop

Inputs, all free and openly licensed (GLEIF publishes under CC0):
  - GLEIF Level 1 LEI-CDF golden copy, the .csv.zip
  - GLEIF Level 2 RR-CDF golden copy, the .csv
  - outputs/cross_section.csv from 00_coverage_and_crosswalk.py

Memory note: the Level 1 file is about 6 GB uncompressed and 338 columns wide.
Do not unzip it. This script streams it row by row straight out of the zip and
keeps 9 columns, which is why it runs in a few hundred MB instead of falling
over.

Usage:  python 03_gleif_crosscheck.py
"""

import csv
import io
import os
import zipfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data", "GLEIF Data")
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)

LEI1_ZIP = os.path.join(DATA, "20260819-0000-gleif-goldencopy-lei2-golden-copy.csv.zip")
RR_CSV = os.path.join(DATA, "20260819-0000-gleif-goldencopy-rr-golden-copy.csv")
CROSS = os.path.join(OUT, "cross_section.csv")

# The nine-column extract is a ~300 MB derived cache, not a result, so it lives
# under Data/derived and is git-ignored rather than sitting in outputs.
DERIVED = os.path.join(HERE, "..", "Data", "derived")
os.makedirs(DERIVED, exist_ok=True)
SLIM = os.path.join(DERIVED, "gleif_level1_slim.csv")

# Column positions in the 338-column Level 1 golden copy. Positions rather than
# names because reading the header of a 6 GB file just to get names is wasteful,
# but the script asserts the header matches before trusting them.
LEI1_COLS = {
    0: ("lei", "LEI"),
    1: ("name", "Entity.LegalName"),
    55: ("hq_country", "Entity.HeadquartersAddress.Country"),
    190: ("jurisdiction", "Entity.LegalJurisdiction"),
    191: ("category", "Entity.EntityCategory"),
    199: ("entity_status", "Entity.EntityStatus"),
    202: ("expiration_reason", "Entity.EntityExpirationReason"),
    203: ("successor_lei", "Entity.SuccessorEntity.1.SuccessorLEI"),
    315: ("reg_status", "Registration.RegistrationStatus"),
}

RR_COLS = [
    "Relationship.StartNode.NodeID",
    "Relationship.EndNode.NodeID",
    "Relationship.RelationshipType",
    "Relationship.RelationshipStatus",
    "Registration.RegistrationStatus",
]


def slim_level1():
    """Stream the Level 1 zip and keep nine columns. Cached, because this is
    the slow step at roughly three and a half million records."""
    # Size guard: an interrupted run leaves a short or empty cache behind, and
    # silently reusing it would understate GLEIF coverage. Anything under
    # 100 MB is treated as incomplete and rebuilt.
    if os.path.exists(SLIM) and os.path.getsize(SLIM) > 100_000_000:
        print(f"using cached {os.path.basename(SLIM)}")
        return pd.read_csv(SLIM, dtype=str).fillna("")

    print("streaming the Level 1 golden copy out of the zip ...")
    z = zipfile.ZipFile(LEI1_ZIP)
    inner = z.namelist()[0]
    idx = sorted(LEI1_COLS)
    n = 0
    with z.open(inner) as f, open(SLIM, "w", newline="") as out:
        t = io.TextIOWrapper(f, encoding="utf-8", newline="")
        r = csv.reader(t)
        header = next(r)
        # Fail loudly if GLEIF ever reorders the file. Reading by position is
        # fast but silently wrong if the layout changes, so it is checked.
        for i in idx:
            short, expected = LEI1_COLS[i]
            assert header[i] == expected, (
                f"column {i} is {header[i]!r}, expected {expected!r}. "
                "The Level 1 layout has changed, fix LEI1_COLS before trusting this.")
        w = csv.writer(out)
        w.writerow([LEI1_COLS[i][0] for i in idx])
        for line in r:
            if len(line) > max(idx):
                w.writerow([line[i] for i in idx])
                n += 1
    print(f"  {n:,} LEI records kept")
    return pd.read_csv(SLIM, dtype=str).fillna("")


def main():
    cs = pd.read_csv(CROSS)
    cs["has_lei"] = cs.has_lei.astype(bool)
    have = cs[cs.has_lei].copy()
    print(f"cross-section: {len(cs)} firms, {len(have)} carrying an LEI")

    L = slim_level1()
    name = dict(zip(L.lei, L.name))
    country = dict(zip(L.lei, L.hq_country))
    status = dict(zip(L.lei, L.entity_status))
    category = dict(zip(L.lei, L.category))

    # ---- A. existence and status ----------------------------------------
    print("\n=== A. does GEM's LEI resolve in GLEIF, and is it ACTIVE? ===")
    have["in_gleif"] = have.lei.isin(set(L.lei))
    have["gleif_status"] = have.lei.map(status)
    have["gleif_category"] = have.lei.map(category)
    print(f"resolve in GLEIF : {have.in_gleif.sum()} of {len(have)}")
    if (~have.in_gleif).any():
        print(have[~have.in_gleif][["name", "hq", "n_assets", "lei"]].to_string(index=False))
    print(f"ACTIVE           : {(have.gleif_status == 'ACTIVE').sum()}")

    # ---- B. entity category ---------------------------------------------
    print("\n=== B. GLEIF entity category ===")
    print(have.gleif_category.value_counts().to_string())
    odd = have[have.gleif_category != "GENERAL"]
    if len(odd):
        print("\nnot GENERAL, so cannot be a listed operating parent:")
        print(odd[["name", "hq", "n_assets", "gleif_category"]].to_string(index=False))

    # ---- C. consolidation ------------------------------------------------
    print("\n=== C. is GEM's LEI consolidated into someone else's accounts? ===")
    rr = pd.read_csv(RR_CSV, dtype=str, usecols=RR_COLS)
    rr = rr[(rr["Relationship.RelationshipStatus"] == "ACTIVE")
            & (rr["Registration.RegistrationStatus"] == "PUBLISHED")
            & (rr["Relationship.RelationshipType"] == "IS_ULTIMATELY_CONSOLIDATED_BY")]
    rr = rr[["Relationship.StartNode.NodeID", "Relationship.EndNode.NodeID"]]
    rr.columns = ["lei", "parent_lei"]

    flag = have[["name", "hq", "n_assets", "lookthrough_assets", "lei"]].merge(
        rr, on="lei", how="inner")
    flag["parent_name"] = flag.parent_lei.map(name)
    flag["parent_country"] = flag.parent_lei.map(country)
    flag["parent_in_cross_section"] = flag.parent_lei.isin(set(have.lei))
    flag = flag.sort_values("n_assets", ascending=False)

    print(f"flagged as consolidated by a parent : {flag.lei.nunique()} of {len(have)} "
          f"({100*flag.lei.nunique()/len(have):.1f}%)")
    print(f"assets sitting on flagged entities  : {flag.n_assets.sum():,}")
    print(f"whose parent is ALSO in the cross-section (double-count risk): "
          f"{flag.parent_in_cross_section.sum()}")
    print("\nHAND-AUDIT LIST. Consolidation is not the same as unlisted, so each")
    print("row needs a human call: keep, replace with parent, or drop.\n")
    print(flag[["name", "hq", "n_assets", "parent_name",
                "parent_country", "parent_in_cross_section"]].to_string(index=False))

    flag.to_csv(os.path.join(OUT, "gleif_consolidation_flags.csv"), index=False)
    have.drop(columns=["in_gleif"]).to_csv(
        os.path.join(OUT, "cross_section_gleif_audited.csv"), index=False)
    print(f"\nwritten to {os.path.abspath(OUT)}")
    print("  gleif_consolidation_flags.csv, cross_section_gleif_audited.csv")


if __name__ == "__main__":
    main()
