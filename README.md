# Paper 1: data layer

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ochofer/paper1-hazard-exposure-data/blob/main/notebooks/01_raw_panels.ipynb)

Raw data acquisition for the physical-hazard-exposure asset pricing study. This repo
holds the acquisition layer only: two raw panels, a manifest, and the checks that
confirm the download was not silently corrupted. No returns, no regressions, no
portfolio construction.

Two commitments are stated here before any result exists, so that they cannot be
quietly relaxed once results start appearing.

**Results so far are in [`FINDINGS_2026-08-21.md`](FINDINGS_2026-08-21.md).** That file
records the data accessed, all three blocking tests with their numbers, the crosswalk
faults found and fixed, and five pre-commitments made before any hazard variable exists.
Step-by-step instructions for running any of it are in
[`EXECUTION_CHECKLIST.html`](EXECUTION_CHECKLIST.html).

---

## 1. Survivorship bias: how it will be handled

**The ticker list currently in this repo is survivorship-biased, and knowingly so.**
`config/tickers_draft_v0.csv` contains twenty firms that all still trade in August 2026.
It exists to prove the data path works. It is not a research universe and no return-based
result may be reported from it. This is stated first because a draft list that quietly
becomes the final list is the single most common way survivorship bias enters a study.

The intended handling, in order:

**Point-in-time universe construction.** Inclusion in the universe at date *t* must be
decided using only information available at *t*. The current construction fails this in
two distinct places, and they need different fixes:

- *Price layer.* Firms delisted before today are absent from a list built from today's
  survivors. Fix: build the universe from the union of listed and delisted firms, taking
  the delisted set from FMP's `delisted-companies` endpoint, and admit a firm to the
  panel from its listing date rather than from the start of the sample.
- *Exposure layer.* The GEM Ownership Tracker is a single undated snapshot whose sector
  vintages span roughly sixteen months. Attributing 2026 asset ownership to a firm in,
  say, 2014 is look-ahead, not survivorship, and it is the larger of the two problems
  because it contaminates the independent variable. This is **unresolved**. It is the
  largest unmitigated threat to the design and it is not fixed by anything in this repo.

**Delisting returns must be included.** A firm that goes to zero must contribute its
final return, not simply disappear. Dropping the last observation converts bankruptcies
into non-events and biases mean returns upward, precisely the direction that would
flatter a hazard-exposure hypothesis. Where a delisting return is unavailable, the
convention will be stated explicitly and applied uniformly rather than case by case.

**The size of the problem will be measured before it is assumed small.**
`code/01_survivorship_test_fmp.py` measures FMP's delisting hit rate against hand-listed
delistings and a fixed-seed random sample, with pass thresholds written into the
docstring *before* any run so the bar cannot move after the answer is seen. An HTTP 200
carrying an empty array counts as a miss, not a hit.

> **Status: this test has not yet returned a number.** Until it does, the magnitude of
> the survivorship problem is *unknown*, not small. Everything in this section is a
> stated intention, which is not the same thing as a measured correction.

---

## 2. Transaction costs: how they will be handled

**Transaction costs are not netted anywhere in this repo, by design.** The raw panels are
gross. Costs belong at the portfolio layer, applied once, visibly, and to turnover rather
than to holdings.

**Gross and net will both be reported.** Any strategy result carries both figures in the
same table. A net figure presented alone hides the cost assumption; a gross figure
presented alone is not a claim about anything achievable.

**Costs apply to turnover.** Per-period cost is one-way cost in basis points multiplied by
period turnover, charged at each rebalance. Turnover is computed from realised portfolio
weights, so it correctly charges for drift-driven rebalancing rather than only for
deliberate signal changes.

**The cost assumption is fixed in advance and varied only as a stated sensitivity.**
Baseline is a flat one-way cost applied uniformly, chosen before results are seen.
Because the universe here is large-cap utilities, energy and materials, a flat assumption
is defensible; it would not be for small caps. Sensitivities are reported across a range,
not tuned to a preferred number.

**The break-even cost is the honest headline.** Rather than defending one cost figure, the
result to report is the one-way cost at which the strategy's excess return reaches zero.
That number is assumption-free and lets a reader apply their own cost beliefs. If
break-even sits below plausible real-world costs, that is the finding and it will be
reported as such.

**Known cost complications specific to this universe**, recorded now so they are not
discovered late: the European leg incurs FX conversion costs not present in the US leg;
`^GSPC` is an index and cannot be traded, so any benchmark-relative cost comparison uses
`SPY`, which is why both are pulled; and MLPs and partnerships were excluded from the
draft list partly because their tax treatment makes net-of-cost comparison with
corporations non-trivial.

---

## 3. Layout

```
config/tickers_draft_v0.csv   draft universe, revisable in one edit
notebooks/01_raw_panels.ipynb acquisition notebook (Colab-ready)
build_notebook.py             generates the notebook; keeps it diffable in git
data/raw/                     outputs + manifest.json (gitignored except manifest)
```

## 4. Running it

Colab is the intended environment. Add `FMP_API_KEY` to the Colab **Secrets** panel (key
icon, left sidebar) and enable it for the notebook. Do not paste it into a cell, or it
will be committed. Locally, `export FMP_API_KEY='...'`.

The notebook writes `panel_a_ff3_daily.csv`, `panel_b_prices_daily.csv`, the untouched
original French download, and `manifest.json` with SHA-256 hashes so a rerun can be
*proved* identical rather than assumed so.

## 5. Data notes that cause silent errors

- **French factors are in percent, not decimals.** `Mkt-RF = 0.55` means 0.55%. Stored as
  published; the `/100` belongs downstream.
- `-99.99` and `-999` are French's missing-value codes, converted to `NaN` at parse.
- **`SHEL.L` is quoted in pence (GBp), not pounds**. A factor-of-100 error waiting to
  happen.
- No FX conversion is applied. US names are USD, European names EUR/CHF/GBp.
- **Panel A is the US factor set.** The European leg must be regressed on French's
  Developed Europe factors. Mixing them is not a currency nuisance, it is the wrong model.

## 6. Draft universe

Twenty firms drawn from the top of `outputs/cross_section.csv` by operating-asset count:
fourteen US, six European. Deliberately excluded from the draft, each for a reason that
is a live design question rather than a data question:

- **KKR, Blackstone**: whether a private-equity sponsor should carry physical hazard
  exposure in a listed-equity study is unsettled.
- **Energy Transfer, Enterprise Products**: MLPs; partnership structure and K-1 tax
  treatment make them non-comparable to corporations without a stated convention.
- **Berkshire Hathaway is included** but flagged: it owns its utilities outright, which is
  defensible, but it is a conglomerate whose returns are mostly not about physical assets.

Revising the list means editing one CSV. Nothing downstream hardcodes a ticker.
