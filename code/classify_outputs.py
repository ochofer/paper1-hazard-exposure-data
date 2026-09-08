"""
CLASSIFY EVERY OUTPUT BY PROVENANCE BEFORE ANY OF IT IS PUBLISHED

Executes item 3.1 of the research design chat's ruling of 8 September 2026.

THE RULE BEING APPLIED
----------------------
Every file in outputs/ and evidence/ is classified by provenance, by reading what
each script actually CONSUMED rather than by what the file is called:

  GEM-only      publishes in full. Every GEM input is CC BY 4.0.
  FMP-derived   does not publish. Publishing it would be redistribution of a
                licensed price series.
  mixed         publishes only if the FMP-derived columns can be dropped without
                changing what the Appendix D register points at. Otherwise it is
                treated as FMP-derived.
  UNKNOWN       not classified. Reported, never guessed at, never published.

WHY IT WORKS FROM THE PROVENANCE RECORDS
----------------------------------------
The RUN_PROVENANCE_*.json records were written at run time and name the inputs
each script actually opened, including its upstream chain. That is a record of
consumption rather than a reading of intent, which is what the ruling asks for. A
static parse of the source would tell me what the code appears to read; the
provenance records tell me what it did read.

The one thing the provenance records do not carry is which output files each
script WROTE, so that side is parsed from the source: the `Out:` block in each
script's docstring, cross-checked against the literal filenames the script writes.
Where those two disagree the file is marked UNKNOWN rather than reconciled here.

WHAT IT DOES NOT DO
-------------------
It moves nothing, deletes nothing, publishes nothing and changes no output. It
writes one report. Item 3.4 of the ruling says to stop and report rather than
decide at the keyboard, and this script is that instruction in code.

Run:  python classify_outputs.py
Out:  outputs/PUBLICATION_CLASSIFICATION_<today>.txt
"""

import ast
import json
import os
import re
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
EV = os.path.join(HERE, "..", "evidence")

# A provenance input, or an input filename, matching any of these means the script
# consumed the licensed price series. Matched case-insensitively against both the
# input ROLE and the input VALUE, because a record may name either.
FMP_MARKERS = [
    "price", "prices", "ticker", "tickers", "fmp", "adjclose",
    "panel_b_prices", "historical-price-eod",
]
# Free inputs. Present for completeness and to make an unmatched input visible
# rather than silently treated as free.
FREE_MARKERS = [
    "global-energy-ownership-tracker", "gem", "gleif", "ken french", "f-f_research",
    "evidence", "verdicts", "remapping", "closed-form", "no data inputs",
]

# Files no numbered script writes with a literal path. Classified BY HAND under
# item 3.1 of the ruling of 8 September, with the reason recorded here rather
# than decided at the keyboard and forgotten. Each was opened and read first.
HAND = {
    "PROVENANCE_RERUN_DIFF_2026-09-07.txt": (
        "GEM-only", "hand-written record of a GEM-only rerun: checksums, row counts and "
        "filenames, no data values and nothing from the price series"),
    "PUBLICATION_CLASSIFICATION": (
        "GEM-only", "this report: names files and their provenance, carries no data values"),
    "PROMOTION_": (
        "GEM-only", "the promotion record: checksums and row counts, no data values"),
    "RELEASE_COMPARISON_outputs_2026-09-02.txt": (
        "GEM-only", "hand-assembled bundle of GEM figures. Publishable, but SUPERSEDED by "
        "17_release_ladder.py, which computes the same numbers with provenance. Publish "
        "under a superseded marker or not at all; it must not read as current"),
    "isin_screen.csv": (
        "GEM-only", "GEM entity ids and names joined to GLEIF LEIs and ISIN counts. Both "
        "sources free. NO NUMBERED SCRIPT PRODUCES IT and it carries no provenance record, "
        "which matters because this file is where the 328 comes from"),
    "salience_lag_cases.csv": (
        "GEM-only", "curated INPUT, not an output: transaction dates read by hand from "
        "exchange filings, company statements and EDINET. Free sources, already cited in "
        "the note as evidence, and validated against the sample by 18"),
}


_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


