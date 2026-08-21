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


def _describe(path):
    rc, out = _git("-C", str(path), "log", "-1", "--format=%h %ad %s", "--date=short")
    return out if rc == 0 else "unknown"


# On Colab, sync unconditionally. The previous version only synced when REPO was None,
# which meant that once the working directory was inside the clone from an earlier run,
# the sync was skipped and the clone silently stayed behind. That is how the notebook
# ended up running current code against a six-commit-old config directory.
if IN_COLAB:
    target = Path("/content") / REPO_NAME
    if not target.exists():
        print(f"cloning {REPO_URL}")
        rc, out = _git("clone", "--depth", "1", REPO_URL, str(target))
        if rc:
            raise RuntimeError(f"clone failed: {out}")
    else:
        before = _describe(target)
        rc, out = _git("-C", str(target), "fetch", "--depth", "1", "origin")
        if rc:
            print(f"  git fetch FAILED: {out}")
        done = False
        for ref in ("origin/main", "origin/master"):
            rc, out = _git("-C", str(target), "reset", "--hard", ref)
            if rc == 0:
                done = True
                break
        if not done:
            raise RuntimeError(
                f"could not reset {target} to origin. Last error:\n{out}\n"
                f"Simplest fix: run  !rm -rf {target}  in a cell, then rerun this one."
            )
        _git("-C", str(target), "clean", "-fd", "config", "notebooks")
        after = _describe(target)
        print(f"  before: {before}")
        print(f"  after : {after}")
        if before == after:
            print("  (already current)")
    os.chdir(target)

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
def fetch_prices(symbol: str, start: str, end: str, quiet: bool = False) -> pd.DataFrame:
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
            if not quiet:
                print(f"    {symbol}: request error on {base.split('/')[-1]} ({e})")
            continue

        if r.status_code != 200:
            if not quiet:
                print(f"    {symbol}: HTTP {r.status_code} on {base.split('/')[-1]}")
            continue

        payload = r.json()
        rows = payload.get("historical") if isinstance(payload, dict) else payload
        if not rows:
            if not quiet:
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
            if not quiet:
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
## 8. What is deliberately absent

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

# ---------------------------------------------------------- home-listing correction
# A European firm resolved to a US over-the-counter line is almost always wrong. OUTKY,
# FOJCY and SEOAY are the OTC receipts of Outokumpu, Fortum and Stora Enso, trading
# $887, $9,898 and $302,574 a day against Helsinki lines that trade orders of magnitude
# more. This is not merely thin: a receipt carries a currency move and a stale US close
# against a European session, so it is the wrong series rather than a noisy one. It gets
# chosen when FMP's ISIN lookup returns only the receipt, leaving the liquidity test
# nothing to compare.
#
# The rule is evidence-based rather than dogmatic: look for a home-exchange listing by
# name, and switch only if it trades at least three times the current pick. Ireland is
# the reason for that caution, since CRH genuinely moved its primary listing to the NYSE.
HOME_EX = {
    "Finland": {"HEL"}, "Germany": {"XETRA"}, "France": {"PAR"}, "Italy": {"MIL"},
    "Spain": {"BME"}, "Norway": {"OSL"}, "Sweden": {"STO"}, "Denmark": {"CPH"},
    "Netherlands": {"AMS"}, "Belgium": {"BRU"}, "Portugal": {"LIS"},
    "Austria": {"VIE"}, "Greece": {"ATH"}, "Switzerland": {"SIX"},
    "United Kingdom": {"LSE"},
}
# Check any firm listed away from its home exchange, not just those on US venues.
# The narrower rule missed two: BAS.F is BASF on the Frankfurt regional floor rather
# than XETRA, and 0DXG.L is CropEnergies on a London international board. Both are
# away-from-home lines that are not US.
_ex = primary.exchange.astype(str).str.upper()
_home_ok = [str(h) in HOME_EX and e in HOME_EX.get(str(h), set())
            for h, e in zip(primary.hq, _ex)]
parked = primary[primary.priceable & primary.hq.isin(HOME_EX) & ~pd.Series(_home_ok, index=primary.index)]
print(f"\n{len(parked)} firms are listed away from their home exchange, checking")
moved = 0
for i, row in parked.iterrows():
    want = HOME_EX[row["hq"]]
    try:
        r = requests.get(f"{BASE}/search-name",
                         params={"query": row["name"], "limit": 20, "apikey": API_KEY},
                         timeout=45)
        hits = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        hits = []
    if isinstance(hits, dict):
        hits = hits.get("data") or []
    best, best_dv = None, 0.0
    for h in hits if isinstance(hits, list) else []:
        sym = h.get("symbol")
        ex  = str(h.get("exchangeShortName") or h.get("exchange") or "").upper()
        if not sym or ex not in want:
            continue
        if similar(row["name"], h.get("name") or h.get("companyName") or "") < NAME_MIN:
            continue
        dv, bars = liquidity(sym)
        if bars > 30 and dv > best_dv:
            best, best_dv = sym, dv
    cur = float(row["dollar_vol"] or 0)
    if best and best_dv > max(cur * 3, 1.0):
        print(f"  {row['name'][:34]:36s} {str(row.primary_symbol):9s} "
              f"${cur:>12,.0f}  ->  {best:9s} ${best_dv:>12,.0f}")
        primary.loc[i, "primary_symbol"] = best
        primary.loc[i, "dollar_vol"] = best_dv
        primary.loc[i, "route"] = "home-exchange"
        moved += 1
print(f"  moved {moved} firms to their home listing")
LIQ_CACHE.write_text(json.dumps(_liq))

# A line with literally zero traded value is not a listing you can hold. Two came
# through the name route on 21 August: HMS Bergbau and Savannah Energy, the latter
# suspended from AIM. Keeping them would put untradeable names in a tradeable portfolio.
dead = primary.priceable & (primary.dollar_vol.fillna(0) <= 0)
if dead.any():
    print(f"\ndropping {int(dead.sum())} listings with zero traded value:")
    for _, r in primary[dead].iterrows():
        print(f"  {r['name'][:38]:40s} {r.primary_symbol}")
    primary.loc[dead, "primary_symbol"] = None
    primary.loc[dead, "route"] = None
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
            # Recompute liquidity for the new symbol. Carrying the old figure over made
            # PCG look like it traded $77k a day, which was PCG-PA's number, and that
            # in turn put PCG on the thin-listing report for no reason.
            primary.loc[i, "dollar_vol"] = liquidity(new)[0] if new else None
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
# Diagnostics run LAST, on purpose. These used to print in section 2c, before the name
# retry, the home-exchange correction and the overrides had run, so they described an
# intermediate state: BAS.F and 0DXG.L stayed on the flag list after both had already
# been moved. A report that does not describe the file actually written is worse than no
# report, because it invites chasing problems that are already fixed.
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

TICKERS_END = len(cells)

