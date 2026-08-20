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

Run this before the main loop. It makes six cheap calls and reports what your key is
allowed to do, which is faster and more reliable than reading a pricing page, and it
tells you *now* rather than twenty tickers into a loop.

> **All endpoints are under `/stable/`.** The older `/api/v3/` paths are refused for keys
> issued today, and the refusal is an HTTP 403, which reads as *"not on your plan"* and is
> nothing of the sort. A 403 on every probe at once, including the most basic US price
> call, is the signature of a retired endpoint rather than a tier limit or a bad key.

Each probe maps to a decision you would otherwise make blind:

| Probe | If it fails |
|---|---|
| US daily prices | Nothing works. The key is wrong, unverified, or the path is retired. |
| Dividend-adjusted prices | **You are stuck with price returns.** See the warning below; this one changes results, not just coverage. |
| European ticker | Free tier. The six EU names will come back empty; drop the EU leg for now. |
| Index `^GSPC` | Use `SPY` alone as the benchmark and record the substitution. |
| History depth | Free keys are typically capped at a few recent years, which silently shortens the sample. |
| Delisted companies | **Blocking test 1 cannot run.** No delisting list means no measured survivorship rate. |

**Why the dividend-adjusted probe was added.** `historical-price-eod/full` is adjusted for
splits but *not* for dividends, so it yields price returns. The Fama-French factors in
Panel A are built from *total* returns. Regressing one on the other subtracts the dividend
yield from your alpha, and this draft universe is mostly regulated utilities, which are the
highest-yielding sector in the market at roughly 3 to 4 percent a year. That is not a
rounding error, it is larger than most published anomaly premia. Use
`historical-price-eod/dividend-adjusted` for anything return-based.

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
#
# Everything lives under /stable/. The /api/v3/ paths that older tutorials and FMP's own
# legacy examples still show are retired for keys issued now, and they answer HTTP 403.
# That status is the trap: it reads as "not on your plan" when the real cause is a dead
# path, so a working key on a paid plan produces an identical failure table to no key at
# all. Checked against the August 2026 documentation, in which every listed endpoint is
# /stable/ and none is /api/v3/. Do not "restore" v3 as a fallback.
BASE   = "https://financialmodelingprep.com/stable"
EOD    = f"{BASE}/historical-price-eod/full"               # split-adjusted, dividends NOT included
EOD_TR = f"{BASE}/historical-price-eod/dividend-adjusted"  # total return, use this for returns

def probe(label, url, params, want, ok_if=None):
    """One capability probe. Returns a row describing what happened.

    An HTTP 200 carrying an empty payload counts as a FAIL, not a pass. FMP answers
    'no access' and 'no data' the same way, so treating 200 as success would report a
    free-tier key as fully capable.

    ok_if lets a probe demand more than "some rows came back". The history probe needs
    it: if the endpoint ignores from/to rather than rejecting them, it returns the full
    series, which looks like a pass while telling you nothing about depth.
    """
    try:
        r = requests.get(url, params={**params, "apikey": API_KEY}, timeout=45)
    except requests.RequestException as e:
        return {"probe": label, "status": "ERROR", "ok": False, "detail": str(e)[:60]}

    if r.status_code != 200:
        hint = {401: "key rejected or not yet verified",
                403: "endpoint retired, or not on your plan",
                429: "rate limited"}.get(r.status_code, "")
        return {"probe": label, "status": f"HTTP {r.status_code}", "ok": False, "detail": hint}

    payload = r.json()
    rows = payload.get("historical") if isinstance(payload, dict) else payload
    if not rows:
        return {"probe": label, "status": "200 empty", "ok": False,
                "detail": "no data returned - usually a plan limit"}
    ok = True if ok_if is None else bool(ok_if(rows))
    return {"probe": label, "status": "200" if ok else "200 wrong range",
            "ok": ok, "detail": want(rows)}

WIN = {"from": "2024-01-02", "to": "2024-03-01"}

results = [
    probe("US daily prices (DUK)",
          EOD, {"symbol": "DUK", **WIN}, lambda r: f"{len(r)} bars"),
    probe("Dividend-adjusted prices (DUK)",
          EOD_TR, {"symbol": "DUK", **WIN}, lambda r: f"{len(r)} bars"),
    probe("European ticker (ENGI.PA)",
          EOD, {"symbol": "ENGI.PA", **WIN}, lambda r: f"{len(r)} bars"),
    probe("S&P 500 index (^GSPC)",
          EOD, {"symbol": "^GSPC", **WIN}, lambda r: f"{len(r)} bars"),
    probe("History depth (2010 data)",
          EOD, {"symbol": "DUK", "from": "2010-01-04", "to": "2010-03-01"},
          lambda r: f"earliest {min(x['date'] for x in r)}",
          ok_if=lambda r: min(x["date"] for x in r) < "2011-01-01"),
    probe("Delisted companies list",
          f"{BASE}/delisted-companies", {"page": 0, "limit": 5},
          lambda r: f"{len(r)} sample rows"),
]

