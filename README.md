# Does physical climate risk show up in share prices?

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ochofer/paper1-hazard-exposure-data/blob/main/notebooks/01_raw_panels.ipynb)

Companies own physical things. Power stations, pipelines, mines, cement works. Those
things sit in places, and places have weather.

I am testing whether investors price the risk that weather damages those assets or
interrupts what they produce. If they do, companies with more exposed assets should earn
different returns from companies with less exposed ones, once I have controlled for
everything else known to move share prices.

**This repository is the data layer for that study.** It builds and audits the data. It
does not test the hypothesis, and I explain below why I keep those two things apart.

---

## What is here

I need three ingredients, and they do not naturally connect to one another.

| Ingredient | What it gives me | Source | Cost |
|---|---|---|---|
| Asset ownership | Which company owns which power station, mine or pipeline | Global Energy Monitor | Free, registration |
| Share prices | What each company's shares actually did, daily | Financial Modeling Prep | Paid |
| Risk factors | The known drivers of returns, used as controls | Kenneth French Data Library | Free |

The awkward part is the join. The ownership data identifies companies by name and by
legal identifiers. The price data is organised entirely by stock ticker. Neither contains
the other, so most of the work in this repository is building that bridge and then trying
to prove it wrong.

**Current state of the sample:** 302 of 328 ownership entities resolve to a tradeable
listing, covering 4,900 of 5,115 tracked assets, or 95.8%. The price panel holds
1,122,798 daily rows across 305 symbols, on a single total-return convention, and passes
16 of 16 integrity checks.

The hazard measurement itself is separate work and is not in this repository.

## Why the data layer is a separate thing

A data layer I can only check by looking at the final result is one I cannot really
check. If the answer looks interesting I will not go back and question the download; if
it looks boring I will. That asymmetry is how bad data survives.

So I audit the raw layer on its own, before anything depends on the answer. The two
**blocking tests** in the notebook take the same idea further: in each I try to prove my
own pipeline is broken, before I use it. I borrowed the term from software, where a
blocking bug is one that stops release.

There is a second benefit I did not plan. The data layer turned out to be
design-agnostic. When the research design changed in August 2026, from a cross-sectional
test to an event study, nothing in this repository needed to change.

## Where to start reading

| If you want | Read |
|---|---|
| The reasoning, with the code | [`notebooks/01_raw_panels.ipynb`](notebooks/01_raw_panels.ipynb) |
| What I found, with numbers | [`FINDINGS_2026-08-21.md`](FINDINGS_2026-08-21.md) |
| To run it yourself | [`EXECUTION_CHECKLIST.html`](EXECUTION_CHECKLIST.html) |

The notebook is written for someone who has not seen the project and may be new to either
quantitative finance or Python. If you are a quantitative researcher it will occasionally
be slower than you need, and I would rather that than the alternative.

Sections 5 and 6 are the ones I would point a sceptical reader at first. Section 6 in
particular takes the finished price panel and tries to prove it is broken, and that
argument stands whether or not you trust anything else here.

---

## Two commitments made before any result exists

I wrote both of these down before I had a hazard variable to test, so that I cannot
quietly relax them once results start appearing. That is the entire point of writing them
in a public repository.

### 1. Survivorship bias

My list of companies comes from an ownership dataset published in 2026, so every company
in it still existed in 2026. A company that owned power stations in 2010 and was then
taken over or wound up is absent, and it is absent because of what happened to it.

If companies with exposed assets failed more often, my sample would systematically drop
the worst outcomes among exactly the group I am studying. That mechanism manufactures the
result I am looking for, so it needs measuring rather than mentioning.

**What I committed to:**

- **Point-in-time universe construction.** Whether a company belongs in the universe at
  date *t* must be decided using only information available at *t*.
- **Delisting returns must be included.** A company that goes to zero contributes its
  final return rather than disappearing. Dropping the last observation turns bankruptcies
  into non-events and biases mean returns upward, which is the direction that would
  flatter my hypothesis.
- **Measure the size of the problem before assuming it is small**, with thresholds fixed
  before the number appears.

