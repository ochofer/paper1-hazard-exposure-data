#!/usr/bin/env python3
"""
20_fmp_extract.py -- bulk extraction from Financial Modeling Prep before cancellation.

Implements HANDOVER_FMP_extraction_2026-08-28.md section 3.

Hard rules, each of which has cost this project something once:
  * Never overwrite an existing raw file. Skip it, or write beside it with a suffix.
  * Sort every collection of symbols before iterating. Never iterate a set.
  * Save the response body exactly as returned, before any parsing.
  * Resumable: skip what is already on disk, survive interruption.
  * Throttle deliberately; back off on 429; hard-stop rather than risk a ban.
  * The key comes from .env. Never a literal, never a filename, never stdout.

Usage:
    python3 20_fmp_extract.py --tier 1                 # tier 1 only
    python3 20_fmp_extract.py --tier 1 --dry-run       # plan without calling
    python3 20_fmp_extract.py --tier 1 --tier 2 --tier 3

Requires FMP_API_KEY in .env (repo root) or the environment.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# --------------------------------------------------------------------------
# Paths. Raw data lands OUTSIDE the git repo. The manifest is the only artefact
# that goes back into the repo, at data/raw/manifest.json, which .gitignore
# un-ignores by name. Nothing else pulled here is ever committed.
# --------------------------------------------------------------------------
PROJECT   = Path(__file__).resolve().parent.parent          # "Finance Project A"
REPO      = PROJECT / "repo_paper1_data"
OUT       = PROJECT / "Data" / "FMP extraction 2026-09"     # private, outside the repo
RAW       = OUT / "raw"
VENDOR_DCF = OUT / "vendor_dcf_DO_NOT_OPEN"                 # sequencing rule, section 2
LEDGER    = OUT / "manifest_entries.jsonl"                  # append-only, resumable
STATE     = OUT / "throttle_state.json"

# --------------------------------------------------------------------------
# Rate limiting. Set these from the plan's documented caps before the first run.
# Deliberately conservative: a ban a week before cancellation is the one
# unrecoverable failure mode.
# --------------------------------------------------------------------------
CALLS_PER_MINUTE   = 240        # confirm against the plan, then lower if unsure
DAILY_CAP          = 100_000    # confirm against the plan
MIN_INTERVAL       = 60.0 / CALLS_PER_MINUTE
BACKOFF_BASE       = 5.0
BACKOFF_MAX        = 600.0
MAX_RETRIES        = 6
CONSECUTIVE_429_STOP = 5        # hard stop; do not push into a ban

BASE_STABLE = "https://financialmodelingprep.com/stable"
BASE_V3     = "https://financialmodelingprep.com/api/v3"

WINDOW_FROM = "1990-01-01"      # ask for everything; record what actually came back
WINDOW_TO   = None              # None = today


# --------------------------------------------------------------------------
# Endpoint registry.
#
# scope="per_symbol"  -> one call and one file per symbol
# scope="per_fx"      -> one call and one file per currency pair
# scope="once"        -> one call, one file
#
# ATTENTION: these paths and parameter names are FMP's REST API. They were NOT
# verifiable through the MCP connector on 2 September 2026, because the connector
# authenticates against a plan below Starter and refused chart, statements,
# company/historical-market-cap, analyst, directory, search, indexes,
# discountedCashFlow, earningsTranscript, ESG and form13F. Probe each one against
# the real key with --probe before trusting the shape.
# --------------------------------------------------------------------------
ENDPOINTS = [
    # ---- tier 1, blocking -------------------------------------------------
    dict(tier=1, name="price_eod_full",            base=BASE_STABLE, path="historical-price-eod/full",
         scope="per_symbol", dated=True,
         note="tier 1 items 1 and 2: unadjusted OHLC plus volume"),
    dict(tier=1, name="price_eod_dividend_adj",    base=BASE_STABLE, path="historical-price-eod/dividend-adjusted",
         scope="per_symbol", dated=True,
         note="tier 1 item 1: adjusted series, kept alongside the raw one"),
    dict(tier=1, name="price_eod_non_split_adj",   base=BASE_STABLE, path="historical-price-eod/non-split-adjusted",
         scope="per_symbol", dated=True,
         note="tier 1 item 1: so the total-return convention can be reconstructed"),
    dict(tier=1, name="dividends",                 base=BASE_STABLE, path="dividends",
         scope="per_symbol", dated=False,
         note="tier 1 item 1: dividends separately, not trusted from the adjusted series"),
    dict(tier=1, name="splits",                    base=BASE_STABLE, path="splits",
         scope="per_symbol", dated=False,
         note="tier 1 item 1: splits separately"),
    dict(tier=1, name="historical_market_cap",     base=BASE_STABLE, path="historical-market-capitalization",
         scope="per_symbol", dated=True,
         note="tier 1 item 3: CONFIRMED blocking, needed for parent-index cap weights"),
    dict(tier=1, name="shares_float",              base=BASE_STABLE, path="shares-float",
         scope="per_symbol", dated=False,
         note="tier 1 item 3: shares outstanding"),
    dict(tier=1, name="profile",                   base=BASE_STABLE, path="profile",
         scope="per_symbol", dated=False,
         note="tier 1 item 4: sector, industry, country, exchange, currency, ISIN, CUSIP, CIK"),
    dict(tier=1, name="delisted_companies",        base=BASE_STABLE, path="delisted-companies",
         scope="once", dated=False, paged=True,
         note="tier 1 item 5: the full delisted list, paged to exhaustion"),
    dict(tier=1, name="fx_eod",                    base=BASE_STABLE, path="historical-price-eod/full",
         scope="per_fx", dated=True,
         note="tier 1 item 6: nine currencies against USD and EUR"),

    # ---- tier 2 -----------------------------------------------------------
    dict(tier=2, name="income_statement_annual",   base=BASE_STABLE, path="income-statement",
         scope="per_symbol", dated=False, extra=dict(period="annual", limit=200)),
    dict(tier=2, name="income_statement_quarter",  base=BASE_STABLE, path="income-statement",
         scope="per_symbol", dated=False, extra=dict(period="quarter", limit=400)),
    dict(tier=2, name="balance_sheet_annual",      base=BASE_STABLE, path="balance-sheet-statement",
         scope="per_symbol", dated=False, extra=dict(period="annual", limit=200)),
    dict(tier=2, name="balance_sheet_quarter",     base=BASE_STABLE, path="balance-sheet-statement",
         scope="per_symbol", dated=False, extra=dict(period="quarter", limit=400)),
    dict(tier=2, name="cash_flow_annual",          base=BASE_STABLE, path="cash-flow-statement",
         scope="per_symbol", dated=False, extra=dict(period="annual", limit=200)),
    dict(tier=2, name="cash_flow_quarter",         base=BASE_STABLE, path="cash-flow-statement",
         scope="per_symbol", dated=False, extra=dict(period="quarter", limit=400)),
    dict(tier=2, name="key_metrics_annual",        base=BASE_STABLE, path="key-metrics",
         scope="per_symbol", dated=False, extra=dict(period="annual", limit=200),
         note="tier 2 item 9"),
    dict(tier=2, name="ratios_annual",             base=BASE_STABLE, path="ratios",
         scope="per_symbol", dated=False, extra=dict(period="annual", limit=200),
         note="tier 2 item 9"),
    dict(tier=2, name="sp500_constituents",        base=BASE_STABLE, path="sp500-constituent",
         scope="once", dated=False, note="tier 2 item 8: current membership"),
    dict(tier=2, name="sp500_historical",          base=BASE_STABLE, path="historical-sp500-constituent",
         scope="once", dated=False,
         note="tier 2 item 8: dated membership if it exists; check what history is real"),

    # ---- tier 3, all four items, DECIDED 28 Aug ---------------------------
    dict(tier=3, name="transcript_dates",          base=BASE_STABLE, path="earning-call-transcript-dates",
         scope="per_symbol", dated=False,
         note="tier 3 item 10, step 1: enumerate before fetching bodies"),
    # transcript bodies are fetched by 21_fmp_transcripts.py, driven off transcript_dates
    dict(tier=3, name="analyst_estimates",         base=BASE_STABLE, path="analyst-estimates",
         scope="per_symbol", dated=False, extra=dict(period="annual", limit=200),
         note="tier 3 item 11"),
    dict(tier=3, name="price_target_consensus",    base=BASE_STABLE, path="price-target-consensus",
         scope="per_symbol", dated=False, note="tier 3 item 11"),
    dict(tier=3, name="esg_ratings",               base=BASE_STABLE, path="esg-ratings",
         scope="per_symbol", dated=False,
         note="tier 3 item 12: a comparison, never a benchmark"),
    dict(tier=3, name="esg_disclosures",           base=BASE_STABLE, path="esg-disclosures",
         scope="per_symbol", dated=False, note="tier 3 item 12"),
    dict(tier=3, name="institutional_positions",   base=BASE_STABLE, path="institutional-ownership/symbol-positions-summary",
         scope="per_symbol", dated=False, note="tier 3 item 13"),

    # ---- vendor DCF: pulled, then NOT OPENED ------------------------------
    dict(tier=3, name="vendor_dcf",                base=BASE_STABLE, path="discounted-cash-flow",
         scope="per_symbol", dated=False, quarantine=True,
         note="SEQUENCING RULE: stored in vendor_dcf_DO_NOT_OPEN, not to be read until "
              "Carlo's own valuation assumptions are written down and dated"),
    dict(tier=3, name="vendor_dcf_levered",        base=BASE_STABLE, path="levered-discounted-cash-flow",
         scope="per_symbol", dated=False, quarantine=True, note="as above"),
]

# Nine currencies from the archive manifest, against both base currencies.
# GBp is pence and ILA is agorot: both are hundredths. FMP quotes GBP and ILS,
# so the pair is pulled in the major unit and the hundredth conversion is applied
# at parse time, never here. This is recorded in the manifest, not silently done.
UNIVERSE_CURRENCIES = ["AUD", "CHF", "DKK", "EUR", "GBp", "ILA", "NOK", "SEK", "USD"]
MINOR_UNIT = {"GBp": ("GBP", 100), "ILA": ("ILS", 100)}


# --------------------------------------------------------------------------
def load_key() -> str:
    """Read FMP_API_KEY from .env or the environment. Never log or echo it."""
    key = os.environ.get("FMP_API_KEY")
    if not key:
        for candidate in (REPO / ".env", PROJECT / ".env"):
            if candidate.exists():
                for line in candidate.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("FMP_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
            if key:
                break
    if not key:
        sys.exit(
            "No FMP_API_KEY found.\n"
            f"Put it in {REPO / '.env'} as:  FMP_API_KEY=...\n"
            ".env is already gitignored. Do not put the key anywhere else."
        )
    return key


def load_symbols() -> list[str]:
    """
    The 304 symbols actually requested in the August panel, taken from the
    archived manifest, which is the authoritative record of what was asked for.
    sorted() is not decoration: a set was iterated once in this project and the
    output was irreproducible.
    """
    archive = PROJECT / "Data" / "FMP Panel B archive" / "paper1_data_20260821" / "data" / "raw" / "manifest.json"
    manifest = json.loads(archive.read_text())
    return sorted(set(manifest["panel_b"]["requested"]))


def fx_pairs() -> list[str]:
    pairs = set()
    for cur in UNIVERSE_CURRENCIES:
        major = MINOR_UNIT.get(cur, (cur, 1))[0]
        for base in ("USD", "EUR"):
            if major != base:
                pairs.add(f"{major}{base}")
    return sorted(pairs)


# --------------------------------------------------------------------------
class Throttle:
    def __init__(self):
        self.last = 0.0
        self.consecutive_429 = 0
        self.state = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "calls": 0}
        if STATE.exists():
            saved = json.loads(STATE.read_text())
            if saved.get("date") == self.state["date"]:
                self.state = saved

    def wait(self):
        gap = time.monotonic() - self.last
        if gap < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - gap)
        self.last = time.monotonic()

    def count(self):
        self.state["calls"] += 1
        STATE.write_text(json.dumps(self.state))
        if self.state["calls"] >= DAILY_CAP:
            sys.exit(f"Daily cap {DAILY_CAP} reached. Stopping cleanly; rerun tomorrow, it resumes.")


def fetch(session, throttle, url, params) -> tuple[int, bytes]:
    """Return (status, raw body bytes). Backs off on 429 and 5xx."""
    for attempt in range(MAX_RETRIES):
        throttle.wait()
        resp = session.get(url, params=params, timeout=60)
        throttle.count()

        if resp.status_code == 429:
            throttle.consecutive_429 += 1
            if throttle.consecutive_429 >= CONSECUTIVE_429_STOP:
                sys.exit(
                    f"{CONSECUTIVE_429_STOP} consecutive 429s. Stopping rather than "
                    "risking a ban. Lower CALLS_PER_MINUTE and resume; nothing is lost."
                )
            delay = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** attempt)) + random.uniform(0, 3)
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = max(delay, float(retry_after))
            print(f"    429, backing off {delay:.0f}s", flush=True)
            time.sleep(delay)
            continue

        throttle.consecutive_429 = 0
        if resp.status_code >= 500:
            time.sleep(min(BACKOFF_MAX, BACKOFF_BASE * (2 ** attempt)))
            continue
        return resp.status_code, resp.content

    return 0, b""


# --------------------------------------------------------------------------
def describe(body: bytes) -> dict:
    """Metadata for the manifest. Parses a COPY; the raw bytes are already saved."""
    out = {"rows": None, "date_min": None, "date_max": None, "parse_ok": False}
    try:
        data = json.loads(body)
    except Exception:
        return out
    out["parse_ok"] = True
    records = data if isinstance(data, list) else data.get("historical") if isinstance(data, dict) else None
    if isinstance(records, list):
        out["rows"] = len(records)
        dates = sorted(r["date"] for r in records if isinstance(r, dict) and isinstance(r.get("date"), str))
        if dates:
            out["date_min"], out["date_max"] = dates[0], dates[-1]
    elif isinstance(data, dict):
        out["rows"] = 1
    return out


def write_raw(target: Path, body: bytes) -> tuple[Path, str]:
    """
    Never overwrite. If the target exists, write beside it with a timestamp suffix
    and say so. Returns (path_written, disposition).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        beside = target.with_name(target.name.replace(".json.gz", f"__refetch_{stamp}.json.gz"))
        with gzip.open(beside, "wb") as fh:
            fh.write(body)
        return beside, "WROTE_BESIDE"
    with gzip.open(target, "wb") as fh:
        fh.write(body)
    return target, "WROTE_NEW"