pre = pd.DataFrame(results)
display(pre[["probe", "status", "detail"]])

us_ok, tr_ok, eu_ok, idx_ok, hist_ok, delist_ok = [x["ok"] for x in results]

print()
if not us_ok:
    print("STOP: even US prices failed, so nothing below is diagnostic.")
    print("      403 on every row at once means the path is retired, not that you need to pay.")
    print("      401 on every row means the key is wrong, or the account email is unverified.")
    print("      Also confirm the Colab secret is named exactly FMP_API_KEY, with notebook")
    print("      access switched on, and that the bootstrap cell copying it into os.environ ran.")
else:
    tier = "paid (international coverage present)" if eu_ok else "free or entry tier (no international)"
    print(f"Assessment: {tier}")
    if not tr_ok:
        print("  -> Dividend-adjusted prices are closed to this key, so you have PRICE returns only.")
        print("     Do not regress these on Fama-French factors, which are TOTAL returns. On a")
        print("     utility-heavy universe that understates alpha by roughly 3 to 4 percent a year.")
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

# ------------------------------------------------------- boundary finder (2b)
cells.append(md(r"""
### 2b. Where exactly is the paywall?

Only run this if section 2a returned any `HTTP 402`. A 402 is *Payment Required*, which means
the key is valid and the path is live, and something about the specific request is above your
plan. That is a much better position than a 403 and it is worth locating precisely, because the
answer decides whether this project can proceed on a free key or needs a paid one.

The interesting fact from 2a is that `^GSPC` returned data from the **same endpoint** that
refused `DUK`. So the wall is not the endpoint. Eight calls below separate the four candidate
explanations:

| Hypothesis | Distinguished by |
|---|---|
| The `full` variant is paid, `light` is free | `light` on DUK succeeds |
| Individual equities are paid, indices and lists are free | every equity call fails regardless of variant |
| Only some symbols are covered | AAPL succeeds where DUK fails |
| History depth is capped | a recent window succeeds where 2024 and 2010 fail |

The last two rows of the probe test the fallback that matters. If `light` prices and the
`dividends` endpoint are both open, total returns can be reconstructed by hand: take the
split-adjusted close, add the cash dividend on its ex-date, and compound. That is more work and
more places to make an error, but it is not a compromise on the economics, and it would keep the
paper on free and redistributable data, which is an architecture constraint rather than a budget
preference.
"""))