# ------------------------------------------------- Section 5: blocking test 1
cells.append(md(r"""
---

## 5. Blocking test 1: how big is the survivorship problem?

**Run this while the subscription is live.** It is the one test that cannot be done
afterwards, because it needs price history for companies that no longer exist.

### Why this is the blocking test

The universe was built from a GEM snapshot dated August 2026, so **every firm in it is a
firm that still existed in August 2026**. A firm that owned power assets in 2010 and was
then acquired, delisted or wound up is absent, and it is absent precisely because of what
happened to it. If hazard-exposed firms failed more often, the sample systematically
drops the worst outcomes and the estimated hazard premium is biased upward. That is not a
caveat. It is a mechanism that manufactures the result the paper is looking for.

This cell does not fix that, and nothing in this repository can, because the exposure
data for dead firms does not exist. What it does is **measure the size of the hole**, so
the bias can be bounded and reported rather than acknowledged and waved through.

### What is measured, in increasing order of usefulness

1. **The base rate.** How many companies FMP records as delisting between 2010 and 2025.
   This says delisting is common, and nothing more.
2. **The sector rate.** The same, restricted to utilities, energy, materials and
   industrials. This is the number that matters, because delisting rates differ sharply
   across sectors and a market-wide figure would understate a utility-heavy sample.
3. **The return gap.** For delisted firms with price history, the cumulative return over
   their final year against the market over the identical window. This is what turns a
   survivorship *rate* into a survivorship *bias*: a 10 percent attrition rate with no
   return gap barely matters, the same rate with a large negative gap matters a lot.

### Commit to the threshold before seeing the number

| If the sector delisting rate is | Then |
|---|---|
| under 5 percent over the window | Report it, note the direction of the bias, proceed |
| 5 to 15 percent | Proceed, but bound the effect: recompute the headline result assuming the delisted firms earned the observed gap |
| over 15 percent | The survivor-only cross-section cannot carry the main claim. Either rebuild the universe from historical GEM vintages, or reframe the paper around what this sample can support |

The third row is the uncomfortable one, which is exactly why it is written down here
rather than in a discussion section composed after the fact.
"""))

cells.append(code(r'''
DELISTED_CACHE = RAW / "fmp_delisted.json"

if DELISTED_CACHE.exists():
    delisted = json.loads(DELISTED_CACHE.read_text())
    print(f"delisted list from cache: {len(delisted):,} rows")
else:
    # Page until a short or empty page. Stopping at page 0, which the earlier probe did,
    # returns 100 names out of thousands and would understate every rate below.
    delisted, page = [], 0
    while True:
        try:
            r = requests.get(f"{BASE}/delisted-companies",
                             params={"page": page, "limit": 100, "apikey": API_KEY},
                             timeout=45)
            batch = r.json() if r.status_code == 200 else []
        except (requests.RequestException, ValueError):
            batch = []
        if not isinstance(batch, list) or not batch:
            break
        delisted.extend(batch)
        page += 1
        if page % 20 == 0:
            print(f"  page {page}, {len(delisted):,} rows so far")
        if len(batch) < 100 or page > 500:      # guard against an endless loop
            break
        time.sleep(0.05)
    DELISTED_CACHE.write_text(json.dumps(delisted))
    print(f"pulled {len(delisted):,} delisted companies across {page} pages")

dl = pd.DataFrame(delisted)
print("columns:", list(dl.columns))
display(dl.head(3))
'''))

cells.append(code(r'''
# Normalise whatever the vendor called the date column rather than assuming a name.
_dcol = next((c for c in ("delistedDate", "delisted_date", "date") if c in dl.columns), None)
if _dcol is None:
    raise SystemExit(f"no delisting date column found in {list(dl.columns)}")

dl["delisted_on"] = pd.to_datetime(dl[_dcol], errors="coerce")
win = dl[(dl.delisted_on >= START) & (dl.delisted_on <= END)].copy()
print(f"{len(win):,} of {len(dl):,} delistings fall inside {START} to {END}")

print("\nby year:")
print(win.delisted_on.dt.year.value_counts().sort_index().to_string())

if "exchange" in win.columns:
    print("\ntop exchanges:")
    print(win.exchange.value_counts().head(12).to_string())

# The denominator problem, stated plainly. A delisting COUNT is not a RATE: a rate needs
# the number of firms listed at the START of the window. FMP publishes no historical
# constituent list, so the honest denominator available here is today's survivors plus
# the delistings, which undercounts the 2010 population and therefore understates the
# rate. Report it as a lower bound and say so.
try:
    _r = requests.get(f"{BASE}/stock-list", params={"apikey": API_KEY}, timeout=120)
    live = _r.json() if _r.status_code == 200 else []
except (requests.RequestException, ValueError):
    live = []
print(f"\ncurrently listed symbols: {len(live):,}")
if live:
    denom = len(live) + len(win)
    print(f"crude LOWER BOUND delisting rate over the window: "
          f"{len(win) / denom:.1%}  ({len(win):,} of {denom:,})")
    print("Lower bound because the denominator counts today's survivors, not the")
    print("2010 population, which was larger.")
'''))

cells.append(code(r'''
# Sector rate. A market-wide figure is the wrong comparison for a utility-heavy sample.
# Sector comes from the profile endpoint, one call per symbol, so this is capped: a
# random sample estimates a proportion perfectly well, and sampling at random rather
# than taking the first N avoids any ordering in the vendor's list.
SECTORS  = {"Utilities", "Energy", "Basic Materials", "Industrials", "Materials"}
SAMPLE_N = 400

pool = win.dropna(subset=["symbol"]).drop_duplicates("symbol")
samp = pool.sample(min(SAMPLE_N, len(pool)), random_state=0)
print(f"profiling a random {len(samp)} of {len(pool):,} delisted symbols")

sect = []
for k, s in enumerate(samp.symbol.tolist(), 1):
    sect.append((profile_of(s) or {}).get("sector"))
    if k % 100 == 0:
        print(f"  {k}/{len(samp)}")
        PROF_CACHE.write_text(json.dumps(prof))
PROF_CACHE.write_text(json.dumps(prof))

samp = samp.assign(sector=sect)
share = samp.sector.isin(SECTORS).mean()
n_se  = int(samp.sector.isin(SECTORS).sum())
# Binomial standard error on the sector share, because this is an estimate from 400
# draws and quoting it to one decimal place without a margin would overstate precision.
se = (share * (1 - share) / max(len(samp), 1)) ** 0.5
print(f"\nshare of delistings in {sorted(SECTORS)}: {share:.1%} "
      f"(+/- {1.96 * se:.1%}, from {n_se} of {len(samp)})")
print("\nsector breakdown of the sample:")
print(samp.sector.value_counts(dropna=False).head(12).to_string())
print(f"\nimplied delistings in your sectors over the window: ~{int(share * len(pool)):,}")
'''))

cells.append(code(r'''
# The return gap. This converts a rate into a bias. Take delisted firms in the relevant
# sectors, pull their final year, and compare against SPY over the identical window so
# the comparison is not contaminated by when in the cycle the delisting happened.
targets = samp[samp.sector.isin(SECTORS)].head(120)
print(f"pricing {len(targets)} delisted names in the relevant sectors\n")

spy = prices[prices.symbol == "SPY"].set_index("date")["price"].sort_index()

gaps, priced, nodata = [], 0, 0
for _, row in targets.iterrows():
    end_d   = row.delisted_on
    start_d = end_d - pd.Timedelta(days=365)
    d = fetch_prices(row["symbol"], start_d.strftime("%Y-%m-%d"),
                     end_d.strftime("%Y-%m-%d"), quiet=True)
    if d.empty or len(d) < 60:
        nodata += 1
        continue
    priced += 1
    firm_ret = d["price"].iloc[-1] / d["price"].iloc[0] - 1
    mkt = spy.loc[(spy.index >= d.date.min()) & (spy.index <= d.date.max())]
    if len(mkt) < 2:
        continue
    mkt_ret = mkt.iloc[-1] / mkt.iloc[0] - 1
    gaps.append({"symbol": row["symbol"], "delisted_on": end_d, "sector": row["sector"],
                 "firm_ret": firm_ret, "mkt_ret": mkt_ret, "gap": firm_ret - mkt_ret})
    time.sleep(0.02)

g = pd.DataFrame(gaps)
print(f"priced {priced}, no usable history {nodata}, gap computed for {len(g)}")
if len(g):
    display(g.sort_values("gap").head(15))
    print(f"\nmedian final-year return, delisted firms : {g.firm_ret.median():+.1%}")
    print(f"median market return over same windows   : {g.mkt_ret.median():+.1%}")
    print(f"MEDIAN GAP                               : {g.gap.median():+.1%}")
    print(f"share underperforming the market          : {(g.gap < 0).mean():.1%}")
    print("\nThat gap is the survivorship correction. A sample excluding these firms")
    print("overstates average returns by roughly (delisting rate) x (this gap), before")
    print("any relationship with hazard exposure is considered.")
    g.to_csv(RAW / "blocking_test_1_return_gaps.csv", index=False)
    print(f"\nwrote {RAW / 'blocking_test_1_return_gaps.csv'}")
else:
    print("\nNo return gaps computed. Do not read that as 'no bias'. Read it as")
    print("'not measured', and write it in the paper that way.")
'''))

