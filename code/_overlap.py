"""
The overlap of two top-k sets when firms tie at the cut.

A top-quintile overlap counts the firms in the top k of one release that are
also in the top k of the other. When several firms share the value at the k-th
place, the top-k set is not one set: which of the tied firms take the places is
an order the data do not give, and a figure computed from one order is not a
result. Fossil share is the case here: dozens of firms sit at a share of exactly
1, so the k-th largest value is 1 and the "top quintile" is any k of them.

overlap_bounds gives the lowest and the highest overlap that the ties at the two
cuts allow, counting the ties in both releases, with the number of firms tied at
each cut and the places they compete for. Where the two bounds are equal the
overlap is one figure. The bounds are exact: test_overlap.py checks them against
every order on made-up cases. Added 19 November 2026, after the results were
known; the scripts that print an overlap (10, 13 and 15) print these bounds.
"""

import itertools

import pandas as pd


def top_cut(s, k):
    """The k-th largest value of s, the firms surely in the top k (above that
    value), the firms tied at it, and the number of places the tied firms
    compete for. s is a pandas Series with one value per firm, no NaN."""
    s = pd.Series(s).astype(float)
    if k < 1:
        raise ValueError("k must be at least 1")
    if s.isna().any():
        raise ValueError("the series carries NaN; drop them before the cut")
    k = min(k, len(s))
    cut = float(s.sort_values(ascending=False).iloc[k - 1])
    sure = set(s.index[s > cut])
    tied = set(s.index[s == cut])
    places = k - len(sure)
    return cut, sure, tied, places


def overlap_bounds(a, b, k):
    """The lowest and the highest number of firms common to the top k of a and
    the top k of b, over every order of the firms tied at the two cuts.

    a and b share their index. Returns a dict: lowest, highest, k, and for each
    release the cut value, the count surely in, the count tied at the cut and
    the places the tied compete for (cut_a, sure_a, tied_a, places_a, ...).
    The two "sure" sets are returned too, for lists of firms that moved
    whatever the order."""
    a, b = pd.Series(a), pd.Series(b)
    if not a.index.equals(b.index):
        raise ValueError("the two series must share their index")
    k = min(k, len(a))
    cut_a, sure_a, tied_a, m_a = top_cut(a, k)
    cut_b, sure_b, tied_b, m_b = top_cut(b, k)
    a0 = len(sure_a & sure_b)
    p = len(tied_a & sure_b)          # tied in a, surely in b
    x1 = len(sure_a & tied_b)         # surely in a, tied in b
    q = len(tied_a & tied_b)          # tied in both
    u_a = len(tied_a) - p - q         # tied in a, out of b whatever happens
    u_b = len(tied_b) - x1 - q
    highest, lowest = None, None
    for t_a in range(0, q + 1):
        # s_a, the tied-in-a firms taken from those surely in b, has a feasible range
        lo_a, hi_a = max(0, m_a - t_a - u_a), min(p, m_a - t_a)
        if lo_a > hi_a:
            continue
        for t_b in range(0, q + 1):
            lo_b, hi_b = max(0, m_b - t_b - u_b), min(x1, m_b - t_b)
            if lo_b > hi_b:
                continue
            up = a0 + hi_a + hi_b + min(t_a, t_b)
            down = a0 + lo_a + lo_b + max(0, t_a + t_b - q)
            highest = up if highest is None else max(highest, up)
            lowest = down if lowest is None else min(lowest, down)
    return {"lowest": lowest, "highest": highest, "k": k,
            "cut_a": cut_a, "sure_a": len(sure_a), "tied_a": len(tied_a), "places_a": m_a,
            "cut_b": cut_b, "sure_b": len(sure_b), "tied_b": len(tied_b), "places_b": m_b,
            "sure_set_a": sure_a, "sure_set_b": sure_b,
            "tied_set_a": tied_a, "tied_set_b": tied_b}


def overlap_by_enumeration(a, b, k):
    """The same two bounds by trying every order of the tied firms. For the
    test alone: it enumerates every choice of the tied firms and is slow."""
    a, b = pd.Series(a), pd.Series(b)
    k = min(k, len(a))
    _, sure_a, tied_a, m_a = top_cut(a, k)
    _, sure_b, tied_b, m_b = top_cut(b, k)
    counts = []
    for ca in itertools.combinations(sorted(tied_a, key=str), m_a):
        top_a = sure_a | set(ca)
        for cb in itertools.combinations(sorted(tied_b, key=str), m_b):
            counts.append(len(top_a & (sure_b | set(cb))))
    return min(counts), max(counts)


def has_ties(r):
    """True when a tie at either cut leaves the top-k set open."""
    return r["tied_a"] > r["places_a"] or r["tied_b"] > r["places_b"]


def overlap_text(r, name_a="March 2025", name_b="August 2026"):
    """One line: the overlap as one figure where the ties leave one, as a
    range with the tie counts where they do not."""
    k = r["k"]
    if not has_ties(r):
        return f"{r['lowest']} of {k} ({100 * r['lowest'] / k:.1f}%), no tie at either cut"
    parts = []
    if r["tied_a"] > r["places_a"]:
        parts.append(f"{r['tied_a']} firms tied at {r['cut_a']:g} for {r['places_a']} "
                     f"place{'s' if r['places_a'] != 1 else ''} in {name_a}")
    if r["tied_b"] > r["places_b"]:
        parts.append(f"{r['tied_b']} firms tied at {r['cut_b']:g} for {r['places_b']} "
                     f"place{'s' if r['places_b'] != 1 else ''} in {name_b}")
    return (f"{r['lowest']} to {r['highest']} of {k} "
            f"({100 * r['lowest'] / k:.1f}% to {100 * r['highest'] / k:.1f}%) "
            f"over every order of the firms tied at the cut: " + "; ".join(parts))


if __name__ == "__main__":
    # A self-check with no test runner: the bounds against every order on a
    # made-up case, then on random small cases with many ties.
    import random
    a = pd.Series([1, 1, 1, 1, 0.5, 0.5, 0.2, 0, 0], index=list("abcdefghi"))
    b = pd.Series([1, 0.5, 1, 0.2, 1, 1, 0.5, 0, 0], index=list("abcdefghi"))
    r = overlap_bounds(a, b, 3)
    assert (r["lowest"], r["highest"]) == overlap_by_enumeration(a, b, 3), r
    rng = random.Random(20261119)
    for case in range(300):
        n = rng.randint(2, 9)
        idx = [f"f{i}" for i in range(n)]
        va = pd.Series([rng.choice([0, 0, 1, 1, 1, 0.5]) for _ in idx], index=idx)
        vb = pd.Series([rng.choice([0, 0, 1, 1, 1, 0.5]) for _ in idx], index=idx)
        k = rng.randint(1, n)
        r = overlap_bounds(va, vb, k)
        assert (r["lowest"], r["highest"]) == overlap_by_enumeration(va, vb, k), (va, vb, k, r)
    print("overlap bounds: the made-up case and 300 random cases agree with every order")
