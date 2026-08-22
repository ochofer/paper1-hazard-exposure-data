# Scripts

Two standalone scripts that run outside the notebook. Both use only free, openly licensed
data, so anyone can rerun them.

| Script | What it does | Inputs |
|---|---|---|
| `00_coverage_and_crosswalk.py` | Builds my company universe from the ownership data and counts survivors at every filtering step. This is blocking test 3, and it is where the 328 companies come from | Global Energy Monitor ownership tracker, CC BY 4.0 |
| `03_gleif_crosscheck.py` | Audits the identifiers in that ownership data against GLEIF, to separate genuine coverage limits from wrong-entity bugs | GLEIF golden copy files, CC0 |

Run them in that order, since the second reads the output of the first.

```
python3 00_coverage_and_crosswalk.py
python3 03_gleif_crosscheck.py
```

## Why the switches at the top of `00` matter more than the code below them

Four decisions in that script change the answer materially: what counts as one asset,
whether to include assets that are not yet operating, whether to attribute an asset to
the nearest listed parent or to every listed entity in its ownership chain, and which
countries to include.

I wrote each as a switch at the top of the file rather than burying it in the logic. A
research design decision nobody can find is a research design decision nobody can argue
with, and the whole point of publishing this is that someone can argue with it.

The most instructive one is `OPERATING_ONLY`. Set it to `False` and the universe goes from
328 companies to 372. That single line accounts for the entire difference between my count
and an earlier one, which is the fastest way to see what a filtering choice actually costs.

## What is not here

**Blocking tests 1 and 2** were originally scripts in this folder. They are now sections 5
and 6 of [`../notebooks/01_raw_panels.ipynb`](../notebooks/01_raw_panels.ipynb), which is
where they belong, since both need the price panel the notebook builds. The earlier
versions never ran against live data and pointed at API paths the provider has since
retired, so I removed them rather than publish code that does not work.

**The vintage and measurement work** lives outside this repository for now. It is active
and moving, and I would rather publish it once it is finished than publish a moving target.

## First-time reader

Start with the notebook rather than these scripts. It explains the project, the data and
the reasoning. These two are the parts of the pipeline that sit upstream of it.
