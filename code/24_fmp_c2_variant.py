#!/usr/bin/env python3
"""
24_fmp_c2_variant.py -- does the returns window have a solution once ticker reuse is
separated from coverage?

23_fmp_appendix.py reports the new C2 as the design chat pre-committed it, and it has no
solution: 2026 itself scores 63.3%, so no start year can produce a window in which every
later year clears 90%.

But the failures do not all mean the same thing. A series that STOPS BEFORE its delisting
date is a coverage gap -- FMP holds a delisting date it has no prices up to. A series that
CONTINUES AFTER its delisting date is not a coverage gap at all: the prices are there, and
past the delisting they belong to a different company. That is ticker reuse, the PARA class.

So this reports the same measure a second way, counting only coverage as failure, and asks
whether the window has a solution under it. It changes no ruling. It gives the design chat
the number it needs to decide whether the new C2 is a coverage gate that reuse is jamming.

    python3 24_fmp_c2_variant.py "<root>"
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

C2_MIN = 90.0
DELIST_TOLERANCE_DAYS = 10


def sanitise(s: str) -> str:
    return re.sub(r'[/\\:*?"<>|]', '_', s)


def rows(raw: Path, endpoint: str, sym: str | None = None):
    d = raw / endpoint
    if not d.is_dir():
        return []
    if sym is None:
        paths = sorted(d.glob('*.json.gz'))
    else:
        s = sanitise(sym)
        paths = [p for p in [d / f'{s}.json.gz'] if p.exists()]
        paths += sorted(d.glob(f'{s}__[0-9]*__[0-9]*.json.gz'))
    dedupe = sym is not None
    out, seen = [], set()
    for p in paths:
        try:
            data = json.loads(gzip.open(p, 'rb').read())
        except Exception:
            continue
        for r in (data if isinstance(data, list) else [data]):
            k = r.get('date') if isinstance(r, dict) else None
            if dedupe and k is not None:
                if k in seen:
                    continue
                seen.add(k)
            out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    args = ap.parse_args()
    root = Path(args.root).expanduser().resolve()
    raw = root / 'raw'

    cache = json.loads((root / '_appendix_cache.json').read_text())
    LAST_PX = cache.get('last_px', {})

    hist = rows(raw, 'sp500_history')
    delisted = rows(raw, 'delisted_companies_paged') or rows(raw, 'delisted_companies')
    delist_date = {}
    for r in delisted:
        if not isinstance(r, dict):
            continue
        sym, dd = (r.get('symbol') or '').strip(), r.get('delistedDate')
        if sym and dd and (sym not in delist_date or dd < delist_date[sym]):
            delist_date[sym] = dd[:10]

    removal_date = {}
    for r in hist:
        t = (r.get('removedTicker') or '').strip()
        if t and r.get('date') and (t not in removal_date or r['date'] > removal_date[t]):
            removal_date[t] = r['date'][:10]
    removed = sorted(removal_date)

    cal = sorted({r['date'][:10] for r in rows(raw, 'b2_price_eod_full', '^GSPC')
                  if isinstance(r, dict) and isinstance(r.get('date'), str)})
    cal_idx = {d: i for i, d in enumerate(cal)}

    def sessions_between(a: str, b: str) -> int:
        if cal_idx:
            lo, hi = min(a, b), max(a, b)
            ia = next((cal_idx[d] for d in cal if d >= lo), None)
            ib = next((cal_idx[d] for d in cal if d >= hi), None)
            if ia is not None and ib is not None:
                return abs(ib - ia)
        return abs((date.fromisoformat(b) - date.fromisoformat(a)).days) * 5 // 7

    on_list = [t for t in removed if t in delist_date]

    by = defaultdict(lambda: {'n': 0, 'ok': 0, 'late': 0, 'early': 0, 'nopx': 0})
    for t in on_list:
        dd = delist_date[t]
        y = int(dd[:4])
        v = by[y]
        v['n'] += 1
        last = LAST_PX.get(t)
        if not last:
            v['nopx'] += 1
            continue
        if sessions_between(last, dd) <= DELIST_TOLERANCE_DAYS:
            v['ok'] += 1
        elif date.fromisoformat(last) > date.fromisoformat(dd):
            v['late'] += 1
        else:
            v['early'] += 1

    years = sorted(by)
    L = []
    say = L.append
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    say(f'# Addendum to the appendix — {today}')
    say('')
    say('## Does the returns window have a solution once reuse is separated from coverage?')
    say('')
    say('The new C2 as pre-committed has no solution. This asks the same question a second')
    say('way, counting a series that continues past its own delisting date as what it is —')
    say('ticker reuse, not a coverage gap. Nothing here overrides the ruling; it is the')
    say('number the design chat needs in order to decide whether to keep C2 as a window gate.')
    say('')
    say('| year | on list | runs to delisting | continues after (reuse) | stops early (gap) | '
        'no price rows | C2 as ruled | C2, coverage only |')
    say('|---|---:|---:|---:|---:|---:|---:|---:|')
    ruled, coverage = {}, {}
    for y in years:
        v = by[y]
        n = max(1, v['n'])
        r_pct = 100.0 * v['ok'] / n
        # Coverage-only: a reuse case is removed from the denominator rather than passed.
        # It is not evidence that coverage is good; it is evidence the ticker is not one
        # company. Passing it would flatter the measure.
        den = v['n'] - v['late']
        c_pct = 100.0 * v['ok'] / den if den > 0 else float('nan')
        ruled[y], coverage[y] = r_pct, c_pct
        cs = 'n/a' if den <= 0 else f'{c_pct:.1f}%'
        say(f"| {y} | {v['n']} | {v['ok']} | {v['late']} | {v['early']} | {v['nopx']} | "
            f"{r_pct:.1f}% | {cs} |")
    say('')

    tot = {k: sum(by[y][k] for y in years) for k in ('n', 'ok', 'late', 'early', 'nopx')}
    den = tot['n'] - tot['late']
    say(f"- overall as ruled: **{tot['ok']} of {tot['n']} "
        f"({100.0*tot['ok']/max(1,tot['n']):.1f}%)**")
    say(f"- overall, coverage only: **{tot['ok']} of {den} "
        f"({100.0*tot['ok']/max(1,den):.1f}%)** — {tot['late']} reuse cases removed from "
        f"the denominator, {tot['early']} genuine coverage gaps and {tot['nopx']} with no "
        f"price rows left in it")
    say('')

    def first_year_from_which_all_pass(score: dict) -> int | None:
        for start in years:
            later = [y for y in years if y >= start]
            if all(score[y] >= C2_MIN for y in later
                   if not (score[y] != score[y])):          # skip NaN
                return start
        return None

    a = first_year_from_which_all_pass(ruled)
    b = first_year_from_which_all_pass(coverage)
    say('## The C2 leg of the returns window')
    say('')
    say('| measure | earliest year from which every later year clears 90% |')
    say('|---|---|')
    say(f'| C2 as ruled | **{a if a else "no solution"}** |')
    say(f'| C2, coverage only | **{b if b else "no solution"}** |')
    say('')
    if b:
        say(f'The other two legs are already satisfied from 1998 and 1969, so under the')
        say(f'coverage-only reading the returns window would start in **{max(b, 1998)}**.')
    say('')
    say('Worst years under the coverage-only reading, which are the ones to look at before')
    say('deciding:')
    say('')
    worst = sorted((coverage[y], y) for y in years
                   if by[y]['n'] - by[y]['late'] > 0 and coverage[y] < C2_MIN)
    if worst:
        say('| year | C2 coverage only | on list | reuse removed | gaps | no price rows |')
        say('|---|---:|---:|---:|---:|---:|')
        for c, y in worst[:12]:
            v = by[y]
            say(f"| {y} | {c:.1f}% | {v['n']} | {v['late']} | {v['early']} | {v['nopx']} |")
    else:
        say('None. Every year with a non-empty denominator clears 90%.')
    say('')
    say('The denominators are small — most years carry fewer than 30 removed tickers that')
    say('reach the delisted list at all — so a single symbol moves a year by several points.')
    say('That is a property of the measure, not of the pull, and it is worth saying out loud')
    say('before anyone reads a year-on-year pattern into the column.')

    out = root / f'ADDENDUM_c2_variant_{today}.md'
    if out.exists():
        stamp = datetime.now(timezone.utc).strftime('%H%M%SZ')
        out = out.with_name(out.stem + f'__{stamp}.md')
        print(f'target existed; writing beside it as {out.name}')
    out.write_text('\n'.join(L) + '\n')
    print('\n'.join(L))
    print(f'\n[written to {out}]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
