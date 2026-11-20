"""Every hash a provenance record holds equals its file, for the files the repository holds.

Run from the repository root: python3 -m pytest tests. Added 20 November 2026.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))
import check_provenance  # noqa: E402


def test_every_recorded_hash_equals_its_file():
    lines, mismatches = check_provenance.check()
    assert mismatches == [], "\n".join(lines)
    # the two records that hash another record are among those checked
    joined = "\n".join(lines)
    assert "upstream_provenance_09" in joined and "upstream_provenance_10" in joined


def test_a_changed_byte_is_a_mismatch(tmp_path):
    # a record that names a committed file with a wrong hash is reported, and nothing else is
    import json
    rec = {"script": "x", "inputs": {"panel": {"filename": "panel_exposure.csv", "bytes": 1,
                                                "sha256": "0" * 64}}}
    p = tmp_path / "RUN_PROVENANCE_x.json"
    p.write_text(json.dumps(rec))
    lines, mismatches = check_provenance.check([str(p)])
    assert mismatches == [("RUN_PROVENANCE_x.json", "panel", "panel_exposure.csv")]
    assert lines[-1].endswith("MISMATCH 1")
