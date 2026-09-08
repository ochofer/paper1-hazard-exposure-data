"""
COPY THE PUBLISHABLE OUTPUTS INTO THE PUBLIC REPOSITORY

Executes items 3.1 to 3.3 of the research design chat's ruling of 8 September 2026,
after classify_outputs.py has classified every file.

WHAT IT COPIES
--------------
Exactly the files the classification report lists as GEM-only, and nothing else.
It reads that report rather than deciding for itself, so the thing that determines
what becomes public is the same artefact a reader can inspect. A file that is
FMP-derived, mixed or UNKNOWN is never copied, and the script aborts outright if
the report still contains an UNKNOWN, because publishing under an unresolved
classification is the failure this whole exercise exists to avoid.

It also copies the numbered scripts, which are mine and carry no vendor data.

WHAT IT CHECKS AFTER COPYING
----------------------------
That every file named in the report as FMP-derived is absent from the repository
tree. A copy list can be right and a working tree still wrong, so the absence is
asserted rather than assumed.

Run:  python publish_outputs.py            (dry run)
      python publish_outputs.py --apply
"""

import os
import re
import shutil
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, "..")
REPO = os.path.join(PROJ, "repo_paper1_data")
REPORT = os.path.join(PROJ, "outputs", f"PUBLICATION_CLASSIFICATION_{date.today().isoformat()}.txt")

# The numbered scripts and their helpers. README.md is DELIBERATELY EXCLUDED: the
# one in this directory is the internal working note and the repository has its own,
# written for strangers. Copying this one over that one is a mistake I made on
# 8 September 2026 and reverted; the exclusion is here so it cannot happen twice.
SCRIPTS = re.compile(r"^(\d\d_.*\.py|_release\.py|classify_outputs\.py|"
                     r"promote_outputs\.py|publish_outputs\.py)$")


# Credential shapes that must never reach a public repository. GitHub's scanner
# found an AWS temporary access key id in a published file on 8 September 2026.
# It was a third party's, inside a presigned URL in GEM's own source column, and
# it had expired on issue, but it should never have been published and this scan
# should have existed before the first push rather than after it.
SECRET_SHAPES = [
    (r"ASIA[A-Z0-9]{16}", "AWS temporary access key id"),
    (r"AKIA[A-Z0-9]{16}", "AWS access key id"),
    # The literals are split so this list does not match itself. An exclusion for
    # the scanner's own file would be a hole someone could widen later.
    (r"X-Amz-" + r"Credential=", "AWS presigned URL credential"),
    (r"X-Amz-" + r"Security-Token=", "AWS session token"),
    (r"AWSAccess" + r"KeyId=", "AWS access key in a query string"),
    (r"gh[pousr]_[A-Za-z0-9]{36}", "GitHub token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r"(?i)api[_-]?key[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}", "api key assignment"),
]


def scan_for_secrets(paths):
    """Read every file about to be published and refuse on a credential shape."""
    hits = []
    for src, rel in paths:
        try:
            body = open(src, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for pat, label in SECRET_SHAPES:
            for m in re.finditer(pat, body):
                line = body.count("\n", 0, m.start()) + 1
                hits.append(f"{rel}:{line}  {label}")
    return hits


def read_report():
    if not os.path.exists(REPORT):
        sys.exit(f"ABORTED: {os.path.basename(REPORT)} not found. Run classify_outputs.py first.")
    buckets, cur = {}, None
    for line in open(REPORT, encoding="utf-8"):
        m = re.match(r"^  (GEM-only|mixed|FMP-derived|UNKNOWN)  \((\d+) file", line)
        if m:
            cur = m.group(1)
            buckets[cur] = []
            continue
        if cur:
            m2 = re.match(r"^    ((?:outputs|evidence)/\S+)", line)
            if m2:
                buckets[cur].append(m2.group(1))
    return buckets


def main(apply_it):
    b = read_report()
    if b.get("UNKNOWN"):
        sys.exit(f"ABORTED: the classification report still lists {len(b['UNKNOWN'])} UNKNOWN "
                 f"file(s). Nothing is published under an unresolved classification.")
    if b.get("mixed"):
        sys.exit("ABORTED: mixed files present. The ruling requires each to be resolved to "
                 "GEM-only or FMP-derived by hand before publishing.")

    pub, withheld = b.get("GEM-only", []), b.get("FMP-derived", [])
    print(f"PUBLISH {len(pub)} GEM-only file(s); WITHHOLD {len(withheld)}: "
          f"{', '.join(os.path.basename(w) for w in withheld)}")

    plan = []
    for rel in pub:
        src = os.path.join(PROJ, rel)
        if not os.path.exists(src):
            sys.exit(f"ABORTED: {rel} is in the report but not on disk.")
        plan.append((src, os.path.join(REPO, rel)))
    # 00 and 03 are already in the repository with docstrings written for strangers
    # and in the first person. The working copies differ in prose only, no executable
    # line, and the published wording is the better one, so they are left alone.
    ALREADY_PUBLIC = {"00_coverage_and_crosswalk.py", "03_gleif_crosscheck.py"}
    for fn in sorted(os.listdir(HERE)):
        if SCRIPTS.match(fn) and fn not in ALREADY_PUBLIC:
            plan.append((os.path.join(HERE, fn), os.path.join(REPO, "code", fn)))

    hits = scan_for_secrets([(src, os.path.relpath(src, PROJ)) for src, _ in plan])
    if hits:
        print("ABORTED: credential shapes found in files about to be published:")
        for h in hits[:40]:
            print("   ", h)
        sys.exit("Nothing was copied. Fix the source, regenerate, and rerun.")
    print(f"  credential scan clean across {len(plan)} file(s)")

    total = sum(os.path.getsize(s) for s, _ in plan)
    print(f"  {len(plan)} file(s), {total/1e6:.1f} MB")
    if not apply_it:
        print("  DRY RUN. Nothing copied. Rerun with --apply.")
        return

    for src, dst in plan:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    print(f"  copied {len(plan)} file(s)")

    leaked = []
    for root, _, files in os.walk(REPO):
        if ".git" in root.split(os.sep):
            continue
        for f in files:
            if f in {os.path.basename(w) for w in withheld}:
                leaked.append(os.path.join(root, f))
    if leaked:
        sys.exit(f"ABORTED AFTER COPY: an FMP-derived file is in the repository tree: {leaked}")
    print("  verified: no FMP-derived file is anywhere in the repository tree")


if __name__ == "__main__":
    main("--apply" in sys.argv)
