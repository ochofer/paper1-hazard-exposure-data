# Scripts

Everything that runs outside the notebook. All of it uses free, openly licensed data, with
one exception noted at the end, so almost all of it can be rerun by anyone.

The first two build the company universe. The numbered scripts from `04` onward are the
vintage and measurement work behind the note on what a vintage difference measures.

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

## The vintage and measurement scripts, `04` onward

They run in numerical order and each reads the outputs of the ones before it. `_release.py`
holds the release pin: the exact filenames of the GEM releases used, resolved by an explicit
name rather than by a glob, so a script fails rather than silently picking up a different
file. Two files were published as August 2026 and nothing inside either marks it as a
version, which is why the pin exists.

| Script | What it does |
|---|---|
| `04_vintage_diff.py` | Differences two releases at the entity and asset level |
| `05_power_comparison.py` | Closed-form power calculation. Reads no dataset |
| `06_change_decomposition.py` | Sorts every apparent change into build-out, restatement or methodology. This is where R comes from |
| `07_decay_curves.py` | Whether the build-out share falls as the database matures |
| `08_event_validation_sample.py` | Draws the random sample of apparent changes to check by hand |
| `09_exposure_proxy.py` | Attributes coal and gas capacity to the nearest listed parent, under both blank-share conventions |
| `10_panel_join.py` | Joins the measure to the company cross-section |
| `11_vintage_return_spread.py` | The pre-registered return test. **Reads the licensed price series** |
| `12_decimal_truncation.py` | How much of the share-value change is one-decimal rounding |
| `13_scaling_second_column.py` | The same measure scaled by fleet share |
| `14_restricted_r.py` | R with residual counterparties removed from both sides |
| `15_bioenergy_check.py` | The pre-committed control on the scaling result |
| `16_figure_register.py` | Holds every figure the note prints against the output file that should contain it, and reports anything untraceable |
| `17_release_ladder.py` | Both August 2026 releases side by side, with V derived from the verdicts and its Wilson interval computed |
| `18_validate_salience_cases.py` | Validates the hand-collected evidence file against the verified sample and computes the recording lags |
| `19_build_note.py` | Builds the note, extracting every figure from an output file at build time |
| `classify_outputs.py` | Classifies every output by what its script consumed, so nothing derived from licensed data is published by accident |
| `promote_outputs.py` | The one-off promotion of 8 September 2026, recorded below |
| `publish_outputs.py` | Copies the publishable outputs into this repository |

### Two conventions these scripts hold to

**No figure is typed by hand.** `19_build_note.py` pulls every number in the note out of a
named output file at build time and aborts if a pattern is missing or matches twice. I wrote
that check after typing twelve entity identifiers into an evidence file from memory instead
of reading them from the source, and getting all twelve wrong.

**Every output is deterministic.** Each is sorted before it is written, so a reader who
reruns a script against the pinned release gets the same bytes and therefore the same
checksum. Two outputs did not meet that until 8 September 2026: they were built by iterating
Python sets, and Python randomises string hashing per process, so their row order varied
between runs while their content did not. Both scripts now sort before writing. The
deterministic versions are the outputs of record, the earlier copies are kept beside them
under a `_SUPERSEDED_` marker and are never deleted, and
[`../outputs/PROMOTION_2026-09-08.txt`](../outputs/PROMOTION_2026-09-08.txt) records the
checksums on both sides with the row count and header shown unchanged. No value moved and no
figure in the note changed.

A checksum on a file whose bytes move between runs is not an audit record, which is the
subject of the note itself. Any output that cannot meet this rule says so in its own
provenance record.


## What is not here

**Blocking tests 1 and 2** were originally scripts in this folder. They are now sections 5
and 6 of [`../notebooks/01_raw_panels.ipynb`](../notebooks/01_raw_panels.ipynb), which is
where they belong, since both need the price panel the notebook builds. The earlier
versions never ran against live data and pointed at API paths the provider has since
retired, so I removed them rather than publish code that does not work.

**The price panel and the two files derived from it.** `11_vintage_return_spread.py` reads a
licensed price series that cannot be redistributed, so `vintage_return_spread.csv` and
`vintage_return_spread.txt` are named in the note's figure register with their checksums but
do not ship here. Rerunning that script against your own pull reproduces them. Every other
output in `../outputs/` is here in full.

## First-time reader

Start with the notebook rather than these scripts. It explains the project, the data and
the reasoning. These two are the parts of the pipeline that sit upstream of it.
