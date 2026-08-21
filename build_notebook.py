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
import os, io, re, sys, zipfile, json, time, hashlib, subprocess, datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import requests

REPO_URL  = "https://github.com/ochofer/paper1-hazard-exposure-data.git"
REPO_NAME = "paper1-hazard-exposure-data"
MARKER    = Path("config") / "tickers_draft_v0.csv"   # a file that exists only inside the repo

IN_COLAB = "google.colab" in sys.modules


def _find_repo(start: Path):
    """Walk up from `start` looking for the repo root. Returns None if not found."""
    for cand in [start, *start.parents]:
        if (cand / MARKER).exists():
            return cand
    return None


# ---------------------------------------------------------------- paths
# Do NOT restore the old one-liner:
#     REPO = Path.cwd() if (Path.cwd() / "data").exists() else Path.cwd().parent
# It failed silently and expensively. On Colab cwd is /content, so the fallback
# resolved REPO to "/". Every path then became /data/... or /config/..., and because
# Colab runs as root the mkdir SUCCEEDED rather than raising. Panel A downloaded itself
# to the filesystem root, section 0 printed a repo line nobody looks at twice, and the
# failure surfaced four cells later as FileNotFoundError on '/config/tickers_draft_v0.csv'.
# A wrong path that works is worse than one that crashes. Resolve against a file that
# only exists inside the repo, and raise if it is missing.
REPO = _find_repo(Path.cwd())

def _git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


if REPO is None and IN_COLAB:
    if Path(REPO_NAME).exists():
        # Hard reset rather than pull. This clone is a disposable read-only copy, so
        # there is nothing here worth preserving, and --ff-only fails on any local
        # divergence. It previously ran with check=False, so a FAILED PULL WAS SILENT:
        # reopening the notebook from GitHub gave fresh notebook code while the repo
        # files stayed old, and config/ticker_overrides.csv simply never arrived. The
        # overrides were skipped without a word. Never make this quiet again.
        print(f"{REPO_NAME} present, resetting to origin")
        for args in (["fetch", "--depth", "1", "origin"],
                     ["reset", "--hard", "origin/HEAD"],
                     ["clean", "-fd", "config", "notebooks"]):
            rc, out = _git(*args, cwd=REPO_NAME)
            if rc != 0:
                print(f"  git {args[0]} FAILED: {out}")
        rc, out = _git("reset", "--hard", "origin/main", cwd=REPO_NAME)
        if rc != 0:
            print(f"  reset to origin/main failed: {out}")
    else:
        print(f"cloning {REPO_URL}")
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL], check=True)
    os.chdir(REPO_NAME)
    REPO = _find_repo(Path.cwd())

if REPO is None:
    raise FileNotFoundError(
        "Could not locate the repository root.\n"
        f"  Looked for {MARKER} in {Path.cwd()} and every parent directory.\n"
        "  On Colab this cell clones the repo for you, so reaching this line means the\n"
        "  clone failed. Check REPO_URL above and that the repo is public.\n"
        "  Locally, start the notebook from inside the checkout."
    )

RAW = REPO / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- API key
# Read from Colab Secrets automatically. Nothing to uncomment: the previous version
# shipped this commented out, which is how the run above ended up with REPO = "/".
if IN_COLAB and not os.environ.get("FMP_API_KEY"):
    try:
        from google.colab import userdata
        os.environ["FMP_API_KEY"] = userdata.get("FMP_API_KEY")
    except Exception as exc:
        print(f"could not read the Colab secret FMP_API_KEY: {exc}")
        print("Section 2 needs it. Key icon in the left sidebar, name it exactly")
        print("FMP_API_KEY, switch on notebook access, then rerun this cell.")

# ---------------------------------------------------------------- FMP endpoints
# Defined here rather than in the Panel B section, because section 2b resolves ISINs to
# FMP symbols and now runs BEFORE Panel B. Anything used by two sections belongs in setup.
#
# Everything lives under /stable/. The /api/v3/ paths that older tutorials and FMP's own
# legacy examples still show are retired for keys issued now, and they answer HTTP 403.
# That status is the trap: it reads as "not on your plan" when the real cause is a dead
# path, so a working key on a paid plan produces an identical failure table to no key at
# all. Checked against the August 2026 documentation, in which every listed endpoint is
# /stable/ and none is /api/v3/. Do not "restore" v3 as a fallback.
API_KEY     = os.environ.get("FMP_API_KEY")
BASE        = "https://financialmodelingprep.com/stable"
EOD         = f"{BASE}/historical-price-eod/full"               # split-adjusted, no dividends
EOD_TR      = f"{BASE}/historical-price-eod/dividend-adjusted"  # total return, use for returns
SEARCH_ISIN = f"{BASE}/search-isin"
PROFILE     = f"{BASE}/profile"

# ---------------------------------------------------------------- window
# Fixed in advance so a rerun on a different day produces the same file.
# Do not change these to "whatever improves the result" later.
START = "2010-01-01"
END   = "2025-12-31"

# Print which commit is actually running. Without this, "the code is new but the data
# files are old" is invisible, and that exact state cost a full Panel B refetch.
_rc, _head = _git("-C", str(REPO), "log", "-1", "--format=%h %ad %s", "--date=short")
print(f"commit : {_head if _rc == 0 else 'unknown'}")
print(f"config : {sorted(p.name for p in (REPO / 'config').glob('*.csv'))}")
print(f"colab  : {IN_COLAB}")
print(f"repo   : {REPO}")
print(f"raw out: {RAW}")
print(f"api key: {'set' if os.environ.get('FMP_API_KEY') else 'MISSING'}")
print(f"window : {START} .. {END}")
'''))

cells.append(md(r"""
### Confirm where you are before going further

The cell above clones the repository and reads the API key by itself, on Colab and
locally. There is nothing to uncomment. The one thing you still have to do by hand is
add the secret: **key icon in the left sidebar**, name it exactly `FMP_API_KEY`, and
switch on notebook access for this notebook. Never paste the key into a cell, because
it would be saved into the notebook output and pushed to a public repository.

Run the check below and read the three lines it prints. **If `repo` is `/` or anything
outside a folder named `paper1-hazard-exposure-data`, stop and rerun the setup cell.**
An earlier version of this notebook silently accepted `/` as the repo root and wrote
Panel A to the filesystem root; the assertion below exists so that cannot recur.
"""))

cells.append(code(r'''
print("cwd     :", Path.cwd())
print("repo    :", REPO)
print("raw out :", RAW)
print("contents:", sorted(p.name for p in REPO.iterdir() if not p.name.startswith(".")))

assert (REPO / MARKER).exists(), f"repo root resolved wrongly: {REPO}. Rerun the setup cell."
assert str(REPO) != "/", "REPO is the filesystem root. Rerun the setup cell."
print("\nrepo root confirmed")
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

# Cells are appended in the order they were written, then reordered at the bottom of
# this file into the order they should be RUN. Ticker resolution was added last but has
# to come before Panel B, because it produces the symbol list Panel B buys prices for.
# These two markers are what make that reordering possible without moving large blocks
# of text around in this file.
PANELB_START = len(cells)

