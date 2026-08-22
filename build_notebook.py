"""
Generates notebooks/01_raw_panels.ipynb.

Why a generator and not a hand-edited notebook
----------------------------------------------
A .ipynb file is JSON. Every cell is a list of strings, and outputs and execution
counts are stored in the same file as the code. That makes hand-edited notebooks
almost impossible to review in a pull request: a one-word change to a comment can
show up as a thousand-line diff because the stored outputs moved.

Keeping the notebook in a plain Python script solves that. This file is the source
of truth, it diffs cleanly, and the notebook is a build artefact. If you want to
change the notebook, change this file and run:

    python3 build_notebook.py

Editing the .ipynb directly appears to work and is then silently overwritten the
next time anyone runs this script.

Carlo Hofer, 2026.
"""
import json
import pathlib


def _lines(src: str) -> list[str]:
    """Split a block of text into the list-of-strings format a .ipynb expects.

    The notebook format stores each cell's source as a list of strings which are
    later joined with the empty string, NOT with a newline. So every line has to
    keep its own trailing "\n". A plain src.split("\n") drops those separators and
    the whole cell collapses onto one line: markdown renders as a single run-on
    paragraph, and code cells raise SyntaxError the moment they are run.

    This is an easy mistake to make and a confusing one to diagnose, so the fix
    lives in one place and is documented here rather than repeated at each call
    site. Please do not "simplify" it back to a bare split.
    """
    parts = src.split("\n")
    return [p + "\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def md(src):
    """Build a markdown cell."""
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(src.strip())}


def code(src):
    """Build a code cell with no stored outputs, so the committed notebook stays clean."""
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": _lines(src.strip("\n"))}


cells = []

# ============================================================ title and orientation
cells.append(md(r"""
# Physical climate hazard and stock returns: building the data

**Carlo Hofer.** Companion notebook to a study asking whether a company's exposure to
physical climate hazards, measured from the locations of the physical assets it owns,
helps explain its stock returns once the usual risk factors are accounted for.

This notebook builds and audits the data. It does not test the hypothesis. That
separation is deliberate and I explain why below.

---

## What you are looking at

If you have arrived here from my CV, this is the part of the project that is usually
invisible: the work of turning three public data sources into something you can
actually run a regression on, and then trying hard to break it before trusting it.

I have written it for someone who has not seen the project before. Where I use a term
from empirical asset pricing I define it. Where the Python does something non-obvious
I say what and why. If you are a quantitative researcher this will occasionally be
slower than you need, and I would rather that than the alternative.

## The research question in one paragraph

Companies own physical things: power stations, pipelines, mines, cement works. Those
things sit in places, and places have weather. If investors price the risk that a
flood, a heatwave or a cyclone damages those assets or interrupts their output, then
companies with more exposed assets should earn different returns from companies with
less exposed ones, after controlling for everything else that is known to move stock
prices. That "after controlling for" is the hard part, and it is what the factor data
in this notebook is for.

## The three ingredients

| Ingredient | What it is | Source |
|---|---|---|
| **Asset ownership** | Which company owns which power station, mine or pipeline | Global Energy Monitor |
| **Stock returns** | What each company's shares actually did, day by day | Financial Modeling Prep |
| **Risk factors** | The known drivers of returns, used as controls | Kenneth French's data library |

This notebook builds the second and third, and the company list that connects them to
the first. The hazard measurement itself is a separate piece of work and is not here.

## What this notebook deliberately does not do

I download data, check it, and stop. I compute no returns for the study, run no
regressions on the hypothesis, form no portfolios and merge no datasets.

My reason is that a data layer I can only check by looking at the final result is one I
cannot really check at all. If the answer looks interesting you
will not go back and question the download, and if it looks boring you will. Auditing
the raw layer on its own, before anything depends on the answer, is how I avoid that
trap. The two blocking tests in sections 5 and 6 take the same idea further. In each I try to
prove my own pipeline is broken, before I use it.

## How to run it

Open it in Google Colab using the badge in the repository README, then Runtime, Run
all. Section 0 clones the repository into the Colab machine for you.

Sections 1, 2 and 6 need no paid access. Sections 3, 4, 5 and 7 need an API key from
Financial Modeling Prep, stored in Colab's Secrets panel under the name `FMP_API_KEY`.
Section 2 works better with a free key from OpenFIGI, stored as `OPENFIGI_API_KEY`.
The notebook tells you when a key is missing rather than failing obscurely.

Full step-by-step instructions, including what each step should print and what to do
when it does not, are in `EXECUTION_CHECKLIST.html` in the repository root.
"""))

cells.append(md(r"""
---

## 0. Setup

This section does four housekeeping jobs: it makes sure the notebook can find the
repository's files, reads the API keys, defines the addresses of the data service we
call later, and fixes the sample period.

None of it is interesting in itself. It is here in one place so that the sections that
follow contain only the work.

### The one design decision worth explaining

The notebook needs to know where the project's files are. On your own machine that is
wherever you cloned the repository. On Colab it is a temporary folder on a virtual
machine that is deleted when you close the tab.

An obvious way to handle this is to guess: use the current folder if it looks right,
otherwise its parent. I wrote it that way at first and it caused a genuinely nasty
failure. On Colab the current folder is `/content`, its parent is the filesystem root
`/`, and Colab runs with administrator rights. So the notebook cheerfully created
`/data/raw` at the root of the machine, downloaded the factor data into it, printed a
success message, and only fell over four sections later with an error mentioning a
path that appears nowhere in this project.

**A wrong path that works is more dangerous than one that crashes.** So the code below
looks for a specific file that exists only inside this repository and refuses to
continue if it cannot find it.
"""))

cells.append(code(r'''
# Standard library first, then the third-party packages. Colab already has all of these
# installed, so there is nothing to pip install.
import os          # environment variables, changing directory
import io          # treating bytes in memory as if they were a file
import re          # regular expressions, for pulling patterns out of text
import sys         # to detect whether we are running inside Colab
import zipfile     # the factor data arrives as a .zip
import json        # reading and writing the cache files
import time        # pausing between API calls so we stay inside rate limits
import hashlib     # SHA-256 checksums, used to prove a file has not changed
import subprocess  # running git commands
import datetime as dt
from pathlib import Path

import numpy as np      # numerical arrays and linear algebra
import pandas as pd     # tables, the workhorse of this notebook
import requests         # making HTTP requests to the data providers

# ----------------------------------------------------------------- where the code lives
REPO_URL  = "https://github.com/ochofer/paper1-hazard-exposure-data.git"
REPO_NAME = "paper1-hazard-exposure-data"

# A file that exists only inside this repository. Finding it proves we are in the right
# place. Using a specific file rather than a folder name matters: "data" or "config" are
# common enough that a wrong match is plausible.
MARKER = Path("config") / "tickers_draft_v0.csv"

# Colab makes its own module importable, so this is a reliable way to detect it.
IN_COLAB = "google.colab" in sys.modules


def _find_repo(start: Path):
    """Walk upwards from `start` looking for the repository root.

    Returns the folder containing MARKER, or None if we reach the top without
    finding it. Path.parents gives the chain of parent folders, so this checks
    the starting folder first and then each ancestor in turn.
    """
    for candidate in [start, *start.parents]:
        if (candidate / MARKER).exists():
            return candidate
    return None


def _git(*args, cwd=None):
    """Run a git command and return (exit code, combined output).

    capture_output keeps git's messages out of the notebook unless we choose to
    print them, and text=True gives us strings rather than raw bytes.
    """
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def _describe(path):
    """One-line summary of the commit a repository is currently on."""
    rc, out = _git("-C", str(path), "log", "-1", "--format=%h %ad %s", "--date=short")
    return out if rc == 0 else "unknown"


# ----------------------------------------------------------------- getting the files
# On Colab we always synchronise, whether or not the repository is already there.
#
# An earlier version only synchronised when it could not already find the repository.
# That sounds sensible and is wrong: once an earlier run had moved into the cloned
# folder, the repository was findable, the synchronise step was skipped, and the clone
# quietly stayed on an old commit while the notebook itself was current. The symptom
# was a notebook running new code against old configuration files, which is a difficult
# thing to spot and an easy thing to waste an afternoon on.
#
# The clone is a disposable read-only copy, so a hard reset is safe and is more reliable
# than a pull, which fails whenever the local copy has diverged for any reason.
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

        # Repositories use either "main" or "master" as the default branch name, so try
        # both rather than assuming.
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

        # Print the commit before and after so that "nothing happened" is visible rather
        # than assumed. This line is how you tell a successful no-op from a failed sync.
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

# Everything downloaded goes here. This folder is excluded from version control: the
# files are large, and one of the providers does not permit redistribution.
RAW = REPO / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------- API keys
# Colab has a Secrets panel (the key icon in the left sidebar) which keeps credentials
# out of the notebook file. This matters: anything printed or pasted into a cell is
# saved into the .ipynb and would be published to GitHub along with everything else.
if IN_COLAB and not os.environ.get("FMP_API_KEY"):
    try:
        from google.colab import userdata
        os.environ["FMP_API_KEY"] = userdata.get("FMP_API_KEY")
    except Exception as exc:
        print(f"could not read the Colab secret FMP_API_KEY: {exc}")
        print("Sections 3 onwards need it. Key icon in the left sidebar, name it exactly")
        print("FMP_API_KEY, switch on notebook access for this notebook, then rerun.")

# ----------------------------------------------------------------- data service addresses
# Financial Modeling Prep serves everything from paths beginning /stable/.
#
# This is worth a note because it cost me an afternoon. Many tutorials, and some of the
# provider's own older examples, use paths beginning /api/v3/. Those are retired for
# keys issued now, and a request to one returns HTTP 403. That status normally means
# "your account is not allowed to do this", so a perfectly good key on a paid plan
# produces exactly the same error table as no key at all, and you go looking at your
# subscription instead of your URL. Every endpoint in the current documentation is
# under /stable/.
API_KEY     = os.environ.get("FMP_API_KEY")
BASE        = "https://financialmodelingprep.com/stable"
EOD         = f"{BASE}/historical-price-eod/full"               # split-adjusted only
EOD_TR      = f"{BASE}/historical-price-eod/dividend-adjusted"  # total return
SEARCH_ISIN = f"{BASE}/search-isin"
PROFILE     = f"{BASE}/profile"

# ----------------------------------------------------------------- sample period
# Fixed here, once, and deliberately not changed later.
#
# It is easy to shorten a sample because the early years are awkward, and doing so after
# seeing results is a way of choosing the answer. Setting the window before any data
# arrives removes the temptation. If the window ever has to change, that is a decision
# to write down and justify, not a constant to quietly edit.
START = "2010-01-01"
END   = "2025-12-31"

print(f"commit : {_describe(REPO)}")
print(f"config : {sorted(p.name for p in (REPO / 'config').glob('*.csv'))}")
print(f"colab  : {IN_COLAB}")
print(f"repo   : {REPO}")
print(f"raw out: {RAW}")
print(f"api key: {'set' if os.environ.get('FMP_API_KEY') else 'MISSING'}")
print(f"window : {START} .. {END}")
'''))

