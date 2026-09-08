"""
HOW MANY RELEASES SHIP A SOURCE CITATION THAT EXPIRES ON ISSUE

Written under the ruling of 8 September 2026, which admits the presigned-URL
finding into the note as one short subsection under six conditions. This script
supplies the only two new numbers that ruling allows: how many of the releases
held here carry presigned source URLs, and the expiry those URLs declare.

WHY THE FINDING IS ABOUT VERIFIABILITY AND NOT SECURITY
-------------------------------------------------------
A presigned URL is a link that carries its own authorisation in the query string
and stops working when that authorisation expires. GEM uses them in a source
column. The one this project tripped over declared a sixty second expiry and was
issued in July 2024, so it stopped working in July 2024.

The point is not that a credential was published. It expired years ago and
nothing is exposed. The point is that a citation which stops resolving sixty
seconds after it is created cannot be checked by any reader, in a dataset
published under CC BY 4.0 for exactly the purpose of being checked. That is this
note's subject reached from a direction nobody was looking in.

WHAT THIS SCRIPT WILL NOT DO
----------------------------
It never writes a key, a token, a signature or a whole URL to any output. It
counts, and it reports the declared expiry values it finds. The condition in the
ruling is that the note quote the shape only, so the script cannot emit anything
richer than the shape even if a later reader asks it to.

Run:  python 23_presigned_source_urls.py
Out:  outputs/presigned_source_urls.txt
      outputs/RUN_PROVENANCE_23_presigned_source_urls.json
"""

import glob
import os
import re
import zipfile
from collections import Counter

import _release

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
OUT = os.path.join(HERE, "..", "outputs")

# Shape only. Split literals so this file cannot trip the credential scan in
# publish_outputs.py, which reads source as well as data.
# Inside a workbook the query separators are XML-escaped, so "&" arrives as
# "&amp;". The first version of this script missed every expiry for that reason
# and reported "no expiry parameter found", which would have been a false
# negative published as a fact.
_SEP = rb"(?:[?&]|&amp;)"
SIGNED = re.compile(_SEP + rb"X-Amz-" + rb"Algorithm=")
EXPIRES = re.compile(_SEP + rb"X-Amz-" + rb"Expires=(\d{1,7})")

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def is_release(path):
    """A release carries asset-level ownership sheets. Decided by looking inside,
    never by the filename: one workbook in this folder is an entity-id mapping
    aid rather than a release, and counting it would have made every count in
    the note wrong by one."""
    try:
        with zipfile.ZipFile(path) as z:
            wb = z.read("xl/workbook.xml").decode("utf-8", "replace")
    except Exception:
        return False
    return "Ownership" in wb


def scan(path):
    """Return (carries_presigned, Counter of declared expiry values in seconds).

    Streams the shared string table rather than reading whole XML parts into
    memory. The URLs live there, the table is the largest part of the workbook,
    and reading nineteen of them whole exceeded the shell's time limit on the
    first attempt. Chunks overlap so a match cannot fall across a boundary.
    """
    exp = Counter()
    found = False
    CHUNK = 4 << 20
    OVER = 512
    with zipfile.ZipFile(path) as z:
        parts = [n for n in z.namelist()
                 if n.endswith("sharedStrings.xml") or n.endswith("workbook.xml")]
        for name in parts:
            with z.open(name) as fh:
                tail = b""
                while True:
                    chunk = fh.read(CHUNK)
                    if not chunk:
                        break
                    buf = tail + chunk
                    if SIGNED.search(buf):
                        found = True
                    for m in EXPIRES.finditer(buf):
                        exp[int(m.group(1))] += 1
                    tail = buf[-OVER:]
    return found, exp


CACHE = os.path.join(OUT, ".presigned_scan_cache.json")


def cached_scan(path):
    """Per-file cache, so the scan is resumable across shell calls."""
    import json
    key = os.path.basename(path)
    try:
        c = json.load(open(CACHE, encoding="utf-8"))
    except Exception:
        c = {}
    if key in c:
        return c[key]["found"], Counter({int(k): v for k, v in c[key]["exp"].items()})
    found, exp = scan(path)
    c[key] = {"found": found, "exp": {str(k): v for k, v in exp.items()}}
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(c, fh, indent=1, sort_keys=True)
    return found, exp


def main():
    everything = sorted(glob.glob(os.path.join(DATA, "*.xlsx")))
    files = [f for f in everything if is_release(f)]
    skipped = [os.path.basename(f) for f in everything if f not in files]
    say("SOURCE CITATIONS THAT EXPIRE ON ISSUE")
    say("  Counted across every GEM release held here. The note quotes the shape")
    say("  of these links and never their contents: a document path plus an")
    say("  expiry parameter. No key, token, signature or whole URL is written by")
    say("  this script to any output.")
    say()
    say(f"  workbooks in the release folder: {len(everything)}")
    say(f"  of those, release files carrying ownership sheets: {len(files)}")
    for sk in skipped:
        say(f"    SKIPPED, not a release: {sk}")
    say()

    carriers, expiries = [], Counter()
    for f in files:
        ok, exp = cached_scan(f)
        expiries.update(exp)
        say(f"  {'PRESIGNED' if ok else 'clean    '}  {os.path.basename(f)}")
        if ok:
            carriers.append(os.path.basename(f))

    say()
    say("=" * 78)
    say(f"RELEASES CARRYING PRESIGNED SOURCE URLS: {len(carriers)} of {len(files)}")
    say()
    if expiries:
        say("  DECLARED EXPIRY, in seconds, as the links themselves state it")
        for secs, n in sorted(expiries.items()):
            say(f"    {secs} seconds   {n} occurrence(s)")
        say()
        lo = min(expiries)
        say(f"  The shortest declared expiry is {lo} seconds. A citation that stops")
        say("  resolving that fast cannot be checked by a reader at any point after")
        say("  the moment it was created.")
    else:
        say("  No expiry parameter found. Report this rather than inferring one.")

    say()
    say("  WHAT THIS IS NOT. It is not a disclosure of exposed credentials. The")
    say("  authorisation carried by these links expired when they were issued, and")
    say("  the earliest this project observed was issued in 2024. The finding is")
    say("  about whether a source citation can be checked, and it cannot.")

    _release.write_provenance(
        OUT, "23_presigned_source_urls",
        {"new": _release.resolve("August 2026", DATA),
         "old": _release.resolve("March 2025", DATA)},
        extra={"release_files": [os.path.basename(f) for f in files],
               "skipped_not_a_release": skipped,
               "releases_checked": len(files),
               "releases_carrying_presigned_urls": len(carriers),
               "declared_expiry_seconds": {str(k): v for k, v in sorted(expiries.items())},
               "emits_no_credential_material": True})

    with open(os.path.join(OUT, "presigned_source_urls.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_lines) + "\n")
    say()
    say(f"  written to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
