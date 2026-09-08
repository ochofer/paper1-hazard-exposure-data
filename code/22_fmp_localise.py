#!/usr/bin/env python3
"""
22_fmp_localise.py -- verify the local copy of the FMP pull against its manifest.

Run this on your own Mac, on the folder you downloaded out of Google Drive, BEFORE you
delete the Drive copy and BEFORE you cancel the subscription.

FMP's written confirmation allows retention on a LOCAL COMPUTER. Google Drive is not that.
The sequence is: download from Drive -> run this -> make a second local copy -> delete from
Drive -> then cancel.

    python3 22_fmp_localise.py "/path/to/fmp_extraction_2026-09"
    python3 22_fmp_localise.py "/path/to/fmp_extraction_2026-09" --second "/Volumes/Backup/fmp_extraction_2026-09"

What it checks:
  1. The manifest's own SHA-256 against its .sha256 sidecar.
  2. Every file the manifest lists is present.
  3. Every file's content hash matches. The manifest records the hash of the RESPONSE BODY,
     and the file on disk is gzipped, so this decompresses before hashing. A gzip stream is
     not byte-stable across writers, so hashing the .gz itself would produce false failures.
  4. Files on disk that the manifest does not list.
  5. If --second is given, that the second copy matches the first file-for-file.

Exit status is 0 only if everything passes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path


def sha256_of_body(path: Path) -> str | None:
    """Hash the decompressed response body, which is what the manifest recorded."""
    try:
        with gzip.open(path, "rb") as fh:
            h = hashlib.sha256()
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def find_manifest(root: Path) -> Path:
    cands = sorted(root.glob("manifest__fmp_pull_*.json"))
    cands = [c for c in cands if not c.name.endswith(".sha256")]
    if not cands:
        sys.exit(f"No manifest__fmp_pull_*.json in {root}.\n"
                 "Did the notebook's manifest cell run? Nothing can be verified without it.")
    if len(cands) > 1:
        print(f"note: {len(cands)} manifests present; using the newest, {cands[-1].name}")
    return cands[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="the downloaded fmp_extraction_2026-09 folder")
    ap.add_argument("--second", help="optional second local copy to compare against")
    ap.add_argument("--show", type=int, default=25, help="how many problem files to list")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    mpath = find_manifest(root)
    print(f"folder   : {root}")
    print(f"manifest : {mpath.name}")

    # ---- 1. the manifest's own hash ------------------------------------
    actual = hashlib.sha256(mpath.read_bytes()).hexdigest()
    sidecar = mpath.with_suffix(mpath.suffix + ".sha256")
    print(f"manifest SHA-256: {actual}")
    if sidecar.exists():
        expected = sidecar.read_text().split()[0]
        if expected == actual:
            print("  sidecar matches.")
        else:
            print(f"  MISMATCH against sidecar: {expected}")
            print("  The manifest itself has changed since it was written. Stop and work out why.")
            return 1
    else:
        print("  no .sha256 sidecar found; recording the hash above is still worth doing.")

    manifest = json.loads(mpath.read_text())
    entries = manifest.get("files", [])
    print(f"entries  : {len(entries)}")
    print()

    # ---- 2 and 3. presence and content ---------------------------------
    missing, mismatched, unhashable = [], [], []
    total_bytes = 0
    listed = set()

    for i, e in enumerate(sorted(entries, key=lambda x: str(x.get("file"))), 1):
        rel = e.get("file")
        if not rel:
            continue
        listed.add(rel)
        p = root / rel
        if not p.exists():
            missing.append(rel)
            continue
        total_bytes += p.stat().st_size
        want = e.get("sha256")
        got = sha256_of_body(p)
        if got is None:
            unhashable.append(rel)
        elif want and got != want:
            mismatched.append(rel)
        if i % 2000 == 0:
            print(f"  ...{i}/{len(entries)} checked", flush=True)

    # ---- 4. files on disk the manifest does not know about --------------
    on_disk = {str(p.relative_to(root)) for p in root.rglob("*.json.gz")}
    unlisted = sorted(on_disk - listed)

    print()
    print(f"checked          : {len(entries)} entries, {human(total_bytes)} on disk")
    print(f"missing          : {len(missing)}")
    print(f"hash mismatches  : {len(mismatched)}")
    print(f"unreadable gzip  : {len(unhashable)}")
    print(f"on disk, unlisted: {len(unlisted)}")

    for label, items in (("MISSING", missing), ("MISMATCHED", mismatched),
                         ("UNREADABLE", unhashable)):
        if items:
            print(f"\n{label}:")
            for r in items[:args.show]:
                print("   ", r)
            if len(items) > args.show:
                print(f"    ...and {len(items) - args.show} more")

    if unlisted:
        print("\nOn disk but not in the manifest. Usually __refetch_ files, which is fine")
        print("and expected; anything else is worth a look:")
        for r in unlisted[:args.show]:
            print("   ", r, "  <- refetch" if "__refetch_" in r else "")
        if len(unlisted) > args.show:
            print(f"    ...and {len(unlisted) - args.show} more")

    # ---- 5. the second local copy ---------------------------------------
    second_ok = True
    if args.second:
        second = Path(args.second).expanduser().resolve()
        print(f"\nsecond copy: {second}")
        if not second.is_dir():
            print("  NOT FOUND. You do not yet have two local copies.")
            second_ok = False
        else:
            s_missing, s_diff = [], []
            for rel in sorted(listed):
                a, b = root / rel, second / rel
                if not b.exists():
                    s_missing.append(rel)
                elif a.exists() and sha256_of_body(a) != sha256_of_body(b):
                    s_diff.append(rel)
            print(f"  missing in second copy : {len(s_missing)}")
            print(f"  differing              : {len(s_diff)}")
            for r in (s_missing + s_diff)[:args.show]:
                print("   ", r)
            second_ok = not (s_missing or s_diff)

    # A missing second copy is not a data problem, and must not be reported as one.
    # The earlier version printed "re-download whatever is missing or mismatched" when
    # nothing was missing and nothing mismatched, which is alarming and wrong.
    content_ok = not (missing or mismatched or unhashable)
    ok = content_ok and second_ok
    print()
    if content_ok and not second_ok:
        print("INCOMPLETE, but the data is fine.")
        print()
        print("Every file the manifest lists is present and its content hash matches. The")
        print("copy you checked is intact. What is missing is the SECOND local copy, and")
        print("nothing else.")
        print()
        print("Make it, then re-run with --second pointing at it. Do not delete the Drive")
        print("copy and do not cancel until it exists.")
        return 1
    if ok:
        print("PASS. Every file the manifest lists is present and its content hash matches.")
        if not args.second:
            print()
            print("You have ONE verified local copy. Before cancelling:")
            print("  1. Make a second local copy (external drive, or confirm Time Machine has it).")
            print("  2. Re-run with --second pointing at it.")
            print("  3. Delete the folder from Google Drive, and empty Drive's bin.")
            print("  4. Send the design chat the handover with the section C numbers.")
            print("  5. Cancel only after they have read it.")
        else:
            print()
            print("Two verified local copies. Now delete the Drive copy, empty Drive's bin,")
            print("and send the handover. Cancel only after the design chat has read it.")
    else:
        print("FAIL. Files are missing, or their contents do not match the manifest.")
        print("Do not delete the Drive copy and do not cancel.")
        print("Re-download the files named above while the subscription is still live.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
