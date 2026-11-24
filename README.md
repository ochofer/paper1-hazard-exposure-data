# A data layer, built and audited, for a physical climate risk study

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ochofer/paper1-hazard-exposure-data/blob/main/notebooks/01_raw_panels.ipynb)

Companies own physical assets, e.g., power stations, pipelines, mines and cement works, and those assets sit in places whose weather varies. The question this data serves is whether investors price the risk that weather damages those assets or interrupts what they produce, i.e., whether companies holding more exposed assets earn different returns from companies holding less exposed ones, once the known drivers of returns are controlled for.

**This repository builds and audits the data for that question, and does not test whether hazard exposure is priced.** A power calculation, published here, set the planned return test, a cross-sectional Fama-MacBeth design, aside. A quintile-spread comparison was run by a rule set in the header of its script before the run, and the note reports its result with the minimum detectable effect that makes it readable.

The note is *What a vintage difference measures*, a hand verification of ownership changes in a public asset-level database, published as the release [`note-v1.4`](https://github.com/ochofer/paper1-hazard-exposure-data/releases/tag/note-v1.4). Every result figure in it is read at build time from a named output file, two of which are withheld. The labels and settings that are typed are listed in its Appendix D.

## What is here

The study needs three sources, and they do not connect to one another.

| Source | What it gives | Provider | Cost |
|---|---|---|---|
| Asset ownership | Which company owns which power station, mine or pipeline | Global Energy Monitor | Free, with registration |
| Share prices | What each company's shares did, daily | Financial Modeling Prep | Paid |
| Risk factors | The known drivers of returns, used as controls | Kenneth French Data Library | Free |

The difficulty is the join. The ownership data identify companies by name and by legal identifiers, the price data by stock ticker, and neither source holds the other's key. Most of the work in this repository builds that bridge and then tries to prove it wrong.

**The sample.** 328 ownership entities resolve to the US and developed-Europe listed universe, 302 of them to a tradeable listing, and the 328 together hold 4,550 distinct operating assets in 5,115 asset holdings, an asset owned by two of the 328 counted in each (`outputs/cross_section_summary.txt`). The price panel holds 1,122,798 daily rows across 304 symbols, i.e., the 302 companies and two benchmarks, on a single total-return convention, and passes 16 of 16 integrity checks.

### Three counts, and why they differ

Three counts of companies appear in this project. They measure different things, so a reader who meets one alone can mistake it for another.

| Count | What it is |
|---|---|
| 372 | Ownership entities that resolve to the US and developed-Europe listed universe and hold at least one tracked asset of **any** status. 200 of them hold five or more |
| 328 | The same, keeping only assets that are **operating**, i.e., not announced, permitted or cancelled. 175 of them hold five or more |
| 302 | Those of the 328 that resolve to a tradeable listing, i.e., the price panel |

The step from 372 to 328 is the operating-asset filter alone. The step from 328 to 302 is identifier coverage, i.e., whether a company's shares can be found in the price data, and every one of the 328 holds at least one operating asset. Both filters are switches at the top of [`code/00_coverage_and_crosswalk.py`](code/00_coverage_and_crosswalk.py), so a reader can rerun the audit either way and see the counts move.

The hazard study itself is closed: the hazard measure is not built and not scheduled, and nothing in this repository depends on it.

## Terms

Each term carries one meaning, the same in the code, the notebook, the outputs and the note.

- **Release**: one dated file published by Global Energy Monitor, identified by its file name and SHA-256 hash. The two files of August 2026 are **V1** and **V2**.
- **Vintage**: the data as they stood in one release. A **vintage difference** is the change between two releases of the same tracker, and it is what this repository measures.
- **Pinned release**: the release a script reads, named by file name and hash in the script's provenance record.
- **Ownership entity**: an owner as Global Energy Monitor records it, before any matching. A **company** is the listed company an ownership entity resolves to, and the note says *firm* for the same thing.
- **Listed parent**: an ownership entity that resolves to the US and developed-Europe listed universe. There are 328, and 302 of them resolve to a listed company with a price series.
- **Priceable**: a listed parent whose shares resolve to a tradeable listing in the price panel. There are 302.
- **Tracked asset**: an operating unit in the ownership data. Global Energy Monitor's own words *unit* and *plant* appear where its fields are named.
- **Build-out, restatement and methodology change**: the three causes into which a vintage difference is split. *Revision* keeps its ordinary sense and is not a fourth cause.
- **Exposure**: attributable capacity, i.e., the share of a tracked asset's capacity assigned to a company through its ownership stake, summed over its assets.
- **Convention**: a stated rule for an ambiguous case, e.g., the blank-share convention, applied the same way in every script and reported with its alternative beside it.
- **Provenance record**: the `RUN_PROVENANCE_*.json` file a script writes at run time, naming every input it opened with its hash.
- **Figure register**: the table that ties every result figure in the note to the output file that carries it.
- **Price panel**: the daily total-return series of the priceable companies and two benchmarks, pulled from Financial Modeling Prep on 21 August 2026 and not redistributed.
- **Crosswalk**: the table that joins ownership entities to security identifiers and tickers, with every hand correction recorded in `config/ticker_overrides.csv`.
- **Blocking test**: a test that stops the pipeline if it fails, run before anything uses the pipeline's output.

## Why the data layer stands apart

A data layer that can be checked only through the final result cannot really be checked, because the incentive to question the download depends on how the answer looks: an interesting result invites no second look, while a dull one does. The raw layer is therefore audited on its own, before anything depends on the answer, and each of the notebook's blocking tests tries to prove the pipeline broken before the pipeline is used.

## Where to start reading

| If you want | Read |
|---|---|
| The reasoning, with the code | [`notebooks/01_raw_panels.ipynb`](notebooks/01_raw_panels.ipynb) |
| What the checks found, with numbers | [`FINDINGS_2026-08-21.md`](FINDINGS_2026-08-21.md) |
| To run it yourself | [`EXECUTION_CHECKLIST.html`](EXECUTION_CHECKLIST.html) |

The notebook is written for a reader who may be new to quantitative finance or to Python. A sceptical reader should take sections 5 and 6 first: section 6 takes the finished price panel and tries to prove it broken, and its argument stands whether or not the rest of the repository is trusted.

## Two commitments made before any hazard variable exists

### 1. Survivorship bias

The list of companies comes from an ownership dataset published in 2026, so every company in it still existed in 2026. A company that owned power stations in 2010 and was then taken over or wound up is absent, and absent because of what happened to it. If companies with exposed assets failed more often, the sample would drop the worst outcomes in exactly the group under study.

The commitments:

- **The universe is point-in-time.** Whether a company belongs in the universe at date *t* is decided with information available at *t* alone.
- **Delisting returns are included.** A company that goes to zero contributes its final return. Dropping the last observation turns bankruptcies into non-events and biases mean returns upward, the direction that would flatter the hypothesis.
- **The size of the problem is measured before it is assumed small**, with thresholds fixed before the number appears.

Section 5 of the notebook runs the measurement, and it returns two results. First, the price provider cannot measure delisting over this sample: its records show seven delistings in 2010 and 2,353 in 2025, a 336-fold rise, and delisting rates do not behave like that, so the series measures the provider's coverage and not delistings. The rate is therefore not quoted. Second, split by how heavily they traded, the smallest delisted companies underperform badly before delisting, while the largest outperform. That fits the usual account, in which small companies delist because they fail and companies of the size studied here mostly delist because they are acquired, at a premium. If it holds, excluding delisted companies biases returns downward, not upward.

**Survivorship bias is therefore unmeasured at the company sizes that matter here.** Ten observations fall in the relevant band, which gives a direction and not a size, and this provider's records cannot settle it. CRSP's delisting file would settle it. No file of this repository uses CRSP, and the question stays open for a later study.

### 2. Transaction costs

Nothing in this repository nets transaction costs. The panels are gross, because costs belong at the portfolio layer, where they are applied once, visibly and to turnover. There is no portfolio layer yet, so these are rules for when one exists:

- **Gross and net are reported together**, in the same table. A net figure alone hides the cost assumption, and a gross figure alone is not a claim about anything achievable.
- **Costs apply to turnover** computed from realised portfolio weights, so that both rebalancing driven by drift and deliberate changes of signal are charged.
- **The cost assumption is fixed in advance** and varied only as a stated sensitivity, never tuned. A flat one-way cost suits a universe of large utilities, energy and materials companies, and would not suit small caps.
- **The break-even cost is the headline**, i.e., the one-way cost at which the excess return reaches zero, so a reader can apply their own view of costs.

Three features of this universe complicate costs. The European leg pays currency conversion that the US leg does not. `^GSPC` is an index and cannot be traded, which is why `SPY` is downloaded beside it. And partnerships carry a tax treatment that makes a comparison net of costs with ordinary companies harder.

## Data notes that cause silent errors

Each of these produces a plausible number and raises no error, which is why it is written down.

- **French's factors are in per cent, not decimals.** `Mkt-RF = 0.55` means 0.55 per cent. They are stored as published, so the division by 100 belongs downstream.
- **`-99.99` and `-999` are missing-value codes**, converted to `NaN` when parsed.
- **UK prices are quoted in pence, not pounds**, labelled `GBp` with a lower-case p, i.e., a factor of 100 in anything weighted by price or market value.
- **No currency conversion is applied.** The panel holds nine currencies.
- **Panel A is the US factor set.** The European companies need French's Developed Europe factors, and mixing the two gives the wrong model.
- **A price index has no total-return version.** `^GSPC` always falls back to the price return, which is why the integrity checks test the convention on companies and test the benchmarks separately.

## What this repository does not contain

**The price panel.** Financial Modeling Prep's terms require a separate licence to redistribute its data, so `data/raw/` is excluded from version control. Published instead are the fetch code, the resolved company list, the hand corrections with a reason for each, and [`data/raw/manifest.json`](data/raw/manifest.json), which carries the SHA-256 hash, byte size and row count of every file the findings were computed on, with each of the 304 symbols' date coverage. A reader with their own access can therefore check that their panel matches this one. `build_manifest.py` writes an `owner` field naming who made the pull, here Carlo Hofer. The committed manifest lacks the field and gains it when it is next written. Running the notebook writes the same kind of record for the reader's own pull as `data/raw/manifest_run.json`, which git ignores and which cannot overwrite the published record. Matching hashes show the same bytes are held, and where they differ the coverage by symbol shows which symbols diverge.

**What the price series is.** Every return is computed from one field, `adjClose`, from Financial Modeling Prep's `historical-price-eod/dividend-adjusted` endpoint, pulled on 21 August 2026. The adjustment is the vendor's, for splits as well as dividends: NextEra's four-for-one split of 26 October 2020 shows no break in the series, and Exxon's adjusted level in January 2010 is about half its nominal close of the time. No unadjusted close is stored beside it, so the adjustment cannot be undone or checked independently. A vendor's adjusted history changes whenever a new dividend or split is applied, so the panel is a snapshot of the vendor's adjustment on 21 August 2026. **The pull is therefore auditable, not repeatable**, and rebuilding the price layer requires a paid subscription, while every other input here is free. The pull did not record a fetch time for each file, and none has been filled in from file system times, which change whenever a file is copied.

**The outputs and the evidence.** `outputs/` holds every file the vintage and measurement scripts produce, and `evidence/` holds the hand-collected input behind the recording-lag table, i.e., transaction dates read from exchange filings, company statements and EDINET, with a source for each. Two files are withheld, `vintage_return_spread.csv` and `vintage_return_spread.txt`, because they are computed from the licensed price series. They are named in the note's figure register with their hashes, and rerunning `code/11_vintage_return_spread.py` against your own pull reproduces them.

One file has no script behind it. `outputs/isin_screen.csv`, which joins the ownership entities to GLEIF identifiers and ISIN counts and from which the 328 come, was built by hand from two free and openly licensed inputs, and it carries no provenance record. Every other file in `outputs/` resolves to a numbered script with a provenance record naming the release and its hash.

Every data output is sorted before it is written, so that rerunning a script against the pinned release reproduces its hash, and the run logs print each output's path relative to the repository. Two files marked `_SUPERSEDED_` hold the same rows as two outputs of record in another order, and `outputs/PROMOTION_2026-09-08.txt` records the hashes of both with their row count and header.

## Layout

```
notebooks/01_raw_panels.ipynb   the analysis, with the reasoning
build_notebook.py               writes the notebook, so that it stays readable in git
build_manifest.py               writes data/raw/manifest.json from a local pull
code/                           the numbered scripts of the vintage study and of the note's build, described in code/README.md
EXECUTION_CHECKLIST.html        how to reproduce it, and what each step should print
FINDINGS_2026-08-21.md          the results of the three blocking tests, with numbers
config/universe.csv             the 328 ownership entities
config/universe_isins.csv       their security identifiers, from GLEIF
config/ticker_overrides.csv     hand corrections to the crosswalk, each with a reason
config/tickers_draft_v0.csv     a 20-name sample kept for testing the data path
data/raw/                       the downloaded panel, licensed and excluded from git
data/raw/manifest.json          hashes and coverage of that panel, committed
data/raw/manifest_run.json      the same for your own run, excluded from git
outputs/                        the files of the vintage and measurement scripts
evidence/                       the hand-collected transaction dates, each with its source
```

`config/tickers_primary.csv`, the resolved file of one listing per company, is written by the notebook and not committed, since it is an output.

## Reproducing it

Open the notebook with the Colab badge above and choose Runtime, Run all. Add `FMP_API_KEY` and `OPENFIGI_API_KEY` to Colab's Secrets panel first, and do not paste either into a cell, because notebook outputs are committed to git. About two thirds of the pipeline runs on free data. [`EXECUTION_CHECKLIST.html`](EXECUTION_CHECKLIST.html) gives each step, what it should print and what to do when it does not.

## References

Every estimator is written in the project's own code on numpy and pandas: the Newey-West standard errors of the factor regressions in notebook 01 (`newey_west_ols`) and of the return test in script 11 and the note's build, and the rank correlations and quintile overlaps of scripts 09, 10, 13 and 15.

> Blume, M. E. and Stambaugh, R. F. (1983). "Biases in computed returns: An application to the size effect." *Journal of Financial Economics* 12(3), 387-404.
>
> Carhart, M. M. (1997). "On persistence in mutual fund performance." *Journal of Finance* 52(1), 57-82.
>
> Fama, E. F. and French, K. R. (1993). "Common risk factors in the returns on stocks and bonds." *Journal of Financial Economics* 33(1), 3-56.
>
> Fama, E. F. and French, K. R. (2015). "A five-factor asset pricing model." *Journal of Financial Economics* 116(1), 1-22.
>
> Newey, W. K. and West, K. D. (1987). "A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix." *Econometrica* 55(3), 703-708.
>
> Shumway, T. (1997). "The delisting bias in CRSP data." *Journal of Finance* 52(1), 327-340.
>
> Shumway, T. and Warther, V. A. (1999). "The delisting bias in CRSP's Nasdaq data and its implications for the size effect." *Journal of Finance* 54(6), 2361-2379.

Data sources: [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
[Global Energy Monitor](https://globalenergymonitor.org/),
[GLEIF](https://www.gleif.org/en/lei-data/gleif-golden-copy),
[OpenFIGI](https://www.openfigi.com/api),
[Financial Modeling Prep](https://site.financialmodelingprep.com/).

## Other projects

**Optimal versus naive diversification.** Under a long-only index-tracking mandate on French's 49 industries, 1979 to 2026, each of five covariance estimators forecasts less tracking error than its portfolio realises: the realised active return is 22 to 61 per cent more volatile than forecast. The replication of DeMiguel, Garlappi and Uppal (2009) reproduces 29 of the 30 out-of-sample Sharpe ratios it tests within 0.03 of the published values, 26 of 27 with the value-weighted market counted once. [Page](https://www.carlohofer.com/projects/optimal-vs-naive-diversification/), [dashboard](https://www.carlohofer.com/optimal-vs-naive-diversification/dashboard/B-P_dashboard.html), [note](https://www.carlohofer.com/optimal-vs-naive-diversification/note/B-P_note_2026-10.pdf), [code](https://github.com/ochofer/optimal-vs-naive-diversification)

**Volatility-managed portfolios: a replication, the real-time critique, and the months after the sample.** Volatility estimation and position sizing on Ken French's equity factors, replicating Moreira and Muir (2017) and the real-time critique of Cederburg, O'Doherty, Wang and Yan (2020). Scaled by the inverse of last month's realised variance, a factor's Sharpe ratio is higher than the original's by a margin that is statistically significant at the 5 per cent level for momentum alone when each of the six factors is tested on its own, and for no factor after Holm's correction for the six tests. In the 136 months after Moreira and Muir's sample no factor's difference is statistically significant, and for the six volatility-managed factors the intervals are too wide to rule out the differences found on their sample. [Page](https://www.carlohofer.com/projects/volatility-managed-portfolios/), [dashboard](https://www.carlohofer.com/volatility-managed-portfolios/dashboard/B-Q_dashboard.html), [note](https://www.carlohofer.com/volatility-managed-portfolios/note/B-Q_note_2026-11.pdf), [code](https://github.com/ochofer/volatility-managed-portfolios)

**Stock-level index tracking: a point-in-time benchmark, a long-only mandate, and its performance attribution by sector.** Rebuilds the S&P 500 month by month from CRSP's list of members, at a tracking error of 11.5 basis points a year from 1926 to 2024 against CRSP's own return of the same list, and runs a long-only index-tracking mandate on it from 1999 to 2024, with its active return attributed by sector. The portfolios realise 78.9 to 83.6 basis points a year of tracking error, and each of four covariance estimators forecasts less: the realised active return is 48 to 85 per cent more volatile than forecast. Index changes require 11.4 per cent of the turnover of the portfolio built with Ledoit-Wolf shrinkage. [Page](https://www.carlohofer.com/projects/stock-level-tracking/), [dashboard](https://www.carlohofer.com/stock-level-tracking/dashboard/), [note](https://www.carlohofer.com/stock-level-tracking/note/stock-level-tracking_note_2026-11.pdf), [code](https://github.com/ochofer/stock-level-tracking)

**Return prediction: machine learning on the S&P 500's members, corrected for overfitting.** Forecasts of each S&P 500 member's return over the next month from twelve characteristics built from CRSP and Compustat, by six models from least squares to a neural network, out of sample from 2006 to 2024. The study follows the method of Gu, Kelly and Xiu (2020), reduced to the index's members, and corrects the best result for overfitting, that is, for having tried many versions and kept the best one. In build: its findings are stated when the study is complete. [Page](https://www.carlohofer.com/projects/ml-return-prediction-backtest-overfitting/), [code](https://github.com/ochofer/ml-return-prediction-backtest-overfitting)

**Rules-based portfolio.** Runs a real-money portfolio under rules published before the first order, with every later change dated in the repository: two UCITS ETFs at 70/30, a monthly cycle with pre-trade checks, look-through exposure and ex-ante risk on a public dashboard. [Page](https://www.carlohofer.com/projects/rules-based-portfolio/), [dashboard](https://www.carlohofer.com/rules-based-portfolio/), [guide](https://www.carlohofer.com/rules-based-portfolio/guide/guide.pdf), [code](https://github.com/ochofer/rules-based-portfolio)

---

Carlo Hofer. Questions and corrections are welcome through the issue tracker.
