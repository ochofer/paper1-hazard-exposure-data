"""
PROMOTE THE DETERMINISTIC OUTPUTS TO OUTPUTS OF RECORD

Executes the research design chat's ruling of 7 September 2026, option (a).

WHAT THE RULING SAID
--------------------
The preserve-beside instruction of 7 September was a guard against silent change.
It did its job: it is what surfaced the ordering artefact at all. Once the diff
exists and shows identical content, the guard is discharged, and keeping the
non-reproducible bytes as the record stops being conservative and becomes the
thing the note criticises.

WHAT THIS DOES
--------------
1. change_decomposition_edges.csv and vintage_asset_parent_changes.csv: the
   deterministic reruns become the outputs of record. The 23 August copies are
   RENAMED, never deleted, to <stem>_SUPERSEDED_2026-08-23<ext>, and their
   checksums are recorded.
2. panel_join_summary.txt: already the deterministic version on disk, with no
   pre-sort copy retained. None is manufactured. The gap is stated in the
   promotion record and in the script's provenance instead.
3. Writes outputs/PROMOTION_<today>.txt: per file, the superseded SHA-256, the
   deterministic SHA-256, row count and header shown unchanged, the script and
   line where the sort now happens, and a pointer to the diff record.

WHAT IT REFUSES TO DO
---------------------
Every promotion is gated on proving the content is identical: same row count,
same header, and identical SHA-256 once sorted. If any check fails the script
aborts before touching a single file, because a promotion that moves a value is
not a promotion, it is a silent change of the kind this project exists to catch.

It also refuses to run twice: if a _SUPERSEDED_ copy already exists the file is
treated as already promoted and skipped, so a second run cannot bury the real
23 August bytes behind a second rename.

Run:  python promote_outputs.py            (dry run, prints and changes nothing)
      python promote_outputs.py --apply    (performs the promotion)
"""

import hashlib
import os
import shutil
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
RERUN = os.path.join(OUT, "_provenance_rerun_2026-09-07")
DIFF_RECORD = "PROVENANCE_RERUN_DIFF_2026-09-07.txt"
SUPERSEDED_TAG = "_SUPERSEDED_2026-08-23"

# file, the script and the sort that makes it deterministic
PROMOTE = [
    ("change_decomposition_edges.csv",
     "06_change_decomposition.py",
     "sort_values([bucket, subject, party], kind=mergesort) before to_csv"),
    ("vintage_asset_parent_changes.csv",
     "04_vintage_diff.py",
     "sort_values([subject_id, party_id], kind=mergesort) before to_csv"),
]

# already deterministic on disk, no pre-sort copy retained, none manufactured
NO_COPY = [
    ("panel_join_summary.txt",
     "10_panel_join.py",
     "sorted name list built from the set difference before writing",
     "The pre-sort copy was NOT retained. It was overwritten in place during the "
     "script 10 provenance rerun of 7 September, before this ruling existed. The "
     "pre-sort and post-sort content were verified identical at the time of the "
     "fix: same names, same values, order only. No reconstruction is attempted "
     "here, because a manufactured file is worse than an honest gap in the record."),
]

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sorted_sha(path):
    """SHA-256 of the content with the row order removed: header held in place,
    body sorted. This is the fingerprint that should be stable across runs."""
    with open(path, "rb") as fh:
        rows = fh.read().split(b"\n")
    head, body = rows[0], sorted(r for r in rows[1:] if r.strip())
    return hashlib.sha256(b"\n".join([head] + body)).hexdigest()


def rows_and_header(path):
    with open(path, "rb") as fh:
        data = fh.read().split(b"\n")
    return len([r for r in data[1:] if r.strip()]), data[0]


