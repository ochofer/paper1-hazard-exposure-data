"""
RELEASE PIN AND PROVENANCE. Shared by scripts 04, 06, 07, 08 and 09.

WHY THIS EXISTS
---------------
Until 2 September 2026 the scripts located a GEM workbook by matching a
filename hint such as "August-2026" against whatever happened to be in
Data/GEM Data/, then preferred any match containing "V2". That rule was
correct when it was written: July 2025 and May 2026 were each reissued, and V2
is the corrected file for those months.

On 26 August 2026 GEM reissued August 2026 as
Global-Energy-Ownership-Tracker-August-2026-V2_External.xlsx. The hint
"August-2026" then matched two files and silently resolved to the new one.
Nothing failed. The pipeline simply split: scripts 00, 04, 06 and 07 had
already run against V1, while 08 and 09 ran against V2, and 10 and 11 joined a
V1 cross-section to a V2 exposure measure.

The measured cost of that split is in RELEASE_SPLIT_MEASUREMENT_2026-09-02.html.
The short version is that R is 36.0% on V1 and 35.4% on V2, and the worst-case
reading of the pre-committed GO threshold clears on one file and fails on the
other. A resolution rule that depends on the contents of a directory is not a
reproducible input, whatever the rule is.

THE DECISION IT ENFORCES
------------------------
Carlo pinned V1 on 3 September 2026. The reasons are recorded in
PROJECT_STATUS.md; the binding one is that the 328-firm cross-section is itself
a V1 artefact, script 00 having been hardcoded to V1 and run on 19 August, and
328 is fixed in public documents.

V2_External is deliberately still listed below under its own key. It is
reported alongside V1 in the note as a second column, including the worst case
that fails on it. It is not the default for anything.

Nothing here chooses a release at runtime. Changing an endpoint means editing
RELEASES, which shows up in a diff.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# The pin. Exact basenames, not hints. A hint that matches two files is the
# bug this module exists to prevent, so nothing here uses a wildcard.
# ---------------------------------------------------------------------------
RELEASES = {
    "March 2025":     "Global-Energy-Ownership-Tracker-March-2025.xlsx",
    "August 2026":    "Global-Energy-Ownership-Tracker-August-2026-V1.xlsx",
    # Reported alongside, never the default. See the module docstring.
    "August 2026 V2": "Global-Energy-Ownership-Tracker-August-2026-V2_External.xlsx",
}

# For 07_decay_curves.py, which walks every release month rather than naming
# two endpoints. Its "prefer V2" rule is CORRECT for July 2025 and May 2026 and
# WRONG for August 2026, so the exception is stated rather than the rule
# changed. Keyed (year, month).
MONTH_PIN = {
    (2026, 8): "Global-Energy-Ownership-Tracker-August-2026-V1.xlsx",
}


def resolve(key, data_dir):
    """Return the absolute path of a pinned release, or fail loudly.

    Fails if the key is unknown, if the file is absent, or if more than one
    file in data_dir has that basename. It never guesses and never prefers.
    """
    if key not in RELEASES:
        raise SystemExit(
            f"_release.resolve: unknown release key {key!r}. "
            f"Known keys: {sorted(RELEASES)}"
        )
    name = RELEASES[key]
    p = os.path.join(data_dir, name)
    if not os.path.isfile(p):
        raise SystemExit(
            f"_release.resolve: pinned workbook not found.\n"
            f"  key      {key}\n  expected {name}\n  in       {os.path.abspath(data_dir)}\n"
            f"Put the file there under its original GEM filename. Do not "
            f"substitute another release: the pin is deliberate."
        )
    twins = [f for f in os.listdir(data_dir) if f == name]
    if len(twins) != 1:
        raise SystemExit(f"_release.resolve: {len(twins)} files named {name!r} in {data_dir}")
    return os.path.abspath(p)


def sha256(path, _chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_chunk), b""):
            h.update(block)
    return h.hexdigest()


def describe(path):
    """Filename, size and checksum, as a dict."""
    return {
        "filename": os.path.basename(path),
        "bytes": os.path.getsize(path),
        "sha256": sha256(path),
    }


def banner(inputs):
    """Provenance lines for the top of a text output.

    `inputs` maps a role ("old", "new", ...) to a file path. Returns a list of
    strings. The checksum is what makes a result auditable: a filename alone
    does not distinguish two files GEM shipped under the same month.
    """
    lines = ["PROVENANCE",
             f"  generated  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}"]
    for role, path in inputs.items():
        d = describe(path)
        lines.append(f"  {role:<10} {d['filename']}")
        lines.append(f"  {'':<10} sha256 {d['sha256']}  ({d['bytes']:,} bytes)")
    return lines


def write_provenance(out_dir, script, inputs, extra=None):
    """Write outputs/RUN_PROVENANCE_<script>.json.

    Text outputs can carry the banner inline, but CSVs cannot without adding a
    column to every row, so the machine-readable record lives beside them.
    """
    rec = {
        "script": script,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_pin": dict(RELEASES),
        "inputs": {role: describe(p) for role, p in inputs.items()},
    }
    if extra:
        # RESERVED KEYS. `extra` is caller-supplied and on 7 September 2026 a
        # caller passed extra={"inputs": [...]} , which silently replaced the
        # dict of release filenames and SHA-256 sums with a list of two
        # unrelated filenames. The provenance record for script 15 was
        # destroyed and nothing complained; it was found only because the gate
        # 5 register tried to read the release out of it. A provenance writer
        # that can be silently emptied by its own caller is worse than none,
        # because it looks like evidence.
        clash = sorted(set(extra) & {"script", "generated_utc", "release_pin", "inputs"})
        if clash:
            raise SystemExit(
                f"write_provenance: extra may not overwrite reserved key(s) {clash}. "
                f"Rename them at the call site; 'inputs' in particular holds the "
                f"release filenames and checksums that gate 5 depends on."
            )
        rec.update(extra)
    p = os.path.join(out_dir, f"RUN_PROVENANCE_{script}.json")
    with open(p, "w") as fh:
        json.dump(rec, fh, indent=2)
    return p


def find_col(df, names):
    """Return the first present column from `names`, or None.

    For a field whose ABSENCE is a documented property of a release rather
    than a schema surprise. March 2025 predates GEM's newest_update column
    entirely, so requiring it there would reject a workbook that is behaving
    exactly as expected. Use require_col wherever absence would be a bug.
    """
    if isinstance(names, str):
        names = [names]
    for n in names:
        if n in df.columns:
            return n
    return None


def require_col(df, names, where):
    """Return the first present column from `names`, or raise.

    GEM has renamed a column three times: Owner GEM Entity ID to Parent GEM
    Entity ID, an inserted Last Review Date that shifted every later column in
    December 2025, and newest_update to Last Review Date in the August 2026 V2
    reissue. A guard of the form

        has_x = "x" in df.columns
        value = row["x"] if has_x else ""

    turns a rename into silent data loss rather than an error. That is exactly
    what happened: the V2 frame carried an empty newest_update on all 2,756
    rows and nothing complained. Aliases are declared, and an unknown schema
    stops the run.
    """
    if isinstance(names, str):
        names = [names]
    for n in names:
        if n in df.columns:
            return n
    raise SystemExit(
        f"require_col: none of {names} present in {where}.\n"
        f"  columns found: {list(df.columns)}\n"
        f"If GEM has renamed the column again, add the new name to the alias "
        f"list at the call site. Do not fall back to a blank value."
    )
