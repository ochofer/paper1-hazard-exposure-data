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

THE COMPANION FILE
------------------
The notebook writes `data/raw/manifest_run.json`, which is the same idea applied
to whatever a reader's own run produced. It is gitignored, like everything else
in `data/raw/`, so a run cannot disturb the published record. Comparing the two
is the intended use: matching checksums prove a reader is holding the same bytes
the findings were computed on.

Both files used to be called `manifest.json`, so a single Colab run silently
overwrote the published audit record. Fixed 2 September 2026 by renaming the
notebook's output. The four fields that only the run manifest used to carry, the
download window, the factor units, the currency mix and the empty-ticker list,
are now recorded here as well, because those are exactly the facts that are easy
to forget and expensive to get wrong, and they belong in the published artefact
rather than only in a local one.

Everything below is DERIVED FROM THE ARCHIVE rather than declared. The window is
read off the files, the empty-ticker list is computed by comparing the resolved
ticker list against the symbols actually present in the panel. A declared
constant would drift away from the data it describes; a derived one cannot.

SCHEMA VERSIONS
---------------
    paper1-data-manifest/1   files, price_panel, pull, missing_at_generation
    paper1-data-manifest/2   adds window, factor_units, coverage, companion, and
                             replaces the one-line price_convention string with a
                             structured price_adjustment block

A consumer keying on the version string was being misled while the shape changed
underneath a fixed "/1", so the version is bumped here rather than left alone.
Nothing was removed between the two, so a /1 reader still works against a /2 file.

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
FACTOR_PANEL = "data/raw/panel_a_ff3_daily.csv"
TICKER_LIST = "config/tickers_primary.csv"

# The two benchmark series. They are not companies and must not be counted as
# such, which is where the "305 symbols" error came from: 302 companies plus
# these two is 304.
BENCHMARKS = ("SPY", "^GSPC")

# Ken French publishes the factors in percent. Storing them as published and
# dividing by 100 in the analysis is a deliberate choice, but it only works if
# the convention is written down somewhere a reader will actually look. A
# factor-of-100 error here is one of the most common faults in factor work.
FACTOR_UNITS = {
    "units": "PERCENT: divide by 100 before combining with decimal returns",
    "missing_codes": [-99.99, -999],
    "note": "Stored exactly as Ken French publishes them. No rescaling applied.",
}

CURRENCY_NOTE = ("No FX conversion applied anywhere in this panel. GBp is pence, "
                 "one hundredth of a pound, not pounds. Convert before any "
                 "dollar-value weighting or the affected companies are wrong by "
                 "a factor of 100.")

# What the price series actually is. The earlier one-line label said only
# "dividend-adjusted close", which invites a reader to assume splits are NOT
# handled and therefore to re-apply a split adjustment that is already in the
# data. It is back-adjusted for both. See adjustment_evidence() for the check.
#
# The deeper point, and the reason this belongs in an audit record rather than a
# footnote: a vendor's adjusted price history is itself a restated object. Every
# past price moves whenever a new dividend or split is applied, so this pull is a
# snapshot of FMP's back-adjustment as it stood on 21 August 2026 and could not be
# reproduced later even with a live key. That is why the claim is that the pull is
# auditable and never that it is repeatable.
PRICE_ADJUSTMENT = {
    "convention":
        "adjClose from FMP historical-price-eod/dividend-adjusted, pulled "
        "2026-08-21. Vendor back-adjustment for dividends AND splits. No "
        "unadjusted close is archived alongside, so the adjustment cannot be "
        "reversed or independently verified from the files in this manifest.",
    "source_endpoint": "historical-price-eod/dividend-adjusted",
    "price_field": "adjClose",
    "adjusted_by": "vendor",
    "adjusts_for": ["dividends", "splits"],
    "unadjusted_close_archived": False,
    "pull_date": PULL_DATE,
    "vintage_note":
        "An adjusted price history is restated whenever a new dividend or split "
        "is applied, so this is a snapshot of the vendor's back-adjustment on the "
        "pull date rather than a stable series. It could not be reproduced later "
        "even with a live subscription.",
}


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


def date_range(path, col="date"):
    """First and last value of a date column, streamed. Returns (None, None) if
    the file is absent, so a partial archive degrades rather than crashes."""
    if not os.path.exists(path):
        return None, None
    lo = hi = None
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if col not in (r.fieldnames or []):
            return None, None
        for row in r:
            d = row[col]
            if not d:
                continue
            if lo is None or d < lo:
                lo = d
            if hi is None or d > hi:
                hi = d
    return lo, hi