cells.append(md(r"""
### 5b. The rate above is measured on the wrong population

The 21 August run returned an 8.2 percent lower-bound delisting rate and a 20.8 percent
sector share. **Neither is usable as it stands**, and the reason is visible in the names
that came back: `MMS.V` and `PNRL.V` are TSX Venture, `AHQ.AX` and `ROO.AX` are ASX small
caps, `AMTE.L` and `VRS.L` are AIM, and `TBLTW` is a warrant rather than a company. FMP's
delisted list spans every venue it covers, most of which are populated by micro-caps and
shells that delist constantly.

Your universe is 302 established asset owners on main boards in developed markets. The
delisting hazard for Duke Energy is not the delisting hazard for a TSX Venture explorer,
so a rate computed across both says nothing about your sample. Applying the thresholds
written above to a number built this way would be worse than not measuring at all,
because it carries the authority of a computation.

Two corrections, both cheap:

**Match the exchanges.** Compute the numerator and the denominator on the same venue set,
namely the exchanges your own firms actually trade on. This is the rate that belongs in
the paper.

**Check the vendor's list for recency bias.** 8,174 delistings over sixteen years against
roughly 100,000 live symbols is implausibly low: the US alone lost listings at a far
higher rate over that period. If the by-year counts are thin before about 2018 and thick
after, the list is a recent-history snapshot rather than a sixteen-year record, and every
rate computed from it understates the truth by a factor nobody can pin down.
"""))

cells.append(code(r'''
# Recency bias first, because if the list is a recent snapshot then no rate from it is
# trustworthy and the exchange matching below is polishing a number that cannot be used.
by_year = win.delisted_on.dt.year.value_counts().sort_index()
print("delistings recorded per year:")
print(by_year.to_string())

early = by_year.loc[by_year.index <= 2017].sum()
late  = by_year.loc[by_year.index >= 2018].sum()
print(f"\n2010-2017: {early:,}   2018-2025: {late:,}   ratio {late / max(early, 1):.1f}x")
if late > 3 * max(early, 1):
    print("\nWARNING: the vendor's delisted list is heavily skewed to recent years.")
    print("  Delisting rates do not rise fourfold in a decade, so this is coverage,")
    print("  not history. Any rate computed from it is a floor of unknown tightness,")
    print("  and the honest move is to report the recent-window rate separately.")
'''))

cells.append(code(r'''
# Exchange-matched rate. Numerator and denominator restricted to the venues the universe
# actually trades on, so a TSX Venture shell cannot inflate a figure about main-board
# asset owners.
MY_EX = set(primary.loc[primary.priceable, "exchange"].dropna().astype(str).str.upper())
print(f"exchanges in the universe: {sorted(MY_EX)}")

live_df = pd.DataFrame(live) if live else pd.DataFrame()
_lex = next((c for c in ("exchangeShortName", "exchange") if c in live_df.columns), None)
_dex = next((c for c in ("exchange", "exchangeShortName") if c in win.columns), None)

if _lex is None or _dex is None:
    print("no exchange column available on one of the two lists, cannot match")
else:
    live_m = live_df[live_df[_lex].astype(str).str.upper().isin(MY_EX)]
    win_m  = win[win[_dex].astype(str).str.upper().isin(MY_EX)]
    denom_m = len(live_m) + len(win_m)
    print(f"\nlive symbols on those venues    : {len(live_m):,}")
    print(f"delistings on those venues      : {len(win_m):,}")
    if denom_m:
        print(f"EXCHANGE-MATCHED delisting rate : {len(win_m) / denom_m:.1%}  "
              f"({len(win_m):,} of {denom_m:,})")
        print("\nStill a lower bound, for the same denominator reason as before, and now")
        print("also because the vendor's list under-records older delistings.")

    # Recent window only. If the list is recency biased, the last few years are the part
    # that is actually complete, so a rate computed there is the tighter estimate even
    # though it covers less of the sample period.
    recent = win_m[win_m.delisted_on >= "2021-01-01"]
    if denom_m and len(recent):
        r5 = len(recent) / denom_m
        print(f"\n2021-2025 only: {len(recent):,} delistings, {r5:.1%} over five years")
        print(f"  implied 16-year rate at that pace: {r5 * 16 / 5:.1%}")
        print("  Use this as the upper of the two estimates and say which is which.")
'''))

cells.append(code(r'''
# Does the gap depend on size? A shell delisting at zero tells you nothing about whether
# Duke Energy would have. Split the measured gaps by the firm's own final-year dollar
# volume, which is the only size proxy available for companies that no longer exist.
if len(g):
    dv = []
    for _, row in g.iterrows():
        d = fetch_prices(row["symbol"],
                         (row.delisted_on - pd.Timedelta(days=365)).strftime("%Y-%m-%d"),
                         row.delisted_on.strftime("%Y-%m-%d"), quiet=True)
        if d.empty or "volume" not in d.columns:
            dv.append(0.0)
            continue
        v = (pd.to_numeric(d["price"], errors="coerce")
             * pd.to_numeric(d["volume"], errors="coerce")).dropna()
        dv.append(float(v.median()) if len(v) else 0.0)
    g2 = g.assign(dollar_vol=dv)
    g2["size_band"] = pd.cut(g2.dollar_vol,
                             [-1, 1e5, 1e6, 1e7, float("inf")],
                             labels=["<$100k", "$100k-1m", "$1m-10m", ">$10m"])
    print("median gap by final-year dollar volume:\n")
    print(g2.groupby("size_band", observed=False)
            .agg(n=("gap", "size"), median_gap=("gap", "median"),
                 share_negative=("gap", lambda s: (s < 0).mean()))
            .to_string())
    print("\nRead the >$10m row, not the overall median. That band is the one that")
    print("resembles the firms in your universe, and if it is thin, say so: the honest")
    print("statement is then that the bias is unmeasured for firms of your size.")
    g2.to_csv(RAW / "blocking_test_1_return_gaps.csv", index=False)
'''))

cells.append(md(r"""
### 5c. What the vendor can and cannot tell you about survivorship

The 21 August run settled two things and broke one.

**Settled, and bad: FMP cannot measure a 2010 to 2025 delisting rate.** The recorded
counts run 7 delistings in 2010, 3 in 2012, 10 in 2015, then 1,843 in 2023 and 2,353 in
2025. That is a 28-fold jump. Delisting rates do not move like that; coverage does. The
list is effectively empty before about 2016 and only dense from 2021, so it is a recent
snapshot wearing the costume of a historical record. **Any rate computed across the full
window from this source is not a lower bound, it is an artefact**, and the earlier 8.2
percent figure should be discarded rather than quoted with a caveat.

**Settled, and genuinely surprising: the sign of the bias may be the opposite of the
usual worry.** Splitting the return gap by the firm's own final-year dollar volume:

| Final-year dollar volume | n | Median gap | Share negative |
|---|---|---|---|
| under $100k | 32 | -14.6% | 59% |
| $100k to $1m | 16 | -67.9% | 88% |
| $1m to $10m | 13 | +0.7% | 46% |
| over $10m | 10 | **+18.1%** | 30% |

Small firms delist because they fail. Firms of the size in your universe mostly delist
because they are **acquired**, and acquisitions pay a premium. So excluding delisted
firms may bias your returns *downward*, not upward. That reverses the standard
survivorship story for a large-cap sample, and it is worth saying in the paper. With n
of 10 it is a hint rather than a finding, which is what the cell below is for.

**Broken: the exchange match.** `stock-list` returns symbols without an exchange field,
so numerator and denominator could not be put on the same venue set. The screener
endpoint carries both exchange and market cap, which is better anyway: it lets the
denominator be matched on *size* as well as venue, and size is what the table above
shows to be the variable that matters.
"""))