cells.append(md(r"""
### Check the setup before continuing

The cell below prints where the notebook thinks it is and then asserts it. An `assert`
is a statement that stops the program if a condition is false; using one here means a
misconfigured run fails immediately and loudly rather than producing confusing errors
several sections later.

The two things to look at:

- **`repo`** should end in `paper1-hazard-exposure-data`. If it shows `/` or `/content`
  then the clone did not work.
- **`commit`** should match the latest commit in the repository. If it is older, the
  copy on the Colab machine is stale and the configuration files will not match the
  code.
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


# ============================================================ Panel A: the factors
cells.append(md(r"""
---

## 1. Panel A: the risk factors

### Why a study about climate needs a file about value and size

Suppose we find that companies with flood-exposed assets earned lower returns than
companies without. Before claiming that investors price flood risk, we have to rule out
duller explanations. Perhaps the exposed companies were simply larger, and large
companies happened to do badly over the period. Perhaps they were cheap relative to
their book value, and cheap stocks did badly.

The standard way to handle this in empirical finance is a **factor model**. We
subtract off the part of a stock's return that is explained by a handful of known,
well-documented drivers, and ask whether anything is left. What is left is called
**alpha**, and it is what we would attribute to our variable of interest.

The three factors used here come from Fama and French (1993):

| Factor | Plain English | What it controls for |
|---|---|---|
| `Mkt-RF` | The whole stock market's return, minus the return on cash | General market movements. A stock that just goes up when the market goes up has told us nothing |
| `SMB` | "Small Minus Big". The return on small companies minus the return on large ones | Company size |
| `HML` | "High Minus Low". The return on cheap stocks minus expensive ones, where cheap means a high book value relative to market value | The long-documented tendency of value stocks to behave differently from growth stocks |

`RF` is the risk-free rate, the return on short-term US Treasury bills, which is what
"minus the return on cash" means above.

Later, in section 6, I also use the two extra factors from Fama and French (2015),
covering profitability and investment, and the momentum factor from Carhart (1997).

### Where the data comes from

Kenneth French publishes these series free, updated regularly, at Dartmouth. They are
the reference implementation: when a paper says "we control for the Fama-French
factors", this is almost always the file it means. I use the published series rather than constructing my own. That removes a category of
possible error and makes my results comparable to the literature.

### Why parsing this file needs care

The file is not a clean CSV. It arrives as a `.zip` containing a text file that has a
multi-line copyright notice at the top, then a header row, then the data, then another
copyright line at the bottom. Handing that to `pandas.read_csv` directly does not work.

There is a worse trap. The **monthly** version of the same file appends a second block
of *annual* data underneath the monthly data, separated by blank lines. A parser that
just skips the preamble will happily glue annual returns onto the bottom of monthly
returns, and every number computed afterwards will be wrong in a way that is very hard
to see.

The parser below avoids all of this by keeping only lines whose first field is exactly
eight digits, the `YYYYMMDD` date format. The preamble, the trailer and the annual block
all fail that test, so they are dropped without needing to know they exist.

### Two things about the numbers

**They are in percent, not decimals.** `Mkt-RF = 0.55` means 0.55%, not 55%. I store
them exactly as published and leave the division by 100 to my analysis code. Getting
this wrong by a factor of 100 is one of the most common errors in factor work, so it is
recorded in the data manifest as well as here.

**`-99.99` and `-999` mean "missing".** They are not real observations. Left in place
they would be catastrophic, since a -99.99% daily return is not something a regression
recovers from gracefully.

> Fama, E. F. and French, K. R. (1993). "Common risk factors in the returns on stocks
> and bonds." *Journal of Financial Economics* 33(1), 3-56.
>
> Fama, E. F. and French, K. R. (2015). "A five-factor asset pricing model."
> *Journal of Financial Economics* 116(1), 1-22.
>
> Carhart, M. M. (1997). "On persistence in mutual fund performance."
> *Journal of Finance* 52(1), 57-82.
>
> Data: Kenneth R. French Data Library,
> https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
"""))

cells.append(code(r'''
FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
FF3_DAILY   = f"{FRENCH_BASE}/F-F_Research_Data_Factors_daily_CSV.zip"


def fetch_french_zip(url: str) -> tuple[str, bytes]:
    """Download one of French's zip files and return (filename inside it, raw bytes).

    Returning the raw bytes as well as the parsed data matters for reproducibility.
    French updates these files in place as new months are added and old data is
    revised, so downloading the same URL next year gives different content. Keeping
    the exact bytes received on the day, and a checksum of them, is what lets someone
    verify later that they are looking at the same input I used.

    io.BytesIO wraps the downloaded bytes so that zipfile can treat them as a file
    without ever writing anything to disk.
    """
    r = requests.get(url, timeout=60, headers={"User-Agent": "paper1-data/0.1"})
    r.raise_for_status()          # turn an HTTP error into a Python exception
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        inner = z.namelist()[0]   # these archives contain exactly one file
        return inner, z.read(inner)


# A regular expression matching lines that begin with exactly eight digits followed by a
# comma, optionally with surrounding spaces. In other words, a YYYYMMDD date field.
#   ^     start of the line
#   \s*   any amount of whitespace
#   (\d{8}) exactly eight digits, captured
#   \s*,  optional whitespace then a comma
DATE8 = re.compile(r"^\s*(\d{8})\s*,")


def parse_french_daily(csv_bytes: bytes) -> pd.DataFrame:
    """Turn the raw bytes of a French daily factor file into a tidy table.

    The approach is to identify the first line that looks like a data row, take the
    line immediately above it as the header, and then keep only data rows. Everything
    else in the file is ignored by construction rather than by counting lines, which
    would break the moment French adds a sentence to the copyright notice.
    """
    text  = csv_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()

    # next() with a generator returns the first match, or None if there is none.
    first_data = next((i for i, ln in enumerate(lines) if DATE8.match(ln)), None)
    if first_data is None:
        # Raise rather than return an empty table. An empty table would flow silently
        # into everything downstream; an exception stops here and says why. The most
        # likely cause is pointing this at a monthly file, whose dates are six digits.
        raise ValueError(
            "No YYYYMMDD rows found. Is this a daily file? Monthly files use YYYYMM "
            "and need a different parser plus handling for their annual block."
        )

    header = [c.strip() for c in lines[first_data - 1].split(",")]
    header[0] = "date"            # French leaves the first column unnamed

    rows = [ln for ln in lines[first_data:] if DATE8.match(ln)]
    df = pd.read_csv(io.StringIO("\n".join(rows)), header=None, names=header)

    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")

    # Convert to floating point BEFORE replacing the missing-value codes.
    #
    # The order matters more than it looks. If you replace first, using pandas' own NA
    # marker, the columns quietly become "object" dtype, meaning pandas stops treating
    # them as numbers. Everything still runs, .describe() returns something plausible,
    # and the magnitude check further down silently stops testing anything. Converting
    # to float64 first and using numpy's NaN keeps the columns numeric throughout.
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")

    n_missing_codes = int(df.iloc[:, 1:].isin([-99.99, -999]).sum().sum())
    df[df.columns[1:]] = df[df.columns[1:]].replace([-99.99, -999], np.nan)
    print(f"  missing-value codes converted to NaN: {n_missing_codes}")

    # Assert the dtypes really are numeric, so the trap described above cannot reappear
    # unnoticed if someone edits this function later.
    assert all(str(t) == "float64" for t in df.dtypes[1:]), f"dtype drift: {df.dtypes.to_dict()}"
    return df.sort_values("date").reset_index(drop=True)


inner_name, ff_bytes = fetch_french_zip(FF3_DAILY)
ff3_full = parse_french_daily(ff_bytes)

print(f"inner file : {inner_name}")
print(f"full range : {ff3_full.date.min():%Y-%m-%d} .. {ff3_full.date.max():%Y-%m-%d}  ({len(ff3_full):,} rows)")
print(f"columns    : {ff3_full.columns.tolist()}")
ff3_full.tail(3)
'''))

cells.append(md(r"""
### Trimming to the sample window, and keeping the original

I cut the series down to 2010 to 2025 and save two files.

`panel_a_ff3_daily.csv` is the trimmed table that the rest of the analysis reads.
`ff3_daily_original.csv` is the untouched bytes exactly as the server sent them. The
second so a reader can verify my parsing rather than take it on trust, and so I can
compare a future rerun against the same input.

**How to read the summary table.** Look at the `mean` row and multiply by roughly 252,
the number of trading days in a year, to get an annual figure. Over this particular
window the market earned a substantial excess return while `SMB` and `HML` earned close
to nothing. That is worth noting rather than glossing over: an alpha measured against
factors that themselves earned nothing over the sample faces weaker competition than it
would in a period when those factors performed well. I report the sample-period factor
premia alongside any alpha for exactly this reason.

The `min` and `max` rows are a useful sanity check. The extreme values should land in
March 2020, and they do.
"""))

cells.append(code(r'''
# Boolean indexing: the expression inside the square brackets produces a column of
# True/False, and pandas keeps the rows where it is True. reset_index(drop=True)
# renumbers the surviving rows from zero and throws the old numbering away.
ff3 = ff3_full[(ff3_full.date >= START) & (ff3_full.date <= END)].reset_index(drop=True)

(RAW / "ff3_daily_original.csv").write_bytes(ff_bytes)   # the audit copy
ff3.to_csv(RAW / "panel_a_ff3_daily.csv", index=False)   # the working copy

print(f"window range: {ff3.date.min():%Y-%m-%d} .. {ff3.date.max():%Y-%m-%d}  ({len(ff3):,} rows)")
print("\nsummary (values are PERCENT, not decimals):")
display(ff3.describe().T[["count", "mean", "std", "min", "max"]])
'''))

# ---------------------------------------------------------------------------------
# Cells are written in this file in the order that made sense while building it, and
# reordered at the bottom into the order they should be RUN. The universe construction
# came last chronologically but has to run before the price download, because it
# produces the list of companies the price download uses. These markers record the
# boundaries so the reordering does not require moving hundreds of lines of text.
# ---------------------------------------------------------------------------------
PANELB_START = len(cells)


# ============================================================ Panel B: the prices
cells.append(md(r"""
---

## 3. Panel B: the price history

With a list of companies in hand, this section downloads their daily share prices and
assembles them into one table.

### One decision that matters more than it looks: total return, not price return

There are two ways to record what a share did yesterday.

A **price return** is simply the change in the quoted price. If a share closed at 100
and closes at 101 today, that is +1%.

A **total return** also counts the dividends the company paid. If that same share had
also gone ex-dividend for 2, the investor is 3 better off, not 1, and the total return
is +3%.

The Fama-French factors in Panel A are built from **total returns**. So if I compute
price returns for my companies and compare them against total-return factors, every
company's return is understated by roughly its dividend yield, and that shortfall lands
in the alpha. My universe is heavy in utilities and pipelines, which yield somewhere
around 3 to 4% a year. That is larger than most of the effects published in this
literature. The mistake would not look like a mistake; it would look like a finding.

So I request the dividend-adjusted series, and I refuse to accept a panel that mixes the
two conventions. Section 4 contains an explicit check for it.

### The two benchmarks, and why there are two

`^GSPC` is the S&P 500 **index**. It is a number, not something you can buy, and it
excludes dividends.

`SPY` is an exchange-traded fund tracking the same index. It is investable, it includes
dividends, and it is the one to use whenever the comparison needs to be against
something a portfolio could actually have held.

I download both. Which one is appropriate depends on the question, and keeping only one
of them would invite using the wrong one.

### What is deliberately not done here

No currency conversion. The panel ends up holding US dollars, euros, pounds, Norwegian
and Swedish and Danish kroner, Swiss francs, Australian dollars and Israeli agorot. I
store the prices exactly as the provider returned them.

A conversion applied invisibly inside a download step is one nobody ever checks. I do it
downstream instead, as an explicit and separately testable step, so my choice of exchange
rate series and conversion date is visible in a diff.

One currency deserves a specific warning. **UK prices are usually quoted in pence, not
pounds**, and the provider labels them `GBp` with a lower-case p. Treating them as
pounds makes those companies look a hundred times larger than they are. It does not
affect simple returns, since the factor of 100 cancels, but it wrecks anything weighted
by price or market value.
"""))

cells.append(code(r'''
# Three possible sources for the company list, in order of preference.
PRIMARY = REPO / "config" / "tickers_primary.csv"   # one listing per firm, from section 2
V1      = REPO / "config" / "tickers_v1.csv"        # every listing per firm, intermediate
DRAFT   = REPO / "config" / "tickers_draft_v0.csv"  # 20 hand-written names, for testing

# The order here is a safety feature rather than a convenience.
#
# tickers_v1.csv holds every stock market listing OpenFIGI could find for each company,
# which is often three or four per firm: a company listed in Frankfurt may also have a
# US depositary receipt and a second line on a US over-the-counter board. Feeding that
# list straight into the download would put the same company into the panel several
# times over, and a portfolio built from it would hold one bet with three weights.
#
# So if the intermediate file exists but the resolved one does not, this stops rather
# than falling back. A silent fallback would rebuild exactly the panel we are avoiding,
# and nothing downstream would reveal it.
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

# The draft file and the resolved file have different columns. Select whichever are
# actually present rather than assuming a fixed set, which is how this cell crashed the
# first time it was handed the resolved file.
SHOW = [c for c in ["name", "hq", "n_assets", "ticker", "exchange", "leg"]
        if c in tick.columns]
display(tick[SHOW].head(40))
'''))

cells.append(md(r"""
### Downloading the prices

The function below fetches one company's history. Three details in it are worth
explaining, because each one exists because of a specific way this can go wrong.

**It asks for the total-return series first and records what it got.** If the
dividend-adjusted series is unavailable for a symbol, it falls back to the
split-adjusted one, but writes the choice into a `series` column so the fallback is
visible in the data rather than hidden. A quiet fallback would produce a panel that
looks uniform and is not.

**An empty response with a success code counts as a failure.** The provider answers
`HTTP 200 OK` with an empty list for symbols it holds nothing for. Counted naively that
is indistinguishable from a successful call, so a loop over 300 symbols could report
300 successes and produce an empty table.

**The two price variants do not share a column name.** The split-adjusted endpoint
returns a column called `close`; the dividend-adjusted one returns `adjClose` and no
`close` at all. Rather than making every later piece of code guess, the function
creates a single `price` column and records in `price_field` which vendor column it
came from.
"""))

cells.append(code(r'''
def fetch_prices(symbol: str, start: str, end: str, quiet: bool = False) -> pd.DataFrame:
    """Download one symbol's daily history. Returns an empty DataFrame on failure.

    The `quiet` flag suppresses the per-symbol messages. It is used when this function
    is called hundreds of times inside a diagnostic, where the messages would bury the
    result rather than illuminate it.
    """
    # Try the total-return series first, then fall back. The order encodes the
    # preference; the recorded label encodes what actually happened.
    attempts = [(EOD_TR, "dividend-adjusted"), (EOD, "split-adjusted")]

    for base, series in attempts:
        params = {"apikey": API_KEY, "symbol": symbol, "from": start, "to": end}
        try:
            r = requests.get(base, params=params, timeout=45)
        except requests.RequestException as e:
            if not quiet:
                print(f"    {symbol}: request error on {base.split('/')[-1]} ({e})")
            continue

        if r.status_code != 200:
            if not quiet:
                print(f"    {symbol}: HTTP {r.status_code} on {base.split('/')[-1]}")
            continue

        payload = r.json()
        # Some endpoints wrap the rows in a dictionary, others return a bare list.
        rows = payload.get("historical") if isinstance(payload, dict) else payload
        if not rows:
            if not quiet:
                print(f"    {symbol}: HTTP 200 but empty payload -> counted as MISS")
            continue

        df = pd.DataFrame(rows)
        df["symbol"] = symbol
        df["series"] = series
        df["date"]   = pd.to_datetime(df["date"])

        # Normalise the closing price into one column whatever the vendor called it,
        # and record the origin. Without this, section 4 fails with a confusing
        # KeyError the first time it meets a purely dividend-adjusted panel.
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
    time.sleep(0.3)   # stay comfortably inside the provider's rate limit

print(f"\nretrieved {len(frames)}, missing {len(missing)}: {missing}")
'''))

cells.append(md(r"""
### Assembling the panel

The individual downloads are stacked into a single long table with one row per company
per day. This shape, sometimes called tidy or long format, is what almost every
statistical tool expects.

The printed output is worth reading rather than skipping. `price taken from` and
`series` should each show a single value. If either shows two, the panel mixes
conventions and the integrity checks in section 4 will fail, which is the intended
behaviour.

The table at the bottom is sorted by row count, so the shortest histories appear first.
Several companies genuinely have short histories because they are recent spin-offs or
listings. That makes this an **unbalanced panel**, meaning the set of companies changes
over time, and it is a fact to state in the methods rather than a problem to hide.
"""))

cells.append(code(r'''
if not frames:
    raise SystemExit("No price data retrieved at all. Check the API key and its plan tier.")

# pd.concat stacks the list of per-symbol tables into one.
prices = pd.concat(frames, ignore_index=True)

# Put the columns we care about first, then keep whatever else the vendor sent. Building
# the list by filtering means a missing column is skipped rather than raising.
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


# ============================================================ integrity checks
cells.append(md(r"""
---

## 4. Checking the data before trusting it

Both panels are now on disk. Here I try to find something wrong with them.

### Why bother, when nothing has obviously failed

Because the failures that matter in this work are usually silent. A download
that half-succeeds, a date column parsed with the day and month the wrong way round, a
duplicated row from a paginated response, a units error of a factor of 100. None of
these raise an exception. They produce a table that looks completely normal and a
result that is wrong.

My checks are deliberately dull. Each asserts something that must be true if the
download worked, and each has a specific failure in mind:

| Check | The failure it is looking for |
|---|---|
| No duplicate dates, no duplicate company-date pairs | A paginated response returned overlapping pages. Any later regression would count those observations twice |
| Factor values below 25 in absolute terms | A units error. Either something has already divided by 100, or the columns are misaligned |
| No weekend dates | The dates were parsed wrongly, or the file is not daily after all |
| Prices strictly positive | Nulls or placeholder values have leaked into the price series |
| Every requested company returned data | Silent partial failure |
| One price convention across the panel | Some companies on total return and others on price return, which is not comparable |
| Factors and prices share more than 2,000 trading days | A calendar mismatch. A later merge would silently discard most rows |

**These test the plumbing, not the research design.** Passing them means my data is
what it claims to be. It says nothing about whether the data can answer the question.
That is what sections 5 and 6 are for.

### One check that had to be narrowed, and why that is not a fudge

The rule "every series must be a total return" fails for `^GSPC` and always will. A
price index has no dividends to reinvest, so a total-return version of it does not
exist at any price from any provider.

Leaving the check as it was would mean one row went red on every single run forever.
That is worse than not having the check, because a warning you always ignore trains you
to ignore warnings. So the convention checks now cover the company panel, and the
benchmarks get their own check requiring that at least one total-return benchmark is
present, which `SPY` satisfies.

The distinction I am drawing is between narrowing a test to what it can meaningfully
assert, and weakening it until it passes. The first is fine. The second is not, and the
difference is whether you can state the reason before you see the result.
"""))

cells.append(code(r'''
# Collect the results in a list of dictionaries and turn it into a table at the end.
# This is easier to read than a series of assert statements, because it reports every
# failure at once rather than stopping at the first.
checks = []


def check(name, ok, detail=""):
    """Record one check. `ok` is anything truthy; `detail` explains a failure."""
    checks.append({"check": name, "pass": bool(ok), "detail": detail})


# ---------------------------------------------------------------- Panel A
check("ff3: has all four factor columns",
      set(["Mkt-RF", "SMB", "HML", "RF"]).issubset(ff3.columns),
      str(ff3.columns.tolist()))
check("ff3: no duplicate dates", ff3.date.duplicated().sum() == 0,
      f"{ff3.date.duplicated().sum()} dupes")
check("ff3: dates strictly increasing", ff3.date.is_monotonic_increasing)
check("ff3: no weekend dates", (ff3.date.dt.dayofweek < 5).all(),
      f"{(ff3.date.dt.dayofweek >= 5).sum()} weekend rows")

# A daily factor move beyond 25 percentage points has never happened. If we see one,
# the file is in decimals rather than percent, or the columns are misaligned.
mx = ff3[["Mkt-RF", "SMB", "HML"]].abs().max().max()
check("ff3: factor magnitudes plausible for PERCENT units", mx < 25, f"max |value| = {mx}")
check("ff3: RF non-negative", (ff3.RF.dropna() >= 0).all())

# ---------------------------------------------------------------- Panel B
check("prices: no duplicate (symbol, date)",
      prices.duplicated(["symbol", "date"]).sum() == 0,
      f"{prices.duplicated(['symbol','date']).sum()} dupes")
check("prices: a canonical price column exists", "price" in prices.columns,
      f"columns: {list(prices.columns)[:12]}")
check("prices: all prices strictly positive",
      (prices["price"].dropna() > 0).all() if "price" in prices else False)

# The backslash continues the expression onto the next line. This picks out the
# price_field column for companies only, excluding the benchmarks.
_eqf = prices.loc[~prices.symbol.isin(BENCHMARKS), "price_field"] \
       if "price_field" in prices.columns else pd.Series(dtype=object)
check("prices: one price field across the EQUITY panel", _eqf.nunique() == 1,
      f"fields: {sorted(_eqf.unique())}")
check("prices: S&P 500 index present", "^GSPC" in set(prices.symbol))
check("prices: every requested symbol returned data",
      len(missing) == 0, f"missing: {missing}")

# The return-convention checks. A panel mixing total and price returns is not comparable
# across companies, and the size of the difference is a dividend yield, which is exactly
# the kind of company characteristic a hazard sort might accidentally pick up. Scoped to
# companies for the reason given in the text above.
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

# The two panels will eventually be joined on date. If their trading calendars barely
# overlap, that join would silently produce almost nothing, so check the overlap now
# rather than discovering it later.
common = set(ff3.date) & set(prices.loc[prices.symbol == "^GSPC", "date"])
check("overlap: FF3 and ^GSPC share >2000 trading days", len(common) > 2000,
      f"{len(common)} shared days")

report = pd.DataFrame(checks)
display(report)

n_fail = int((~report["pass"]).sum())
print(f"\n{len(report) - n_fail}/{len(report)} checks passed"
      + (f" {n_fail} FAILED, read the detail column before using these files." if n_fail else ""))
'''))

cells.append(md(r"""
### The manifest

The last step writes `manifest.json`, a small file recording what was downloaded, when,
how many rows, and a **SHA-256 checksum** of every file.

A checksum is a short fingerprint computed from a file's contents. Change one byte
anywhere in a 90 megabyte file and the fingerprint changes completely. That makes it
possible to prove two copies are identical rather than assume it, which matters here
for three reasons:

- The price data comes from a paid subscription that will be cancelled. Once it is
  gone, this archive cannot be rebuilt, so being able to detect corruption in a backup
  is not a theoretical nicety.
- The factor file is updated in place by its publisher. A checksum of what was received
  on the day is the only way to demonstrate later which version was used.
- If someone wants to replicate this work, comparing manifests is a faster and more
  conclusive test than comparing results.

The manifest also records the things that are easy to forget and expensive to get
wrong: that the factors are in percent, and that no currency conversion has been
applied.
"""))

cells.append(code(r'''
def sha256(p: Path) -> str:
    """SHA-256 checksum of a file, read in 1 MB blocks so large files fit in memory.

    `1 << 20` is 2 to the power 20, which is 1,048,576, that is one megabyte. The
    iter(callable, sentinel) form keeps calling f.read until it returns the sentinel,
    here an empty bytes object, which marks the end of the file.
    """
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


# ============================================================ Section 2 continues


# ============================================================ Section 2: the universe
cells.append(md(r"""
---

## 2. Building the list of companies

I expected this section to be trivial. It turned out to contain most of the traps in
the project. It is also the part that decides the sample, so it deserves
the space.

### The problem

The ownership data identifies companies by name, by their Legal Entity Identifier, by a
Refinitiv PermID, and for US filers by their SEC number. It does not contain a single
stock market ticker. The price data is organised entirely by ticker. So there is no way
to connect the two without building the bridge.

That bridge is called a **crosswalk**. Building one is a standard, unglamorous and
error-prone part of empirical finance. It is also where a sample quietly becomes the
wrong sample.

### Three questions that sound like one

I first thought of this as "find the ticker for each company". It is three separate
questions, and I made mistakes by conflating them.

1. **Is this entity a listed company at all?** Many owners of power stations are not:
   municipal utilities, state bodies, co-operatives, infrastructure funds, and
   wholly owned subsidiaries whose parent is the listed entity.
2. **If it is listed, where does its stock trade?** Large companies often have several
   listings. A German company may trade in Frankfurt, and also have a US depositary
   receipt, and also a second line on a US over-the-counter board.
3. **Which of those listings should represent the company in the study?** Exactly one,
   and choosing wrongly is not a rounding error.

### Why question 3 matters more than it sounds

Suppose Allianz appears in the panel three times: `ALV` in Frankfurt, `ALIZY` as a US
depositary receipt, and `ALIZF` on the US foreign board. A portfolio built from that
panel holds one bet with three weights. The three lines are almost perfectly
correlated, so they look to any statistical test like three independent observations
when they are one. Standard errors come out too small, in the direction that makes a
result look more significant than it is.

There is a second problem. A **depositary receipt** is a certificate representing
shares held abroad. Its price moves with the underlying shares *and* with the exchange
rate, and it trades during US hours against a European closing price. Using one in
place of the home listing injects a currency factor and a timing mismatch into a study
about weather.

### The route taken

```
Legal Entity Identifier  ->  ISIN  ->  instrument record  ->  ticker  ->  one chosen listing
        (GLEIF)                          (OpenFIGI)                        (by liquidity)
```

**GLEIF** is the Global Legal Entity Identifier Foundation, the body that runs the LEI
system. It publishes a free mapping from LEI to ISIN.

**An ISIN** is an International Securities Identification Number, a twelve-character
code identifying a specific security. Crucially it identifies a *security*, not a
company, and companies issue many securities.

**OpenFIGI** is a free service from Bloomberg that maps identifiers to instrument
records, including what kind of security each one is.

### Why the ISIN alone is not enough

Because bonds have ISINs too. A heavily indebted utility can have hundreds of ISINs and
no listed shares at all. In this dataset the LEI-to-ISIN mapping produced 98,104
company-security pairs for 328 companies. The largest single holder was a bank with
21,793 of them, nearly all structured notes.

So an ISIN existing tells you almost nothing. What OpenFIGI adds is the security *type*,
which is what separates common stock from debt.

> GLEIF, https://www.gleif.org/en/lei-data/gleif-golden-copy
>
> OpenFIGI, https://www.openfigi.com/api
"""))

cells.append(code(r'''
# An OpenFIGI key is free and optional. Without one you get 25 requests a minute at 10
# identifiers each; with one you get 25 requests every 6 seconds at 100 each. On this
# dataset that is the difference between about a minute and most of a day.
OPENFIGI_KEY = os.environ.get("OPENFIGI_API_KEY")
if IN_COLAB and not OPENFIGI_KEY:
    try:
        from google.colab import userdata
        OPENFIGI_KEY = userdata.get("OPENFIGI_API_KEY")
        os.environ["OPENFIGI_API_KEY"] = OPENFIGI_KEY or ""
    except Exception:
        pass   # no secret configured is a supported state, not an error

BATCH = 100 if OPENFIGI_KEY else 10               # identifiers per request
PAUSE = 6.0 / 25 if OPENFIGI_KEY else 60.0 / 25   # seconds to wait between requests

universe = pd.read_csv(REPO / "config" / "universe.csv")       # one row per company
pairs    = pd.read_csv(REPO / "config" / "universe_isins.csv") # one row per company-ISIN

# Order each company's ISINs so that home-country ones come first.
#
# The first two characters of an ISIN are the country of issue. A company's primary
# stock listing is almost always in its home country, so trying domestic identifiers
# first resolves most companies immediately and avoids sending a bank's 21,793 mostly
# foreign structured-note identifiers before its actual shares.
HQ_ISO = {
    "United States": "US", "United Kingdom": "GB", "Germany": "DE", "France": "FR",
    "Italy": "IT", "Spain": "ES", "Norway": "NO", "Switzerland": "CH", "Finland": "FI",
    "Austria": "AT", "Belgium": "BE", "Portugal": "PT", "Sweden": "SE", "Greece": "GR",
    "Netherlands": "NL", "Ireland": "IE", "Denmark": "DK",
}
lei_hq = dict(zip(universe.lei, universe.hq.map(HQ_ISO)))

# A pandas gotcha worth knowing. Write pairs["isin"], never pairs.isin, because
# DataFrames already have a method called .isin() and the attribute form returns that
# method rather than the column. The resulting error message points nowhere useful.
pairs["home"] = [i[:2] == lei_hq.get(l) for l, i in zip(pairs["lei"], pairs["isin"])]
pairs = pairs.sort_values(["lei", "home", "isin"], ascending=[True, False, True])

# Build a plain dictionary of company -> list of identifiers once, up front.
#
# The alternative is filtering the 98,000-row table inside the loop below, which would
# rescan the whole table several hundred times per pass. Doing the work once and looking
# it up afterwards is the difference between seconds and minutes.
BY_LEI = {lei: g["isin"].tolist() for lei, g in pairs.groupby("lei", sort=False)}

print(f"{len(universe)} firms, {len(pairs):,} ISINs")
print(f"OpenFIGI key: {'present' if OPENFIGI_KEY else 'ABSENT, will run slowly'}")
print(f"batch size {BATCH}, {PAUSE:.2f}s between requests")
'''))

cells.append(md(r"""
### Looking the identifiers up, in waves

Sending all 98,104 identifiers would be wasteful, because most companies resolve on
their first few. So I run the lookup in **waves**: the first tries at most 20 identifiers
per company, the second raises the limit to 100 for whatever is still unresolved, the
third to 500. Only unresolved companies carry forward.

Two implementation points are worth pulling out.

**I cache results to disk.** Every identifier looked up is written to a JSON file, so
rerunning the notebook costs nothing for work already done. Negative results are cached
too. "This identifier is not in OpenFIGI" is a real answer, and re-asking it on every
run wastes the rate limit for no information.

**The cap is a budget, not a conclusion.** A company still unresolved after 500 tries
has not been shown to be unlisted; it has been shown to have more than 500 identifiers.
Exxon Mobil is a good example. Its identifiers sort alphabetically within the United
States, so the code for its ordinary shares sits behind every US0, US1 and US2 code the
company has ever issued for anything else. Dropping Exxon from a study of energy asset
owners because of an alphabetical tiebreak would be a sampling error created purely by
an implementation detail, and nothing downstream would ever reveal it. So after the
capped waves there is one uncapped pass over just those companies, which is cheap
because so few reach it.

That distinction, between a limit imposed for cost and a genuine finding about the
data, is one I have tried to make explicit everywhere in this notebook.
"""))

cells.append(code(r'''
FIGI_URL = "https://api.openfigi.com/v3/mapping"
CACHE    = RAW / "openfigi_cache.json"

# Load whatever we resolved on a previous run, if anything.
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
print(f"cache: {len(cache):,} ISINs already resolved")


def figi_lookup(isins):
    """Look identifiers up at OpenFIGI, filling the cache. Returns {isin: [records]}.

    Unknown identifiers are cached as an empty list. That is deliberate: "OpenFIGI has
    never heard of this" is information, and asking again every run costs rate limit
    and returns the same answer.
    """
    todo = [i for i in isins if i not in cache]

    # range(start, stop, step) with step=BATCH walks the list in chunks.
    for k in range(0, len(todo), BATCH):
        chunk = todo[k:k + BATCH]
        body  = [{"idType": "ID_ISIN", "idValue": i} for i in chunk]
        head  = {"Content-Type": "application/json"}
        if OPENFIGI_KEY:
            head["X-OPENFIGI-APIKEY"] = OPENFIGI_KEY

        # Retry loop with exponential backoff. HTTP 429 means "too many requests"; the
        # wait doubles each attempt (2**attempt) so we back off rather than hammering.
        for attempt in range(5):
            r = requests.post(FIGI_URL, json=body, headers=head, timeout=60)
            if r.status_code == 429:
                time.sleep(PAUSE * (2 ** attempt) + 1)
                continue
            r.raise_for_status()
            # zip pairs each identifier we sent with the response in the same position.
            for isin_code, res in zip(chunk, r.json()):
                cache[isin_code] = res.get("data", []) if isinstance(res, dict) else []
            break
        else:
            # A for/else runs the else block only if the loop finished without break,
            # meaning all five attempts were rate limited.
            raise RuntimeError("OpenFIGI kept returning 429. Wait a minute and rerun.")
        time.sleep(PAUSE)

    return {i: cache.get(i, []) for i in isins}


def equity_rows(records):
    """Keep only records that are actually listed shares.

    This is the step that does the real work. marketSector separates equity from debt,
    and securityType2 separates ordinary shares and depositary receipts from preferred
    stock, warrants and everything else. Requiring a ticker and an exchange code as
    well drops records that exist but are not tradeable anywhere.
    """
    return [d for d in records
            if d.get("marketSector") == "Equity"
            and d.get("securityType2") in ("Common Stock", "Depositary Receipt")
            and d.get("ticker") and d.get("exchCode")]


resolved   = {}                                        # company -> list of share records
unresolved = list(universe.lei.dropna().unique())

CAPS = [20, 100, 500]     # identifiers per company to try in each successive wave


def run_wave(leis, cap, label):
    """Look up at most `cap` identifiers for each company, then see who resolved."""
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
        CACHE.write_text(json.dumps(cache))   # save after every wave, not just at the end

    still = []
    for lei in leis:
        # Keep the identifier alongside the record, because the next section needs to
        # know which ISIN produced which listing.
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

# The uncapped pass, over companies that ran out of budget rather than out of
# identifiers. See the explanation above: this is what stops an alphabetical tiebreak
# from silently removing large companies from the sample.
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
#### The candidate table

The cell below turns the resolved records into a table with one row per company per
candidate listing, saves it, and reports coverage by country.

`tickers_v1.csv` is an intermediate file, not the answer. It deliberately keeps every
candidate listing rather than choosing between them, so that the choice made in the next
step is visible and reversible rather than baked in. Section 2b reduces it to one
listing per company.

The two numbers printed at the bottom are the sample size, and they belong in the
methods section of any paper that uses this data: how many of the ownership entities are
listed companies at all, and what share of the tracked assets those companies hold.
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

# how="left" keeps every company even if it has no listing, which is what we want:
# a company with no shares is a finding, not a row to drop.
out = universe.merge(cand, on="lei", how="left")
out["listed"] = out.ticker.notna()
out.to_csv(REPO / "config" / "tickers_v1.csv", index=False)

firm = out.groupby("entity_id").agg(hq=("hq", "first"), n_assets=("n_assets", "first"),
                                    listed=("listed", "max"))
tab = firm.groupby("hq").agg(firms=("listed", "size"), listed=("listed", "sum"),
                             assets=("n_assets", "sum")).sort_values("firms", ascending=False)
tab["listed_assets"] = firm[firm.listed].groupby("hq").n_assets.sum().reindex(tab.index).fillna(0).astype(int)
display(tab)

# Headline coverage. These two numbers are the sample size, and they belong in the
# methods section of the paper rather than only in a notebook output.
u = firm[firm.listed]
print(f"\nlisted companies : {len(u):3d} of {len(firm)}")
print(f"assets covered   : {int(u.n_assets.sum()):5,} of {int(firm.n_assets.sum()):,}"
      f"  ({u.n_assets.sum() / firm.n_assets.sum():.1%})")
print(f"\nwrote {REPO / 'config' / 'tickers_v1.csv'}")
'''))

cells.append(md(r"""
### 2b. Choosing one listing per company

The previous step produced every stock market listing OpenFIGI knows about for each
company, which is several per company. This step reduces that to exactly one.

#### The rule: let trading volume decide

For each candidate listing I ask the price provider for one recent quarter of data and
compute the **median daily value traded**, meaning price multiplied by shares, taken as
a median across the days. The listing with the highest figure wins.

This works because the difference between a company's primary listing and its secondary
ones is usually enormous, often two or three orders of magnitude, so the comparison is
not close. It also avoids maintaining a hand-written table of which exchange counts as
primary for each country, which would be tedious and would go out of date.

Three details:

- **Value traded, not share count.** A euro-denominated ordinary share and a dollar
  receipt have different prices for the same claim, so their share counts are not
  comparable. Multiplying by price puts them on the same scale.
- **Median, not mean.** Index rebalancing days produce enormous one-day volumes. A mean
  would let one such day decide which listing represents a company.
- **Market value would not work here.** The provider reports market capitalisation per
  listing computed in that listing's own currency without conversion, so the same
  company can appear larger on a thinly traded foreign line than on its home exchange.
  Value traded does not have that problem.

#### Reading the raw response before parsing it

The first cell prints three unparsed API responses. This is worth doing whenever a new
data source enters a project. Field names change without notice, and a parser written
against yesterday's names does not crash when they change: it returns nothing, which is
indistinguishable from "this security is not covered". Ten seconds of looking prevents
a long search in the wrong place.
"""))

cells.append(code(r'''
# Look before parsing.
#
# This prints three raw API responses so that the actual field names are visible before
# any code depends on them. Providers rename fields without notice, and a parser written
# against yesterday's field names does not crash when they change, it returns nothing and
# looks exactly like "this identifier is not covered". Ten seconds here saves an hour of
# debugging the wrong thing.
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
    """Ask the price provider which of its own symbols corresponds to an ISIN.

    Going through the provider's own lookup, rather than trying to guess its ticker
    format from the OpenFIGI exchange code, avoids an entire class of error. Providers
    use different suffix conventions for the same exchange and there is no reliable
    mapping between them.

    The parsing is deliberately defensive. This endpoint has returned a bare list at
    some times and a list wrapped in a dictionary at others, and an unhandled KeyError
    here would look identical to "this security is not covered", which would quietly
    shrink the sample.
    """
    if isin_code in isin_map:
        return isin_map[isin_code]
    # Catch only network and JSON-decoding failures.
    #
    # A bare `except Exception` here is tempting and wrong. It also catches programming
    # errors such as a misspelled variable, and reports them as "this identifier is not
    # covered", which is indistinguishable from a genuine coverage gap. Narrow exception
    # handling means bugs surface as bugs.
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
    """How heavily a listing trades: median daily value traded over one recent quarter.

    Two choices in here matter.

    Dollar volume, meaning price times shares, rather than share count alone. Share
    counts cannot be compared between a euro-denominated ordinary share and a dollar
    receipt, because the two have different prices for the same economic claim.

    Median rather than mean. Index rebalancing days produce enormous one-day volumes,
    and a mean would let a single such day decide which listing represents a company.
    """
    # This function always returns exactly two values, even though the cache stores
    # three. Returning the cached row whole would mean the function returns two values
    # on a cache miss and three on a cache hit, so callers would work perfectly until
    # the cache warmed up and then break. Share volume is reached through
    # share_volume() below instead.
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

cells.append(md(r"""
#### Reducing to one listing, and a second route for companies the first one missed

The cell below picks the winner for each company and then handles two complications.

**Share classes need a second criterion.** Some companies have two classes of ordinary
share with different prices. Berkshire Hathaway is the extreme case: its A share costs
about 1,500 times its B share, so a few hundred A shares changing hands rivals millions
of B shares by value. Both represent the same company and their returns are nearly
identical, but the A share's tiny share count means stale, coarse daily prices. So the
rule becomes two-stage: use value traded to find which listings are seriously traded,
then among the close contenders prefer the one with more shares changing hands.

**Some companies have no usable identifier at all.** In this dataset thirteen had the
literal text `not found` where their identifier should be, and one of them was Chevron,
among the largest asset owners in the whole study. For those, the code falls back to the
US Securities and Exchange Commission's Central Index Key, which US filers all have.

That second route is also where a subtle pandas behaviour matters. Pandas treats missing
values as equal to one another when joining tables, so joining on an identifier column
containing thirteen identical `not found` strings merges all thirteen companies into
each other. The code assigns through dictionary lookups instead, which skip missing keys
rather than matching them.
"""))

cells.append(code(r'''
# Reduce the candidate listings to exactly one per company.
# Note the bracket form again: cand.isin would be the DataFrame method, not the column.
lei_of = dict(zip(cand["isin"], cand["lei"]))
sc["lei"] = sc["isin"].map(lei_of)

alive = sc[(sc.dollar_vol > 0) & (sc.bars_q1_24 > 30)].copy()

# Choosing between share classes needs a second criterion, and Berkshire Hathaway shows
# why. Its A share costs roughly 1,500 times its B share, so a few hundred A shares
# changing hands rivals millions of B shares in value traded. Both are claims on the
# same company and their returns are nearly identical, but the A share trades in such
# small share counts that its daily closing prices are stale and coarse, which adds
# noise to a daily return series for no benefit.
#
# So the rule is two-stage: use value traded to identify which listings are seriously
# traded at all, then among those within a factor of three of the best, prefer the one
# with more shares changing hands.
alive["dv_rank"] = alive.groupby("lei")["dollar_vol"].transform("max")
contenders = alive[alive.dollar_vol >= alive.dv_rank / 3]
pick = (contenders.sort_values(["share_vol", "dollar_vol"], ascending=False)
                  .drop_duplicates("lei")
                  .rename(columns={"symbol": "primary_symbol"}))

# Assign through dictionary lookups rather than pandas' merge.
#
# This is not a style preference. pandas treats missing values as equal to each other
# when joining, so every company lacking an identifier would be matched to every other
# company lacking one. In this dataset thirteen companies had the literal text
# "not found" where an identifier should be, Chevron among them, and joining on that
# string merged all thirteen into each other. A dictionary lookup skips missing keys
# instead of matching them.
LEICOLS = ["primary_symbol", "currency", "exchange", "dollar_vol"]
by_lei  = pick.set_index("lei")[LEICOLS].to_dict("index")

primary = universe.copy()
for c in LEICOLS:
    primary[c] = primary["lei"].map(lambda l: (by_lei.get(l) or {}).get(c)
                                    if pd.notna(l) else None)
primary["route"] = primary.primary_symbol.notna().map({True: "isin", False: None})

# ---- second route: companies with no usable identifier, found through their SEC number
#
# US companies that file with the Securities and Exchange Commission have a Central Index
# Key. Where the LEI route failed, this uses the CIK instead. It recovered thirteen
# companies here, including Chevron, which is one of the largest asset owners in the
# whole study and would otherwise have been silently absent.
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

# A safety check. If one ticker ends up representing two different companies, the
# crosswalk has merged them, and the assets of both would be attributed to a single
# firm. That inflates the exposure measure for that firm and removes another entirely.
# Print it rather than fix it automatically: the right correction depends on which two
# companies were merged and why.
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
### 2c. Currency, exchange, and looking at what was lost

Two gaps remain after the previous step.

**The identifier lookup does not return a currency.** It returns a symbol, a name and a
market value, and nothing else. Currency is not decoration here: this panel ends up
holding nine of them, and a euro-denominated return regressed on a dollar-denominated
factor measures the asset plus the exchange rate. The company profile endpoint carries
currency and exchange, so this step fills them in. It has to happen while the
subscription is live, because afterwards it cannot be recovered.

**Nothing yet says which companies were lost.** An aggregate count cannot distinguish
thirty trivial holders from one large one. The second cell lists the excluded companies
ordered by how many assets they own, so an expensive omission is visible immediately,
and prints the chosen listing for the largest companies so that a European company
sitting on a US over-the-counter line can be spotted at a glance.

That second table is the single most useful check in this whole section. A wrong listing
does not produce a missing value or an error. It produces a plausible-looking price
series for the wrong security.
"""))