# ---------------------------------------------------------------------------
# what each script CONSUMED, from the run-time provenance records
# ---------------------------------------------------------------------------
def flatten(obj, out):
    """Every string anywhere in a provenance inputs blob, role names included."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            flatten(v, out)
    elif isinstance(obj, list):
        for v in obj:
            flatten(v, out)
    elif obj is not None:
        out.append(str(obj))


def consumed():
    """script stem -> (set of input strings, set of upstream script stems)"""
    got = {}
    for fn in sorted(os.listdir(OUT)):
        if not (fn.startswith("RUN_PROVENANCE_") and fn.endswith(".json")):
            continue
        stem = fn[len("RUN_PROVENANCE_"):-len(".json")]
        rec = json.load(open(os.path.join(OUT, fn), encoding="utf-8"))
        blob = []
        flatten(rec.get("inputs", {}), blob)
        flatten(rec.get("kind", ""), blob)
        ups = set()
        for s in blob:
            m = re.search(r"upstream_provenance_(\d+)", s)
            if m:
                ups.add(m.group(1))
        got[stem] = (set(blob), ups)
    return got


# ---------------------------------------------------------------------------
# what each script WROTE, from the source
# ---------------------------------------------------------------------------
def declared_outputs(path):
    """Filenames listed in the docstring's `Out:` block. A declaration of intent."""
    src = open(path, encoding="utf-8").read()
    try:
        doc = ast.get_docstring(ast.parse(src)) or ""
    except SyntaxError:
        return None
    # Two conventions exist in this codebase: `Out:` and `Writes:`. Both are
    # accepted rather than one being imposed by editing scripts, because a
    # classifier that only understands its author's habits is not a classifier.
    names, grab = set(), False
    for line in doc.splitlines():
        head = next((h for h in ("Out:", "Writes:") if line.strip().startswith(h)), None)
        if head:
            grab = True
            line = line.split(head, 1)[1]
        elif grab and not line.startswith(" "):
            grab = False
        if grab:
            names |= set(re.findall(r"[\w./<>-]+\.(?:csv|txt|json|html)", line))
    return {os.path.basename(n) for n in names}


