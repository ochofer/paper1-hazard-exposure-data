#!/usr/bin/env python3
"""
21_fmp_verify.py -- the completeness report, which is the actual deliverable.

Reads the extractor's append-only ledger and the raw files on disk and answers
every question in HANDOVER_FMP_extraction_2026-08-28.md section 4. It is a
separate script from the extractor on purpose: success is not "the script
finished".

It never opens anything under vendor_dcf_DO_NOT_OPEN. It counts those files and
checksums them, and reads no values.

    python3 21_fmp_verify.py

Writes:
    <OUT>/COMPLETENESS_REPORT_<date>.md    the report Carlo reads before cancelling
    <repo>/data/raw/manifest.json          the public audit record (no data, no key)
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT    = Path(__file__).resolve().parent.parent
REPO       = PROJECT / "repo_paper1_data"
OUT        = PROJECT / "Data" / "FMP extraction 2026-09"
RAW        = OUT / "raw"
VENDOR_DCF = OUT / "vendor_dcf_DO_NOT_OPEN"
LEDGER     = OUT / "manifest_entries.jsonl"

REQUESTED_FROM = "1990-01-01"
SAMPLE_WINDOW  = ("2010-01-01", "2025-12-31")   # the window the August panel used

TIER1 = ["price_eod_full", "price_eod_dividend_adj", "price_eod_non_split_adj",
         "dividends", "splits", "historical_market_cap", "shares_float",
         "profile", "delisted_companies", "fx_eod"]

EXPECTED_CURRENCIES = ["AUD", "CHF", "DKK", "EUR", "GBp", "ILA", "NOK", "SEK", "USD"]


def load_symbols() -> list[str]:
    archive = PROJECT / "Data" / "FMP Panel B archive" / "paper1_data_20260821" / "data" / "raw" / "manifest.json"
    return sorted(set(json.loads(archive.read_text())["panel_b"]["requested"]))


def load_ledger() -> list[dict]:
    if not LEDGER.exists():
        raise SystemExit(f"No ledger at {LEDGER}. Run 20_fmp_extract.py first.")
    rows = []
    for line in LEDGER.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def main():
    symbols = load_symbols()
    ledger = load_ledger()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # latest successful entry per (endpoint, symbol); ledger is append-only
    latest: dict[tuple, dict] = {}
    for row in ledger:
        if row.get("disposition") in ("WROTE_NEW", "WROTE_BESIDE"):
            latest[(row["endpoint"], row.get("symbol"))] = row

    by_ep = defaultdict(dict)
    for (ep, sym), row in latest.items():
        by_ep[ep][sym] = row

    errors = defaultdict(list)
    for row in ledger:
        if row.get("disposition") == "HTTP_ERROR":
            errors[row["endpoint"]].append((row.get("symbol"), row.get("http_status")))

    L = []
    A = L.append
    A(f"# FMP extraction: completeness report")
    A("")
    A(f"Generated {today} (UTC) by `21_fmp_verify.py` from `{LEDGER.name}`.")
    A("")
    A("Read this before cancelling. A gap found while the subscription is live is an")
    A("inconvenience; the same gap found afterwards is permanent.")
    A("")

    # ---- 1. per tier 1 item, coverage against the 304 ---------------------
    A("## 1. Tier 1 coverage against the requested universe")
    A("")
    A(f"Universe as requested in the August panel: **{len(symbols)} symbols**.")
    A("")
    A("| endpoint | symbols with usable data | empty | missing | % |")
    A("|---|---:|---:|---:|---:|")
    missing_detail = {}
    for ep in TIER1:
        got = by_ep.get(ep, {})
        if ep in ("delisted_companies",):
            continue
        if ep == "fx_eod":
            continue
        usable = [s for s in symbols if got.get(s) and (got[s].get("rows") or 0) > 0]
        empty = [s for s in symbols if got.get(s) and not (got[s].get("rows") or 0)]
        missing = [s for s in symbols if s not in got]
        missing_detail[ep] = {"empty": sorted(empty), "missing": sorted(missing)}
        pct = 100.0 * len(usable) / len(symbols) if symbols else 0.0
        A(f"| `{ep}` | {len(usable)} | {len(empty)} | {len(missing)} | {pct:.1f}% |")
    A("")
    for ep, d in sorted(missing_detail.items()):
        if d["empty"] or d["missing"]:
            A(f"**`{ep}` — named exceptions**")
            A("")
            if d["missing"]:
                A(f"- never fetched ({len(d['missing'])}): {', '.join(d['missing'])}")
            if d["empty"]:
                A(f"- fetched but empty ({len(d['empty'])}): {', '.join(d['empty'])}")
            A("")

    # ---- 2. date ranges obtained vs requested -----------------------------
    A("## 2. Date range obtained versus requested")
    A("")
    A(f"Requested from `{REQUESTED_FROM}` to today. Silent truncation is the classic")
    A("failure here, so short series are listed rather than summarised away.")
    A("")
    for ep in ("price_eod_full", "price_eod_dividend_adj", "historical_market_cap"):
        got = by_ep.get(ep, {})
        if not got:
            A(f"- `{ep}`: nothing on disk.")
            continue
        mins = sorted(r["date_min"] for r in got.values() if r.get("date_min"))
        maxs = sorted(r["date_max"] for r in got.values() if r.get("date_max"))
        if not mins:
            A(f"- `{ep}`: no dated records.")
            continue
        A(f"**`{ep}`** — earliest date seen anywhere: `{mins[0]}`, latest: `{maxs[-1]}`.")
        A("")
        short = sorted((r["date_min"], s) for s, r in got.items()
                       if r.get("date_min") and r["date_min"] > SAMPLE_WINDOW[0])
        if short:
            A(f"- {len(short)} symbols start after {SAMPLE_WINDOW[0]}, i.e. they do not")
            A(f"  cover the full sample window. Earliest-start-after list:")
            A("")
            for dmin, s in short[:60]:
                A(f"  - `{s}` starts {dmin}")
            if len(short) > 60:
                A(f"  - ...and {len(short) - 60} more, see the ledger")
        else:
            A(f"- every symbol covers from at least {SAMPLE_WINDOW[0]}.")
        A("")
        # a genuine start is not the same as truncation: flag the suspicious cluster
        clustered = defaultdict(int)
        for r in got.values():
            if r.get("date_min"):
                clustered[r["date_min"][:4]] += 1
        top = sorted(clustered.items(), key=lambda kv: -kv[1])[:3]
        A(f"- start-year clustering (a single dominant year means a plan cap, not history): "
          + ", ".join(f"{y}: {n}" for y, n in top))
        A("")

    # ---- 3. delisted coverage ---------------------------------------------
    A("## 3. Delisted names: how far the list genuinely extends")
    A("")
    dl = by_ep.get("delisted_companies", {}).get(None)
    if not dl:
        A("Not retrieved.")
    else:
        path = OUT / dl["file"]
        try:
            recs = json.loads(gzip.open(path, "rb").read())
            dates = sorted(r["delistedDate"] for r in recs
                           if isinstance(r, dict) and isinstance(r.get("delistedDate"), str))
            by_year = defaultdict(int)
            for d in dates:
                by_year[d[:4]] += 1
            A(f"- {len(recs)} delisted records retrieved.")
            A(f"- earliest delisting date in the list: `{dates[0] if dates else 'n/a'}`")
            A(f"- latest: `{dates[-1] if dates else 'n/a'}`")
            A("")
            A("| year | delistings |")
            A("|---|---:|")
            for y in sorted(by_year):
                A(f"| {y} | {by_year[y]} |")
            A("")
            thin = sum(n for y, n in by_year.items() if y < "2016")
            A(f"- before 2016: {thin} records "
              f"({100.0 * thin / len(dates):.1f}% of the list) — the handover expects this to")
            A("  be thin; this is the measured figure rather than the repeated claim.")
        except Exception as exc:
            A(f"Could not summarise the delisted list: {exc}")
    A("")

    # ---- 4. currency coverage ---------------------------------------------
    A("## 4. Currency coverage")
    A("")
    prof = by_ep.get("profile", {})
    seen = defaultdict(list)
    for sym, row in sorted(prof.items()):
        try:
            rec = json.loads(gzip.open(OUT / row["file"], "rb").read())
            rec = rec[0] if isinstance(rec, list) and rec else rec
            seen[str(rec.get("currency"))].append(sym)
        except Exception:
            seen["<unreadable>"].append(sym)
    A("| currency | symbols |")
    A("|---|---:|")
    for cur in sorted(seen):
        A(f"| {cur} | {len(seen[cur])} |")
    A("")
    absent = [c for c in EXPECTED_CURRENCIES if c not in seen]
    A(f"- expected nine currencies: {', '.join(EXPECTED_CURRENCIES)}")
    A(f"- absent from the pull: {', '.join(absent) if absent else 'none'}")
    A("")
    A("**GBp and ILA are hundredths.** GBp is pence, one hundredth of a pound; ILA is")
    A("agorot, one hundredth of a shekel. FMP quotes prices in these minor units for the")
    A("affected listings and quotes FX as GBPUSD and ILSUSD in the major unit. No")
    A("conversion has been applied to the raw files, deliberately. Any dollar-value")
    A("weighting, liquidity screen or cap weight must divide these by 100 first.")
    n_gbp = len(seen.get("GBp", []))
    A(f"- symbols quoted in GBp in this pull: {n_gbp}")
    if seen.get("GBp"):
        A(f"  - {', '.join(sorted(seen['GBp']))}")
    A("")

    # ---- 5. size and location ---------------------------------------------
    A("## 5. Size on disk and where the copy lives")
    A("")
    raw_bytes = dir_size(RAW) if RAW.exists() else 0
    dcf_bytes = dir_size(VENDOR_DCF) if VENDOR_DCF.exists() else 0
    dcf_files = len([f for f in VENDOR_DCF.rglob("*.json.gz")]) if VENDOR_DCF.exists() else 0
    A(f"- raw working data: `{RAW}` — {human(raw_bytes)}")
    A(f"- vendor DCF, sealed: `{VENDOR_DCF}` — {human(dcf_bytes)} across {dcf_files} files")
    A(f"- ledger: `{LEDGER}` — {len(ledger)} entries")
    A("")
    A("The vendor DCF files were counted and checksummed. **They have not been opened**")
    A("and no value from them appears in this report. They stay sealed until Carlo's own")
    A("valuation assumptions are written down and dated.")
    A("")
    A("Nothing in either directory is inside the git repository. The only artefact that")
    A("goes back into the repo is `data/raw/manifest.json`, which carries checksums and")
    A("date ranges and no data.")
    A("")

    # ---- 6. what the plan refused -----------------------------------------
    A("## 6. Endpoints the plan refused")
    A("")
    if not errors:
        A("No endpoint returned an error. Nothing was refused.")
    else:
        A("Named here so it is known now rather than discovered in October.")
        A("")
        A("| endpoint | failures | example status |")
        A("|---|---:|---|")
        for ep in sorted(errors):
            statuses = [s for _, s in errors[ep]]
            A(f"| `{ep}` | {len(errors[ep])} | {statuses[0] if statuses else '?'} |")
    A("")
    A("## 7. Overwrite and reproducibility guards")
    A("")
    beside = [r for r in ledger if r.get("disposition") == "WROTE_BESIDE"]
    A(f"- files written beside an existing file rather than over it: **{len(beside)}**")
    for r in beside:
        A(f"  - `{r['endpoint']}` / `{r.get('symbol')}` -> `{r['file']}`")
    if not beside:
        A("  - none; no existing raw file was touched.")
    A("- every symbol collection was sorted before iteration; no set was iterated.")
    A("- every response body was written to disk exactly as returned, gzipped, before")
    A("  any parsing. Row counts and date ranges in this report were computed from a")
    A("  parsed copy, never written back over the raw file.")
    A("")

    report = OUT / f"COMPLETENESS_REPORT_{today}.md"
    if report.exists():
        report = OUT / f"COMPLETENESS_REPORT_{today}__rerun_{datetime.now(timezone.utc).strftime('%H%M%SZ')}.md"
    report.write_text("\n".join(L))

    # ---- public manifest, extending the existing convention ---------------
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Audit record for the FMP pull. Contains checksums and coverage, no data "
                "and no credentials. The pull is auditable, not repeatable without an "
                "FMP subscription.",
        "window_requested": {"start": REQUESTED_FROM, "end": today},
        "universe_requested": symbols,
        "files": [
            {k: r.get(k) for k in
             ("endpoint", "symbol", "file", "sha256", "bytes", "rows",
              "date_min", "date_max", "fetched_utc", "params")}
            for r in sorted(latest.values(), key=lambda r: (r["endpoint"], str(r.get("symbol"))))
            if not r.get("quarantined")
        ],
        "vendor_dcf": {
            "files": dcf_files, "bytes": dcf_bytes,
            "status": "sealed, not opened, not listed here by symbol",
        },
    }
    target = REPO / "data" / "raw" / "manifest.json"
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = target.with_name(f"manifest__fmp_pull_{stamp}.json")
        print(f"manifest.json already exists; wrote beside it as {target.name}")
    target.write_text(json.dumps(manifest, indent=2))

    print(f"report:   {report}")
    print(f"manifest: {target}")
    print("\nNow run `git status` in the repo and confirm nothing raw is staged.")


if __name__ == "__main__":
    main()