cells.append(code(r'''
def wall(label, path, params):
    """Minimal probe. Reports status and row count only, no interpretation."""
    try:
        r = requests.get(f"{BASE}/{path}", params={**params, "apikey": API_KEY}, timeout=45)
    except requests.RequestException as e:
        return {"test": label, "status": "ERROR", "rows": 0, "note": str(e)[:40]}
    if r.status_code != 200:
        return {"test": label, "status": f"HTTP {r.status_code}", "rows": 0,
                "note": {402: "above your plan", 403: "path retired",
                         401: "key rejected", 429: "rate limited"}.get(r.status_code, "")}
    try:
        payload = r.json()
    except ValueError:
        return {"test": label, "status": "200 non-JSON", "rows": 0, "note": r.text[:40]}
    rows = payload.get("historical") if isinstance(payload, dict) else payload
    n = len(rows) if rows else 0
    return {"test": label, "status": "200", "rows": n,
            "note": "EMPTY, treat as a miss" if n == 0 else ""}

W24    = {"from": "2024-01-02", "to": "2024-03-01"}
RECENT = {"from": "2026-06-01", "to": "2026-08-01"}

wall_tests = [
    # variant, holding the symbol and window fixed
    wall("DUK  light        2024",  "historical-price-eod/light",              {"symbol": "DUK",  **W24}),
    wall("DUK  full         2024",  "historical-price-eod/full",               {"symbol": "DUK",  **W24}),
    wall("DUK  non-split    2024",  "historical-price-eod/non-split-adjusted", {"symbol": "DUK",  **W24}),
    # symbol, holding variant and window fixed
    wall("AAPL full         2024",  "historical-price-eod/full",               {"symbol": "AAPL", **W24}),
    wall("SPY  full         2024",  "historical-price-eod/full",               {"symbol": "SPY",  **W24}),
    # window, holding symbol and variant fixed
    wall("DUK  full       recent",  "historical-price-eod/full",               {"symbol": "DUK",  **RECENT}),
    wall("DUK  full     no dates",  "historical-price-eod/full",               {"symbol": "DUK"}),
    # the manual-total-return fallback
    wall("DUK  dividends",          "dividends",                               {"symbol": "DUK"}),
]

w = pd.DataFrame(wall_tests)
display(w)

open_ = set(w.loc[w.status == "200", "test"])
def got(prefix): return any(t.startswith(prefix) for t in open_)

print()
if got("DUK  light") and not got("DUK  full"):
    print("DIAGNOSIS: the variant is the wall. 'light' is open, 'full' is not.")
    print("  light returns date, price and volume only, split-adjusted, no dividends.")
    print("  Workable for a plumbing test. NOT sufficient for factor regressions on its own.")
elif got("AAPL full") and not got("DUK  full"):
    print("DIAGNOSIS: symbol coverage is the wall, not the endpoint or the plan level.")
    print("  Check whether the covered set is an exchange, an index membership, or a fixed list.")
elif got("DUK  full       recent") and not got("DUK  full         2024"):
    print("DIAGNOSIS: history depth is the wall. Recent data is open, older data is not.")
    print(f"  The window fixed at the top of this notebook starts {START} and is unreachable.")
    print("  Do not silently shorten START. A sample chosen by what the vendor will sell you")
    print("  is a sample chosen by the vendor, and that belongs in the limitations section.")
elif not any(t.startswith("DUK") or t.startswith("AAPL") for t in open_):
    print("DIAGNOSIS: all single-equity price history is closed to this key.")
    print("  Indices and reference lists are open, individual equity EOD is not.")
    print("  Panel B cannot be built on this key at all. See the note below.")
else:
    print("DIAGNOSIS: mixed. Read the table row by row before concluding anything.")

if got("DUK  dividends") and got("DUK  light"):
    print()
    print("FALLBACK AVAILABLE: light prices + dividends are both open, so total returns can")
    print("  be reconstructed by hand. Slower and more error-prone than dividend-adjusted,")
    print("  but economically equivalent and it keeps every input free and redistributable.")
'''))

# ------------------------------------------------------ symbol coverage (2c)
cells.append(md(r"""
### 2c. What is the covered symbol list, exactly?

2b said the wall is symbol coverage: `AAPL`, `CVX`, `XOM` and `SPY` return full history while
`DUK`, `SO`, `NEE`, `BRK-B` and every European name return 402. Size does not explain it, since
`BRK-B` is one of the largest listed companies in the world and is refused while `CVX` is served.

The hypothesis worth testing is that the free list is **a Dow Jones Industrial Average membership
snapshot taken before September 2020**. `XOM` was removed from the Dow on 31 August 2020, so a
current-membership list would not include it, and a stale one would. `AAPL` and `CVX` are on both
the old and the current list, so they do not discriminate.

The probe below splits the Dow into three groups and adds controls:

| Group | Prediction if the list is a pre-2020 Dow snapshot |
|---|---|
| Removed since 2020: `PFE`, `RTX`, `WBA`, `DOW`, `INTC` | **covered** |
| Added since 2020: `CRM`, `AMGN`, `HON`, `NVDA`, `SHW` | **refused** |
| On both lists: `MSFT`, `JNJ`, `KO`, `JPM` | covered |
| Large non-Dow: `GOOGL`, `META`, `TSLA`, `BRK-B` | refused |

The last probe matters more than the rest put together. The delisted *companies list* is open to
your key, but that only gives you names. **Blocking test 1 needs the price history of a delisted
firm**, and if that is refused then the survivorship rate cannot be measured on this key no matter
how many names the list returns. This probe pulls a real symbol out of the delisted list and
immediately asks for its prices.
"""))