cells.append(code(r'''
PROF_CACHE = RAW / "fmp_profile_cache.json"
prof = json.loads(PROF_CACHE.read_text()) if PROF_CACHE.exists() else {}


def profile_of(symbol):
    # Cached in the same way as everything else here, because after the subscription
    # ends this information cannot be retrieved again at any price.
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

# A specific warning about UK listings. Prices there are usually quoted in pence rather
# than pounds, and the provider signals this with a lower-case p: GBp rather than GBP.
# Treating pence as pounds makes a company look a hundred times more valuable than it
# is. Simple returns are unaffected, since the factor of 100 cancels top and bottom, but
# anything weighted by price or market value is silently wrong.
gbp = primary[primary.currency.astype(str).str.upper().isin(["GBP", "GBX", "GBP PENCE"])]
if len(gbp):
    print(f"\n{len(gbp)} UK listings: check GBp (pence) versus GBP before any conversion")
'''))

cells.append(code(r'''
# Report the companies that could not be priced, ordered by how many assets they own.
# An aggregate count cannot distinguish thirty trivial holders from one large one, and
# the difference decides whether the gap matters.
lost = (primary[~primary.priceable]
        .sort_values("n_assets", ascending=False)[["name", "hq", "n_assets", "lei", "cik"]])
print(f"{len(lost)} firms not priceable, holding "
      f"{int(lost.n_assets.sum()):,} of {int(primary.n_assets.sum()):,} assets "
      f"({lost.n_assets.sum() / primary.n_assets.sum():.1%})")
print("\nlargest losses first. A well-known listed company here is a resolution failure,")
print("not evidence that it is unlisted. It is a resolution failure worth chasing.")
display(lost.head(25))

print("\nspot check. The chosen listing for the 20 largest owners. A European firm showing")
print("a US over-the-counter symbol here means the liquidity test picked the wrong line:")
display(primary[primary.priceable]
        .sort_values("n_assets", ascending=False)
        .head(20)[["name", "hq", "n_assets", "primary_symbol", "exchange",
                   "currency", "route"]])
'''))