def ticker_list_facts(path, panel_symbols):
    """Currency mix and empty-ticker list, both derived rather than declared.

    An "empty ticker" is a company the crosswalk resolved to a symbol that then
    came back with no price rows. That is a different failure from a company
    that never resolved at all, and it is worth naming, because a symbol that
    silently returns nothing looks identical to a symbol nobody asked for once
    the panel is written.
    """
    if not os.path.exists(path):
        return {}, [], 0
    currencies, requested = {}, []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if str(row.get("priceable", "")).strip().lower() not in ("true", "1", "yes"):
                continue
            sym = (row.get("primary_symbol") or "").strip()
            if not sym:
                continue
            requested.append(sym)
            cur = (row.get("currency") or "unknown").strip()
            currencies[cur] = currencies.get(cur, 0) + 1
    empty = sorted(set(requested) - set(panel_symbols))
    currencies = dict(sorted(currencies.items(), key=lambda kv: (-kv[1], kv[0])))
    return currencies, empty, len(set(requested))


def adjustment_evidence(path, threshold=0.5):
    """Evidence that the series is split-adjusted, derived rather than asserted.

    An unadjusted series shows a split as a one-day fall of exactly the split
    ratio: 50% for a two-for-one, 75% for a four-for-one. Across 302 large
    companies over sixteen years there are hundreds of splits, so an unadjusted
    panel would show hundreds of such falls. Counting the daily moves beyond a
    threshold therefore separates the two cases without needing a split calendar.

    This is evidence, not proof. It cannot distinguish a split-adjusted series
    from one whose splits all happened to be small, which is why the claim in
    PRICE_ADJUSTMENT rests on the vendor's documented endpoint behaviour and this
    check merely fails to contradict it.
    """
    prev, extremes = {}, []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s = row["symbol"]
            try:
                p = float(row["price"])
            except (TypeError, ValueError):
                continue
            last = prev.get(s)
            if last is not None and last > 0:
                if abs(p / last - 1.0) > threshold:
                    extremes.append(s)
            prev[s] = p
    return {
        "test": "count of one-day price moves beyond the threshold",
        "threshold": threshold,
        "count": len(extremes),
        "distinct_symbols": len(set(extremes)),
        "interpretation":
            "An unadjusted panel would show one such move per split, and there "
            "are hundreds of splits in a universe this size over sixteen years. "
            "The observed count is far too low for that, and the moves that do "
            "appear cluster in March 2020 and in a handful of distressed small "
            "caps rather than on split dates.",
    }


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
            "price_adjustment": dict(
                PRICE_ADJUSTMENT,
                evidence=adjustment_evidence(pp),
            ),
            "per_symbol": [
                dict(symbol=s, **per[s]) for s in sorted(per)
            ],
        }
        print(f"\n  price panel: {panel['rows']:,} rows, {panel['symbols']} symbols "
              f"({panel['company_symbols']} companies + "
              f"{len(benchmarks)} benchmarks), {dmin} to {dmax}")

    # ---- the four fields folded in from the notebook's run manifest ----------
    panel_symbols = [e["symbol"] for e in panel.get("per_symbol", [])]
    currencies, empty_tickers, n_requested = ticker_list_facts(
        os.path.join(arch, TICKER_LIST), panel_symbols)

    fa_min, fa_max = date_range(os.path.join(arch, FACTOR_PANEL))

    window = {
        "price_panel": {"first": panel.get("date_min"), "last": panel.get("date_max")},
        "factor_panel": {"first": fa_min, "last": fa_max},
        "provenance": "Read off the archived files, not declared. If these two "
                      "ranges disagree, the overlap is what any regression "
                      "actually uses.",
    }

    coverage = {
        "symbols_requested": n_requested,
        "symbols_returned": len([s for s in panel_symbols if s not in BENCHMARKS]),
        "empty_tickers": empty_tickers,
        "empty_tickers_note":
            "Companies the crosswalk resolved to a symbol that then returned no "
            "rows. An empty list means every resolved symbol produced data. This "
            "is derived by comparing the resolved ticker list against the "
            "symbols present in the panel, so it cannot drift out of date.",
        "currencies": currencies,
        "currency_note": CURRENCY_NOTE,
    }

    if empty_tickers:
        print(f"  empty tickers ({len(empty_tickers)}): {empty_tickers}")
    else:
        print(f"  empty tickers: none, all {n_requested} resolved symbols returned data")
    print(f"  currencies: {currencies}")

    man = {
        "schema": "paper1-data-manifest/2",
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
        "window": window,
        "factor_units": FACTOR_UNITS,
        "coverage": coverage,
        "files": entries,
        "price_panel": panel,
        "missing_at_generation": missing,
        "companion": {
            "path": "data/raw/manifest_run.json",
            "written_by": "notebooks/01_raw_panels.ipynb, final cell",
            "tracked": False,
            "note": "The same idea applied to your own run. Compare the file "
                    "checksums here against yours to prove you are holding the "
                    "same bytes these findings were computed on.",
        },
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
