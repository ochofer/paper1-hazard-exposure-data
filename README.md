# A data layer, built and audited, for a physical climate risk study

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ochofer/paper1-hazard-exposure-data/blob/main/notebooks/01_raw_panels.ipynb)

Companies own physical assets, among them power stations, pipelines, mines and cement
works, and those assets sit in particular places whose weather varies. The question that
started this project is whether investors price the risk that weather damages those assets
or interrupts what they produce. If they do, then companies holding more exposed assets
should earn different returns from companies holding less exposed ones, once everything
else known to move share prices is controlled for.

**This repository is the data layer, and only the data layer.** It builds and audits the
data, and it has never tested that hypothesis; the section below sets out why the two are
kept apart.

Two return tests are distinguished here. A cross-sectional Fama-MacBeth design was
specified and then set aside before it ran, on a power calculation published in this
repository. A separate quintile-spread comparison was pre-registered and run, and its
result, together with the minimum detectable effect that makes that result readable, is
reported in the data-quality note.

That note is published as *What a vintage difference measures*, a hand verification of
ownership changes in a public asset-level database. It is the tagged release
`note-v1.2`, at
https://github.com/ochofer/paper1-hazard-exposure-data/releases/tag/note-v1.2, and
every figure in it resolves to a named output file under `outputs/`.

---

## What is here

The study needs three ingredients, and they do not naturally connect to one another.

| Ingredient | What it gives me | Source | Cost |
|---|---|---|---|
| Asset ownership | Which company owns which power station, mine or pipeline | Global Energy Monitor | Free, registration |
| Share prices | What each company's shares actually did, daily | Financial Modeling Prep | Paid |
| Risk factors | The known drivers of returns, used as controls | Kenneth French Data Library | Free |

The difficulty lies in the join. The ownership data identifies companies by name and by
legal identifiers, whereas the price data is organised entirely by stock ticker, and
neither source contains the other's key. Most of the work in this repository therefore goes
into building that bridge and then attempting to prove it wrong.

**Current state of the sample:** 328 ownership entities resolve to the US and
developed-Europe listed universe, 302 of them to a tradeable listing, and all 328
together hold 5,115 tracked assets. The price panel holds
1,122,798 daily rows across 304 symbols, being those 302 companies plus two benchmarks,
on a single total-return convention, and passes 16 of 16 integrity checks.

### Three counts, and why they differ

Three company counts appear in this project. Because they measure different things and are
not nested, a reader who meets them in isolation will read one for another.

| Count | What it is |
|---|---|
| 372 | Listed US and developed-Europe companies holding at least one tracked asset of **any** status. 200 of them hold five or more |
| 328 | The same audit, keeping only assets that are **operating**, rather than announced, permitted or cancelled. 175 of them hold five or more |
| 302 | The subset of those 328 that resolves to a tradeable listing. This is the price panel |

The step from 372 to 328 is the operating-asset filter and nothing else. The step from 328
to 302 is identifier coverage, that is, whether a company's shares can be found, and not
whether it owns anything.

Both filters are switches at the top of
[`code/00_coverage_and_crosswalk.py`](code/00_coverage_and_crosswalk.py), so a reader can
rerun the audit either way and watch the counts move rather than take the figures on trust.

The hazard measurement itself is not built and not scheduled, and it is not in this
repository.

## Terms

One term for each idea, used the same way in the code, the notebook, the outputs and the
note.

- **release**: one dated file published by Global Energy Monitor, identified by its filename
  and SHA-256. The two August 2026 files are **V1** and **V2**, and *version* is used only
  for them.
- **vintage**: the data as they stood in one release. A **vintage difference** is the change
  between two releases of the same tracker, and it is the object this repository measures.
- **pinned release**: the release a script reads, named by filename and checksum in the
  script's provenance record; to *pin* is to fix it.
- **ownership entity**: an owner as recorded by Global Energy Monitor, before any matching.
  **company** is the listed company an ownership entity resolves to; the note says *firm*
  for the same thing, and both forms are used.
- **listed parent**: an ownership entity that resolves to a company in the US and
  developed-Europe listed universe; there are 328.
- **priceable**: a listed parent whose shares resolve to a tradeable listing in the price
  panel; there are 302.
- **tracked asset**: an operating unit in the ownership data, counted once; the 328 hold
  5,115. Global Energy Monitor's own words *unit* and *plant* appear where its fields are
  named.
- **build-out, restatement, methodology change**: the three causes into which a vintage
  difference is decomposed. *Revision* is not a fourth category and keeps its ordinary
  sense.