def already_done(target: Path) -> bool:
    return target.exists() and target.stat().st_size > 0


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", type=int, action="append", default=[],
                    help="tier to pull; repeatable. Default: 1")
    ap.add_argument("--only", action="append", default=[], help="endpoint name filter")
    ap.add_argument("--dry-run", action="store_true", help="plan and count, call nothing")
    ap.add_argument("--probe", action="store_true",
                    help="one call per endpoint on the first symbol, print shape, then stop")
    args = ap.parse_args()
    tiers = sorted(set(args.tier)) or [1]

    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    VENDOR_DCF.mkdir(parents=True, exist_ok=True)
    guard = VENDOR_DCF / "DO_NOT_OPEN.md"
    if not guard.exists():
        guard.write_text(
            "# Do not open these files\n\n"
            "FMP's own DCF valuations. They are a validation check for Carlo's valuation\n"
            "model, to be compared only AFTER that model is finished and its assumptions\n"
            "are written down and dated. Reading them first would anchor the assumptions,\n"
            "which is the valuation-model version of the specification search this project\n"
            "is built to avoid.\n\n"
            "FMP's DCF is an automated calculation on standardised inputs, not a\n"
            "research-grade valuation. It is a check against arithmetic error and gross\n"
            "mis-specification, not a benchmark of truth.\n"
        )

    symbols = load_symbols()
    pairs = fx_pairs()
    selected = [e for e in ENDPOINTS if e["tier"] in tiers and (not args.only or e["name"] in args.only)]

    print(f"symbols: {len(symbols)}   fx pairs: {len(pairs)}   endpoints: {len(selected)}   tiers: {tiers}")
    print(f"raw -> {RAW}")
    print(f"vendor DCF -> {VENDOR_DCF}  (written, never read)")

    planned = 0
    for ep in selected:
        n = len(symbols) if ep["scope"] == "per_symbol" else len(pairs) if ep["scope"] == "per_fx" else 1
        planned += n
    print(f"planned calls: {planned}   at {CALLS_PER_MINUTE}/min that is ~{planned / CALLS_PER_MINUTE:.0f} min\n")

    if args.dry_run:
        for ep in selected:
            print(f"  tier {ep['tier']}  {ep['name']:<28} {ep['base']}/{ep['path']}")
        return

    key = load_key()
    session = requests.Session()
    throttle = Throttle()

    # ----------------------------------------------------------------------
    # --probe: one call per endpoint, raw saved, shape printed, then stop.
    # The MCP wrapper renames parameters and reshapes output relative to the
    # REST API, and the connector could not be used to check any of this, so
    # the registry above is UNVERIFIED. Run this before the loop, every time.
    # Probe output goes to its own directory so it can never block a real pull.
    # ----------------------------------------------------------------------
    if args.probe:
        probe_dir = OUT / "probe"
        probe_dir.mkdir(parents=True, exist_ok=True)
        print("PROBE: one call per endpoint. No loop is run.\n")
        refused = []
        for ep in selected:
            sym = (symbols[0] if ep["scope"] == "per_symbol"
                   else pairs[0] if ep["scope"] == "per_fx" else None)
            target = probe_dir / f"{ep['name']}__{(sym or 'all').replace('/', '_')}.json.gz"
            if already_done(target):
                print(f"  {ep['name']:<28} probe already on disk, skipped")
                continue

            params = {"apikey": key}
            if sym:
                params["symbol"] = sym
            if ep.get("dated"):
                params["from"] = WINDOW_FROM
                params["to"] = WINDOW_TO or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            params.update(ep.get("extra", {}))

            status, body = fetch(session, throttle, f"{ep['base']}/{ep['path']}", params)
            if status != 200 or not body:
                refused.append((ep["name"], status))
                print(f"  {ep['name']:<28} HTTP {status}   <-- REFUSED")
                continue

            write_raw(target, body)
            meta = describe(body)
            try:
                parsed = json.loads(body)
                first = parsed[0] if isinstance(parsed, list) and parsed else parsed
                keys = sorted(first.keys()) if isinstance(first, dict) else type(first).__name__
            except Exception:
                keys, first = "<unparsed>", None

            if ep.get("quarantine"):
                # SEQUENCING RULE: shape only. Printing a vendor fair value here
                # would anchor the valuation model exactly as reading the files would.
                print(f"  {ep['name']:<28} HTTP 200  {len(body)}B  rows={meta['rows']}")
                print(f"      keys: {keys}")
                print(f"      [SEALED] values withheld; file written to vendor probe, not opened")
                print()
                continue

            print(f"  {ep['name']:<28} HTTP 200  {len(body)}B  rows={meta['rows']}  "
                  f"{meta['date_min']}..{meta['date_max']}")
            print(f"      keys: {keys}")
            if isinstance(first, dict):
                print(f"      first record: {json.dumps(first)[:400]}")
            print()

        print("\nProbe raw saved to:", probe_dir)
        if refused:
            print("\nREFUSED, record these in the completeness report as endpoints the plan denied:")
            for name, status in refused:
                print(f"  {name}: HTTP {status}")
        print("\nCheck every shape above against the ENDPOINTS registry before running the loop.")
        print("A silently short date range is the failure to watch for, not an error.")
        return

    ledger = LEDGER.open("a")

    counts = {"WROTE_NEW": 0, "WROTE_BESIDE": 0, "SKIP_EXISTS": 0, "EMPTY": 0, "HTTP_ERROR": 0}

    for ep in selected:
        targets = symbols if ep["scope"] == "per_symbol" else pairs if ep["scope"] == "per_fx" else [None]
        root = (VENDOR_DCF / ep["name"]) if ep.get("quarantine") else (RAW / ep["name"])
        print(f"\n=== tier {ep['tier']}  {ep['name']}  ({len(targets)}) ===", flush=True)

        for i, sym in enumerate(targets, 1):
            fname = f"{(sym or 'all').replace('/', '_')}.json.gz"
            target = root / fname
            if already_done(target):
                counts["SKIP_EXISTS"] += 1
                continue

            params = {"apikey": key}
            if sym:
                params["symbol"] = sym
            if ep.get("dated"):
                params["from"] = WINDOW_FROM
                params["to"] = WINDOW_TO or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            params.update(ep.get("extra", {}))

            status, body = fetch(session, throttle, f"{ep['base']}/{ep['path']}", params)

            if status != 200 or not body:
                counts["HTTP_ERROR"] += 1
                ledger.write(json.dumps({
                    "endpoint": ep["name"], "symbol": sym, "http_status": status,
                    "fetched_utc": datetime.now(timezone.utc).isoformat(),
                    "disposition": "HTTP_ERROR",
                }) + "\n")
                ledger.flush()
                print(f"  [{i}/{len(targets)}] {sym}: HTTP {status}", flush=True)
                continue

            if body.strip() in (b"[]", b"{}", b""):
                counts["EMPTY"] += 1

            path, disposition = write_raw(target, body)
            counts[disposition] += 1
            meta = describe(body)

            # Parameters are recorded WITHOUT the key.
            safe_params = {k: v for k, v in params.items() if k != "apikey"}
            ledger.write(json.dumps({
                "endpoint": ep["name"], "symbol": sym,
                "url": f"{ep['base']}/{ep['path']}", "params": safe_params,
                "fetched_utc": datetime.now(timezone.utc).isoformat(),
                "http_status": status, "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "file": str(path.relative_to(OUT)),
                "disposition": disposition,
                "quarantined": bool(ep.get("quarantine")),
                **meta,
            }) + "\n")
            ledger.flush()

            if i % 25 == 0 or i == len(targets):
                print(f"  [{i}/{len(targets)}] {sym}  rows={meta['rows']} "
                      f"{meta['date_min']}..{meta['date_max']}", flush=True)

    ledger.close()
    print("\n" + json.dumps(counts, indent=2))
    print(f"\nledger: {LEDGER}")
    print("Now run 21_fmp_verify.py to produce the completeness report.")
    print("Then run `git status` in the repo and confirm nothing new is staged.")


if __name__ == "__main__":
    main()