# ------------------------------------------------------------------ Panel B
cells.append(md(r"""
## 3. Panel B: daily prices from FMP

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
# Prefer the resolved list from section 2. Fall back to the 20-name hand-written draft
# only if section 2 has not been run yet, and say clearly which one is in use, because
# the two mean very different things: one is a research universe, the other is a
# plumbing test made of firms that happen to still trade in 2026.
PRIMARY = REPO / "config" / "tickers_primary.csv"
V1      = REPO / "config" / "tickers_v1.csv"
DRAFT   = REPO / "config" / "tickers_draft_v0.csv"

# Order matters. tickers_v1.csv holds EVERY listing line per firm, so using it directly
# downloads a company three or four times over: ALV, ALIZY and ALIZF are all Allianz.
# Section 2b collapses those to one primary listing each. Never fall back from primary
# to v1 silently; raise instead, because a duplicated panel inflates cross-sectional
# precision and nothing downstream would reveal it.
if PRIMARY.exists():
    tick    = pd.read_csv(PRIMARY)
    tick    = tick[tick.priceable & tick.primary_symbol.notna()]
    TICKERS = sorted(tick.primary_symbol.unique().tolist())
    SOURCE  = "tickers_primary.csv (one listing per firm, chosen by dollar volume)"
    print(f"{len(TICKERS)} primary listings from {tick.entity_id.nunique()} firms")
    print(tick.groupby("hq").entity_id.nunique().sort_values(ascending=False).to_string())
    if "currency" in tick.columns:
        print("\ncurrencies:", tick.currency.value_counts(dropna=False).to_dict())
elif V1.exists():
    raise SystemExit(
        "config/tickers_v1.csv exists but config/tickers_primary.csv does not.\n"
        "  v1 holds every listing line per firm, several per company. Downloading it\n"
        "  would build a panel that double counts. Run section 2b first."
    )
else:
    tick    = pd.read_csv(DRAFT)
    TICKERS = tick.ticker.tolist()
    SOURCE  = "tickers_draft_v0.csv (HAND-WRITTEN DRAFT, survivorship biased)"
    print(f"{len(TICKERS)} draft tickers  "
          f"({(tick.leg=='US').sum()} US, {(tick.leg=='EU').sum()} EU)")
    print("\nWARNING: section 2 has not been run, so this is the convenience sample.")
    print("Fine for testing the data path. Not a research universe.")

BENCHMARKS = ["^GSPC", "SPY"]
print(f"\nsource : {SOURCE}")
print(f"benchmarks: {BENCHMARKS}")

# The two files have different schemas: the draft carries a hand-assigned `leg` column,
# the resolved one carries `exchange`. Pick whichever columns are actually present
# rather than assuming, which is how this cell crashed the first time it saw v1.
SHOW = [c for c in ["name", "hq", "n_assets", "ticker", "exchange", "leg"]
        if c in tick.columns]
display(tick[SHOW].head(40))
'''))

# --------------------------------------------------------------- preflight
cells.append(md(r"""
### 3a. Preflight: what can this API key actually see?

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
if not API_KEY:
    raise SystemExit(
        "FMP_API_KEY is not set. Section 0 prints 'api key: MISSING' when this happens.\n"
        "  Colab : add it in the Secrets panel, switch on notebook access, rerun section 0.\n"
        "  Local : export FMP_API_KEY='...'"
    )


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
    print("      access switched on. Section 0 prints 'api key: set' when it read correctly.")
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
### 3b. Where exactly is the paywall?

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
if len(open_) == len(w) and (w["rows"] > 0).all():
    print("DIAGNOSIS: no wall. Every variant, symbol and history depth returned data.")
    print("  This is the expected result on a paid tier. Nothing below applies; the")
    print("  branches after this one exist to name a paywall, and there is not one.")
elif got("DUK  light") and not got("DUK  full"):
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
### 3c. What is the covered symbol list, exactly?

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

        # The two variants do not share a column name for the closing price. /full
        # returns open/high/low/close, while /dividend-adjusted returns adjOpen/adjHigh/
        # adjLow/adjClose and no plain `close`. Everything downstream wants one column,
        # so normalise here and record which field it came from rather than leaving each
        # consumer to guess. Section 4 crashed with KeyError('close') on the first
        # dividend-adjusted panel because of exactly this.
        src_col = next((c for c in ("adjClose", "close", "price") if c in df.columns), None)
        if src_col is None:
            print(f"    {symbol}: no recognisable close column in {list(df.columns)}")
            return pd.DataFrame()
        df["price"] = pd.to_numeric(df[src_col], errors="coerce")
        df["price_field"] = src_col
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
lead = [c for c in ["symbol", "date", "price", "price_field", "series",
                    "open", "high", "low", "close", "adjOpen", "adjHigh", "adjLow",
                    "adjClose", "volume"]
        if c in prices.columns]
prices = prices[lead + [c for c in prices.columns if c not in lead]]

prices.to_csv(RAW / "panel_b_prices_daily.csv", index=False)

print(f"{len(prices):,} rows, {prices.symbol.nunique()} symbols")
print("columns returned:", list(prices.columns))
print("price taken from:", prices.price_field.value_counts().to_dict())
print("series:", prices.series.value_counts().to_dict())
display(
    prices.groupby("symbol")
          .agg(rows=("date", "size"), start=("date", "min"), end=("date", "max"))
          .sort_values("rows")
)
'''))

# ------------------------------------------------------------------ integrity
cells.append(md(r"""
## 4. Integrity checks and manifest

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
check("prices: a canonical price column exists", "price" in prices.columns,
      f"columns: {list(prices.columns)[:12]}")
check("prices: all prices strictly positive",
      (prices["price"].dropna() > 0).all() if "price" in prices else False)
_eqf = prices.loc[~prices.symbol.isin(BENCHMARKS), "price_field"] \
       if "price_field" in prices.columns else pd.Series(dtype=object)
check("prices: one price field across the EQUITY panel", _eqf.nunique() == 1,
      f"fields: {sorted(_eqf.unique())}")
check("prices: S&P 500 index present", "^GSPC" in set(prices.symbol))
check("prices: every requested symbol returned data",
      len(missing) == 0, f"missing: {missing}")
# A panel that mixes total-return and price-return series is not comparable across
# symbols, and the difference is a dividend yield, so it loads on exactly the kind of
# firm characteristic a hazard sort is likely to pick up. Fail loudly rather than let
# the mixture pass as a footnote.
# Scope the convention checks to the equity panel. A price index has no dividends to
# reinvest, so ^GSPC has no dividend-adjusted series at any price and will always fall
# back. Letting that fail the check permanently would teach us to ignore a red row,
# which is worse than not having the check. SPY is the total-return benchmark; ^GSPC is
# carried as a price index and labelled as one.
_eq = prices[~prices.symbol.isin(BENCHMARKS)]
_series = sorted(_eq["series"].unique()) if "series" in _eq.columns else ["unknown"]
check("prices: one return convention across the EQUITY panel", len(_series) == 1,
      f"series present: {_series}")
check("prices: equity convention is dividend-adjusted (total return)",
      _series == ["dividend-adjusted"],
      "price returns are not comparable with Fama-French total-return factors")

_bench = (prices[prices.symbol.isin(BENCHMARKS)]
          .groupby("symbol").series.first().to_dict())
check("benchmarks: at least one total-return benchmark present",
      "dividend-adjusted" in _bench.values(),
      f"{_bench}. ^GSPC is a price index and legitimately has no total-return series; "
      f"use SPY where a total-return benchmark is needed.")

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
        "price_field": sorted(prices["price_field"].unique()) if "price_field" in prices.columns else ["unknown"],
        "currencies": (pd.read_csv(REPO / "config" / "tickers_primary.csv")
                         .query("priceable").currency.value_counts().to_dict()
                       if (REPO / "config" / "tickers_primary.csv").exists() else {}),
        "currency_note": ("no FX conversion applied. GBp is pence, one hundredth of a "
                          "pound. Convert before any dollar-value weighting."),
    },
    "checks_failed": n_fail,
    "files": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
              for p in sorted(RAW.glob("*")) if p.is_file()},
}

(RAW / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2)[:1500])
'''))