**What I found.** Section 5 of the notebook runs that measurement. Two results, and the
second surprised me.

The price provider **cannot** measure delisting over my sample window. Its records show
seven delistings in 2010 and 2,353 in 2025, a thirty-fold rise. Delisting rates do not
behave like that, so I read this as coverage rather than history, and I discarded the
resulting rate rather than quoting it with a caveat.

Splitting delisted companies by how heavily they traded, the smallest underperform badly
before delisting while the largest **outperform**. That fits: small companies delist
because they fail, and companies the size of mine mostly delist because they are
acquired, which is announced at a premium. If that holds, excluding delisted companies
biases my returns downward rather than upward.

**The honest statement is that survivorship bias is unmeasured at the company sizes that
matter here.** I have ten observations in the relevant band, which is a direction and not
a magnitude. CRSP's delisting file would settle it and I have applied for access.

### 2. Transaction costs

Nothing in this repository nets transaction costs, deliberately. The panels are gross.
Costs belong at the portfolio layer, applied once, visibly, and to turnover rather than
to holdings.

- **I report gross and net together**, in the same table. A net figure alone hides the
  cost assumption. A gross figure alone is not a claim about anything achievable.
- **Costs apply to turnover**, computed from realised portfolio weights, so drift-driven
  rebalancing is charged for and not only deliberate signal changes.
- **The cost assumption is fixed in advance** and varied only as a stated sensitivity
  across a range, rather than tuned to a preferred number. A flat one-way cost is
  defensible for a universe of large utilities, energy and materials companies. It would
  not be for small caps.
- **The break-even cost is the honest headline.** Rather than defending one cost figure,
  I report the one-way cost at which the excess return reaches zero. That number is
  assumption-free and lets a reader apply their own beliefs. If break-even sits below
  plausible real costs, that is the finding.

Complications specific to this universe, recorded now so I do not discover them late: the
European leg incurs currency conversion costs the US leg does not; `^GSPC` is an index and
cannot be traded, which is why I also download `SPY`; and partnership structures have tax
treatment that makes net-of-cost comparison with ordinary companies non-trivial.

---

## Data notes that cause silent errors

Each of these produces a plausible-looking number rather than an error, which is what
makes them worth writing down.

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
agreement to redistribute their data, so `data/raw/` is excluded from version control.

What I publish instead is everything needed to rebuild it: the fetch code, the resolved
company list, the hand corrections with a written reason for each, and a manifest of
SHA-256 checksums so anyone with their own access can prove their panel matches mine
rather than assuming it.

**The hazard exposure variable.** Not built yet. The ownership dataset carries no asset
coordinates, so it needs the separate sector datasets plus a hazard dataset. None of that
requires a subscription.

## Layout

```
notebooks/01_raw_panels.ipynb   the analysis, with the reasoning
build_notebook.py               generates the notebook, keeps it diffable in git
EXECUTION_CHECKLIST.html        how to reproduce it, and what each step should print
FINDINGS_2026-08-21.md          results of the three blocking tests, with numbers
config/universe.csv             the 328 ownership entities
config/universe_isins.csv       their security identifiers, from GLEIF
config/ticker_overrides.csv     hand corrections to the crosswalk, each with a reason
config/tickers_draft_v0.csv     a 20-name sample kept only for testing the data path
data/raw/                       downloads and manifest.json, gitignored
```

`config/tickers_primary.csv`, the resolved one-listing-per-company file, is generated by
the notebook rather than committed, because it is an output rather than an input.

## Reproducing it

Open the notebook with the Colab badge above and choose Runtime, Run all. Add
`FMP_API_KEY` and `OPENFIGI_API_KEY` to Colab's Secrets panel first, and do not paste
either into a cell, because notebook outputs are committed to git.

Roughly two thirds of this runs on free data. Full details, including what each step
should print and what to do when it does not, are in
[`EXECUTION_CHECKLIST.html`](EXECUTION_CHECKLIST.html).

## References

The methods here are standard and I have used the published implementations rather than
writing my own.

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