cells.append(md(r"""
### 2d. A last pass by company name, and hand corrections

Some companies fail both identifier routes for uninteresting reasons. This step retries
them by name, which is a weaker key and is therefore used last and cautiously.

#### Why name matching needs a guard

Company names are not unique and are not written consistently. So a candidate is only
accepted if a similarity score clears a threshold, and every accepted match is printed
with its score for a human to read rather than applied silently. The score comes from
Python's built-in `difflib`, after stripping legal suffixes such as Corp, PLC, AG and
NV, which otherwise dominate the comparison and make unrelated companies look similar.

#### The correction that catches a wrong security rather than a missing one

After the name pass, the code checks every company listed away from its home exchange
and looks for a home-exchange listing instead, switching only if the home line trades at
least three times as much.

This matters because a US over-the-counter receipt is the wrong security for a European
company, not a noisy version of the right one. Three Finnish companies
in this dataset were on receipts trading a few hundred to a few hundred thousand dollars
a day, against home listings trading tens of millions. A receipt also carries an
exchange rate movement and trades during US hours against a European closing price, so
using one imports both a currency factor and a timing mismatch into a study about
weather.

The rule is deliberately evidence-based rather than dogmatic. Some companies genuinely
do move their primary listing abroad, so the switch requires the home listing to be
clearly more liquid rather than merely to exist.

#### Hand corrections

Everything above is automatic, and automatic rules match identifiers and names without
being able to see what a security actually *is*. The name search returned preferred
shares for two companies here. Preferred stock pays a fixed dividend and does not carry
the equity return, so a company represented by its preferred shares behaves like a bond
inside an equity portfolio.

Rather than piling more automatic rules on top of automatic rules, corrections live in
`config/ticker_overrides.csv`: a company name, a replacement symbol, and a written
reason. A blank symbol means exclude the company. That file is version controlled, so
every judgement call in the crosswalk is visible and arguable rather than buried in
code. This is what a hand-checked crosswalk is supposed to look like.
"""))