cells.append(code(r'''
def covered(sym):
    """True if this key can retrieve any daily history for the symbol."""
    try:
        r = requests.get(f"{BASE}/historical-price-eod/full",
                         params={"symbol": sym, "from": "2024-01-02",
                                 "to": "2024-03-01", "apikey": API_KEY}, timeout=45)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return False
    try:
        rows = r.json()
    except ValueError:
        return False
    return bool(rows.get("historical") if isinstance(rows, dict) else rows)

GROUPS = {
    "Dow, removed since 2020": ["PFE", "RTX", "WBA", "DOW", "INTC"],
    "Dow, added since 2020":   ["CRM", "AMGN", "HON", "NVDA", "SHW"],
    "Dow, on both lists":      ["MSFT", "JNJ", "KO", "JPM"],
    "Large non-Dow":           ["GOOGL", "META", "TSLA", "BRK-B"],
    "ETFs":                    ["QQQ", "IWM", "VTI"],
    "Indices":                 ["^DJI", "^IXIC"],
}

rows = []
for group, syms in GROUPS.items():
    for s in syms:
        rows.append({"group": group, "symbol": s, "covered": covered(s)})
        time.sleep(0.25)

cov = pd.DataFrame(rows)
display(cov.groupby("group").agg(n=("symbol", "size"), covered=("covered", "sum")))
print()
print("covered  :", sorted(cov.loc[cov.covered == True,  "symbol"].tolist()))
print("refused  :", sorted(cov.loc[cov.covered == False, "symbol"].tolist()))

old = cov.loc[cov.group == "Dow, removed since 2020", "covered"]
new = cov.loc[cov.group == "Dow, added since 2020",   "covered"]
print()
if old.all() and not new.any():
    print("CONFIRMED: the free list is a pre-September-2020 Dow 30 snapshot.")
    print("  That caps the investable universe at 30 US mega-caps, frozen six years ago,")
    print("  and the freeze is itself a survivorship filter: membership was decided by")
    print("  a committee using information you would not have had at the start of the sample.")
elif cov.loc[cov.group.str.startswith("Dow"), "covered"].all() and not new.any():
    print("PARTIAL: Dow-linked, but not cleanly a pre-2020 snapshot. Read the lists above.")
else:
    print("NOT the Dow hypothesis. Read the covered and refused lists and look for the pattern.")

# --- the probe that decides whether blocking test 1 can run at all
print()
try:
    dl = requests.get(f"{BASE}/delisted-companies",
                      params={"page": 0, "limit": 20, "apikey": API_KEY}, timeout=45).json()
except Exception as e:
    dl = []
    print("delisted list call failed:", e)

if dl:
    sample = [d.get("symbol") for d in dl if d.get("symbol")][:5]
    print(f"delisted list returned names, testing prices for: {sample}")
    hits = {s: covered(s) for s in sample}
    for s, ok in hits.items():
        print(f"  {s:8} prices {'AVAILABLE' if ok else 'REFUSED'}")
    if not any(hits.values()):
        print()
        print("  CONCLUSION: the delisted LIST is open but delisted PRICE HISTORY is not.")
        print("  Blocking test 1 cannot return a survivorship hit rate on this key. Knowing")
        print("  which firms died without being able to price them measures nothing.")
    else:
        print()
        print("  Blocking test 1 is runnable for at least some delisted names. Report the")
        print("  hit rate as a measured fraction and say which names could not be priced.")
'''))

cells.append(code(r'''
def fetch_prices(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Daily EOD bars for one symbol, as a tidy frame. Empty frame if unavailable.

    Tries the dividend-adjusted series first and falls back to the split-adjusted one.
    That order is deliberate: dividend-adjusted gives total returns, which is what the
    Fama-French factors in Panel A are built from. The fallback is a degradation, not an
    equivalent, so the column 'series' records which one each symbol actually got and
    the integrity checks below refuse to let a mixed panel pass unremarked.

    An HTTP 200 carrying an empty payload is treated as a MISS, not a hit, the same
    convention used in 01_survivorship_test_fmp.py, and the reason that matters is that
    a silent empty array otherwise looks identical to a successful call in aggregate
    counts.
    """
    attempts = [(EOD_TR, "dividend-adjusted"), (EOD, "split-adjusted")]
    for base, series in attempts:
        params = {"apikey": API_KEY, "symbol": symbol, "from": start, "to": end}
        url = base
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
        df["series"] = series
        df["date"] = pd.to_datetime(df["date"])
        if series != "dividend-adjusted":
            print(f"    {symbol}: fell back to {series}, PRICE returns only for this symbol")
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
# A panel that mixes total-return and price-return series is not comparable across
# symbols, and the difference is a dividend yield, so it loads on exactly the kind of
# firm characteristic a hazard sort is likely to pick up. Fail loudly rather than let
# the mixture pass as a footnote.
_series = sorted(prices["series"].unique()) if "series" in prices.columns else ["unknown"]
check("prices: one return convention across the whole panel", len(_series) == 1,
      f"series present: {_series}")
check("prices: convention is dividend-adjusted (total return)",
      _series == ["dividend-adjusted"],
      "price returns are not comparable with Fama-French total-return factors")

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
        "source": "FMP stable/historical-price-eod, dividend-adjusted preferred",
        "return_convention": sorted(prices["series"].unique()) if "series" in prices.columns else ["unknown"],
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
