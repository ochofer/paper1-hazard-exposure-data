"""
Build data/raw/manifest.json: the audit record for the price pull.

WHY THIS EXISTS
---------------
The price panel comes from Financial Modeling Prep, whose terms require a
separate licensing agreement to redistribute. So the panel itself cannot go in
this repository, and `data/raw/` is gitignored apart from this manifest.

That leaves a hole. A reader can see the fetch code and the resolved company
list, but has no way to check that their own pull matches the one the findings
were computed on. The manifest closes it: checksums, row counts and per-symbol
date coverage, published so that anyone holding their own FMP access can prove
equivalence rather than assume it.

The claim this supports is that the pull is AUDITABLE. It is not that the pull
is REPEATABLE. Repeating it requires a paid FMP subscription.

WHAT IT DELIBERATELY DOES NOT CONTAIN
---------------------------------------
No prices. Checksums, row counts, symbols and date ranges are metadata about a
licensed file, not the licensed data itself. Nothing here would let a reader
reconstruct a single price.

FETCH TIMESTAMPS
----------------
The 21 August 2026 pull did not record per-file fetch timestamps, so this
manifest says so rather than inventing them from filesystem mtimes, which
change when a file is copied. The next extraction must capture real fetch
timestamps at request time; see `capture_fetch_timestamps` in the schema notes.

A COLLISION TO FIX, RECORDED HERE SO IT IS NOT DISCOVERED LATE
----------------------------------------------------------------
The notebook's final cell also writes `data/raw/manifest.json`, with a
different and partly complementary schema: it records the download window, the
factor units, the currency mix and which tickers came back empty, but not
per-symbol date coverage, and it fingerprints only files in `data/raw/`.

So there are currently two producers of one path. That is wrong and should be
resolved by having the notebook write `manifest_run.json` instead, leaving this
file as the single published audit record. It is not urgent, because
`data/raw/manifest.json` is the one path in `data/raw/` that git tracks, so an
overwrite shows up immediately as a modified file rather than passing silently.
It is still a latent trap and it is on the follow-up list.

USAGE
    python3 build_manifest.py                    # default archive location
    python3 build_manifest.py --archive PATH     # elsewhere

The archive lives outside this repository because it is not redistributable.
If it is not present the script says so and writes nothing, rather than
emitting an empty manifest that looks like a real one.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "raw", "manifest.json")

DEFAULT_ARCHIVE = os.path.join(
    HERE, "..", "Data", "FMP Panel B archive", "paper1_data_20260821")

PULL_ID = "fmp_2026-08-21"
PULL_DATE = "2026-08-21"

# Which files belong in the audit record, and whether each may be redistributed.
# The FF3 panels are Ken French's and are free; the config files are already in
# this repository; only the price panel is licensed and withheld.
FILES = [
    ("data/raw/panel_b_prices_daily.csv", "Financial Modeling Prep", False),
    ("data/raw/panel_a_ff3_daily.csv", "Kenneth French Data Library", True),
    ("data/raw/ff3_daily_original.csv", "Kenneth French Data Library", True),
    ("data/raw/blocking_test_1_return_gaps.csv", "derived", True),
    ("data/raw/blocking_test_2_ff3.csv", "derived", True),
    ("data/raw/blocking_test_2_subperiods.csv", "derived", True),
    ("data/raw/blocking_test_2_weighting.csv", "derived", True),
    ("config/tickers_primary.csv", "derived", True),
    ("config/tickers_v1.csv", "derived", True),
    ("config/universe.csv", "derived", True),
    ("config/universe_isins.csv", "GLEIF", True),
    ("config/ticker_overrides.csv", "hand-written", True),
    ("config/tickers_draft_v0.csv", "derived", True),
]

PRICE_PANEL = "data/raw/panel_b_prices_daily.csv"


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def count_rows(path):
    """Data rows, excluding the header. Counted by streaming so a large panel
    does not have to be held in memory."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        n = sum(1 for _ in f)
    return max(0, n - 1)