- **exposure**: attributable capacity, the share of a tracked asset's capacity assigned to a
  company through its ownership stake and summed over its assets; **attributable** is the
  adjective.
- **convention**: a stated rule for an ambiguous case, such as the blank-share convention,
  applied the same way in every script and reported with its alternative beside it.
- **provenance record**: the `RUN_PROVENANCE_*.json` file a script writes at run time,
  naming every input it opened with its checksum.
- **figure register**: the table that ties every number in the note to the output file
  carrying it; shipping **gate** 5 is the requirement that it be complete.
- **price panel**: the daily total-return series for the priceable companies plus two
  benchmarks, pulled from Financial Modeling Prep on 21 August 2026 and not redistributed.
- **crosswalk**: the table that joins ownership entities to security identifiers and
  tickers, with every hand correction recorded in `config/ticker_overrides.csv`.

## Why the data layer is a separate thing

A data layer that can only be checked by looking at the final result is one that cannot
really be checked, because the incentive to go back and question the download depends on
how the answer looks: an interesting result invites no second look, while a boring one
does. That asymmetry is plausibly how bad data survives.

The raw layer is therefore audited on its own, before anything depends on the answer. The
two **blocking tests** in the notebook take the same idea further, in that each attempts to
prove the pipeline broken before the pipeline is used; the term is borrowed from software,
where a blocking bug is one that stops release.

A second benefit followed that was not planned for. The research design changed in August
2026 and was then stood down altogether, and nothing in this repository needed to change
either time, which indicates that the data layer is design-agnostic in practice and not
only in intention. A data layer that survives its own study being abandoned is a stronger
demonstration of the separation than one that survives a change of method.

## Where to start reading

| If you want | Read |
|---|---|
| The reasoning, with the code | [`notebooks/01_raw_panels.ipynb`](notebooks/01_raw_panels.ipynb) |
| What I found, with numbers | [`FINDINGS_2026-08-21.md`](FINDINGS_2026-08-21.md) |
| To run it yourself | [`EXECUTION_CHECKLIST.html`](EXECUTION_CHECKLIST.html) |

The notebook is written for a reader who has not seen the project and may be new to either
quantitative finance or Python, so a quantitative researcher will find it slower in places
than it needs to be. That is a deliberate trade against the alternative.

Sections 5 and 6 are the ones a sceptical reader should take first. Section 6 in particular
takes the finished price panel and attempts to prove it broken, and that argument stands
whether or not the rest of the repository is trusted.

---

## Two commitments made before any result exists

Both commitments were written down before there was a hazard variable to test, so that
neither can be quietly relaxed once results start appearing. Recording them in a public
repository is what makes the constraint binding.

### 1. Survivorship bias

The list of companies comes from an ownership dataset published in 2026, so every company
in it still existed in 2026. A company that owned power stations in 2010 and was then taken
over or wound up is therefore absent, and it is absent because of what happened to it.

If companies with exposed assets failed more often, the sample would systematically drop
the worst outcomes among exactly the group under study, which is a mechanism that
manufactures the result the design is looking for. A bias of that kind needs measuring
rather than mentioning.

**What I committed to:**

- **Point-in-time universe construction.** Whether a company belongs in the universe at
  date *t* must be decided using only information available at *t*.
- **Delisting returns must be included.** A company that goes to zero contributes its
  final return rather than disappearing. Dropping the last observation turns bankruptcies
  into non-events and biases mean returns upward, which is the direction that would
  flatter my hypothesis.
- **Measure the size of the problem before assuming it is small**, with thresholds fixed
  before the number appears.

**What I found.** Section 5 of the notebook runs that measurement, and it returns two
results, the second of which was not the one expected.

First, the price provider **cannot** measure delisting over this sample window. Its records
show seven delistings in 2010 and 2,353 in 2025, a thirty-fold rise, and delisting rates do
not behave like that, so the series is better read as coverage than as history. The
resulting rate was accordingly discarded rather than quoted with a caveat.

Second, splitting delisted companies by how heavily they traded, the smallest underperform
badly before delisting while the largest **outperform**. That pattern is consistent with
the usual account, in which small companies delist because they fail while companies of the
size studied here mostly delist because they are acquired, which is announced at a premium.
If it holds, then excluding delisted companies biases returns downward rather than upward,
which is the opposite of the direction that would flatter the hypothesis.