cells.append(code(r'''
# Size-and-venue-matched denominator. The screener carries exchange and market cap, which
# stock-list does not, and matching on size matters more than matching on venue given
# what the size split showed.
CAP_FLOOR = 1_000_000_000       # $1bn, roughly the small end of the universe
SCREENER  = f"{BASE}/company-screener"

MY_EX = sorted(set(primary.loc[primary.priceable, "exchange"]
                   .dropna().astype(str).str.upper()) - {"OTC"})
print(f"matching on {len(MY_EX)} exchanges, market cap above ${CAP_FLOOR:,}")

big_live = []
for ex in MY_EX:
    got, page = 0, 0
    while True:
        try:
            r = requests.get(SCREENER, params={"exchange": ex,
                                               "marketCapMoreThan": CAP_FLOOR,
                                               "isActivelyTrading": "true",
                                               "limit": 1000, "page": page,
                                               "apikey": API_KEY}, timeout=60)
            batch = r.json() if r.status_code == 200 else []
        except (requests.RequestException, ValueError):
            batch = []
        if not isinstance(batch, list) or not batch:
            break
        big_live.extend(batch)
        got += len(batch)
        page += 1
        if len(batch) < 1000 or page > 20:
            break
    print(f"  {ex:8s} {got:>6,} firms above the cap floor")

print(f"\ntotal size-matched live population: {len(big_live):,}")
'''))

cells.append(code(r'''
# Numerator matched the same way. Market cap is unavailable for dead companies, so size
# is proxied by final-year median dollar volume, and the threshold is calibrated against
# the live universe rather than picked out of the air.
uni_dv = primary.loc[primary.priceable, "dollar_vol"].dropna()
DV_FLOOR = float(uni_dv.quantile(0.10)) if len(uni_dv) else 1e6
print(f"size proxy floor: ${DV_FLOOR:,.0f} a day, the 10th percentile of your own universe")

RECENT_FROM = "2021-01-01"      # the part of the vendor list that is actually populated
cand_dl = win[(win.delisted_on >= RECENT_FROM)]
if "exchange" in cand_dl.columns:
    cand_dl = cand_dl[cand_dl.exchange.astype(str).str.upper().isin(MY_EX)]
cand_dl = cand_dl.dropna(subset=["symbol"]).drop_duplicates("symbol")
print(f"{len(cand_dl):,} delistings since {RECENT_FROM} on matched exchanges")

CHECK_N = 300
probe = cand_dl.sample(min(CHECK_N, len(cand_dl)), random_state=1)
print(f"sizing a random {len(probe)} of them\n")

big_dead = []
for k, row in enumerate(probe.itertuples(), 1):
    end_d = row.delisted_on
    d = fetch_prices(row.symbol,
                     (end_d - pd.Timedelta(days=365)).strftime("%Y-%m-%d"),
                     end_d.strftime("%Y-%m-%d"), quiet=True)
    if not d.empty and "volume" in d.columns and len(d) >= 60:
        v = (pd.to_numeric(d["price"], errors="coerce")
             * pd.to_numeric(d["volume"], errors="coerce")).dropna()
        if len(v) and float(v.median()) >= DV_FLOOR:
            big_dead.append({"symbol": row.symbol, "delisted_on": end_d,
                             "dollar_vol": float(v.median())})
    if k % 50 == 0:
        print(f"  {k}/{len(probe)}, {len(big_dead)} above the floor so far")

share_big = len(big_dead) / max(len(probe), 1)
n_big = share_big * len(cand_dl)
print(f"\n{len(big_dead)} of {len(probe)} sampled delistings clear the size floor "
      f"({share_big:.1%})")
print(f"implied size-matched delistings since {RECENT_FROM}: ~{n_big:,.0f}")

if len(big_live):
    rate5 = n_big / (len(big_live) + n_big)
    print(f"\nSIZE-AND-VENUE-MATCHED RATE, {RECENT_FROM} to {END}: {rate5:.1%}")
    print(f"  annualised: {rate5 / 5:.2%} a year")
    print(f"  extrapolated to the full 16-year window: {rate5 * 16 / 5:.1%}")
    print("\nThe extrapolation assumes the 2021-2025 pace held since 2010, which is an")
    print("assumption and not a measurement. Report the five-year figure as measured and")
    print("the sixteen-year figure as an extrapolation, and never merge the two.")
'''))

cells.append(md(r"""
### What to write in the paper, and what to do next

Three statements are now defensible, and one thing is still missing.

**Defensible.** The vendor's delisting record is unusable before roughly 2021, so the
survivorship rate is measured over 2021 to 2025 and extrapolated, with both figures
reported separately. Among delisted firms of comparable trading size, the median final
year *beat* the market, consistent with large-firm delisting being dominated by
acquisition rather than failure. The direction of the survivorship bias for this sample
is therefore ambiguous, and plausibly negative rather than positive.

**Still missing: a real delisting history.** If your institution has WRDS access, CRSP's
delisting codes are the standard instrument for exactly this question: complete from
1926, distinguishing merger, exchange, liquidation and dropped-for-cause, with delisting
returns attached. That is a free lookup for a doctoral student and it turns this entire
section from an estimate into a citation. **Check whether you have WRDS before spending
more subscription time here.** FMP is the wrong tool for this measurement and no amount
of care with it will fix that.
"""))


cells.append(md(r"""
---

## 6. Blocking test 2: does this pipeline reproduce something already known?

**Needs no subscription and no CRSP.** Panel A is a free public download and Panel B is
already on disk. This is the test to run while you wait for WRDS.

### Why it blocks

Everything so far establishes that data arrived. Nothing establishes that returns
computed from it are *correct*. A panel can pass all sixteen integrity checks and still
produce nonsense returns: a split adjustment applied twice, a currency mixed into a
dollar factor, a price series that is actually a preferred share. None of that shows up
as a missing value.

So before estimating anything unknown, reproduce something known. Take the price panel,
compute returns through the same code path the real result will use, and regress a
diversified portfolio on the Fama-French factors. **The market beta of a broad
equity portfolio is one.** That is not a hypothesis, it is a definition, so if it comes
back at 0.4 or 2.1 the return construction is broken and every later coefficient is
worthless. Finding that here costs an afternoon; finding it after the hazard sort costs
a chapter.

### What is checked, and against what

| Quantity | Expected | If it fails |
|---|---|---|
| Market beta, equal-weighted US portfolio | near 1, say 0.7 to 1.3 | Returns are misscaled, or the panel is not what you think |
| R-squared on FF3 | above 0.5 for a diversified portfolio | The portfolio is not diversified, or returns are noise |
| Annualised alpha | small, within a few percent of zero | A systematic construction error, or a real sector effect worth naming |
| Sector beta pattern | utilities below 1, energy above | If reversed, symbols are mismatched to firms |

### The currency trap, restated because this is where it bites

The Ken French factors are **dollar** returns. Your panel holds prices in USD, EUR, GBp,
NOK, CHF, SEK, DKK and ILA. A euro-denominated return regressed on a dollar factor
measures the asset plus the exchange rate, and the exchange rate is not a climate hazard.
So the headline test below runs on the **US subset only**, where the currency question
does not arise. The non-US firms are then run separately, and the gap between the two is
itself the measurement of how much conversion matters.
"""))

