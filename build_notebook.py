"""
Generates notebooks/01_raw_panels.ipynb.

Kept as a generator rather than a hand-edited .ipynb so the notebook source
stays diffable in git. Run:  python build_notebook.py
"""
import json, pathlib

def _lines(src: str) -> list[str]:
    """Split into .ipynb source lines, KEEPING the trailing newline on each.

    The notebook format joins source with "", not "\n". A plain .split("\n")
    therefore collapses every cell onto a single line: markdown renders as one
    run-on paragraph and code cells raise SyntaxError on the first run. Caught
    only after the notebook was already pushed. Do not "simplify" this back.
    """
    parts = src.split("\n")
    return [p + "\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])

def md(src):   return {"cell_type": "markdown", "metadata": {}, "source": _lines(src.strip())}
def code(src): return {"cell_type": "code", "execution_count": None, "metadata": {},
                       "outputs": [], "source": _lines(src.strip("\n"))}

cells = []

cells.append(md(r"""
# Paper 1: raw data panels

**Scope of this notebook: acquisition only.** It downloads two panels, writes them to
`data/raw/`, and stops. There is no return calculation, no factor regression, no
portfolio formation and no merging of the two panels. That is deliberate. The raw
layer should be reproducible and auditable on its own before anything is estimated
on top of it.

| Panel | Source | Contents |
|---|---|---|
| A | Ken French Data Library | Fama-French 3 factors, daily (`Mkt-RF`, `SMB`, `HML`, `RF`) |
| B | Financial Modeling Prep | Daily EOD prices, draft ticker list + S&P 500 |

**Two things this notebook is not, and must not be read as:**

1. The draft ticker list is a **survivorship-biased convenience sample**. Every name in
   it is a firm that still trades in August 2026. It is a plumbing test for the data
   path, not a research universe. See the README before any return-based estimate.
2. Prices are stored **as returned by the vendor**. Units are not converted, currencies
   are not converted, and nothing is adjusted. Transformations belong downstream, where
   they can be diffed.
"""))

cells.append(md("## 0. Setup"))

cells.append(code(r'''
# Standard library only, plus pandas/requests which Colab already has.
import os, io, re, zipfile, json, time, hashlib, datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------- paths
# In Colab, clone the repo first (see the cell below) so that REPO points at it.
# Locally, the notebook sits in notebooks/ so the repo root is one level up.
REPO = Path.cwd() if (Path.cwd() / "data").exists() else Path.cwd().parent
RAW  = REPO / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- window
# Fixed in advance so a rerun on a different day produces the same file.
# Do not change these to "whatever improves the result" later.
START = "2010-01-01"
END   = "2025-12-31"

print(f"repo   : {REPO}")
print(f"raw out: {RAW}")
print(f"window : {START} .. {END}")
'''))

cells.append(md(r"""
### Running in Colab

Uncomment and run this cell if you are on Colab rather than a local checkout. Replace
the URL with your repo. The FMP key is read from Colab's **Secrets** panel (the key
icon in the left sidebar), then add a secret named `FMP_API_KEY` and enable it for this
notebook. Do not paste the key into a cell; it would end up in the committed output.
"""))

cells.append(code(r'''
# --- Colab bootstrap (uncomment on Colab) ---------------------------------
# !git clone https://github.com/ochofer/paper1-hazard-exposure-data.git
# %cd paper1-hazard-exposure-data
# REPO = Path.cwd(); RAW = REPO / "data" / "raw"; RAW.mkdir(parents=True, exist_ok=True)
#
# from google.colab import userdata
# os.environ["FMP_API_KEY"] = userdata.get("FMP_API_KEY")
# --------------------------------------------------------------------------
pass
'''))

# ------------------------------------------------------------------ Panel A
cells.append(md(r"""
## 1. Panel A: Fama-French 3 factors, daily

Source: Ken French's data library, file `F-F_Research_Data_Factors_daily_CSV.zip`.

The file needs real parsing rather than a plain `read_csv`. It carries a multi-line
copyright preamble, then the header row, then dated rows, then a trailing copyright
line. The monthly version of this file additionally appends an *annual* block after the
monthly block, separated by blank lines. If you ever swap this URL for the monthly one,
a naive parser will silently concatenate annual rows onto monthly rows and every
subsequent number will be wrong.

The parser below sidesteps all of that by keeping only lines whose first field is
exactly eight digits (`YYYYMMDD`). It is therefore immune to the preamble, the trailer,
and the annual block.

**Units: the values are in percent, not decimals.** `Mkt-RF = 0.55` means 0.55%. They are
stored here exactly as published. The `/100` belongs in the analysis layer, and this is
one of the most common silent errors in factor work, so it is flagged in the manifest too.

`-99.99` and `-999` are French's missing-value codes.
"""))

cells.append(code(r'''
FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
FF3_DAILY   = f"{FRENCH_BASE}/F-F_Research_Data_Factors_daily_CSV.zip"

def fetch_french_zip(url: str) -> tuple[str, bytes]:
    """Download a French .zip and return (inner_filename, raw_csv_bytes).

    The raw bytes are returned as well as the text so we can hash exactly what the
    server sent, which is what makes the download reproducible/auditable later.
    """
    r = requests.get(url, timeout=60, headers={"User-Agent": "paper1-data/0.1"})
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        inner = z.namelist()[0]
        return inner, z.read(inner)

DATE8 = re.compile(r"^\s*(\d{8})\s*,")

def parse_french_daily(csv_bytes: bytes) -> pd.DataFrame:
    """Parse a French daily factor CSV into a tidy frame.

    Keeps only rows whose first field is an 8-digit date, which drops the preamble,
    the trailing copyright line, and (for monthly files) the appended annual block.
    """
    text  = csv_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()

    # Locate the header: the last non-dated line before the first dated line.
    first_data = next((i for i, ln in enumerate(lines) if DATE8.match(ln)), None)
    if first_data is None:
        # Fails loudly rather than returning an empty frame. The most likely cause is
        # pointing this at a MONTHLY file (dates are YYYYMM, six digits, not eight).
        raise ValueError(
            "No YYYYMMDD rows found. Is this a daily file? Monthly files use YYYYMM "
            "and need a different parser plus handling for their annual block."
        )
    header = [c.strip() for c in lines[first_data - 1].split(",")]
    header[0] = "date"

    rows = [ln for ln in lines[first_data:] if DATE8.match(ln)]
    df = pd.read_csv(io.StringIO("\n".join(rows)), header=None, names=header)

    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")

    # Coerce to float BEFORE substituting missing values. Using pd.NA here instead of
    # np.nan silently flips these columns to object dtype, which then breaks .describe()
    # and the magnitude check further down. Caught in testing; do not "simplify" this.
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")

    n_missing_codes = int(df.iloc[:, 1:].isin([-99.99, -999]).sum().sum())
    df[df.columns[1:]] = df[df.columns[1:]].replace([-99.99, -999], np.nan)
    print(f"  missing-value codes converted to NaN: {n_missing_codes}")

    assert all(str(t) == "float64" for t in df.dtypes[1:]), f"dtype drift: {df.dtypes.to_dict()}"
    return df.sort_values("date").reset_index(drop=True)

inner_name, ff_bytes = fetch_french_zip(FF3_DAILY)
ff3_full = parse_french_daily(ff_bytes)

print(f"inner file : {inner_name}")
print(f"full range : {ff3_full.date.min():%Y-%m-%d} .. {ff3_full.date.max():%Y-%m-%d}  ({len(ff3_full):,} rows)")
print(f"columns    : {ff3_full.columns.tolist()}")
ff3_full.tail(3)
'''))

cells.append(code(r'''
# Clip to the study window and persist. Both the clipped panel and the untouched
# original are written: the original is the audit artefact, the clipped one is what
# downstream code reads.
ff3 = ff3_full[(ff3_full.date >= START) & (ff3_full.date <= END)].reset_index(drop=True)

(RAW / "ff3_daily_original.csv").write_bytes(ff_bytes)
ff3.to_csv(RAW / "panel_a_ff3_daily.csv", index=False)

print(f"window range: {ff3.date.min():%Y-%m-%d} .. {ff3.date.max():%Y-%m-%d}  ({len(ff3):,} rows)")
print("\nsummary (values are PERCENT, not decimals):")
display(ff3.describe().T[["count", "mean", "std", "min", "max"]])
'''))

# ------------------------------------------------------------------ Panel B
cells.append(md(r"""
## 2. Panel B: daily prices from FMP

The draft ticker list is read from `config/tickers_draft_v0.csv` rather than being
hardcoded here, so revising it is a one-line CSV edit and shows up cleanly in a diff.
It was drawn from the top of `outputs/cross_section.csv` by operating-asset count.

Two benchmarks are pulled, and the distinction matters later:

- `^GSPC` is the S&P 500 **index**. Price return only, no dividends, not investable.
- `SPY` is the **investable** proxy. This is the one a transaction-cost model can be
  applied to, because it is a thing you can actually buy.

Known issues that are recorded rather than fixed here, because fixing them silently in
the raw layer is how errors get buried:

- **`SHEL.L` is quoted in pence (GBp), not pounds.** A 100x error waiting to happen.
- European names are in **EUR/CHF**, US names in **USD**. No FX conversion is applied.
- The European leg must be regressed on French's **Developed Europe** factors, not the
  US factors in Panel A. Mixing them is not a currency nuisance, it is the wrong model.
"""))

cells.append(code(r'''
tick = pd.read_csv(REPO / "config" / "tickers_draft_v0.csv")
TICKERS    = tick.ticker.tolist()
BENCHMARKS = ["^GSPC", "SPY"]

print(f"{len(TICKERS)} draft tickers  ({(tick.leg=='US').sum()} US, {(tick.leg=='EU').sum()} EU)")
print(f"benchmarks: {BENCHMARKS}")
display(tick[["name", "hq", "n_assets", "ticker", "leg"]])
'''))

# --------------------------------------------------------------- preflight
cells.append(md(r"""
### 2a. Preflight: what can this API key actually see?

Run this before the main loop. It makes five cheap calls and reports what your key is
allowed to do, which is faster and more reliable than reading a pricing page, and it
tells you *now* rather than twenty tickers into a loop.

Each probe maps to a decision you would otherwise make blind:

| Probe | If it fails |
|---|---|
| US daily prices | Nothing works. The key is wrong or unauthorised, not a tier problem. |
| European ticker | Free tier. The six EU names will come back empty; drop the EU leg for now. |
| Index `^GSPC` | Use `SPY` alone as the benchmark and record the substitution. |
| History depth | Free keys are typically capped at a few recent years, which silently shortens the sample. |
| Delisted companies | **Blocking test 1 cannot run.** No delisting list means no measured survivorship rate. |

That last row is the one that matters most, and it is easy to miss. The survivorship test
in `01_survivorship_test_fmp.py` draws its random sample from FMP's own delisted list. If
that endpoint is closed to your key, the test cannot return a number at all, and the
survivorship problem stays unquantified rather than merely unquantified-so-far.
"""))

cells.append(code(r'''
API_KEY = os.environ.get("FMP_API_KEY")
if not API_KEY:
    raise SystemExit(
        "FMP_API_KEY is not set.\n"
        "  Colab : add it in the Secrets panel and switch on notebook access, "
        "then run the bootstrap cell above.\n"
        "  Local : export FMP_API_KEY='...'"
    )

# Endpoint bases, defined here because the preflight below uses them too.
V3     = "https://financialmodelingprep.com/api/v3/historical-price-full"
STABLE = "https://financialmodelingprep.com/stable/historical-price-eod/full"

def probe(label, url, params, want):
    """One capability probe. Returns a row describing what happened.

    An HTTP 200 carrying an empty payload counts as a FAIL, not a pass. FMP answers
    'no access' and 'no data' the same way, so treating 200 as success would report a
    free-tier key as fully capable.
    """
    try:
        r = requests.get(url, params={**params, "apikey": API_KEY}, timeout=45)
    except requests.RequestException as e:
        return {"probe": label, "status": "ERROR", "ok": False, "detail": str(e)[:60]}

    if r.status_code != 200:
        hint = {401: "key rejected", 403: "not on your plan", 429: "rate limited"}.get(
            r.status_code, "")
        return {"probe": label, "status": f"HTTP {r.status_code}", "ok": False, "detail": hint}

    payload = r.json()
    rows = payload.get("historical") if isinstance(payload, dict) else payload
    if not rows:
        return {"probe": label, "status": "200 empty", "ok": False,
                "detail": "no data returned - usually a plan limit"}
    return {"probe": label, "status": "200", "ok": True, "detail": want(rows)}

results = [
    probe("US daily prices (DUK)",
          f"{V3}/DUK", {"from": "2024-01-01", "to": "2024-03-01"},
          lambda r: f"{len(r)} bars"),
    probe("European ticker (ENGI.PA)",
          f"{V3}/ENGI.PA", {"from": "2024-01-01", "to": "2024-03-01"},
          lambda r: f"{len(r)} bars"),
    probe("S&P 500 index (^GSPC)",
          f"{V3}/{requests.utils.quote('^GSPC')}", {"from": "2024-01-01", "to": "2024-03-01"},
          lambda r: f"{len(r)} bars"),
    probe("History depth (2010 data)",
          f"{V3}/DUK", {"from": "2010-01-01", "to": "2010-03-01"},
          lambda r: f"earliest {min(x['date'] for x in r)}"),
    probe("Delisted companies list",
          "https://financialmodelingprep.com/api/v3/delisted-companies", {"limit": 5},
          lambda r: f"{len(r)} sample rows"),
]

pre = pd.DataFrame(results)
display(pre[["probe", "status", "detail"]])

us_ok, eu_ok, idx_ok, hist_ok, delist_ok = [x["ok"] for x in results]

print()
if not us_ok:
    print("STOP: even US prices failed. This is authentication, not a plan tier.")
    print("      Check the key value and, on Colab, the secret's notebook-access toggle.")
else:
    tier = "paid (international coverage present)" if eu_ok else "free or entry tier (no international)"
    print(f"Assessment: {tier}")
    if not eu_ok:
        print("  -> The 6 European tickers will return empty. Either drop the EU leg for now")
        print("     and rerun with US-only, or upgrade before building the European panel.")
    if not idx_ok:
        print("  -> ^GSPC unavailable. Use SPY as the benchmark and RECORD the substitution;")
        print("     SPY includes dividends and a fee drag, ^GSPC is price-only. Not interchangeable.")
    if not hist_ok:
        print(f"  -> History does not reach {START}. Your usable window is shorter than the")
        print("     one fixed at the top of this notebook. Change START deliberately, not silently.")
    if not delist_ok:
        print("  -> Delisted list is closed to this key, so 01_survivorship_test_fmp.py CANNOT run.")
        print("     Nothing return-based should be estimated until that test returns a number.")
'''))

cells.append(code(r'''
def fetch_prices(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Daily EOD bars for one symbol, as a tidy frame. Empty frame if unavailable.

    Tries the v3 endpoint (which the existing 01/02 scripts use) and falls back to the
    newer 'stable' endpoint, since FMP is migrating v3 out. An HTTP 200 carrying an
    empty payload is treated as a MISS, not a hit, the same convention used in
    01_survivorship_test_fmp.py, and the reason that matters is that a silent empty
    array otherwise looks identical to a successful call in aggregate counts.
    """
    attempts = [
        (V3,     {"symbol_in_path": True,  "from": start, "to": end}),
        (STABLE, {"symbol_in_path": False, "from": start, "to": end}),
    ]
    for base, opt in attempts:
        params = {"apikey": API_KEY, "from": opt["from"], "to": opt["to"]}
        url = f"{base}/{requests.utils.quote(symbol)}" if opt["symbol_in_path"] else base
        if not opt["symbol_in_path"]:
            params["symbol"] = symbol
        try:
            r = requests.get(url, params=params, timeout=45)
        except requests.RequestException as e:
            print(f"    {symbol}: request error on {base.split('/')[-1]} ({e})")
            continue

        if r.status_code != 200:
            print(f"    {symbol}: HTTP {r.status_code} on {base.split('/')[-1]}")
            continue

        payload = r.json()
        rows = payload.get("historical") if isinstance(payload, dict) else payload
        if not rows:
            print(f"    {symbol}: HTTP 200 but empty payload -> counted as MISS")
            continue

        df = pd.DataFrame(rows)
        df["symbol"] = symbol
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)

    return pd.DataFrame()

frames, missing = [], []
for i, sym in enumerate(TICKERS + BENCHMARKS, 1):
    print(f"[{i:>2}/{len(TICKERS) + len(BENCHMARKS)}] {sym}")
    d = fetch_prices(sym, START, END)
    if d.empty:
        missing.append(sym)
    else:
        frames.append(d)
        print(f"    {len(d):,} rows  {d.date.min():%Y-%m-%d} .. {d.date.max():%Y-%m-%d}")
    time.sleep(0.3)   # gentle on the rate limit

print(f"\nretrieved {len(frames)}, missing {len(missing)}: {missing}")
'''))

cells.append(code(r'''
if not frames:
    raise SystemExit("No price data retrieved at all. Check the API key and its plan tier.")

prices = pd.concat(frames, ignore_index=True)

# Keep a stable column order; retain whatever extra columns FMP returns.
lead = [c for c in ["symbol", "date", "open", "high", "low", "close", "adjClose", "volume"]
        if c in prices.columns]
prices = prices[lead + [c for c in prices.columns if c not in lead]]

prices.to_csv(RAW / "panel_b_prices_daily.csv", index=False)

print(f"{len(prices):,} rows, {prices.symbol.nunique()} symbols")
display(
    prices.groupby("symbol")
          .agg(rows=("date", "size"), start=("date", "min"), end=("date", "max"))
          .sort_values("rows")
)
'''))

# ------------------------------------------------------------------ integrity
cells.append(md(r"""
## 3. Integrity checks and manifest

These assertions are here so that a broken download fails loudly at acquisition time
rather than showing up as a puzzling coefficient three weeks later. They check the
plumbing only. They make no claim about whether the data is fit for the research
question. The manifest records SHA-256 hashes so a later rerun can be proved identical
(or proved different) rather than assumed so.
"""))

cells.append(code(r'''
checks = []
def check(name, ok, detail=""):
    checks.append({"check": name, "pass": bool(ok), "detail": detail})

# --- Panel A
check("ff3: has all four factor columns",
      set(["Mkt-RF", "SMB", "HML", "RF"]).issubset(ff3.columns),
      str(ff3.columns.tolist()))
check("ff3: no duplicate dates", ff3.date.duplicated().sum() == 0,
      f"{ff3.date.duplicated().sum()} dupes")
check("ff3: dates strictly increasing", ff3.date.is_monotonic_increasing)
check("ff3: no weekend dates", (ff3.date.dt.dayofweek < 5).all(),
      f"{(ff3.date.dt.dayofweek >= 5).sum()} weekend rows")
# Daily factor moves outside +/-25% would indicate a units or parsing error.
mx = ff3[["Mkt-RF", "SMB", "HML"]].abs().max().max()
check("ff3: factor magnitudes plausible for PERCENT units", mx < 25, f"max |value| = {mx}")
check("ff3: RF non-negative", (ff3.RF.dropna() >= 0).all())

# --- Panel B
check("prices: no duplicate (symbol, date)",
      prices.duplicated(["symbol", "date"]).sum() == 0,
      f"{prices.duplicated(['symbol','date']).sum()} dupes")
check("prices: all closes strictly positive",
      (prices["close"].dropna() > 0).all())
check("prices: S&P 500 index present", "^GSPC" in set(prices.symbol))
check("prices: every requested symbol returned data",
      len(missing) == 0, f"missing: {missing}")

# Trading-day overlap is the join key sanity check for the (later) merge step.
common = set(ff3.date) & set(prices.loc[prices.symbol == "^GSPC", "date"])
check("overlap: FF3 and ^GSPC share >2000 trading days", len(common) > 2000,
      f"{len(common)} shared days")

report = pd.DataFrame(checks)
display(report)

n_fail = int((~report["pass"]).sum())
print(f"\n{len(report) - n_fail}/{len(report)} checks passed"
      + (f" {n_fail} FAILED, read the detail column before using these files." if n_fail else ""))
'''))

cells.append(code(r'''
def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()

manifest = {
    "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "window": {"start": START, "end": END},
    "panel_a": {
        "source": FF3_DAILY,
        "inner_file": inner_name,
        "rows": int(len(ff3)),
        "units": "PERCENT: divide by 100 before combining with decimal returns",
        "missing_codes": [-99.99, -999],
    },
    "panel_b": {
        "source": "FMP historical-price-eod (v3 with stable fallback)",
        "requested": TICKERS + BENCHMARKS,
        "missing": missing,
        "rows": int(len(prices)),
        "currency_note": "no FX applied; SHEL.L is GBp (pence); EU names EUR/CHF",
    },
    "checks_failed": n_fail,
    "files": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
              for p in sorted(RAW.glob("*")) if p.is_file()},
}

(RAW / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2)[:1500])
'''))

cells.append(md(r"""
## 4. What is deliberately absent

No returns, no regressions, no portfolio construction, no merge of the two panels, and
no survivorship correction. Those belong downstream of this file.

Before anything return-based is estimated on this data, two upstream items have to
close, both carried over from the 19 August handover:

1. **`01_survivorship_test_fmp.py` has not returned a number.** Until there is a measured
   delisting hit rate for FMP, the size of the survivorship problem is unknown rather
   than small. The README states the intended handling; that is not the same as having
   measured it.
2. **The ownership snapshot is undated.** The GEM Ownership Tracker is a single snapshot
   with sector vintages spanning roughly sixteen months, so the exposure variable
   currently carries look-ahead of unknown size.
"""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
        "colab": {"provenance": [], "toc_visible": True},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = pathlib.Path(__file__).parent / "notebooks" / "01_raw_panels.ipynb"
out.write_text(json.dumps(nb, indent=1))
print(f"wrote {out}  ({len(cells)} cells)")