PANELB_END = len(cells)

# Held back and appended last: this is the closing scope statement, so it has to come
# after every section, including ones added later.
absent_cell = md(r"""
## 5. What is deliberately absent

No returns, no regressions, no portfolio construction, no merge of the two panels, and
no survivorship correction. Those belong downstream of this file. This section is the
only place inside the notebook itself that says so, which is why it is worth keeping
even though the same limits are tracked in more detail elsewhere: a stranger who opens
this file on GitHub sees the scope statement without having to find anything else.

Before anything return-based is estimated on this data, three things have to close.

1. **The delisting hit rate is unmeasured, and now known to be blocked.**
   `01_survivorship_test_fmp.py` has never returned a number. Section 3c established
   why: the delisted companies *list* is open on a free key but delisted *price
   history* is refused, and knowing which firms died without being able to price them
   measures nothing. Until that rate is a number, the size of the survivorship problem
   is unknown rather than small.
2. **The ownership snapshot is undated.** The GEM Ownership Tracker is a single
   snapshot with sector vintages spanning roughly sixteen months, so the exposure
   variable carries look-ahead of unknown size. This is the worst of the three,
   because it contaminates the independent variable rather than the dependent one.
3. **The universe is not yet a universe.** Section 2 resolves entities to tickers, but
   a resolved ticker is not a price series, and some of the 328 entities are owners
   only in a financing sense. Both counts belong in the methods section, and they are
   different numbers.

For where each of these stands and what unblocks it, see `EXECUTION_CHECKLIST.html`
in the repository root rather than duplicating the detail here.
""")

# ------------------------------------------------------- Section 4: ticker resolution
cells.append(md(r"""
---

## 2. Resolving the universe to tickers

**Run this once, before buying an FMP plan. It needs no FMP key and costs nothing.**

**It does not depend on sections 1 to 3**, so it works whether or not the price panel
came back empty. Section 0 is the only prerequisite, because it sets `REPO` and reads
the Colab secrets.

The problem it solves: `outputs/cross_section.csv` identifies 328 asset owners by name,
LEI, PermID and CIK, and by no ticker at all. So there is no symbol list to buy prices
for, and nothing has yet established that 328 *listed* entities are even in the file.
For an asset ownership tracker they probably are not. State utilities, municipal
generators, co-operatives, infrastructure funds and wholly owned subsidiaries all own
power assets without having listed equity.

That gap sits directly under the plan decision. Premium at $49 covers the US, UK and
Canada, which is 185 of the 328 entities. Ultimate at $99 adds the 143 continental
European ones. Whether that $50 is worth paying depends entirely on how many of the 143
are listed, and no pricing page can answer that.

### Why ISINs, and why they are not enough on their own

`config/universe_isins.csv` maps each firm's LEI to its ISINs, taken from the GLEIF
golden copy you already hold. 296 of the 328 firms have at least one, including 137 of
the 143 continental European ones. That number is an upper bound rather than an answer,
because **ISINs are issued for bonds as readily as for shares**, and heavily indebted
utilities are exactly the entities that hold many ISINs and no listed equity. The file
carries 98,104 pairs, and the largest holders are banks: Deutsche Bank alone accounts
for 21,793, almost all structured notes.

OpenFIGI resolves this. It maps an ISIN to an instrument record carrying `marketSector`
and `securityType2`, so common stock can be separated from debt. It is free, and an API
key is optional but strongly recommended: without one you get 25 requests a minute at 10
ISINs each, with one you get 25 requests every 6 seconds at 100 each, which is the
difference between minutes and most of a day. Get one at
[openfigi.com/api](https://www.openfigi.com/api), then add it to Colab Secrets as
`OPENFIGI_API_KEY`. If you skip it the cell still runs, just slowly.
"""))

cells.append(code(r'''
# Optional. Everything below works without it, only slower.
OPENFIGI_KEY = os.environ.get("OPENFIGI_API_KEY")
if IN_COLAB and not OPENFIGI_KEY:
    try:
        from google.colab import userdata
        OPENFIGI_KEY = userdata.get("OPENFIGI_API_KEY")
        os.environ["OPENFIGI_API_KEY"] = OPENFIGI_KEY or ""
    except Exception:
        pass   # secret absent is a supported state, not an error

BATCH = 100 if OPENFIGI_KEY else 10          # jobs per request, set by OpenFIGI
PAUSE = 6.0 / 25 if OPENFIGI_KEY else 60.0 / 25   # seconds between requests

universe = pd.read_csv(REPO / "config" / "universe.csv")
pairs    = pd.read_csv(REPO / "config" / "universe_isins.csv")

# Try each firm's home-country ISINs first. A primary listing is usually domestic, so
# this resolves most firms in the first wave and keeps the 21,793-ISIN banks from
# dominating the job.
HQ_ISO = {
    "United States": "US", "United Kingdom": "GB", "Germany": "DE", "France": "FR",
    "Italy": "IT", "Spain": "ES", "Norway": "NO", "Switzerland": "CH", "Finland": "FI",
    "Austria": "AT", "Belgium": "BE", "Portugal": "PT", "Sweden": "SE", "Greece": "GR",
    "Netherlands": "NL", "Ireland": "IE", "Denmark": "DK",
}
lei_hq = dict(zip(universe.lei, universe.hq.map(HQ_ISO)))

# NOTE: always pairs["isin"], never pairs.isin. The attribute form returns the DataFrame
# .isin() method rather than the column, and the resulting error is confusing.
pairs["home"] = [i[:2] == lei_hq.get(l) for l, i in zip(pairs["lei"], pairs["isin"])]
pairs = pairs.sort_values(["lei", "home", "isin"], ascending=[True, False, True])

# Materialise lei -> ordered ISIN list once. Filtering a 98k row frame inside the wave
# loop would rescan it several hundred times per wave for no reason.
BY_LEI = {lei: g["isin"].tolist() for lei, g in pairs.groupby("lei", sort=False)}

print(f"{len(universe)} firms, {len(pairs):,} ISINs")
print(f"OpenFIGI key: {'present' if OPENFIGI_KEY else 'ABSENT, will run slowly'}")
print(f"batch size {BATCH}, {PAUSE:.2f}s between requests")
'''))