def price_panel_coverage(path):
    """Per-symbol row count and date range, streamed.

    Deliberately uses the stdlib csv reader rather than pandas so that this
    script has no dependencies and a reader can run it without installing
    anything.
    """
    per = {}
    dmin, dmax = None, None
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "symbol" not in r.fieldnames or "date" not in r.fieldnames:
            raise SystemExit(f"unexpected columns in {path}: {r.fieldnames}")
        for row in r:
            s, d = row["symbol"], row["date"]
            e = per.get(s)
            if e is None:
                per[s] = {"rows": 1, "first_date": d, "last_date": d}
            else:
                e["rows"] += 1
                if d < e["first_date"]:
                    e["first_date"] = d
                if d > e["last_date"]:
                    e["last_date"] = d
            if dmin is None or d < dmin:
                dmin = d
            if dmax is None or d > dmax:
                dmax = d
    return per, dmin, dmax


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default=DEFAULT_ARCHIVE)
    args = ap.parse_args()
    arch = os.path.abspath(args.archive)

    if not os.path.isdir(arch):
        print(f"archive not found: {arch}")
        print("The price archive is not redistributable and lives outside this")
        print("repository. Nothing written.")
        return 1

    entries, missing = [], []
    for rel, source, redist in FILES:
        p = os.path.join(arch, rel)
        if not os.path.exists(p):
            missing.append(rel)
            continue
        e = {
            "path": rel,
            "sha256": sha256(p),
            "bytes": os.path.getsize(p),
            "source": source,
            "redistributable": redist,
        }
        if rel.endswith(".csv"):
            e["rows"] = count_rows(p)
        entries.append(e)
        print(f"  {rel:<44} {e['bytes']:>12,} B  {e['sha256'][:16]}...")

    panel = {}
    pp = os.path.join(arch, PRICE_PANEL)
    if os.path.exists(pp):
        per, dmin, dmax = price_panel_coverage(pp)
        benchmarks = sorted(s for s in per if s in ("SPY", "^GSPC"))
        panel = {
            "file": PRICE_PANEL,
            "rows": sum(v["rows"] for v in per.values()),
            "symbols": len(per),
            "benchmark_symbols": benchmarks,
            "company_symbols": len(per) - len(benchmarks),
            "date_min": dmin,
            "date_max": dmax,
            "price_convention": "dividend-adjusted close, single convention "
                                "across the whole panel",
            "per_symbol": [
                dict(symbol=s, **per[s]) for s in sorted(per)
            ],
        }
        print(f"\n  price panel: {panel['rows']:,} rows, {panel['symbols']} symbols "
              f"({panel['company_symbols']} companies + "
              f"{len(benchmarks)} benchmarks), {dmin} to {dmax}")

    man = {
        "schema": "paper1-data-manifest/1",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "build_manifest.py",
        "pull": {
            "id": PULL_ID,
            "source": "Financial Modeling Prep",
            "pull_date": PULL_DATE,
            "pull_date_provenance":
                "declared, from the archive README. Per-file fetch timestamps "
                "were not captured for this pull and are not inferred from "
                "filesystem mtimes, which change when a file is copied.",
            "capture_fetch_timestamps":
                "TODO for the next extraction: record the request time per "
                "symbol at fetch time, not afterwards.",
            "redistributable": False,
            "repeatable_without_payment": False,
            "note":
                "This manifest makes the pull auditable, not repeatable. "
                "Rebuilding the price layer requires a paid FMP subscription. "
                "Every other input in this repository is free and "
                "redistributable.",
        },
        "files": entries,
        "price_panel": panel,
        "missing_at_generation": missing,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, sort_keys=False)
        f.write("\n")
    print(f"\n  wrote {OUT}  ({os.path.getsize(OUT):,} bytes)")
    if missing:
        print(f"  NOT FOUND in the archive, recorded as missing: {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