cells.append(code(r'''
# difflib is part of the Python standard library. SequenceMatcher scores how similar two
# strings are, from 0 to 1, which is what makes a name-based match testable rather than
# a guess.
from difflib import SequenceMatcher

SUFFIX = re.compile(r"\b(corp|corporation|inc|plc|ltd|limited|ag|sa|spa|nv|oyj|asa|se|"
                    r"holding|holdings|group|company|co|lp|llc|the)\b\.?", re.I)


def norm(s):
    s = SUFFIX.sub(" ", str(s).lower())
    return re.sub(r"[^a-z0-9 ]", " ", s).split()


def similar(a, b):
    return SequenceMatcher(None, " ".join(norm(a)), " ".join(norm(b))).ratio()


# The similarity threshold. Below this, matches are usually a different company with a
# superficially similar name. Chosen by inspecting matches at several thresholds, and
# fixed here rather than tuned until the sample looked right.
NAME_MIN = 0.72

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
#
# The single most valuable check in this section, because what it catches is not a
# missing value but a wrong one.
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
# through the name route in this dataset: HMS Bergbau and Savannah Energy, the latter
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
# Hand corrections, applied last, after every automatic route has run.
#
# The automatic routes match on identifiers and names. Neither can see what a security
# actually is, so the name search returned preferred shares for two companies. Preferred
# stock is a bond-like claim: it pays a fixed dividend and does not carry the equity
# return, so a company represented by its preferred shares would behave like debt inside
# an equity portfolio.
#
# Rather than adding more automatic rules on top of automatic rules, corrections go in a
# small CSV with a written reason for each one. That is what a hand-checked crosswalk is
# supposed to be: every judgement call visible, arguable, and recorded in version
# control rather than buried in code. A blank symbol means exclude the company.
OVR = REPO / "config" / "ticker_overrides.csv"
if not OVR.exists():
    raise SystemExit(
        f"config/ticker_overrides.csv is missing from {REPO}.\n"
        "  It is committed, so this means the Colab clone is behind the repository.\n"
        "  Check the `commit :` line printed by section 0 against the repository head.\n"
        "  Refusing to continue: silently skipping the overrides ships preferred\n"
        "  shares into the price panel, which is what a silent skip did once before."
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

# Guessing what a security is from the shape of its ticker is a weak method, and the
# first version of these rules demonstrated it: of 23 tickers flagged, 20 were ordinary
# common stock. HOLN.SW matched a warrant rule because the Swiss exchange suffix happens
# to end in W, and AEP, COP and CNP matched a preferred-share rule because they contain
# a P.
#
# The rules below therefore test only the part of the ticker before the exchange suffix,
# and keep only patterns that are almost always right. The real work is done by the
# liquidity screen underneath. Preferred shares, warrants and secondary international
# lines are all thinly traded, and thinness is a measurable property of the security
# rather than a guess about its name.
# The diagnostics below run last, after every correction and after the file is written,
# so that they describe the data that actually exists rather than an intermediate state.
#
# This ordering is not cosmetic. An earlier arrangement printed these tables before the
# corrections ran, so listings that had already been fixed were still reported as
# problems. A report that does not describe the file on disk is worse than no report,
# because it sends the reader chasing things that are already resolved.
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

# The stronger signal, and the one to read first. Value traded was already measured
# above. A genuine primary listing of a company large enough to own power stations does
# not trade a few thousand dollars a day. Anything appearing here is one of three things,
# and all three matter: a preferred line, a secondary trading venue, or a company too
# illiquid to hold in a portfolio at all. The last of those is a real limitation to
# report rather than a bug to fix.
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


TICKERS_END = len(cells)

cells.append(md(r"""
---

## 5. Blocking test 1: how much does survivorship bias matter?

### What a blocking test is

I use the term for a test I run *before* the analysis, to establish whether the analysis
is worth doing at all. The name is borrowed from software, where a blocking bug
is one that stops release. If a blocking test fails, no amount of careful work
downstream rescues the result.

I have three in this project. This is the first.

### The problem, stated plainly

My list of companies comes from an ownership dataset published in 2026. So **every
company in it is a company that still existed in 2026**. A company that owned power
stations in 2010 and was subsequently taken over, wound up or delisted is simply absent,
and it is absent precisely because of what happened to it.

This is **survivorship bias**, and it is not a minor caveat. Suppose companies with
flood-exposed assets failed more often. The sample would then systematically exclude the
worst outcomes among exactly the group I am studying, and the surviving exposed
companies would look like they earned a premium. That mechanism manufactures the
result I am looking for.

The classic reference is Shumway (1997), which showed that ignoring the returns of
delisted firms materially changes estimated premia in US data.

### What this test can and cannot do

I cannot fix the problem, because the exposure data for companies that no longer exist
does not exist either. What I can do is **measure the size of the hole**, so I can bound
and report the bias rather than acknowledge it and move on.

Three quantities, in increasing order of usefulness:

1. **The base rate.** How many companies the price provider records as delisting during
   the sample window. This tells you delisting happens, and little else.
2. **The sector rate.** The same, restricted to utilities, energy, materials and
   industrials. Delisting rates differ sharply by sector, so a market-wide figure would
   badly understate a utility-heavy sample.
3. **The return gap.** For delisted companies, the return over their final year against
   the market over the same window. This is what turns a *rate* into a *bias*. A 10%
   attrition rate with no return gap barely matters; the same rate with a large negative
   gap matters a great deal.

### The threshold, written down before the number appears

| If the sector delisting rate is | Then |
|---|---|
| under 5% over the window | Report it, note the direction of the bias, proceed |
| 5% to 15% | Proceed, but bound the effect by recomputing the headline result assuming delisted firms earned the observed gap |
| over 15% | The survivor-only sample cannot carry the main claim. Either rebuild the universe from historical data, or reframe the paper around what this sample can support |

I write this down before running the test. A threshold chosen after seeing the number
is worthless.

> Shumway, T. (1997). "The delisting bias in CRSP data." *Journal of Finance* 52(1),
> 327-340.
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

The numbers that just printed are not usable, and it is worth being explicit about why
rather than quoting them with a footnote.

Look at the delisted companies that came back. They include listings from the TSX
Venture exchange, Australian small caps, London's AIM market, and at least one warrant
rather than a company. The provider's delisted list covers every venue it touches, and
most of those venues are populated by micro-caps and shell companies that delist
constantly.

My universe is a few hundred established asset owners on developed-market main boards.
**The delisting hazard of a large integrated utility is not the delisting hazard of a
junior mining exploration company.** Applying the threshold above to a rate computed
across both would be worse than not measuring at all, because the number would carry the
authority of a computation while describing a different population.

There is a second problem, and it may be larger. The recorded delisting counts by year
rise by a factor of roughly thirty between the start of the window and the end.
Delisting rates do not behave like that. **Coverage does.** If the provider's list is
effectively a recent snapshot rather than a historical record, then no rate computed
from it across the full window means anything.

So I do three things here. I test the list for that recency pattern first, because if it
is a snapshot then everything else is polishing an unusable number. I compute a rate with
the numerator and denominator restricted to the same exchanges. And I split the return
gap by company size.

The last of those is where I found the interesting result.
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
### 5c. What the data source can and cannot support

Two conclusions and one correction.

**The provider cannot measure delisting over my window.** The by-year counts confirm the
recency pattern. The list is close to empty in the early years and dense in the
recent ones, so it is a current snapshot wearing the costume of a historical record. Any
rate computed across the full window from it is an artefact and should be discarded
rather than quoted carefully.

**The direction of the bias may be the opposite of the textbook worry.** Splitting the
return gap by how heavily each delisted company traded produces a pattern worth reading
carefully: the smallest companies underperform badly before delisting, while the largest
ones *outperform*. That makes sense once stated. Small companies delist because they
fail. Companies the size of those in my universe mostly delist because they are
**acquired**, and acquisitions are announced at a premium to the market price.

If that holds, excluding delisted companies biases returns *downward* in a large-cap
sample rather than upward. With a handful of observations in the relevant size band this
is a direction rather than a magnitude, and the honest statement is that the bias is
**unmeasured at the sizes that matter**.

**The exchange match needed fixing.** The full symbol list endpoint returns symbols
without an exchange field, so numerator and denominator could not be put on the same
footing. The screener endpoint carries both exchange and market value, which is better
anyway, because it allows the comparison population to be matched on size as well as
venue, and size is what the split above shows to be the variable that matters.

### The right instrument, for the record

The standard tool for this question is CRSP's delisting file, which is complete from
1926, distinguishes mergers from liquidations from involuntary delistings, and attaches
a delisting return to each event. It is available through WRDS at most universities.
Everything I do in this section is a substitute for it, and I would replace it given
access.

Free alternatives worth noting: SEC Form 25 filings, which are the formal delisting
notice and are searchable on EDGAR back well before 2010 for US companies; and the GLEIF
entity status field, which records corporate dissolutions and mergers globally.
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
---

## 6. Blocking test 2: can this pipeline reproduce something already known?

### The idea

Everything up to here establishes that data arrived and is internally consistent. None
of it establishes that returns computed from it are **correct**.

A panel can pass every integrity check and still be wrong. A stock split applied twice,
a currency mixed into a dollar-denominated factor, a preferred share standing in for
common stock: none of these produce a missing value or an error. They produce numbers.

So before estimating anything unknown, reproduce something known.

### The specific test

I take my price panel, compute returns through the same code path the real analysis will
use, form a diversified portfolio, and regress its returns on the Fama-French factors.

**The market beta of a broad equity portfolio is one.** That is close to a definition
rather than a hypothesis: the market factor is the value-weighted return of the whole
market, so a diversified basket of large stocks must move roughly one-for-one with it.
If the number comes back at 0.4 or 2.1, the return construction is broken, and every
coefficient computed later is worthless.

| Quantity | Expected | What a failure means |
|---|---|---|
| Market beta, equal-weighted portfolio | roughly 0.7 to 1.3 | Returns are misscaled, or the panel is not what it appears to be |
| R-squared | above 0.5 | The portfolio is not diversified, or the returns are noise |
| Annualised alpha | small | A systematic construction error, or a real effect that needs a name |
| Utility betas below energy betas | yes | If reversed, tickers are attached to the wrong companies |

That last row deserves emphasis. Regulated utilities are famously less sensitive to the
market than integrated oil companies, because their revenues are set by regulators
rather than by a commodity price. Checking individual companies against that expectation
catches a whole class of error the portfolio test cannot see: if tickers are matched to
the wrong companies, the aggregate can still look fine while every individual number is
meaningless.

### Why the headline test uses US companies only

The Fama-French factors are **dollar** returns. My panel holds nine currencies. A euro
return regressed on a dollar factor measures the asset plus the exchange rate, and an
exchange rate is not a climate hazard.

So I run the main test on the US subset, where the question does not arise. I run the
non-US companies separately, and I read the gap between the two as a measurement of how
much the currency question matters.

### A note on the standard errors

Daily portfolio returns are heteroskedastic, meaning their variability changes over
time, and mildly autocorrelated, meaning today's return carries information about
tomorrow's. Ordinary least squares standard errors assume neither, and would overstate
how precisely the coefficients are estimated.

I use Newey and West (1987) standard errors, which are robust to both. Five lags is the
conventional choice for daily data, and I fixed it before seeing any result rather than
tuning it afterwards.

> Newey, W. K. and West, K. D. (1987). "A simple, positive semi-definite,
> heteroskedasticity and autocorrelation consistent covariance matrix."
> *Econometrica* 55(3), 703-708.
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
### 6b. Where does the alpha come from?

The test passes on every formal criterion, and then hands me something I have to explain:
a statistically significant positive alpha on a portfolio with no obvious reason to have
one.

That number is roughly the size of the effect I might plausibly report. If it is an
artefact, my headline result inherits it and I would have no way to tell the two apart.
So I cannot leave it alone.

There are four candidate explanations and three of them are mechanical.

**Equal weighting with daily rebalancing.** Computing a daily equal-weighted return
implicitly rebalances the portfolio every day, selling whatever rose and buying whatever
fell. Because quoted prices bounce between the bid and the ask, that harvests the bounce
as if it were return. This is the bias documented by Blume and Stambaugh (1983), and it
is largest in illiquid stocks, of which this panel has a fair number.

**Survivorship.** The universe is survivor-only by construction, as section 5 discussed.

**Missing factors.** Three factors are not many. Fama and French (2015) add profitability
and investment, and Carhart (1997) adds momentum. Utilities and energy companies load
distinctively on those, so a three-factor model can leave real structure in the residual
and call it alpha.

**A genuine sector effect.** Possible, and it would be a finding rather than a bug, but
it is the last explanation to reach for rather than the first.

I separate the first from the rest by running the same regression four ways: equal against value weighted, and daily against monthly buy-and-hold. Monthly
returns are compounded within each month for each company before the portfolio is
formed, which is what removes the implicit daily rebalancing. **If the alpha collapses
under value weighting or monthly compounding, it was microstructure.**

I also exclude companies showing repeated single-day moves above 50%. Those are
usually broken price series rather than volatile companies: one in this dataset shows a
move of more than 1,000% in a day, which is a corporate reorganisation the price series
did not handle. Excluding them is a judgement call, so I make it explicitly and print the names I drop.

> Blume, M. E. and Stambaugh, R. F. (1983). "Biases in computed returns: An application
> to the size effect." *Journal of Financial Economics* 12(3), 387-404.
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
### 6c. Not microstructure, and not missing factors. So what?

The alpha barely moves across weighting schemes and return frequencies, so I can rule out
the rebalancing bias. Next I rule out missing factors, and I have a specific reason to
expect that one to matter.

The portfolio loads positively on the value factor, and the value premium was negative
through most of the 2010s. So a three-factor model *predicts* low returns for this
portfolio, and anything it actually earned above that prediction is recorded as alpha.
These are also profitable, capital-intensive companies, which is precisely what the
profitability and investment factors exist to price. Both are free downloads from the
same library as Panel A.

I split the sample into three periods, chosen on economic events rather than to split the
result: the decade before COVID, the pandemic and the 2022 European
gas crisis, and the recent period of data-centre electricity demand.

That split matters beyond this diagnostic. If most of the return variation in the sample
comes from a small number of recent years, then **any cross-sectional sort will be
dominated by those years**. Worse, both recent episodes are correlated with hazard
exposure by construction: the gas crisis was a shock to European energy assets, and the
data-centre trade is concentrated in US independent power producers, which are among the
largest asset owners in this universe. A hazard sort could load on either and report it
as a climate risk premium with a convincing t-statistic.

I would rather know that before running the sort than after.

Subperiods carry few observations relative to the number of factors, so the alphas
should be read as indicative magnitudes and the t-statistics as weak evidence.
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

## 7. Archiving the data

The price data comes from a paid subscription. When that subscription ends, it cannot be
rebuilt at any price without paying again. Everything in this notebook otherwise runs on
free data.

There is a second, less obvious reason to archive carefully. Colab runs on a temporary
virtual machine that is deleted when the session ends, so "it worked and the files are
there" is true for a few hours.

So I copy everything to Google Drive, build a single archive file, and then **verify the
copies by checksum rather than by file count**. That distinction is the
point of the section. A truncated copy has the wrong size and would be caught by almost
any check; a corrupted one has the right size and would not. Comparing SHA-256 hashes
catches both, and the archive ships with a checksum list inside it so the copy can be
verified again at any point in the future by anyone.

The files that cannot be regenerated after the subscription ends are the price panel,
the delisted company list and the company profiles. The identifier caches can be
rebuilt, slowly. The factor data is a free public download, with one caveat: its
publisher updates the file in place, so a download next year returns different bytes for
the same nominal series. That is why the untouched original is archived alongside the
parsed version.
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
# Export EVERYTHING in data/raw, then separately assert that the critical files are
# among them. The first version listed filenames by hand and got one wrong: Panel A is
# written as panel_a_ff3_daily.csv, not ff3_daily.csv, so both Panel A files were
# once silently left out of the archive while the cell reported success on everything
# else. A hand-maintained list of filenames drifts away from the code that writes them.
# A glob cannot.
present = sorted(f.name for f in RAW.iterdir() if f.is_file())

CRITICAL = ["panel_b_prices_daily.csv",   # cannot be rebuilt without a paid key
            "panel_a_ff3_daily.csv",      # parsed Panel A
            "ff3_daily_original.csv",     # the exact bytes Ken French served, the audit record
            "manifest.json",
            "fmp_delisted.json", "fmp_profile_cache.json"]
missing_req = [f for f in CRITICAL if f not in present]

print(f"\n{len(present)} files to export, "
      f"{(sum((RAW / f).stat().st_size for f in present) / 1e6):.1f} MB total")
for f in present:
    print(f"  {f:38s} {(RAW / f).stat().st_size / 1e6:8.1f} MB")
if missing_req:
    print(f"\nMISSING REQUIRED FILES: {missing_req}")
    print("Run the sections that produce them before exporting, or you will cancel")
    print("the subscription with a hole in the archive.")
    print("\nff3_daily_original.csv matters more than it looks. Ken French updates that")
    print("file in place, so a re-download next year returns different bytes. Those are")
    print("the exact bytes served on the day the panel was built, and the manifest hash")
    print("only means something if they are kept.")
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

# A checksum manifest travels INSIDE the zip. The Drive copy is hash-verified above, but
# when the mount fails there is no verification on the download path at all, and the
# copy that actually matters is the one extracted on the laptop. Shipping the sums with
# the data means that copy can be verified at any point in the future, by me or by
# anyone I send it to.
sums = {f: sha256_of(RAW / f) for f in present}
for f in (REPO / "config").glob("*.csv"):
    sums[f"config/{f.name}"] = sha256_of(f)
sums_txt = "\n".join(f"{h}  {n}" for n, h in sorted(sums.items())) + "\n"

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in present:
        z.write(RAW / f, arcname=f"data/raw/{f}")
    for f in (REPO / "config").glob("*.csv"):
        z.write(f, arcname=f"config/{f.name}")
    z.writestr("SHA256SUMS.txt", sums_txt)

print(f"{zip_path.name}: {zip_path.stat().st_size / 1e6:.0f} MB, "
      f"{len(sums)} files, checksums included")

# Verify the archive by reading it back, rather than trusting that writing worked.
bad_zip = []
with zipfile.ZipFile(zip_path) as z:
    if z.testzip() is not None:
        print("ZIP IS CORRUPT. Do not rely on it.")
    for f in present:
        h = hashlib.sha256()
        with z.open(f"data/raw/{f}") as fh:
            for blk in iter(lambda: fh.read(1 << 20), b""):
                h.update(blk)
        if h.hexdigest() != sums[f]:
            bad_zip.append(f)
if bad_zip:
    print(f"HASH MISMATCH INSIDE THE ZIP: {bad_zip}")
else:
    print("every file inside the zip matches its source, byte for byte")
print("\nAfter extracting the archive locally, verify it with:")
print(f"  cd <extracted folder> && shasum -a 256 -c SHA256SUMS.txt")

if IN_COLAB:
    try:
        from google.colab import files
        print("\nStarting the browser download. A large file can take a few minutes and")
        print("Colab sometimes drops it silently, so check the downloads folder and")
        print("rerun this cell if nothing arrives.")
        files.download(str(zip_path))
    except Exception as exc:
        print(f"browser download unavailable ({exc})")
        print(f"Use the file browser in the left sidebar instead: navigate to {zip_path}")
        print("right-click, Download.")
'''))

