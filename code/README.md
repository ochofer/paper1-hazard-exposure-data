# Scripts

Everything that runs outside the notebook. The ownership data is free and openly licensed,
and the price series is licensed and withheld, as the last section says. The fourteen past
releases of the ownership tracker that scripts 04, 06 to 09, 12 to 15, 17 and 25 read were
supplied by the vendor on request and are neither on the vendor's site nor in this
repository, so those scripts cannot be rerun from what is published; scripts 05, 10, 16 and
18 read committed files alone and can, and so does `check_provenance.py`.

The first two build the company universe. The numbered scripts from `04` onward are the
vintage and measurement work behind the note on what a vintage difference measures.

| Script | What it does | Inputs |
|---|---|---|
| `00_coverage_and_crosswalk.py` | Builds my company universe from the ownership data and counts survivors at every filtering step. This is blocking test 3, and it is where the 328 ownership entities come from | Global Energy Monitor ownership tracker, CC BY 4.0 |
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

I wrote each as a switch at the top of the file, where a reader can find it. A research
design decision nobody can find is a research design decision nobody can argue with, and the
whole point of publishing this is that someone can argue with it.

The most instructive one is `OPERATING_ONLY`. Set it to `False` and the universe goes from
328 ownership entities to 372. That single line accounts for the whole difference between
the two counts, which is the fastest way to see what a filtering choice costs.

## The vintage and measurement scripts, `04` onward

They run in numerical order and each reads the outputs of the ones before it. `_release.py`
holds the release pin: the exact filenames of the GEM releases used, resolved by an explicit
name, so that a script stops when the named file is missing and never reads another file in
its place. Two files I hold carry August 2026, one of them sent to me on 26 August 2026, and
nothing inside either marks it as a version, which is why the pin exists. `_overlap.py`,
added 20 November 2026, gives a top-quintile overlap as the lowest and the highest count
that the firms tied at each cut allow, with the tie counts, so that scripts 10, 13 and 15
print one figure only where no tie leaves the top set open; `tests/test_overlap.py` checks
the two bounds against every order on made-up cases (`python3 -m pytest tests` from the
repository root, or `python3 code/_overlap.py` for the same check without a test runner).

| Script | What it does |
|---|---|
| `04_vintage_diff.py` | Differences two releases at the entity and asset level |
| `05_power_comparison.py` | Closed-form power calculation. Reads no dataset |
| `06_change_decomposition.py` | Sorts every apparent change into build-out, restatement or methodology. This is where R comes from |
| `07_decay_curves.py` | Whether the build-out share falls as the database matures |
| `08_event_validation_sample.py` | Draws the random sample of apparent changes to check by hand |
| `09_exposure_proxy.py` | Attributes coal and gas capacity to the nearest listed parent, under both blank-share conventions |
| `10_panel_join.py` | Joins the measure to the company cross-section |
| `11_vintage_return_spread.py` | The return test, whose rule is set in its header. **Reads the licensed price series** |
| `12_decimal_truncation.py` | How much of the share-value change is one-decimal rounding |
| `13_scaling_second_column.py` | The same measure scaled by fleet share |
| `14_restricted_r.py` | R with residual counterparties removed from both sides |
| `15_bioenergy_check.py` | The control on the scaling result, set in its header before the run |
| `16_figure_register.py` | Holds the figures of the note's running order against the output file that should contain each, and reports anything untraceable |
| `17_release_ladder.py` | Both August 2026 releases side by side, with V derived from the verdicts and its Wilson interval computed |
| `18_validate_salience_cases.py` | Validates the hand-collected evidence file against the verified sample and computes the recording lags |
| `25_panel_entrants.py` | For the firms that enter the panel between the two releases, splits their August 2026 capacity unit by unit by what the March 2025 file held of each unit and under which listed entity: units held under a listed entity that owns the entrant, the rest of what the file carried, units it did not carry. Added 20 November 2026; the measure by the capacity of units set after the script's first run |
| `check_provenance.py` | Compares every hash the provenance records hold with its file; `tests/test_provenance.py` runs it. Added 20 November 2026 |
| `19_build_note.py` | Builds the note, extracting every figure from an output file at build time |
| `classify_outputs.py` | Classifies every output by what its script consumed, so nothing derived from licensed data is published by accident |
| `promote_outputs.py` | The one-off promotion of 8 September 2026, recorded below |
| `publish_outputs.py` | Copies the publishable outputs into this repository |

### Two conventions these scripts hold to

**No result figure is typed by hand.** `19_build_note.py` pulls every result figure in the
note out of a named output file at build time and aborts if a pattern is missing or matches
twice; the typed labels and settings are listed in the note's Appendix D. The check
exists so that no result figure is typed where a file can give it.

**Every data output is deterministic.** Each is sorted before it is written, so a reader who
reruns a script against the pinned release gets the same bytes and therefore the same
checksum; the run logs print the output path relative to the repository, so their checksums do
not depend on where the script ran. Two of the outputs are built by iterating Python sets,
whose order differs from one process to the next because Python randomises string hashing,
so the two scripts sort their rows before writing and the bytes are the same on every run.
Those sorted files are the outputs of record; the copies beside them under a `_SUPERSEDED_`
marker hold the same rows in another order, and
[`../outputs/PROMOTION_2026-09-08.txt`](../outputs/PROMOTION_2026-09-08.txt) records the
checksums of both with the row count and header.

A checksum on a file whose bytes move between runs is not an audit record, which is the
subject of the note itself. Any output that cannot meet this rule says so in its own
provenance record.


## What is not here

**Blocking tests 1 and 2** are sections 5 and 6 of
[`../notebooks/01_raw_panels.ipynb`](../notebooks/01_raw_panels.ipynb), since both need the
price panel the notebook builds.

**The price panel and the two files derived from it.** `11_vintage_return_spread.py` reads a
licensed price series that cannot be redistributed, so `vintage_return_spread.csv` and
`vintage_return_spread.txt` are named in the note's figure register with their checksums but
do not ship here. Rerunning that script against your own pull reproduces them. Every other
output in `../outputs/` is here in full.

## First-time reader

[`../notebooks/01_raw_panels.ipynb`](../notebooks/01_raw_panels.ipynb) explains the project,
the data and the reasoning, and is the first file to read. Scripts `00` and `03` are the
parts of the pipeline that sit upstream of it.