**The honest statement is that survivorship bias is unmeasured at the company sizes that
matter here.** Ten observations fall in the relevant band, which gives a direction and not
a magnitude, and the question cannot be settled from this provider's records, since those
records do not measure delisting over the window. CRSP's delisting file would settle it.
Access to CRSP through WRDS was granted by Queen Mary's School of Economics and Finance on
15 September 2026, after this repository was closed; nothing in it depends on that access,
and the delisting question stays open for a later study.

### 2. Transaction costs

Nothing in this repository nets transaction costs, and the omission is deliberate. The
panels are gross, because costs belong at the portfolio layer, where they are applied once,
visibly, and to turnover rather than to holdings.

**What I have committed to, for when a portfolio layer exists.** There is no portfolio
layer yet, so what follows is a set of rules written in advance rather than a description of
something already done.

- **Gross and net will be reported together**, in the same table. A net figure alone hides
  the cost assumption. A gross figure alone is not a claim about anything achievable.
- **Costs will apply to turnover**, computed from realised portfolio weights, so
  drift-driven rebalancing is charged for and not only deliberate signal changes.
- **The cost assumption is fixed in advance** and will be varied only as a stated
  sensitivity across a range, rather than tuned to a preferred number. A flat one-way cost
  is defensible for a universe of large utilities, energy and materials companies. It
  would not be for small caps.
- **The break-even cost will be the headline.** Rather than defending one cost figure, I
  will report the one-way cost at which the excess return reaches zero. That number is
  assumption-free and lets a reader apply their own beliefs. If break-even sits below
  plausible real costs, that is the finding.

Three complications specific to this universe are recorded now rather than discovered late.
The European leg incurs currency conversion costs that the US leg does not; `^GSPC` is an
index and cannot be traded, which is why `SPY` is downloaded alongside it; and partnership
structures carry tax treatment that makes net-of-cost comparison with ordinary companies
non-trivial.

---

## Data notes that cause silent errors

Each of the following produces a plausible-looking number rather than an error, and it is
that property, rather than their difficulty, that makes them worth writing down.

- **The French factors are in percent, not decimals.** `Mkt-RF = 0.55` means 0.55%. I
  store them as published, so the division by 100 belongs downstream.
- **`-99.99` and `-999` are missing-value codes**, converted to `NaN` when parsed.
- **UK prices are quoted in pence, not pounds**, labelled `GBp` with a lower-case p. A
  factor-of-100 error waiting to happen in anything weighted by price or market value.
- **No currency conversion is applied.** The panel holds nine currencies.
- **Panel A is the US factor set.** The European companies need French's Developed Europe
  factors. Mixing them is the wrong model rather than a currency nuisance.
- **A price index has no total-return version.** `^GSPC` will always fall back to price
  return, which is why the integrity checks scope the convention test to companies and
  test benchmarks separately.

## What this repository does not contain, and why

**The price panel.** Financial Modeling Prep's terms require a separate licensing
agreement to redistribute their data, so `data/raw/` is excluded from version control and
the panel itself lives outside this repository.

What is published instead is the fetch code, the resolved company list, the hand
corrections with a written reason for each, and
[`data/raw/manifest.json`](data/raw/manifest.json), which carries SHA-256 checksums, byte
sizes and row counts for every file the findings were computed on, together with per-symbol
date coverage for all 304 symbols in the price panel. A reader with their own FMP access
can therefore establish that their panel matches this one rather than assuming it.

The manifest describes one person's pull, and that person is Carlo Hofer, at this
repository. A checksum record with no owner cannot be challenged by anyone, since there is
nobody to ask what was pulled or when; `build_manifest.py` writes an `owner` field for that
reason, and the manifest committed here predates the field and will carry it the next time
it is regenerated.

Running the notebook writes the same kind of record for the reader's own pull, as
`data/raw/manifest_run.json`. It is gitignored and deliberately carries a different name, so
that a run cannot overwrite the published record. Comparing the two is what the record is
for: matching checksums establish that the same bytes are held, and where they differ, the
per-symbol coverage identifies which symbols diverge.

**What the price series actually is.** Every return in this project is computed from a
single field, `adjClose`, taken from Financial Modeling Prep's
`historical-price-eod/dividend-adjusted` endpoint and pulled on 21 August 2026. **The
adjustment is the vendor's, not mine.** It is back-adjusted for splits as well as
dividends: NextEra's four-for-one split of 26 October 2020 shows no discontinuity in the
series, and 2010 levels sit well below the nominal closes of the time, for example Exxon
at 37.14 on 4 January 2010 against a nominal close near 69. **No unadjusted close is
stored beside it in the archive**, so the adjustment cannot be undone or independently
checked from what this repository describes.