cells.append(md(r"""
---

## 8. Scope, and what is deliberately absent

I download two datasets, build the list of companies that connects them to a third, and
try to break all three. I compute no returns for the study, run no regressions on the
hypothesis, form no portfolios and merge no datasets. Here I state what falls outside
that scope.

### Known limitations, stated rather than buried

**The exposure variable does not exist yet.** The ownership dataset identifies which
company owns which asset, but carries no coordinates. Building a physical hazard measure
requires the individual sector datasets, which do carry locations, plus a hazard dataset
to intersect them with. None of that is here and none of it needs a subscription.

**The ownership snapshot is undated.** It records who owns what now, not who owned what
in 2012. Using a current ownership map to explain historical returns attributes to a
company assets it may not have owned at the time. This is **look-ahead bias**, and it is
worse than survivorship bias because it contaminates the explanatory variable rather
than the outcome, so no amount of care downstream repairs it. I have investigated
whether the publisher's earlier releases can reconstruct a historical map, and the
answer so far is that they cannot: most of the apparent change between releases is the
publisher's own research catching up rather than ownership actually changing.

**Survivorship is unmeasured at the relevant company size.** Section 5 explains why, and
what would fix it.

**No currency conversion has been applied.** Nine currencies, and UK prices are in pence
rather than pounds.

**Two subsidiary questions are open.** Some asset owners are wholly owned subsidiaries of
listed parents. Whether to roll them up into the parent changes what counts as a company
in the sample and interacts with the ownership structure already in the source data, so
it is a research design decision rather than a lookup, and it is not made here.

### On reporting a null result

If the exposure measure turns out to have no explanatory power for returns, that is a
result and I intend to report it as one, alongside the minimum effect size the sample
could have detected. A study that can only publish one of its two possible answers is
not a test of anything.
"""))