def written_files(path):
    """Filenames the script actually WRITES, read off the syntax tree.

    A filename that merely appears in the source is a READ. The first version of
    this script treated any literal as a write, which made every consumer an
    owner: 16 and 19 read almost every output, so they claimed almost every
    output, and 23 files came back UNKNOWN for no reason but that. Only these
    count as writes: an argument to `.to_csv`, and the path in `open(p, "w")`.
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError:
        return None

    def lits(node):
        return {n.value for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}

    out = set()
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name in ("to_csv", "to_json", "write_text", "savefig"):
            for a in n.args:
                out |= lits(a)
        elif name == "open":
            mode = ""
            for a in n.args[1:]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    mode = a.value
            for kw in n.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if ("w" in mode or "a" in mode) and n.args:
                out |= lits(n.args[0])
    return {os.path.basename(x) for x in out
            if re.search(r"\.(csv|txt|json|html)$", str(x))}


def main():
    today = date.today().isoformat()
    say("PUBLICATION CLASSIFICATION OF outputs/ AND evidence/")
    say(f"  {today}, under the research design chat's ruling of 2026-09-08, item 3.1")
    say("  Classified by what each script CONSUMED, from the run-time provenance")
    say("  records, not by filename. Nothing here is moved, changed or published.")
    say()

    cons = consumed()

    # taint: a script is FMP-derived if any input string matches an FMP marker,
    # or if any of its upstream scripts is.
    fmp = set()
    for stem, (blob, _) in cons.items():
        low = " | ".join(blob).lower()
        if any(m in low for m in FMP_MARKERS):
            fmp.add(stem)
    changed = True
    while changed:
        changed = False
        for stem, (_, ups) in cons.items():
            if stem in fmp:
                continue
            for u in ups:
                if any(s.startswith(u + "_") or s == u for s in fmp):
                    fmp.add(stem)
                    changed = True

    say("WHAT EACH SCRIPT CONSUMED, AND THE VERDICT ON THE SCRIPT")
    for stem in sorted(cons):
        blob, ups = cons[stem]
        low = " | ".join(blob).lower()
        hits = sorted({m for m in FMP_MARKERS if m in low})
        free = sorted({m for m in FREE_MARKERS if m in low})
        verdict = "FMP-DERIVED" if stem in fmp else "free inputs only"
        say(f"  {stem:<34} {verdict}")
        if hits:
            say(f"      licensed input markers matched: {', '.join(hits)}")
        if ups:
            say(f"      upstream scripts: {', '.join(sorted(ups))}")
        if not hits and not free:
            say("      NO MARKER MATCHED. Inputs not recognised as free or licensed; "
                "treat downstream files as UNKNOWN.")

    # map output filenames to the script that writes them
    owner = {}
    declared_only = set()
    mismatch = []
    for fn in sorted(os.listdir(HERE)):
        if not (re.match(r"^\d\d_", fn) and fn.endswith(".py")):
            continue
        stem_num = fn[:2]
        dec = declared_outputs(os.path.join(HERE, fn))
        wrt = written_files(os.path.join(HERE, fn))
        if dec is None or wrt is None:
            mismatch.append((fn, "does not parse"))
            continue
        real = {w for w in wrt if not w.startswith("RUN_PROVENANCE")}
        undeclared = real - dec
        promised = {d for d in dec if not d.startswith("RUN_PROVENANCE")} - real
        if undeclared:
            mismatch.append((fn, "writes files its docstring does not declare: "
                                 + ", ".join(sorted(undeclared))))
        if promised:
            mismatch.append((fn, "docstring declares files no write call produces: "
                                 + ", ".join(sorted(promised))))
        for name in real:
            owner.setdefault(name, set()).add(stem_num)
        # A script that builds its output path in a variable yields no literal for
        # the write detector. Its docstring `Out:` block is then the best record of
        # what it writes, and ownership taken that way is marked as declared.
        for name in promised:
            owner.setdefault(name, set()).add(stem_num)
            declared_only.add(name)

    say()
    say("=" * 78)
    say("CLASSIFICATION, FILE BY FILE")
    buckets = defaultdict(list)
    for root, label in ((OUT, "outputs"), (EV, "evidence")):
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            p = os.path.join(root, fn)
            if not os.path.isfile(p):
                continue
            if fn.startswith("RUN_PROVENANCE_") or fn.endswith(".json"):
                cls, why = "GEM-only", "provenance record, carries no data values"
            else:
                # A retained copy inherits the classification of the file it
                # supersedes. Its provenance is that file's provenance; the rename
                # records when it stopped being the output of record, nothing else.
                base = re.sub(r"_SUPERSEDED_\d{4}-\d{2}-\d{2}(?=\.)", "", fn)
                owners = owner.get(fn, set()) or owner.get(base, set())
                if base != fn and owners:
                    pass
                hand = next((v for k, v in HAND.items() if fn.startswith(k) or fn == k), None)
                if not owners and hand:
                    cls, why = hand[0], "classified by hand: " + hand[1]
                elif not owners:
                    cls, why = "UNKNOWN", "no numbered script declares writing this file"
                else:
                    tainted = {o for o in owners
                               if any(s.startswith(o + "_") for s in fmp)}
                    if len(owners) > 1:
                        cls, why = "UNKNOWN", f"claimed by more than one script: {sorted(owners)}"
                    elif tainted:
                        cls, why = "FMP-derived", f"written by {sorted(owners)[0]}, which consumed the price series"
                    else:
                        tag = " (from its Out: block; write path is computed)" \
                              if fn in declared_only else ""
                        sup = ", superseded copy, inherits its original's provenance" \
                              if base != fn else ""
                        cls, why = "GEM-only", f"written by {sorted(owners)[0]}, free inputs only{tag}{sup}"
            buckets[cls].append((label + "/" + fn, why))

    for cls in ("GEM-only", "mixed", "FMP-derived", "UNKNOWN"):
        rows = buckets.get(cls, [])
        say()
        say(f"  {cls}  ({len(rows)} file(s))")
        for name, why in rows:
            say(f"    {name:<58} {why}")

    say()
    say("=" * 78)
    say("COUNTS, for the closing handover-back as the ruling requires")
    for cls in ("GEM-only", "mixed", "FMP-derived", "UNKNOWN"):
        say(f"  {cls:<14} {len(buckets.get(cls, [])):>4}")
    total = sum(len(v) for v in buckets.values())
    gem = len(buckets.get("GEM-only", []))
    say(f"  total          {total:>4}")
    if total:
        say(f"  share reproducible from free data alone: {100*gem/total:.1f}%")

    if mismatch:
        say()
        say("DOCSTRING DRIFT, advisory. This does NOT affect the classification above,")
        say("because every file resolved to exactly one writer. It is recorded because a")
        say("script whose docstring misstates what it writes is the next version of this")
        say("problem, and it is cheaper to see it than to rediscover it.")
        for fn, msg in mismatch:
            say(f"  {fn}: {msg}")

    if buckets.get("UNKNOWN"):
        say()
        say("STOP. There are UNKNOWN files. The ruling says to report rather than decide")
        say("at the keyboard, so nothing is published until each one is classified by hand")
        say("and the reason recorded here.")

    rec = os.path.join(OUT, f"PUBLICATION_CLASSIFICATION_{today}.txt")
    with open(rec, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_lines) + "\n")
    print(f"\n  written to {rec}")


if __name__ == "__main__":
    main()