cells.append(md(r"""
### The resolution loop

It runs in waves. Wave 1 tries at most 20 ISINs per firm, wave 2 raises the cap to 100
for whatever is still unresolved, and so on. **Only unresolved firms carry into the next
wave**, which is what keeps this from becoming a 98,104-call job: most firms resolve on
their domestic ISINs in the first wave, and only the handful of large bond issuers ever
reach the later ones.

Partial results are written to disk after every wave, so a dropped Colab runtime costs
you the current wave rather than the whole run.
"""))

cells.append(code(r'''
FIGI_URL = "https://api.openfigi.com/v3/mapping"
CACHE    = RAW / "openfigi_cache.json"

cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
print(f"cache: {len(cache):,} ISINs already resolved")


def figi_lookup(isins):
    """Map ISINs to instrument records. Returns {isin: [records]}.

    Unknown ISINs get an empty list, which is cached too: 'OpenFIGI has never heard of
    this' is a real answer and re-asking it on every rerun wastes the rate limit.
    """
    todo = [i for i in isins if i not in cache]
    for k in range(0, len(todo), BATCH):
        chunk = todo[k:k + BATCH]
        body  = [{"idType": "ID_ISIN", "idValue": i} for i in chunk]
        head  = {"Content-Type": "application/json"}
        if OPENFIGI_KEY:
            head["X-OPENFIGI-APIKEY"] = OPENFIGI_KEY

        for attempt in range(5):
            r = requests.post(FIGI_URL, json=body, headers=head, timeout=60)
            if r.status_code == 429:                 # rate limited, back off and retry
                time.sleep(PAUSE * (2 ** attempt) + 1)
                continue
            r.raise_for_status()
            for isin_code, res in zip(chunk, r.json()):
                cache[isin_code] = res.get("data", []) if isinstance(res, dict) else []
            break
        else:
            raise RuntimeError("OpenFIGI kept returning 429. Wait a minute and rerun.")
        time.sleep(PAUSE)
    return {i: cache.get(i, []) for i in isins}


def equity_rows(records):
    """Keep only listed common stock. This is the whole point of the exercise."""
    return [d for d in records
            if d.get("marketSector") == "Equity"
            and d.get("securityType2") in ("Common Stock", "Depositary Receipt")
            and d.get("ticker") and d.get("exchCode")]


resolved   = {}                        # lei -> list of equity records
unresolved = list(universe.lei.dropna().unique())

# Caps keep the early waves cheap: most firms resolve on their first few domestic ISINs,
# so there is no reason to send Deutsche Bank's 21,793 in wave 1.
CAPS = [20, 100, 500]


def run_wave(leis, cap, label):
    """Look up at most `cap` ISINs per firm, then re-test which firms resolved."""
    seen, batch_isins = set(), []
    for lei in leis:
        for i in BY_LEI.get(lei, [])[:cap]:
            if i not in seen and i not in cache:
                seen.add(i)
                batch_isins.append(i)

    print(f"\n{label}: {len(leis)} firms unresolved, "
          f"{len(batch_isins):,} new ISINs to look up")
    if batch_isins:
        figi_lookup(batch_isins)
        CACHE.write_text(json.dumps(cache))

    still = []
    for lei in leis:
        eqs = [(i, d) for i in BY_LEI.get(lei, [])[:cap]
               for d in equity_rows(cache.get(i, []))]
        if eqs:
            resolved[lei] = eqs
        else:
            still.append(lei)
    print(f"  resolved so far: {len(resolved)}  still unresolved: {len(still)}")
    return still


for wave, cap in enumerate(CAPS, start=1):
    if not unresolved:
        break
    unresolved = run_wave(unresolved, cap, f"wave {wave}, cap {cap}")

# A cap is a budget, not a finding. The 20 August run stopped at 500 and reported seven
# firms unresolved, among them Exxon Mobil, Alphabet and JPMorgan, which are obviously
# listed. Their equity ISIN simply sorts late: ISINs are ordered alphabetically within
# home country, so US30231G1022 sits behind every US0, US1 and US2 code Exxon has ever
# issued. Dropping Exxon and its 72 assets because of an alphabetical tiebreak would be
# a sampling error introduced by an implementation detail, which is the worst kind
# because nothing downstream would ever reveal it.
#
# Uncapping looked prohibitive when this was first written, but that estimate came from
# a mocked dry run where over a hundred firms were unresolved. In the real data it is a
# handful, so finishing them properly costs well under a minute. Measure, then decide.
capped = [l for l in unresolved if len(BY_LEI.get(l, [])) > CAPS[-1]]
if capped:
    rest = [l for l in unresolved if l not in set(capped)]
    total = sum(len(BY_LEI[l]) for l in capped)
    unresolved = rest + run_wave(capped, 10 ** 9,
                                 f"final pass, no cap, {total:,} ISINs across "
                                 f"{len(capped)} firms")

no_isin = [l for l in universe.lei.dropna().unique() if not BY_LEI.get(l)]

print(f"\ndone. {len(resolved)} of {len(universe)} firms have listed common stock")
print(f"  no ISIN at all in GLEIF   : {len(no_isin)}")
print(f"  ISINs, but none is equity : {len(unresolved) - len(no_isin)}")
if unresolved:
    nm  = universe.set_index("lei")["name"]
    big = sorted(unresolved, key=lambda l: -len(BY_LEI.get(l, [])))[:12]
    print("\n  largest unresolved, by ISIN count. A well-known listed name appearing")
    print("  here means the search missed it, not that it is unlisted:")
    for l in big:
        print(f"      {nm.get(l, '?')[:44]:46s} {len(BY_LEI.get(l, [])):>6,} ISINs")
'''))

cells.append(md(r"""
### The table that decides the plan

`listed` below counts firms with at least one common stock line anywhere in the world.
Read the two summary lines under it: they are the Premium and Ultimate reach, measured
rather than assumed.

One caveat to carry into the methods section. A firm resolving to *some* listed equity
is not the same as that equity being the right one to price. Subsidiaries with their own
listings, dual-class structures and depositary receipts all need a deliberate choice of
which line represents the firm. `config/tickers_v1.csv` keeps every candidate so that
choice is visible and revisable rather than baked in.
"""))

cells.append(code(r'''
rows = []
for lei, recs in resolved.items():
    for isin_code, d in recs:
        rows.append({"lei": lei, "isin": isin_code,
                     "ticker": d["ticker"], "exchange": d["exchCode"],
                     "figi_name": d.get("name"), "type": d.get("securityType2")})
cand = pd.DataFrame(rows).drop_duplicates(["lei", "ticker", "exchange"])
print(f"{len(cand):,} candidate listing lines across {cand.lei.nunique()} firms, "
      f"median {cand.groupby('lei').size().median():.0f} per firm")

out = universe.merge(cand, on="lei", how="left")
out["listed"] = out.ticker.notna()
out.to_csv(REPO / "config" / "tickers_v1.csv", index=False)

firm = out.groupby("entity_id").agg(hq=("hq", "first"), n_assets=("n_assets", "first"),
                                    listed=("listed", "max"))
tab = firm.groupby("hq").agg(firms=("listed", "size"), listed=("listed", "sum"),
                             assets=("n_assets", "sum")).sort_values("firms", ascending=False)
tab["listed_assets"] = firm[firm.listed].groupby("hq").n_assets.sum().reindex(tab.index).fillna(0).astype(int)
display(tab)

PREMIUM = ["United States", "United Kingdom", "Canada"]
p = firm[firm.hq.isin(PREMIUM) & firm.listed]
u = firm[firm.listed]
print(f"\nPREMIUM  $49: {len(p):3d} listed firms, {int(p.n_assets.sum()):5,} assets")
print(f"ULTIMATE $99: {len(u):3d} listed firms, {int(u.n_assets.sum()):5,} assets")
print(f"the extra $50 buys {len(u) - len(p)} firms and {int(u.n_assets.sum() - p.n_assets.sum()):,} assets")
print(f"\nwrote {REPO / 'config' / 'tickers_v1.csv'}")
'''))