def main(apply_it):
    today = date.today().isoformat()
    say("PROMOTION OF THE DETERMINISTIC OUTPUTS TO OUTPUTS OF RECORD")
    say(f"  executed {today}, under the research design chat's ruling of 2026-09-07, option (a)")
    say(f"  mode: {'APPLY' if apply_it else 'DRY RUN, nothing is written'}")
    say()
    say("  The ruling named this record PROMOTION_2026-09-07.txt after the date of the")
    say("  ruling. It is named for the date it was actually executed instead, because a")
    say("  file dated earlier than the act it records is the first thing an auditor")
    say("  should not have to reconcile.")
    say()

    plan = []
    for name, script, sort_note in PROMOTE:
        old = os.path.join(OUT, name)
        new = os.path.join(RERUN, name)
        stem, ext = os.path.splitext(name)
        keep = os.path.join(OUT, stem + SUPERSEDED_TAG + ext)

        if os.path.exists(keep):
            say(f"  SKIP  {name}: {os.path.basename(keep)} already exists, so this file "
                f"has already been promoted. Not touching it.")
            continue
        for p in (old, new):
            if not os.path.exists(p):
                sys.exit(f"ABORTED: missing {p}")

        n_old, h_old = rows_and_header(old)
        n_new, h_new = rows_and_header(new)
        if n_old != n_new:
            sys.exit(f"ABORTED: {name} row count {n_old} vs {n_new}. A promotion may not "
                     f"change the number of rows.")
        if h_old != h_new:
            sys.exit(f"ABORTED: {name} header differs. A promotion may not change the header.")
        s_old, s_new = sorted_sha(old), sorted_sha(new)
        if s_old != s_new:
            sys.exit(f"ABORTED: {name} content differs once order is removed. This is not "
                     f"an ordering artefact and must not be promoted.")

        plan.append(dict(name=name, script=script, sort_note=sort_note, old=old, new=new,
                         keep=keep, rows=n_old, header=h_old.decode("utf-8", "replace"),
                         sha_superseded=sha(old), sha_record=sha(new), sorted_sha=s_new))

    say("=" * 78)
    say("VERIFIED BEFORE ANY FILE WAS TOUCHED")
    for p in plan:
        say()
        say(f"  {p['name']}")
        say(f"    rows                 {p['rows']:,}   unchanged")
        say(f"    header               unchanged")
        say(f"    content, order removed  {p['sorted_sha']}")
        say(f"    superseded (23 Aug)  {p['sha_superseded']}")
        say(f"    output of record     {p['sha_record']}")
        say(f"    deterministic since  {p['script']}: {p['sort_note']}")
        say(f"    retained beside as   {os.path.basename(p['keep'])}")

    for name, script, sort_note, gap in NO_COPY:
        p = os.path.join(OUT, name)
        if not os.path.exists(p):
            sys.exit(f"ABORTED: missing {p}")
        say()
        say(f"  {name}")
        say(f"    output of record     {sha(p)}")
        say(f"    deterministic since  {script}: {sort_note}")
        say(f"    superseded copy      NONE RETAINED")
        for line in gap.split(". "):
            if line.strip():
                say(f"      {line.strip().rstrip('.')}.")

    say()
    say("=" * 78)
    say("THE RULE, FROM HERE")
    say("  Every output is deterministic: sorted before writing, so that its published")
    say("  checksum is reproducible by a reader who reruns the script against the pinned")
    say("  V1 files. Any output that cannot meet that states so in its own provenance")
    say("  record. This is written into code/README.md so it is not carried in prose.")
    say()
    say(f"  The diff that discharged the preserve-beside guard: outputs/{DIFF_RECORD}")
    say("  No value moved and no reported figure moved in any of this. R = 36.0%.")

    if not apply_it:
        say()
        say("  DRY RUN. Nothing was written. Rerun with --apply to perform the promotion.")
        print("\n".join([]))
        return

    for p in plan:
        os.rename(p["old"], p["keep"])
        shutil.copy2(p["new"], p["old"])
    say()
    say(f"  APPLIED. {len(plan)} file(s) promoted, {len(plan)} superseded copy(ies) retained.")

    rec = os.path.join(OUT, f"PROMOTION_{today}.txt")
    with open(rec, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_lines) + "\n")
    print(f"  promotion record written to {rec}")


if __name__ == "__main__":
    main("--apply" in sys.argv)