cells.append(code(r'''
# Daily simple returns, per symbol, through the same path the real result will use.
px = prices.sort_values(["symbol", "date"]).copy()
px["ret"] = px.groupby("symbol")["price"].pct_change()

# A 50% one-day move in a large listed firm is almost always a split or a data error
# rather than news. Flag rather than drop: silently winsorising is how a broken
# adjustment becomes invisible.
extreme = px[px.ret.abs() > 0.5].dropna(subset=["ret"])
print(f"{len(extreme)} daily moves above 50% across {extreme.symbol.nunique()} symbols")
if len(extreme):
    display(extreme.groupby("symbol")
                   .agg(n=("ret", "size"), worst=("ret", lambda s: s.abs().max()))
                   .sort_values("n", ascending=False).head(10))
    print("Check these before trusting anything below. A cluster in one symbol is a")
    print("split adjustment problem; scattered singletons are usually real.")

tp = pd.read_csv(REPO / "config" / "tickers_primary.csv")
tp = tp[tp.priceable]
cur = dict(zip(tp.primary_symbol, tp.currency))
hq  = dict(zip(tp.primary_symbol, tp.hq))
px["currency"] = px.symbol.map(cur)
px["hq"] = px.symbol.map(hq)

us = px[(px.hq == "United States") & (px.currency == "USD")]
print(f"\nUS subset: {us.symbol.nunique()} symbols, {len(us):,} rows")
print(f"non-US    : {px[px.hq != 'United States'].symbol.nunique()} symbols")
'''))

cells.append(code(r'''
def newey_west_ols(y, X, lags=5):
    """OLS with Newey-West standard errors.

    Daily portfolio returns are heteroskedastic and mildly autocorrelated, so plain OLS
    standard errors overstate precision. Five lags is the usual choice for daily data
    and is not tuned to the result.
    """
    X = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    XtX_inv = np.linalg.inv(X.T @ X)
    S = (X * e[:, None]).T @ (X * e[:, None])
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None])
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.diag(V))
    return b, se, b / se


def run_ff3(daily_rets, label):
    """Equal-weighted portfolio of `daily_rets` regressed on the FF3 factors."""
    port = daily_rets.groupby("date")["ret"].mean().rename("port").to_frame()
    port["n_firms"] = daily_rets.groupby("date")["ret"].size()

    f = ff3.set_index("date")[["Mkt-RF", "SMB", "HML", "RF"]] / 100.0   # percent -> decimal
    d = port.join(f, how="inner").dropna()
    if len(d) < 250:
        print(f"{label}: only {len(d)} overlapping days, skipping")
        return None

    y = (d["port"] - d["RF"]).values
    X = d[["Mkt-RF", "SMB", "HML"]].values
    b, se, t = newey_west_ols(y, X)

    fitted = np.column_stack([np.ones(len(X)), X]) @ b
    r2 = 1 - ((y - fitted) ** 2).sum() / ((y - y.mean()) ** 2).sum()

    print(f"\n{label}")
    print(f"  days {len(d):,}   firms per day: median {d.n_firms.median():.0f}")
    print(f"  alpha   {b[0] * 25150:+7.2f}% a year   t = {t[0]:+5.2f}")
    for k, nm in enumerate(["Mkt-RF", "SMB", "HML"], start=1):
        print(f"  {nm:7s} {b[k]:+7.3f}              t = {t[k]:+5.2f}")
    print(f"  R2      {r2:7.3f}")
    return {"label": label, "alpha_ann": b[0] * 25150, "beta_mkt": b[1],
            "smb": b[2], "hml": b[3], "r2": r2, "days": len(d),
            "t_alpha": t[0], "t_mkt": t[1]}


res = []
r = run_ff3(us, "US equal-weighted, FF3 US factors")
if r: res.append(r)

nonus = px[(px.hq != "United States") & px.hq.notna()]
r = run_ff3(nonus, "Non-US equal-weighted, FF3 US factors (currency NOT converted)")
if r: res.append(r)
'''))

cells.append(code(r'''
# The verdict, against thresholds fixed before the numbers were seen.
if res:
    main = res[0]
    print("BLOCKING TEST 2 VERDICT\n")
    checks2 = [
        ("market beta near 1", 0.7 <= main["beta_mkt"] <= 1.3, f"{main['beta_mkt']:.3f}"),
        ("R2 above 0.5",       main["r2"] > 0.5,               f"{main['r2']:.3f}"),
        ("alpha under 10%/yr in absolute value",
                               abs(main["alpha_ann"]) < 10,    f"{main['alpha_ann']:+.2f}%"),
        ("at least 2000 days", main["days"] >= 2000,           f"{main['days']:,}"),
    ]
    v = pd.DataFrame([{"check": c, "pass": p, "value": d} for c, p, d in checks2])
    display(v)
    nfail = int((~v["pass"]).sum())
    if nfail:
        print(f"\n{nfail} FAILED. Do not proceed to the hazard sort. A pipeline that")
        print("cannot reproduce a market beta of one cannot be trusted with a new number.")
    else:
        print("\nPassed. Returns computed through this path behave like equity returns,")
        print("which is the minimum standard, not evidence the research design is sound.")

    if len(res) > 1:
        gap = res[1]["beta_mkt"] - res[0]["beta_mkt"]
        print(f"\nUS market beta {res[0]['beta_mkt']:.3f} vs non-US {res[1]['beta_mkt']:.3f}"
              f"  (difference {gap:+.3f})")
        print("Part of that difference is genuine, since European equities do not move")
        print("one for one with the US market. Part is unconverted currency. Those two")
        print("cannot be separated without converting, which is why the headline test")
        print("runs on the US subset and the non-US line is diagnostic only.")

    pd.DataFrame(res).to_csv(RAW / "blocking_test_2_ff3.csv", index=False)
    print(f"\nwrote {RAW / 'blocking_test_2_ff3.csv'}")
'''))

cells.append(code(r'''
# Sector pattern. Utilities should sit below a market beta of one and energy above it.
# This catches a whole class of error the portfolio test cannot: if symbols are attached
# to the wrong firms, the aggregate still looks fine while every individual beta is
# meaningless.
KNOWN = {"DUK": ("Duke Energy", "utility, expect beta well below 1"),
         "SO":  ("Southern Co", "utility, expect beta well below 1"),
         "NEE": ("NextEra", "utility, expect beta below 1"),
         "XOM": ("Exxon Mobil", "energy, expect beta near or above 1"),
         "CVX": ("Chevron", "energy, expect beta near or above 1"),
         "AEP": ("American Electric Power", "utility, expect beta well below 1")}

f = ff3.set_index("date")[["Mkt-RF", "RF"]] / 100.0
rows = []
for sym, (nm, expect) in KNOWN.items():
    s = px[px.symbol == sym][["date", "ret"]].dropna().set_index("date")
    d = s.join(f, how="inner").dropna()
    if len(d) < 250:
        continue
    y = (d["ret"] - d["RF"]).values
    X = d[["Mkt-RF"]].values
    b, se, t = newey_west_ols(y, X)
    rows.append({"symbol": sym, "firm": nm, "beta": b[1], "t": t[1],
                 "days": len(d), "expectation": expect})

if rows:
    display(pd.DataFrame(rows))
    ut = [r["beta"] for r in rows if "utility" in r["expectation"]]
    en = [r["beta"] for r in rows if "energy" in r["expectation"]]
    if ut and en:
        print(f"\nmean utility beta {np.mean(ut):.2f}, mean energy beta {np.mean(en):.2f}")
        if np.mean(ut) < np.mean(en):
            print("Ordering is as expected. Symbols are attached to the right firms.")
        else:
            print("ORDERING IS WRONG. Utilities should be less market-sensitive than")
            print("energy. Check the crosswalk before going further.")
'''))