cells.append(md(r"""
### 2b. Choosing one listing per firm

**Needs a paid FMP key. Do not run Panel B before this.**

`tickers_v1.csv` above holds every listing line OpenFIGI knows about, which is several
per firm rather than one. Allianz appears as `ALV` in Frankfurt, `ALIZY` as a US
depositary receipt and `ALIZF` on the US foreign board. Akzo Nobel appears as `AKZOY`
and `AKZOF`. Archer Daniels appears as `ADM` and as `ADMUSD`, a currency-denominated
line on an international order book. These are the same company.

Keeping all of them is wrong three times over, and the first reason is the one that
actually matters:

1. **The panel would double count.** A hazard-sorted portfolio holding `ALV`, `ALIZY`
   and `ALIZF` holds one bet with three weights. Cross-sectional standard errors
   computed on that panel are wrong in a direction that flatters you, because the
   duplicate lines are perfectly correlated and look like independent observations.
2. **Depositary receipts are not the security.** An ADR carries the underlying return
   plus an exchange rate move plus a sponsorship spread, and it trades on US hours
   against a European close. Mixing ADRs and ordinaries puts a currency factor into
   your cross-section that has nothing to do with climate hazard.
3. Downloading them costs a multiple of the time, which matters while the subscription
   is running.

The rule used here is to let **liquidity arbitrate**, measured rather than assumed.
For every candidate, ask FMP what it can price, pull one recent quarter, and keep the
line with the highest median daily dollar volume. That reliably picks the primary
listing without needing a hand-maintained table of exchange codes, and it records why
each choice was made so the decision is auditable rather than buried.

The first cell probes the ISIN search endpoint and prints one raw response. **Read
that output before running the rest.** If the field names differ from what the next
cell expects, send it to me rather than guessing, because a silent mis-parse here
becomes a wrong universe that nothing downstream will flag.
"""))

cells.append(code(r'''
# Probe first, parse second. This prints the raw shape of one response so a field-name
# change in the vendor API is visible immediately rather than becoming a silent
# mis-parse in the cell below.
_probe_isins = cand["isin"].dropna().unique()[:3].tolist()
for _i in _probe_isins:
    _r = requests.get(SEARCH_ISIN, params={"isin": _i, "apikey": API_KEY}, timeout=45)
    print(f"{_i}  HTTP {_r.status_code}")
    if _r.status_code == 200:
        print("   ", json.dumps(_r.json())[:400])
    time.sleep(0.1)
'''))

cells.append(code(r'''
ISIN_CACHE = RAW / "fmp_isin_cache.json"
isin_map = json.loads(ISIN_CACHE.read_text()) if ISIN_CACHE.exists() else {}
print(f"isin cache: {len(isin_map):,} already looked up")


def fmp_symbols_for_isin(isin_code):
    """FMP's own symbols for an ISIN. Parsed defensively: the payload has been a bare
    list and a dict-wrapped list at different times, and a KeyError here would be
    indistinguishable from 'this ISIN is not covered'."""
    if isin_code in isin_map:
        return isin_map[isin_code]
    # Catch network and decode failures only. A bare `except Exception` here once
    # swallowed a NameError and reported every ISIN as uncovered, which looks exactly
    # like a plan limit and took an integration run to find. Let bugs raise.
    try:
        r = requests.get(SEARCH_ISIN, params={"isin": isin_code, "apikey": API_KEY},
                         timeout=45)
        payload = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        payload = []
    if isinstance(payload, dict):
        payload = payload.get("data") or payload.get("results") or []
    out = []
    for d in payload if isinstance(payload, list) else []:
        if isinstance(d, dict) and d.get("symbol"):
            out.append({"symbol": d["symbol"],
                        "currency": d.get("currency"),
                        "exchange": d.get("exchange") or d.get("exchangeShortName"),
                        "name": d.get("name") or d.get("companyName")})
    isin_map[isin_code] = out
    return out


PROBE_FROM, PROBE_TO = "2024-01-02", "2024-03-28"
LIQ_CACHE = RAW / "fmp_liquidity_cache.json"
_liq = json.loads(LIQ_CACHE.read_text()) if LIQ_CACHE.exists() else {}


def liquidity(symbol):
    """Median daily dollar volume over one recent quarter, and the bar count.

    Dollar volume rather than share volume, because share counts are not comparable
    across a EUR ordinary and a USD receipt. Median rather than mean, because a single
    index-rebalance day would otherwise decide the primary listing.
    """
    # Always exactly two values. The cache row is [dollar_vol, bars, share_vol] and an
    # early version returned it whole, so every caller unpacking two broke the moment
    # the cache was warm and worked fine while it was cold. Share volume is reached
    # through share_volume() instead.
    if symbol in _liq:
        return _liq[symbol][0], _liq[symbol][1]
    try:
        r = requests.get(EOD, params={"symbol": symbol, "from": PROBE_FROM,
                                      "to": PROBE_TO, "apikey": API_KEY}, timeout=45)
        rows = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        rows = []
    if isinstance(rows, dict):
        rows = rows.get("historical", [])
    if not rows:
        _liq[symbol] = [0.0, 0, 0.0]
        return 0.0, 0
    d = pd.DataFrame(rows)
    if not {"close", "volume"}.issubset(d.columns):
        _liq[symbol] = [0.0, len(d), 0.0]
        return 0.0, len(d)
    px  = pd.to_numeric(d["close"], errors="coerce")
    vol = pd.to_numeric(d["volume"], errors="coerce")
    dv  = (px * vol).dropna()
    out = [float(dv.median()) if len(dv) else 0.0, len(d),
           float(vol.median()) if len(vol.dropna()) else 0.0]
    _liq[symbol] = out
    return out[0], out[1]


def share_volume(symbol):
    """Shares traded per day, used only to break ties between share classes."""
    return (_liq.get(symbol) or [0, 0, 0])[2]


scored = []
uniq_isins = cand["isin"].dropna().unique().tolist()
print(f"resolving {len(uniq_isins):,} equity ISINs to FMP symbols")

for k, isin_code in enumerate(uniq_isins, 1):
    if k % 100 == 0:
        print(f"  {k}/{len(uniq_isins)}")
        ISIN_CACHE.write_text(json.dumps(isin_map))
    for s in fmp_symbols_for_isin(isin_code):
        scored.append({"isin": isin_code, **s})
ISIN_CACHE.write_text(json.dumps(isin_map))

if not scored:
    raise SystemExit(
        "FMP returned no symbol for any of the equity ISINs.\n"
        "  That is not a normal result on a paid key. Check that the probe cell above\n"
        "  printed real responses, and that section 2 produced a non-empty `cand`."
    )
sc = pd.DataFrame(scored).drop_duplicates("symbol")
print(f"{len(sc):,} distinct FMP symbols to score")

liq = {}
for k, s in enumerate(sc["symbol"].tolist(), 1):
    if k % 100 == 0:
        print(f"  scored {k}/{len(sc)}")
    liq[s] = liquidity(s)
sc["dollar_vol"]  = sc["symbol"].map(lambda s: liq[s][0])
sc["bars_q1_24"]  = sc["symbol"].map(lambda s: liq[s][1])
sc["share_vol"]   = sc["symbol"].map(share_volume)
LIQ_CACHE.write_text(json.dumps(_liq))
'''))