That property matters more than it first appears, and it runs in the same direction as the
rest of this work. A vendor's adjusted price history is itself a restated, vintage-dependent
object, since every historical adjusted price moves whenever a new dividend or split is
applied. It follows that the panel pulled on 21 August 2026 is a snapshot of FMP's
back-adjustment as it stood that day, and could not be reproduced later even with a live
subscription. That conclusion supports the manifest rather than undermining it, and it is
the reason the claim below is worded as it is.

**The claim is that this pull is auditable, not that it is repeatable.** Rebuilding the
price layer requires a paid FMP subscription, whereas every other input here is free and
redistributable. The manifest also records what it lacks: the pull of 21 August 2026 did not
capture per-file fetch timestamps, and these have not been back-filled from filesystem
timestamps, since those change whenever a file is copied and would therefore be fiction.

**The outputs and the evidence.** `outputs/` carries every file the vintage and measurement
scripts produce, and `evidence/` carries the hand-collected input behind the recording-lag
table: transaction dates read from exchange filings, company statements and EDINET, with a
source for each. Two files are withheld, `vintage_return_spread.csv` and
`vintage_return_spread.txt`, because they are computed from the licensed price series;
they are named in the note's figure register with their checksums, and rerunning
`code/11_vintage_return_spread.py` against your own pull reproduces them. Everything else
is here in full, which is 53 of the 55 files.

One known gap is recorded here rather than left silent. `outputs/isin_screen.csv` joins the
ownership entities to GLEIF identifiers and ISIN counts, and it is the file the 328 companies
come from. Both of its inputs are free and openly licensed, but no script in `code/` produces
it and it carries no provenance record, because it was built by hand. It is published as it
stands, and closing that gap is a task for the paper rather than for this repository.
Everything else in `outputs/` resolves to a numbered script with a provenance record naming
the release and its checksum.

Every output is sorted before it is written, so that rerunning a script against the pinned
release reproduces its checksum exactly. Files carrying a `_SUPERSEDED_` marker are earlier
copies of two outputs whose row order varied between runs before that rule was enforced, and
they are kept rather than deleted; `outputs/PROMOTION_2026-09-08.txt` records the checksums
on both sides and shows the row count and header unchanged. No value moved.

**The hazard exposure variable.** This is not built and not started. The ownership dataset
carries no asset coordinates, so building it would require the separate sector datasets
together with a hazard dataset, none of which needs a subscription. There are no exposure
results anywhere in this repository, because there is no exposure variable yet.

## Layout

```
notebooks/01_raw_panels.ipynb   the analysis, with the reasoning
build_notebook.py               generates the notebook, keeps it diffable in git
build_manifest.py               generates data/raw/manifest.json from my local pull
code/                           two upstream scripts, blocking test 3 and the identifier audit
EXECUTION_CHECKLIST.html        how to reproduce it, and what each step should print
FINDINGS_2026-08-21.md          results of the three blocking tests, with numbers
config/universe.csv             the 328 ownership entities
config/universe_isins.csv       their security identifiers, from GLEIF
config/ticker_overrides.csv     hand corrections to the crosswalk, each with a reason
config/tickers_draft_v0.csv     a 20-name sample kept only for testing the data path
data/raw/                       the downloaded panel. Gitignored, licensed, not here
data/raw/manifest.json          checksums and coverage for that panel. Committed
data/raw/manifest_run.json      the same for your own run. Gitignored, compare it to mine
```

`config/tickers_primary.csv`, the resolved one-listing-per-company file, is generated by the
notebook rather than committed, since it is an output rather than an input.

## Reproducing it

Open the notebook with the Colab badge above and choose Runtime, Run all. Add `FMP_API_KEY`
and `OPENFIGI_API_KEY` to Colab's Secrets panel first, and do not paste either into a cell,
because notebook outputs are committed to git.

Roughly two thirds of the pipeline runs on free data. Full details, including what each step
should print and what to do when it does not, are in
[`EXECUTION_CHECKLIST.html`](EXECUTION_CHECKLIST.html).

## References

The methods used here are standard, and the published implementations have been used rather
than substitutes written for this project.

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

Data sources: [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
[Global Energy Monitor](https://globalenergymonitor.org/),
[GLEIF](https://www.gleif.org/en/lei-data/gleif-golden-copy),
[OpenFIGI](https://www.openfigi.com/api),
[Financial Modeling Prep](https://site.financialmodelingprep.com/).

---

Carlo Hofer. Questions and corrections are welcome through the issue tracker.
