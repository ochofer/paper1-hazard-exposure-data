"""The three parts of an entrant's August 2026 capacity, on made-up units.

Run from the repository root: python3 -m pytest tests. Added 20 November 2026.
"""
import importlib.util
import os
import sys

CODE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code")
sys.path.insert(0, CODE)
_spec = importlib.util.spec_from_file_location("panel_entrants", os.path.join(CODE, "25_panel_entrants.py"))
pe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pe)

# Made-up units the March 2025 file carried, and the listed entities it attributed each to.
MARCH = {"u1", "u2", "u3", "u4", "u5"}
HOLDERS = {"u1": {"P"}, "u2": {"P"}, "u3": {"P", "Q"}, "u4": {"Q"}, "u5": set()}


def test_the_three_parts_add_to_the_entrants_total():
    # four made-up entrants: a subsidiary whose units the earlier file held under its owner P, a firm
    # held under Q, which does not own it, a firm listed and identified in March 2025, and a firm whose
    # units the earlier file did not carry
    entrants = [
        ({"u1": 100.0, "u2": 50.0}, {"P", "G"}, False),
        ({"u4": 40.0, "u5": 8.0}, {"P"}, False),
        ({"u3": 20.0}, {"P"}, True),
        ({"n1": 12.5, "n2": 2.5}, set(), False),
    ]
    parts = [pe.split_capacity(mw, MARCH, HOLDERS, owners, listed) for mw, owners, listed in entrants]
    assert parts == [(150.0, 0.0, 0.0), (0.0, 48.0, 0.0), (0.0, 20.0, 0.0), (0.0, 0.0, 15.0)]
    for (mw, _o, _l), p in zip(entrants, parts):
        assert sum(p) == sum(mw.values())
    assert sum(sum(p) for p in parts) == sum(sum(mw.values()) for mw, _o, _l in entrants) == 233.0


def test_an_entrant_with_one_new_unit_keeps_its_other_units_in_the_first_part():
    # three units the earlier file held under the owner P (one of them jointly with Q, which does not
    # own the entrant) and one unit new in August 2026: the three stay in (i), the new one is (iii)
    unit_mw = {"u1": 100.0, "u2": 50.0, "u3": 25.0, "new": 10.0}
    i, ii, iii = pe.split_capacity(unit_mw, MARCH, HOLDERS, {"P"}, False)
    assert (i, ii, iii) == (175.0, 0.0, 10.0)
    assert i + ii + iii == sum(unit_mw.values())
    # without the new unit the same three units give the same (i)
    del unit_mw["new"]
    assert pe.split_capacity(unit_mw, MARCH, HOLDERS, {"P"}, False) == (175.0, 0.0, 0.0)