cells.append(code(r'''
# One line per firm: the most liquid FMP-priceable listing.
lei_of = dict(zip(cand["isin"], cand["lei"]))   # cand.isin is the method, not the column
sc["lei"] = sc["isin"].map(lei_of)

alive = sc[(sc.dollar_vol > 0) & (sc.bars_q1_24 > 30)].copy()

# Dollar volume alone picks BRK-A over BRK-B: the A share costs about 1,500 times more,
# so a few hundred shares a day rivals the B share's millions. They are claims on the
# same firm with near identical returns, but the A share trades in tiny share counts,
# which means stale prices and coarse discreteness in a daily return series. So: use
# dollar volume to decide which lines are seriously traded, then among lines within a
# factor of three of the best, prefer the one with more SHARES changing hands.
alive["dv_rank"] = alive.groupby("lei")["dollar_vol"].transform("max")
contenders = alive[alive.dollar_vol >= alive.dv_rank / 3]
pick = (contenders.sort_values(["share_vol", "dollar_vol"], ascending=False)
                  .drop_duplicates("lei")
                  .rename(columns={"symbol": "primary_symbol"}))

# Map through dictionaries rather than pd.merge(on="lei"). pandas joins NaN keys to each
# other, so any firm without a LEI would be matched to every other firm without one. The
# 13 firms whose `lei` column read the literal string "not found", Chevron among them,
# are exactly that case.
LEICOLS = ["primary_symbol", "currency", "exchange", "dollar_vol"]
by_lei  = pick.set_index("lei")[LEICOLS].to_dict("index")

primary = universe.copy()
for c in LEICOLS:
    primary[c] = primary["lei"].map(lambda l: (by_lei.get(l) or {}).get(c)
                                    if pd.notna(l) else None)
primary["route"] = primary.primary_symbol.notna().map({True: "isin", False: None})

# ---- fallback for firms with no usable LEI, resolved through their SEC CIK instead.
need_cik = primary[primary.primary_symbol.isna() & primary["cik"].notna()]
print(f"\n{len(need_cik)} firms unresolved by ISIN but carrying a CIK, trying CIK route")
for _, row in need_cik.iterrows():
    try:
        r = requests.get(f"{BASE}/search-cik",
                         params={"cik": int(row["cik"]), "apikey": API_KEY}, timeout=45)
        hits = r.json() if r.status_code == 200 else []
    except Exception:
        hits = []
    if isinstance(hits, dict):
        hits = hits.get("data") or []
    best, best_dv = None, 0.0
    for h in hits if isinstance(hits, list) else []:
        s = h.get("symbol")
        if not s:
            continue
        dv, bars = liquidity(s)
        if dv > best_dv and bars > 30:
            best, best_dv = h, dv
    if best:
        i = row.name
        primary.loc[i, "primary_symbol"] = best["symbol"]
        primary.loc[i, "currency"]  = best.get("currency")
        primary.loc[i, "exchange"]  = best.get("exchange") or best.get("exchangeShortName")
        primary.loc[i, "dollar_vol"] = best_dv
        primary.loc[i, "route"] = "cik"
        print(f"  {row['name'][:38]:40s} -> {best['symbol']}")

primary["priceable"] = primary.primary_symbol.notna()

# A symbol standing for two different GEM entities means the crosswalk collapsed two
# firms into one, which would double the assets attributed to that firm.
dupes = primary.loc[primary.priceable & primary.primary_symbol.duplicated(keep=False)]
if len(dupes):
    print(f"\nWARNING: {len(dupes)} rows share a primary_symbol with another entity:")
    print(dupes[["entity_id", "name", "primary_symbol"]].to_string(index=False))
else:
    print("\nno symbol is claimed by two entities")

primary.to_csv(REPO / "config" / "tickers_primary.csv", index=False)

n_cand   = cand["lei"].nunique()
n_priced = int(primary.priceable.sum())
print(f"\nfirms with an equity line found by OpenFIGI : {n_cand}")
print(f"firms FMP can actually price               : {n_priced}"
      f"  ({int((primary.route == 'isin').sum())} via ISIN, "
      f"{int((primary.route == 'cik').sum())} via CIK)")
print(f"candidate lines collapsed: {len(sc):,} symbols -> {n_priced} primaries")

print("\ncurrency of the chosen listings:")
print(primary.currency.value_counts(dropna=False).to_string())

tab2 = (primary.groupby("hq")
        .agg(firms=("entity_id", "size"), priceable=("priceable", "sum"),
             assets=("n_assets", "sum"))
        .sort_values("firms", ascending=False))
tab2["priceable_assets"] = (primary[primary.priceable].groupby("hq").n_assets.sum()
                            .reindex(tab2.index).fillna(0).astype(int))
display(tab2)
print(f"\nTOTAL priceable: {n_priced} firms, "
      f"{int(primary[primary.priceable].n_assets.sum()):,} assets")
print(f"wrote {REPO / 'config' / 'tickers_primary.csv'}")
'''))

cells.append(md(r"""
### 2c. Fill in currency, and look at what was lost

Two gaps in the cell above, both worth closing before any download.

**`search-isin` does not return a currency.** The 21 August run left `currency` empty
for 295 of 328 firms. That field is not cosmetic: a price series from Paris is in euros,
from Milan in euros, from London often in *pence* rather than pounds, and Ken French's
factors are in dollars. Mixing them without conversion produces returns that are part
asset return and part exchange rate move, and the contamination is invisible in the
data. The `profile` endpoint returns currency and exchange per symbol, so this fills
them from there while the subscription is live. After you cancel it is unrecoverable.

**Nothing yet shows which firms were dropped.** 37 of 328 came back unpriceable, and an
aggregate count cannot tell you whether those are 37 tiny holders or one firm with 61
assets. Ireland went from 2 firms to 0, and CRH is a large owner that trades on the
NYSE, so at least one of those two is a resolution failure rather than a genuinely
unlisted entity. The cell prints the losses ordered by asset count so the expensive ones
are at the top, and prints the chosen listing for the largest firms so a wrong pick,
a US over-the-counter line standing in for a European primary, is visible at a glance
rather than buried in a CSV.
"""))