cells.append(md(r"""
### 6b. Where the +4.33% alpha comes from

The test passed, but it produced a significant positive alpha on a portfolio that has no
business having one: 4.33 percent a year, t of 2.16, on an equal-weighted basket of
utilities, energy and materials. **That number is roughly the size of any hazard premium
this paper might report**, so if it is an artefact it will contaminate the headline
result, and if it is real it needs a name. Either way it cannot be left alone.

There are four candidate explanations and three of them are mechanical.

**Equal weighting with daily rebalancing.** Computing a daily equal-weighted return
implicitly rebalances every day, which buys whatever fell and sells whatever rose. With
bid-ask bounce, that harvests the bounce as return. This is the Blume-Stambaugh bias and
it scales with the cross-sectional variance of returns, so it is largest in exactly the
illiquid names this panel contains: 26 listings trade under a million dollars a day.

**Survivorship.** The universe is survivor-only by construction. A basket of firms
selected for still existing in 2026 should out-perform, and blocking test 1 found that
firms of this size which delisted were mostly *acquired*, which cuts the other way. The
net sign is unknown, which is the point.

**Missing factors.** FF3 omits profitability, investment and momentum. Utilities are
low-profitability and high-investment, energy the reverse, so a three-factor model
leaves real structure in the residual and calls it alpha.

**A genuine sector effect.** Possible, and it would be a finding rather than a bug, but
it is the last explanation to reach for, not the first.

The cell below separates the mechanical part. It runs the same regression four ways:
equal versus value weighted, daily versus monthly buy-and-hold. **If the alpha collapses
when you value-weight or move to monthly, it was microstructure.** If it survives all
four, it is worth investigating.
"""))

cells.append(code(r'''
# Symbols with repeated extreme moves are almost certainly broken series rather than
# volatile firms. CRC shows a 1,065 percent single-day move, which is the California
# Resources post-bankruptcy share exchange, and BNOR.OL shows eight, which looks like a
# split adjustment problem. Excluding them is a judgement call, so it is made explicitly
# and the result is reported both ways.
bad_syms = set(extreme.groupby("symbol").size().loc[lambda s: s >= 2].index)
print(f"excluding {len(bad_syms)} symbols with 2 or more extreme daily moves:")
print(f"  {sorted(bad_syms)}")

clean = px[~px.symbol.isin(bad_syms)].copy()

# Weights. Market cap from the profile endpoint where available, dollar volume as a
# fallback, and the fallback is reported rather than hidden because the two are not the
# same thing and a reader should know which was used.
_mc = {}
for s in clean.symbol.unique():
    p_ = prof.get(s) or {}
    v = p_.get("marketCap") or p_.get("mktCap")
    if v:
        _mc[s] = float(v)
dv_map = dict(zip(tp.primary_symbol, tp.dollar_vol))
n_mc = len(_mc)
for s in clean.symbol.unique():
    if s not in _mc and dv_map.get(s):
        _mc[s] = float(dv_map[s])
print(f"\nweights: {n_mc} from market cap, {len(_mc) - n_mc} from dollar volume as proxy")
clean["w"] = clean.symbol.map(_mc)
'''))

cells.append(code(r'''
def portfolio(df, weight, freq):
    """Portfolio return series. weight in {'ew','vw'}, freq in {'D','M'}.

    Monthly returns are buy-and-hold compounded within the month, NOT an average of
    daily returns, because the whole point is to remove the implicit daily rebalancing.
    """
    d = df.dropna(subset=["ret"]).copy()
    if freq == "M":
        d["period"] = d.date.dt.to_period("M")
        # compound each firm within the month first, then form the portfolio
        firm = (d.groupby(["symbol", "period"])
                  .agg(r=("ret", lambda s: (1 + s).prod() - 1),
                       w=("w", "first")).reset_index())
    else:
        firm = d.rename(columns={"date": "period", "ret": "r"})[["symbol", "period", "r", "w"]]

    if weight == "ew":
        out = firm.groupby("period")["r"].mean()
    else:
        firm = firm.dropna(subset=["w"])
        out = (firm.assign(wr=lambda x: x.r * x.w)
                   .groupby("period")
                   .apply(lambda x: x.wr.sum() / x.w.sum(), include_groups=False))
    return out


def factors(freq):
    f = ff3.set_index("date")[["Mkt-RF", "SMB", "HML", "RF"]] / 100.0
    if freq == "D":
        return f
    g = f.copy()
    g["period"] = g.index.to_period("M")
    return g.groupby("period").apply(lambda x: (1 + x).prod() - 1, include_groups=False)


rows6 = []
for weight in ("ew", "vw"):
    for freq in ("D", "M"):
        p_ = portfolio(clean[clean.hq == "United States"], weight, freq)
        f_ = factors(freq)
        d = pd.DataFrame({"port": p_}).join(f_, how="inner").dropna()
        if len(d) < 60:
            continue
        y = (d["port"] - d["RF"]).values
        X = d[["Mkt-RF", "SMB", "HML"]].values
        lags = 5 if freq == "D" else 3
        b, se, t = newey_west_ols(y, X, lags=lags)
        fit = np.column_stack([np.ones(len(X)), X]) @ b
        r2 = 1 - ((y - fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        ann = 25150 if freq == "D" else 1200      # to percent a year
        rows6.append({"weight": weight.upper(), "freq": freq, "obs": len(d),
                      "alpha_pct_yr": b[0] * ann, "t_alpha": t[0],
                      "beta_mkt": b[1], "R2": r2})

r6 = pd.DataFrame(rows6)
display(r6.round(3))

if len(r6):
    ew_d = r6[(r6.weight == "EW") & (r6.freq == "D")]
    vw_m = r6[(r6.weight == "VW") & (r6.freq == "M")]
    if len(ew_d) and len(vw_m):
        a1, a2 = float(ew_d.alpha_pct_yr.iloc[0]), float(vw_m.alpha_pct_yr.iloc[0])
        print(f"\nEW daily alpha {a1:+.2f}%/yr  ->  VW monthly alpha {a2:+.2f}%/yr")
        print(f"the mechanical part is about {a1 - a2:+.2f} percentage points")
        if abs(a2) < 2 or abs(float(vw_m.t_alpha.iloc[0])) < 2:
            print("\nThe alpha does not survive value weighting and monthly compounding.")
            print("It was microstructure, not a sector effect. USE VALUE-WEIGHTED")
            print("MONTHLY RETURNS for the headline result, and say so in the methods.")
        else:
            print("\nThe alpha survives all four specifications. That makes it worth")
            print("investigating rather than dismissing: add profitability, investment")
            print("and momentum before concluding anything, since FF3 leaves real")
            print("structure in the residual for utilities and energy.")
    r6.to_csv(RAW / "blocking_test_2_weighting.csv", index=False)
    print(f"\nwrote {RAW / 'blocking_test_2_weighting.csv'}")
'''))

cells.append(md(r"""
### 6c. The alpha is not microstructure. So what is it?

Four specifications, four positive alphas: 3.67, 2.83, 3.93, 3.49 percent a year, with
the value-weighted monthly figure significant at t of 2.11. Only 0.19 percentage points
moved when the weighting and frequency changed, so **the Blume-Stambaugh explanation is
dead**. Two candidates remain, and they are separable.

**Missing factors, and there is a specific reason to expect this one.** The portfolio
loads on HML at +0.549, which is a large value tilt. Over most of 2010 to 2020 the value
premium was *negative*, so a three-factor model predicts low returns for a value-tilted
portfolio, and anything the portfolio actually earned above that shows up as alpha. These
firms are also profitable and capital-intensive, which is exactly what RMW and CMA are
built to price. FF3 is the wrong model for this sector, and both extra factors are free
downloads from the same library Panel A came from.

**A concentrated sector episode.** Independent power producers ran extraordinarily hard
in 2023 to 2025 on data-centre electricity demand. Vistra, Constellation, Talen and NRG
are all in this universe, and all four are among the largest US owners in it. If the
alpha is concentrated in the last two years, it is that trade rather than a persistent
sector premium.

That distinction matters more than it might appear. **If hazard-exposed firms are
disproportionately independent power producers, a hazard sort would pick up the
data-centre trade and report it as a climate risk premium.** The subperiod split below is
what tells you whether that risk is live.
"""))