cells.append(md(r"""
---

## Appendix A: diagnosing the data provider's coverage limits

These cells are not part of the pipeline. They are the diagnostic work I did to establish
what a given API key can and cannot retrieve. I kept them because the method generalises,
and because the reasoning is more useful than the answer.

### The situation

An initial attempt to download prices on a free API key returned data for a handful of
symbols and refused the rest with `HTTP 402 Payment Required`. The obvious inference is
"the free tier is too small, pay for a bigger one". That inference is worth resisting
until it is tested, because the correct action differs completely depending on *what
kind* of limit it is.

### Distinguishing the possibilities by measurement

My approach was to hold two things constant and vary the third. If the limit is the type
of price series requested, then one symbol should succeed on one variant and fail on
another. If it is the length of history, recent data should work where older data does
not. If it is the set of covered symbols, some symbols should work fully and others not
at all.

The answer was the third. The free key covered a hand-picked set of household-name
symbols: no rule to work around, and nothing that could be turned into a
research universe.

### Three status codes that look alike and mean opposite things

This is the practically useful part.

| Code | Means | Correct response |
|---|---|---|
| `401` | The key is wrong, or the account email is unverified | Fix the key |
| `402` | The key is valid, the endpoint is live, the request is above your plan | A real plan limit |
| `403` | Not permitted. Very often a retired endpoint rather than a plan limit | Check the URL before the subscription |

The 403 case cost me an afternoon and is worth repeating. Older documentation and many
tutorials use URL paths that have since been retired. Requests to them return 403, which
reads as "your account may not do this", so a perfectly valid key on a paid plan produces
exactly the same error table as no key at all. If every probe fails at once, including
the most basic one, suspect the URL rather than the subscription.
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
        print("  -> Dividend-adjusted prices are closed to this key: PRICE returns only.")
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
    print("  a committee using information unavailable at the start of the sample.")
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


# ---------------------------------------------------------------- run order
# The cells above are written in the order that made sense while building the project.
# They are reordered here into the order they should be RUN.
#
# Two moves are needed. The company list has to be built before the prices can be
# downloaded, because it produces the list of tickers to request, but it was written
# afterwards. And the blocking tests have to run after the price panel exists, because
# they analyse it.
head     = cells[:PANELB_START]              # title, setup, Panel A
panel_b  = cells[PANELB_START:PANELB_END]    # Panel B and the integrity checks
tickers  = cells[PANELB_END:TICKERS_END]     # section 2, the company list
blocking = cells[TICKERS_END:]               # blocking tests, archiving, appendix

cells = head + tickers + panel_b + blocking

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