cells.append(code(r'''
PROF_CACHE = RAW / "fmp_profile_cache.json"
prof = json.loads(PROF_CACHE.read_text()) if PROF_CACHE.exists() else {}


def profile_of(symbol):
    if symbol in prof:
        return prof[symbol]
    try:
        r = requests.get(PROFILE, params={"symbol": symbol, "apikey": API_KEY}, timeout=45)
        payload = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        payload = []
    if isinstance(payload, dict):
        payload = payload.get("data") or [payload]
    rec = payload[0] if isinstance(payload, list) and payload else {}
    prof[symbol] = rec if isinstance(rec, dict) else {}
    return prof[symbol]


syms = primary.loc[primary.priceable, "primary_symbol"].tolist()
print(f"fetching profiles for {len(syms)} primary listings")
for k, s in enumerate(syms, 1):
    profile_of(s)
    if k % 100 == 0:
        print(f"  {k}/{len(syms)}")
        PROF_CACHE.write_text(json.dumps(prof))
PROF_CACHE.write_text(json.dumps(prof))


def field(sym, *names):
    p = prof.get(sym) or {}
    for n in names:
        if p.get(n):
            return p[n]
    return None


for col, keys in [("currency", ("currency",)),
                  ("exchange", ("exchangeShortName", "exchange")),
                  ("listed_country", ("country",)),
                  ("ipo_date", ("ipoDate",))]:
    primary[col] = primary.primary_symbol.map(
        lambda s: field(s, *keys) if pd.notna(s) else None)

primary.to_csv(REPO / "config" / "tickers_primary.csv", index=False)

print("\ncurrency of the chosen listings:")
print(primary.loc[primary.priceable, "currency"].value_counts(dropna=False).to_string())
print("\nexchange:")
print(primary.loc[primary.priceable, "exchange"].value_counts(dropna=False).head(15).to_string())

# GBp is pence, one hundredth of a pound. Left unconverted it inflates a UK price level
# by 100x. It does not affect simple returns, but it does affect anything scaled by
# price, and it will silently wreck a dollar-value weighting scheme.
gbp = primary[primary.currency.astype(str).str.upper().isin(["GBP", "GBX", "GBP PENCE"])]
if len(gbp):
    print(f"\n{len(gbp)} UK listings: check GBp (pence) versus GBP before any conversion")
'''))

cells.append(code(r'''
lost = (primary[~primary.priceable]
        .sort_values("n_assets", ascending=False)[["name", "hq", "n_assets", "lei", "cik"]])
print(f"{len(lost)} firms not priceable, holding "
      f"{int(lost.n_assets.sum()):,} of {int(primary.n_assets.sum()):,} assets "
      f"({lost.n_assets.sum() / primary.n_assets.sum():.1%})")
print("\nlargest losses first. A well-known listed company here is a resolution failure,")
print("not evidence that it is unlisted, and it should be chased before you cancel:")
display(lost.head(25))

print("\nspot check. The chosen listing for the 20 largest owners. A European firm showing")
print("a US over-the-counter symbol here means the liquidity test picked the wrong line:")
display(primary[primary.priceable]
        .sort_values("n_assets", ascending=False)
        .head(20)[["name", "hq", "n_assets", "primary_symbol", "exchange",
                   "currency", "route"]])
'''))

cells.append(md(r"""
### 2d. Last pass: find the ones the identifiers missed

The 21 August run left 37 firms unpriceable, holding 287 assets, 5.6 percent of the
total. Reading that list rather than the count is what separates a real limitation from
a bug, and it contains both.

**Correctly excluded, and they should stay excluded.** City of Vienna is a city.
enercity AG is municipally owned. UBS Fund Management is an unlisted subsidiary whose
parent UBS Group is already in the sample separately. Edison SpA was taken private by
EDF. EVRAZ is suspended from the LSE under sanctions, so it is genuinely unpriceable
rather than merely unresolved.

**Resolution failures, and there are more than a handful.** CRH holds 61 assets and
trades on the NYSE. UPM-Kymmene, Kemira and Metsä Board are all listed in Helsinki and
all three failed, which looks like a pattern rather than three coincidences. Morgan
Stanley, Linde and LyondellBasell are among the most liquid equities in the world. None
of these is unlisted; the identifier route simply did not reach them.

So this cell retries the unpriceable firms by **name**, which is a weaker key than an
ISIN and therefore used last and defensively: a candidate is only accepted if the name
similarity clears a threshold, and the match is printed for you to read rather than
applied silently.

**One category is left deliberately unresolved, because it is your decision and not a
lookup.** Entergy Louisiana LLC and Pacific Gas and Electric Co are wholly owned
operating subsidiaries of listed parents, Entergy Corp and PG&E Corp. Their assets are
real and the priced claim on them is the parent's equity. Rolling them up would recover
the assets, but it also changes what a firm is in your cross-section, and it interacts
with the lookthrough already in the GEM ownership graph, so doing it silently risks
double counting assets the parent is credited with twice. The cell flags these rather
than merging them.
"""))

cells.append(code(r'''
from difflib import SequenceMatcher

SUFFIX = re.compile(r"\b(corp|corporation|inc|plc|ltd|limited|ag|sa|spa|nv|oyj|asa|se|"
                    r"holding|holdings|group|company|co|lp|llc|the)\b\.?", re.I)


def norm(s):
    s = SUFFIX.sub(" ", str(s).lower())
    return re.sub(r"[^a-z0-9 ]", " ", s).split()


def similar(a, b):
    return SequenceMatcher(None, " ".join(norm(a)), " ".join(norm(b))).ratio()


NAME_MIN = 0.72          # below this, a "match" is usually a different company

todo = primary[~primary.priceable].copy()
print(f"retrying {len(todo)} unpriceable firms by name, threshold {NAME_MIN}\n")

found = 0
for i, row in todo.iterrows():
    try:
        r = requests.get(f"{BASE}/search-name",
                         params={"query": row["name"], "limit": 10, "apikey": API_KEY},
                         timeout=45)
        hits = r.json() if r.status_code == 200 else []
    except Exception:
        hits = []
    if isinstance(hits, dict):
        hits = hits.get("data") or []

    best, best_key = None, (0.0, 0.0)
    for h in hits if isinstance(hits, list) else []:
        sym = h.get("symbol")
        if not sym:
            continue
        sim = similar(row["name"], h.get("name") or h.get("companyName") or "")
        if sim < NAME_MIN:
            continue
        dv, bars = liquidity(sym)
        if bars <= 30:
            continue
        if (sim, dv) > best_key:
            best, best_key = h, (sim, dv)

    if best:
        found += 1
        primary.loc[i, "primary_symbol"] = best["symbol"]
        primary.loc[i, "dollar_vol"] = best_key[1]
        primary.loc[i, "route"] = "name"
        print(f"  {row['name'][:36]:38s} -> {best['symbol']:12s} "
              f"(similarity {best_key[0]:.2f}, {int(row['n_assets'])} assets)")
    time.sleep(0.05)

LIQ_CACHE.write_text(json.dumps(_liq))
primary["priceable"] = primary.primary_symbol.notna()

dupes = primary.loc[primary.priceable & primary.primary_symbol.duplicated(keep=False)]
print(f"\nrecovered {found} firms by name")
print("duplicate symbols after the name pass:",
      "NONE" if not len(dupes) else f"{len(dupes)} rows, READ THESE")
if len(dupes):
    display(dupes[["entity_id", "name", "hq", "n_assets", "primary_symbol", "route"]])
'''))