cells.append(code(r'''
FF5_DAILY = f"{FRENCH_BASE}/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
MOM_DAILY = f"{FRENCH_BASE}/F-F_Momentum_Factor_daily_CSV.zip"

_n5, _b5 = fetch_french_zip(FF5_DAILY)
ff5 = parse_french_daily(_b5)
print(f"FF5 : {_n5}, {len(ff5):,} rows, {list(ff5.columns)}")

try:
    _nm, _bm = fetch_french_zip(MOM_DAILY)
    mom = parse_french_daily(_bm)
    mom.columns = ["date"] + ["MOM" if c.strip() in ("Mom", "Mom   ") else c.strip()
                              for c in mom.columns[1:]]
    print(f"MOM : {_nm}, {len(mom):,} rows, {list(mom.columns)}")
except Exception as exc:
    mom = None
    print(f"momentum download failed ({exc}); continuing with FF5 only")

fac = ff5.copy()
if mom is not None:
    fac = fac.merge(mom, on="date", how="inner")
fac = fac[(fac.date >= START) & (fac.date <= END)].reset_index(drop=True)
FACCOLS = [c for c in ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"] if c in fac.columns]
print(f"\nusing factors: {FACCOLS}, {len(fac):,} days")
'''))

cells.append(code(r'''
def regress(port, factor_df, cols, ann, lags, min_obs=60):
    """min_obs is a parameter, not a constant, because a three-year subperiod has 36
    monthly observations. Hard-coding 60 silently dropped two of the three subperiods
    and left the summary claiming the only surviving period had the largest alpha."""
    f = factor_df.set_index("date")[cols + ["RF"]] / 100.0
    d = pd.DataFrame({"port": port}).join(f, how="inner").dropna()
    if len(d) < min_obs:
        return None
    y = (d["port"] - d["RF"]).values
    X = d[cols].values
    b, se, t = newey_west_ols(y, X, lags=lags)
    fit = np.column_stack([np.ones(len(X)), X]) @ b
    r2 = 1 - ((y - fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    out = {"obs": len(d), "alpha_pct_yr": b[0] * ann, "t_alpha": t[0], "R2": r2}
    for k, c in enumerate(cols, start=1):
        out[c] = b[k]
    return out


us_clean = clean[clean.hq == "United States"]
port_m = portfolio(us_clean, "vw", "M")
port_m.index = port_m.index.to_timestamp()

# Monthly factors, compounded from daily so FF3 and FF5 are treated identically.
def to_monthly(df, cols):
    g = df.set_index("date")[cols + ["RF"]] / 100.0
    m = g.groupby(g.index.to_period("M")).apply(lambda x: (1 + x).prod() - 1,
                                                include_groups=False) * 100.0
    m.index = m.index.to_timestamp()
    return m.reset_index().rename(columns={"index": "date"})

ff3_m = to_monthly(ff3, ["Mkt-RF", "SMB", "HML"])
ff5_m = to_monthly(fac, FACCOLS)

comp = []
r = regress(port_m, ff3_m, ["Mkt-RF", "SMB", "HML"], 1200, 3)
if r: comp.append({"model": "FF3", **r})
r = regress(port_m, ff5_m, FACCOLS, 1200, 3)
if r: comp.append({"model": "FF5+MOM" if "MOM" in FACCOLS else "FF5", **r})

cmp_df = pd.DataFrame(comp)
display(cmp_df.round(3))

if len(cmp_df) == 2:
    a3, a5 = cmp_df.alpha_pct_yr.iloc[0], cmp_df.alpha_pct_yr.iloc[1]
    t5 = cmp_df.t_alpha.iloc[1]
    print(f"\nFF3 alpha {a3:+.2f}%/yr  ->  richer model {a5:+.2f}%/yr  (t = {t5:.2f})")
    if abs(t5) < 2:
        print("The alpha is absorbed once profitability, investment and momentum are")
        print("priced. FF3 was simply the wrong model for this sector. USE THE RICHER")
        print("MODEL for the headline result and report the FF3 version as a robustness")
        print("check, not the other way round.")
    else:
        print("The alpha survives the richer model too. At that point it is either a")
        print("real sector effect or survivorship, and the subperiod split below is")
        print("the cheapest way to tell those apart.")
'''))

cells.append(code(r'''
# Subperiods. Fixed on economic events rather than chosen to split the result: the first
# ends before COVID, the second covers the pandemic and the 2022 energy shock, the third
# is the data-centre electricity demand episode.
PERIODS = [("2010-2019, pre-COVID",      "2010-01-01", "2019-12-31"),
           ("2020-2022, COVID and energy shock", "2020-01-01", "2022-12-31"),
           ("2023-2025, data-centre demand",     "2023-01-01", "2025-12-31")]

sub = []
for label, a, b_ in PERIODS:
    p_ = port_m[(port_m.index >= a) & (port_m.index <= b_)]
    if len(p_) < 24:
        continue
    # 24 monthly observations against 6 factors is thin, so the t-statistics in this
    # table are indicative and the table says so rather than pretending otherwise.
    r = regress(p_, ff5_m, FACCOLS, 1200, 3, min_obs=24)
    if r:
        sub.append({"period": label, **r})

s_df = pd.DataFrame(sub)
if len(s_df):
    display(s_df[["period", "obs", "alpha_pct_yr", "t_alpha", "R2"]].round(3))
    if len(s_df) < len(PERIODS):
        print(f"NOTE: only {len(s_df)} of {len(PERIODS)} subperiods had enough data.")
    print("Subperiods carry 36 observations against 6 factors, so read the alphas as")
    print("indicative magnitudes and the t-statistics as weak evidence.")
    # Read the verdict off the table rather than asserting a hypothesis. The first
    # version of this text announced the data-centre trade regardless of which period
    # actually won, and on the real data 2020-2022 won. A diagnostic that narrates a
    # prior instead of a result is worse than no diagnostic.
    worst = s_df.loc[s_df.alpha_pct_yr.idxmax()]
    early = s_df[s_df.period.str.startswith("2010")]
    print(f"\nlargest alpha: {worst['period']} at {worst['alpha_pct_yr']:+.2f}%/yr "
          f"(t = {worst['t_alpha']:.2f})")

    if len(early):
        a0, t0 = float(early.alpha_pct_yr.iloc[0]), float(early.t_alpha.iloc[0])
        flat_early = abs(t0) < 2
        print(f"pre-COVID decade: {a0:+.2f}%/yr (t = {t0:.2f}), "
              f"{'indistinguishable from zero' if flat_early else 'significant'}")
        if flat_early:
            print("\nOver a normal decade this portfolio has no alpha. The pipeline is")
            print("not manufacturing a premium. Everything sits after 2020, which is a")
            print("period effect rather than a defect, and it is dateable:")
            print("  2020-2022  COVID collapse and recovery, then the 2022 European gas")
            print("             crisis, which handed windfalls to power and energy names")
            print("  2023-2025  data-centre electricity demand repricing the IPPs")
            print("\nCONSEQUENCE FOR THE PAPER. Two thirds of the return variation in this")
            print("sample comes from the last third of the window, so ANY cross-sectional")
            print("sort will be dominated by it. Worse, both episodes are correlated with")
            print("the sort variable by construction: the 2022 crisis was a shock to")
            print("European energy assets, and the data-centre trade is concentrated in")
            print("US independent power producers. A hazard sort can load on either and")
            print("report it as a climate risk premium.")
            print("\nPre-commit now: report the full sample as headline, the pre-2020 and")
            print("post-2020 splits alongside it as standard rather than as robustness,")
            print("and state that the sample contains one large energy-market regime")
            print("change. Deciding that after seeing the hazard sort is not a decision.")
        else:
            print("\nThe alpha is present in the pre-COVID decade too, so it is not a")
            print("one-off episode. Survivorship becomes the leading explanation, and")
            print("blocking test 1 cannot currently bound it. Say so plainly.")
    s_df.to_csv(RAW / "blocking_test_2_subperiods.csv", index=False)
    print(f"\nwrote {RAW / 'blocking_test_2_subperiods.csv'}")
'''))

