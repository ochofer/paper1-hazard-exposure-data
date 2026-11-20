"""
EVERY HASH A PROVENANCE RECORD HOLDS, AGAINST ITS FILE

Added 20 November 2026. Each outputs/RUN_PROVENANCE_<script>.json records the SHA-256 of the files the
script read. Two of the records hash another record (script 10 hashes script 09's, script 11 hashes
script 10's), and a record carries its own run time, so a record that hashes another breaks when the
upstream script runs again and the downstream one does not. This check compares every recorded hash
with the file as it stands and prints one line per input: OK, MISMATCH, or NOT IN THE REPOSITORY for the
tracker's releases and the price archive, which are not committed. It exits with status 1 on a
mismatch, so the check fails where a chain is broken, and tests/test_provenance.py runs it.

Run:  python3 code/check_provenance.py   (from the repository root, or from code/)
"""

import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "outputs")
# Where a recorded file can stand, searched in this order; the first match by name is the file.
SEARCH = ["outputs", "config", "evidence", "data", "Data"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def locate(filename):
    """The path of a recorded file, by its name, under the folders of SEARCH; None where absent."""
    for folder in SEARCH:
        base = os.path.join(ROOT, folder)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            if filename in files:
                return os.path.join(dirpath, filename)
    return None


def check(records=None):
    """Returns (lines, mismatches): the printed lines and the list of (record, role, filename) that
    disagree with their file."""
    records = records or sorted(glob.glob(os.path.join(OUT, "RUN_PROVENANCE_*.json")))
    lines, mismatches = [], []
    lines.append(f"{'record':<42} {'role':<24} {'file':<52} status")
    for rec_path in records:
        rec = json.load(open(rec_path))
        name = os.path.basename(rec_path)
        for role, d in rec.get("inputs", {}).items():
            fn = d["filename"]
            path = locate(fn)
            if path is None:
                status = "NOT IN THE REPOSITORY"
            elif sha256(path) == d["sha256"]:
                status = "OK"
            else:
                status = "MISMATCH"
                mismatches.append((name, role, fn))
            lines.append(f"{name:<42} {role:<24} {fn:<52} {status}")
    n_ok = sum(1 for l in lines[1:] if l.endswith(" OK"))
    n_absent = sum(1 for l in lines[1:] if l.endswith("NOT IN THE REPOSITORY"))
    lines.append(f"recorded inputs {len(lines) - 1} | OK {n_ok} | not in the repository {n_absent} "
                 f"| MISMATCH {len(mismatches)}")
    return lines, mismatches


def main():
    lines, mismatches = check()
    print("\n".join(lines))
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