cells.append(code(r'''
# ---------------------------------------------------------------- hand overrides
# Applied last, after every automatic route, because the automatic routes cannot see
# what a security IS. The name search matches on company name alone, so it happily
# returned PCG-PA and UEPEP, which are preferred shares: bond-like claims that do not
# carry the equity return and would sit in a hazard-sorted portfolio behaving like debt.
# An override file keeps each correction explicit, reasoned and diffable, which is what
# a hand-checked crosswalk should be. A blank symbol means drop the firm.
OVR = REPO / "config" / "ticker_overrides.csv"
if not OVR.exists():
    raise SystemExit(
        f"config/ticker_overrides.csv is missing from {REPO}.\n"
        "  It is committed, so this means the Colab clone is behind the repository.\n"
        "  Check the `commit :` line printed by section 0 against your latest push.\n"
        "  Refusing to continue: silently skipping the overrides ships preferred\n"
        "  shares into the price panel, which is what happened on 21 August."
    )
if OVR.exists():
    ov = pd.read_csv(OVR)
    print(f"\napplying {len(ov)} hand overrides from {OVR.name}")
    for _, o in ov.iterrows():
        hit = primary.name.astype(str).str.strip() == str(o["name"]).strip()
        if not hit.any():
            print(f"  WARNING no match for {o['name']!r}, override not applied")
            continue
        new = o["symbol"] if isinstance(o["symbol"], str) and o["symbol"].strip() else None
        for i in primary.index[hit]:
            was = primary.loc[i, "primary_symbol"]
            primary.loc[i, "primary_symbol"] = new
            primary.loc[i, "route"] = "override" if new else None
            print(f"  {o['name'][:34]:36s} {str(was):10s} -> {str(new)}")
    primary["priceable"] = primary.primary_symbol.notna()

# Refresh currency and exchange for anything the name pass added, then write.
for s in primary.loc[primary.priceable, "primary_symbol"]:
    profile_of(s)
PROF_CACHE.write_text(json.dumps(prof))

for col, keys in [("currency", ("currency",)),
                  ("exchange", ("exchangeShortName", "exchange")),
                  ("listed_country", ("country",)),
                  ("ipo_date", ("ipoDate",))]:
    primary[col] = primary.primary_symbol.map(
        lambda s: field(s, *keys) if pd.notna(s) else None)

primary.to_csv(REPO / "config" / "tickers_primary.csv", index=False)

still = primary[~primary.priceable].sort_values("n_assets", ascending=False)
print(f"FINAL: {int(primary.priceable.sum())} of {len(primary)} firms priceable, "
      f"{int(primary.loc[primary.priceable, 'n_assets'].sum()):,} of "
      f"{int(primary.n_assets.sum()):,} assets "
      f"({primary.loc[primary.priceable, 'n_assets'].sum() / primary.n_assets.sum():.1%})")
print("\nby route:", primary.route.value_counts(dropna=False).to_dict())
print(f"\nstill unpriceable: {len(still)} firms, {int(still.n_assets.sum())} assets")
display(still[["name", "hq", "n_assets"]].head(20))

# Symbol patterns are a weak signal and the first version proved it: 23 flags of which
# 20 were false. "HOLN.SW" matched a warrant rule because the Swiss exchange suffix ends
# in W, and AEP, COP and CNP matched a preferred rule for containing a P. So: test the
# root only, keep just the patterns that are nearly always right, and let liquidity do
# the real work. A preferred share, a warrant and a secondary international line are all
# thinly traded, which is a property of the security rather than a guess about its name.
SUSPECT = [
    (re.compile(r"-P[A-Z]?$"),        "US preferred share"),
    (re.compile(r"^[A-Z]{1,4}PR[A-Z]?$"), "preferred series"),
    # No trailing-W warrant rule. Three-letter tickers ending in W are ordinary common
    # stock far more often than they are warrants: DOW, PNW, CLW and LOW would all be
    # flagged for nothing. Warrants are rare here and the liquidity screen below catches
    # them anyway, which is the better trade.
    (re.compile(r"^0[A-Z0-9]{3}$"),   "London international line, not a primary listing"),
]
SUFFIX_OK = re.compile(r"\.(F|BE|MU|SG|DU|HM)$")     # German regional floors, not XETRA

flags = []
for _, r in primary[primary.priceable].iterrows():
    sym  = str(r.primary_symbol)
    root = sym.split(".")[0]
    why  = None
    for rx, label in SUSPECT:
        if rx.search(root):
            why = label
            break
    if why is None and SUFFIX_OK.search(sym):
        why = "regional German floor rather than the primary XETRA line"
    if why:
        flags.append({"name": r["name"], "symbol": sym,
                      "n_assets": r["n_assets"], "why": why})

print(f"\n{len(flags)} symbols match a high-precision pattern:")
if flags:
    display(pd.DataFrame(flags).sort_values("n_assets", ascending=False))

# The stronger signal. Median daily dollar volume was already measured in 2b, and a
# genuinely primary listing of a firm large enough to own power assets does not trade
# a few thousand dollars a day. Anything down here is a preferred line, a secondary
# venue, or a firm too illiquid to hold in a tradeable portfolio, and all three matter.
THIN = 1_000_000
thin = (primary[primary.priceable & (primary.dollar_vol.fillna(0) < THIN)]
        .sort_values("dollar_vol")[["name", "hq", "n_assets", "primary_symbol",
                                    "exchange", "dollar_vol", "route"]])
print(f"\n{len(thin)} listings trade under ${THIN:,} a day. Read these: the reason a line")
print("is thin is usually that it is not the security you meant to buy.")
display(thin.head(25))

print("\nAnything wrong goes in config/ticker_overrides.csv, which is applied above and")
print("committed, so every hand correction stays visible and reviewable in git.")

print("\nwholly owned subsidiaries of listed parents, YOUR CALL, not merged here:")
SUBS = ["Entergy Louisiana", "Pacific Gas and Electric Co", "Union Electric"]
flag = primary[primary.name.astype(str).str.contains("|".join(SUBS), case=False, na=False)]
display(flag[["name", "hq", "n_assets", "primary_symbol", "priceable"]])
print(f"wrote {REPO / 'config' / 'tickers_primary.csv'}")
'''))

cells.append(md(r"""
### Before you read this as settled

Two things this cell does not tell you, both worth a line in the methods section.

**A ticker is not a price series.** OpenFIGI says the instrument exists; whether FMP
covers it, and from what date, is a separate question that only the paid key answers.
Expect attrition between this count and the delivered panel, and report both numbers.

**Some of these entities are owners only in a financing sense.** Deutsche Bank,
JPMorgan, Goldman Sachs, Santander and Crédit Agricole all appear in the 328. Their
presence almost certainly reflects lookthrough of financing stakes rather than
operational control, and a bank's hazard exposure computed that way is an artefact of
the ownership graph rather than a fact about its balance sheet. Decide explicitly
whether financial holders belong in the cross-section, and say which way you went.
"""))

# ---------------------------------------------------------------- run order
# Written order is not run order. Ticker resolution was added after Panel B but has to
# come before it, because it produces the symbol list Panel B prices. Reassemble here
# rather than shuffling hundreds of lines of text above.
head    = cells[:PANELB_START]    # title, setup, Panel A
panel_b = cells[PANELB_START:PANELB_END]
tickers = cells[PANELB_END:]      # everything appended after the marker

cells = head + tickers + panel_b + [absent_cell]

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