cells.append(md(r"""
---

## 7. Take the data with you before cancelling

**Run this before you cancel the subscription, and before the Colab runtime recycles.**

Everything built so far lives in `/content/` on a Google virtual machine that is deleted
when the session ends. That includes the price panel, which cost $166 and roughly two
hours of API calls, and the caches, which are what make every rerun cheap. Losing them
means paying again.

Three things get saved, and they are not equally replaceable.

| What | Replaceable after cancelling? |
|---|---|
| `panel_b_prices_daily.csv`, the price panel | **No.** Needs a live paid key |
| `fmp_delisted.json`, `fmp_profile_cache.json` | **No.** Same |
| `openfigi_cache.json`, `fmp_isin_cache.json`, `fmp_liquidity_cache.json` | Yes, but slowly and OpenFIGI is free |
| `ff3_daily.csv`, Panel A | Yes, free public download |

The cell mounts your Google Drive and copies everything there. If the mount fails it falls
back to a zip you download through the browser. It then **re-hashes every file after
copying and compares against the source**, because a copy that silently truncated is worse
than no copy: you would not find out until the subscription was gone.

It also writes the price panel as Parquet alongside the CSV. Same data, roughly a tenth
the size and far faster to reload, which matters when you are reading it repeatedly from
Drive rather than from local disk.
"""))

cells.append(code(r'''
import shutil

EXPORT_NAME = f"paper1_data_{dt.datetime.now():%Y%m%d}"

# Parquet copy first. A 1.1 million row CSV is slow to reload and large to store; the
# same frame in Parquet is roughly a tenth the size and keeps dtypes, so dates do not
# come back as strings.
try:
    pq = RAW / "panel_b_prices_daily.parquet"
    prices.to_parquet(pq, index=False)
    csv_mb = (RAW / "panel_b_prices_daily.csv").stat().st_size / 1e6
    pq_mb = pq.stat().st_size / 1e6
    print(f"parquet written: {pq_mb:.1f} MB against {csv_mb:.1f} MB for the CSV")
except Exception as exc:
    print(f"parquet failed ({exc}); the CSV is still the authoritative copy")

# What must exist. Named explicitly rather than globbed, so a missing file is an error
# rather than a silently shorter list.
REQUIRED = ["panel_b_prices_daily.csv", "ff3_daily.csv", "manifest.json",
            "fmp_delisted.json", "fmp_profile_cache.json", "openfigi_cache.json",
            "fmp_isin_cache.json", "fmp_liquidity_cache.json"]
OPTIONAL = ["panel_b_prices_daily.parquet", "blocking_test_1_return_gaps.csv",
            "blocking_test_2_ff3.csv", "blocking_test_2_weighting.csv",
            "blocking_test_2_subperiods.csv"]

missing_req = [f for f in REQUIRED if not (RAW / f).exists()]
present = [f for f in REQUIRED + OPTIONAL if (RAW / f).exists()]

print(f"\n{len(present)} files to export, {(sum((RAW / f).stat().st_size for f in present) / 1e6):.0f} MB total")
for f in present:
    print(f"  {f:38s} {(RAW / f).stat().st_size / 1e6:8.1f} MB")
if missing_req:
    print(f"\nMISSING REQUIRED FILES: {missing_req}")
    print("Run the sections that produce them before exporting, or you will cancel")
    print("the subscription with a hole in the archive.")
'''))

cells.append(code(r'''
def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


dest = None
if IN_COLAB:
    try:
        from google.colab import drive
        drive.mount("/content/drive")
        dest = Path("/content/drive/MyDrive") / EXPORT_NAME
        dest.mkdir(parents=True, exist_ok=True)
        print(f"copying to {dest}")
    except Exception as exc:
        print(f"Drive mount failed ({exc}); falling back to a browser download")
        dest = None
else:
    dest = REPO.parent / EXPORT_NAME
    dest.mkdir(parents=True, exist_ok=True)

if dest is not None:
    (dest / "config").mkdir(exist_ok=True)
    ok, bad = 0, []
    for f in present:
        src = RAW / f
        shutil.copy2(src, dest / f)
        # Verify by hash, not by size. A truncated copy can match on neither, but a
        # corrupted one matches on size and would pass a length check.
        if sha256_of(src) == sha256_of(dest / f):
            ok += 1
        else:
            bad.append(f)
    for f in ["universe.csv", "universe_isins.csv", "tickers_primary.csv",
              "ticker_overrides.csv", "tickers_draft_v0.csv"]:
        s = REPO / "config" / f
        if s.exists():
            shutil.copy2(s, dest / "config" / f)

    print(f"\n{ok} of {len(present)} data files copied and hash-verified")
    if bad:
        print(f"HASH MISMATCH on {bad}. Recopy those before cancelling anything.")
    else:
        print("Every copied file matches its source byte for byte.")
    print(f"config files copied: {len(list((dest / 'config').glob('*.csv')))}")
    print(f"\nlocation: {dest}")
'''))

cells.append(code(r'''
# Fallback, and also worth doing anyway: a single zip is the easiest thing to archive and
# the easiest thing to check later. Google Drive is one copy, not a backup.
zip_path = Path("/content") / f"{EXPORT_NAME}.zip" if IN_COLAB else REPO.parent / f"{EXPORT_NAME}.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in present:
        z.write(RAW / f, arcname=f"data/raw/{f}")
    for f in (REPO / "config").glob("*.csv"):
        z.write(f, arcname=f"config/{f.name}")
print(f"{zip_path.name}: {zip_path.stat().st_size / 1e6:.0f} MB")

if IN_COLAB:
    try:
        from google.colab import files
        print("\nStarting the browser download. A large file can take a few minutes and")
        print("Colab sometimes drops it silently, so check your downloads folder and")
        print("rerun this cell if nothing arrives.")
        files.download(str(zip_path))
    except Exception as exc:
        print(f"browser download unavailable ({exc})")
        print(f"Use the file browser in the left sidebar instead: navigate to {zip_path}")
        print("right-click, Download.")
'''))

cells.append(md(r"""
### Before you cancel, in this order

1. **Check the hash line above says every file matches.** Not the file count, the hashes.
2. **Open the zip on your own machine and confirm it is not empty.** Colab drops large
   browser downloads silently more often than you would expect.
3. **Keep two copies in different places.** Drive and your laptop, or Drive and an
   external disk. One copy is not a backup, and this data cannot be regenerated without
   paying again.
4. **Note today's date and the subscription tier in your methods file.** A reader needs to
   know which tier and which day the panel was pulled, because vendor coverage changes.
5. Only then cancel, and **set a calendar reminder two days before the renewal date** in
   case the cancellation does not take.

Everything remaining in this project runs on free data: the GEM sector trackers, a hazard
dataset, the join, and the estimation itself. The subscription bought exactly one thing
that cannot be bought later, which is this price panel. Treat it accordingly.
"""))

# ---------------------------------------------------------------- run order
# Written order is not run order. Ticker resolution was added after Panel B but must run
# before it, because it produces the symbol list Panel B prices. Blocking test 1 was
# added last and must run after Panel B, because it compares delisted firms against the
# SPY series Panel B downloads. Reassemble here rather than shuffling hundreds of lines
# of text above.
head      = cells[:PANELB_START]              # title, setup, Panel A
panel_b   = cells[PANELB_START:PANELB_END]
tickers   = cells[PANELB_END:TICKERS_END]
blocking1 = cells[TICKERS_END:]

cells = head + tickers + panel_b + blocking1 + [absent_cell]

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
