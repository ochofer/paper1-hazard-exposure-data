"""The bounds of a top-k overlap under ties, against every order.

Run from the repository root: python3 -m pytest tests. Added 20 November 2026.
"""
import os
import random
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code"))
import _overlap  # noqa: E402


def test_a_made_up_case_against_every_order():
    # nine firms, k = 3: four tie at 1 in the first release for three places,
    # four tie at 1 in the second for three places, two of them in both; the
    # orders run from no firm in common to two.
    a = pd.Series([1, 1, 1, 1, 0.5, 0.5, 0.2, 0, 0], index=list("abcdefghi"))
    b = pd.Series([1, 0.5, 1, 0.2, 1, 1, 0.5, 0, 0], index=list("abcdefghi"))
    r = _overlap.overlap_bounds(a, b, 3)
    assert (r["tied_a"], r["places_a"], r["tied_b"], r["places_b"]) == (4, 3, 4, 3)
    assert (r["lowest"], r["highest"]) == _overlap.overlap_by_enumeration(a, b, 3) == (0, 2)
    assert _overlap.has_ties(r)
    assert _overlap.overlap_text(r).startswith("0 to 2 of 3 (0.0% to 66.7%)")


def test_no_tie_gives_one_figure():
    a = pd.Series([5, 4, 3, 2, 1], index=list("abcde"))
    b = pd.Series([5, 3, 4, 1, 2], index=list("abcde"))
    r = _overlap.overlap_bounds(a, b, 2)
    assert (r["lowest"], r["highest"]) == (1, 1)
    assert not _overlap.has_ties(r)
    assert _overlap.overlap_text(r) == "1 of 2 (50.0%), no tie at either cut"


def test_every_firm_tied_says_nothing():
    a = pd.Series([1.0] * 6, index=list("abcdef"))
    b = pd.Series([1.0] * 6, index=list("abcdef"))
    r = _overlap.overlap_bounds(a, b, 2)
    assert (r["lowest"], r["highest"]) == (0, 2) == _overlap.overlap_by_enumeration(a, b, 2)


def test_random_small_cases_against_every_order():
    rng = random.Random(20261119)
    for _ in range(300):
        n = rng.randint(2, 9)
        idx = [f"f{i}" for i in range(n)]
        a = pd.Series([rng.choice([0, 0, 1, 1, 1, 0.5]) for _ in idx], index=idx)
        b = pd.Series([rng.choice([0, 0, 1, 1, 1, 0.5]) for _ in idx], index=idx)
        k = rng.randint(1, n)
        r = _overlap.overlap_bounds(a, b, k)
        assert (r["lowest"], r["highest"]) == _overlap.overlap_by_enumeration(a, b, k)
