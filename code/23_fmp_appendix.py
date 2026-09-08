#!/usr/bin/env python3
"""
23_fmp_appendix.py -- the appendix the design chat asked for, 8 September 2026.

Computes, entirely from the local verified copy and with no API access:

  1. NEW C2 by year   share of removed tickers that appear on the delisted-companies
                      list whose price series runs to within 10 trading days of the
                      delisting date recorded there. Plus two context shares that are
                      reported but are not gates.
  2. C3 by year       share of a year's members whose market-cap rows cover at least
                      90% of their membership months in that year. By year, not decade:
                      a decade is too coarse to bind.
  3. Two windows      the returns window and the market-cap window, each by its own rule.
  4. PARA-class       two detectors for reused tickers across the whole union.
  5. Repairs nothing. Every list is reported and left alone.

Usage:
    python3 23_fmp_appendix.py "/path/to/FMP extraction 2026-09"
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

CURRENT_SIZE_TOLERANCE = 10      # year-end count within 10 of the current list
ROLLING_WINDOW_YEARS   = 3
ROLLING_MIN_ROWS       = 24
C2_MIN                 = 90.0    # per cent
C3_MEMBER_MIN          = 90.0    # per cent of members
C3_MONTH_MIN           = 0.90    # fraction of a member's months in that year
DELIST_TOLERANCE_DAYS  = 10      # trading days


def sanitise(s: str) -> str:
    return re.sub(r'[/\\:*?"<>|]', '_', s)


class Store:
    """Reads the raw tree. Merges date-window chunks and de-duplicates by date."""

    def __init__(self, root: Path):
        self.root = root
        self.raw = root / 'raw'
        if not self.raw.is_dir():
            sys.exit(f'No raw/ directory under {root}')

    def rows(self, endpoint: str, sym: str | None = None):
        d = self.raw / endpoint
        if not d.is_dir():
            return []
        if sym is None:
            paths = sorted(d.glob('*.json.gz'))
        else:
            s = sanitise(sym)
            paths = [p for p in [d / f'{s}.json.gz'] if p.exists()]
            paths += sorted(d.glob(f'{s}__[0-9]*__[0-9]*.json.gz'))
        # De-duplicate by date only when reading ONE symbol across its date windows.
        # Reading a whole directory (sym=None) collects different records that legitimately
        # share a date — constituent changes, delistings — and must not be collapsed.
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

    def dates(self, endpoint: str, sym: str) -> list[str]:
        return sorted({r['date'][:10] for r in self.rows(endpoint, sym)
                       if isinstance(r, dict) and isinstance(r.get('date'), str)})

    def one(self, endpoint: str, sym: str):
        r = self.rows(endpoint, sym)
        return r[0] if r else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('root', help='the FMP extraction 2026-09 folder')
    args = ap.parse_args()
    root = Path(args.root).expanduser().resolve()
    S = Store(root)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # The cache from _appendix_prep.py: last price date, market-cap year-months and the
    # three profile fields, per symbol. Parsing 11,000 files for those costs minutes;
    # reading them from here costs nothing. Required — run the prep first.
    cache_path = root / '_appendix_cache.json'
    if not cache_path.exists():
        sys.exit(f'No {cache_path.name}. Run _appendix_prep.py until it prints DONE first.')
    C = json.loads(cache_path.read_text())
    LAST_PX = C.get('last_px', {})
    MCAP_MONTHS = {k: set(v) for k, v in C.get('mcap_months', {}).items()}
    PROFILE = C.get('profile', {})

    # ---- inputs -----------------------------------------------------------
    cur = S.rows('sp500_current')
    hist = S.rows('sp500_history')
    if not cur or not hist:
        sys.exit('Constituent files not found. Expected raw/sp500_current and raw/sp500_history.')

    CURRENT = {r['symbol'].strip() for r in cur if r.get('symbol')}
    hist_dates = sorted(r['date'] for r in hist if r.get('date'))
    Y0, Y1 = 1957, int(hist_dates[-1][:4])

    per_year = defaultdict(int)
    for d in hist_dates:
        per_year[int(d[:4])] += 1

    # The delisted list: block 1d's paginated pull, falling back to block 0's single page.
    delisted = S.rows('delisted_companies_paged') or S.rows('delisted_companies')
    delist_date = {}
    for r in delisted:
        if not isinstance(r, dict):
            continue
        sym, dd = (r.get('symbol') or '').strip(), r.get('delistedDate')
        if sym and dd and (sym not in delist_date or dd < delist_date[sym]):
            delist_date[sym] = dd[:10]      # earliest recorded delisting for a ticker

    # Removed tickers and the date each left the index.
    removal_date = {}
    for r in hist:
        t = (r.get('removedTicker') or '').strip()
        if t and r.get('date') and (t not in removal_date or r['date'] > removal_date[t]):
            removal_date[t] = r['date'][:10]
    removed = sorted(removal_date)

    # Trading calendar, measured rather than approximated from weekdays.
    cal = S.dates('b2_price_eod_full', '^GSPC') or S.dates('b2_price_eod_full', 'SPY')
    cal_idx = {d: i for i, d in enumerate(cal)}

    def sessions_between(a: str, b: str) -> int:
        if cal_idx:
            lo, hi = min(a, b), max(a, b)
            ia = next((cal_idx[d] for d in cal if d >= lo), None)
            ib = next((cal_idx[d] for d in cal if d >= hi), None)
            if ia is not None and ib is not None:
                return abs(ib - ia)
        return abs((date.fromisoformat(b) - date.fromisoformat(a)).days) * 5 // 7

    L: list[str] = []
    say = L.append

    say(f'# Appendix to the handover-back — {today}')
    say('')
    say('Computed from the local verified copy. No API access; nothing here needed the')
    say('subscription. Answers the four decisions of the design chat\'s reply of 8 September.')
    say('')
    say(f'- source: `{root}`')
    say(f'- trading calendar: {"^GSPC" if cal else "none — weekday approximation used"}, '
        f'{len(cal)} sessions')
    say(f'- delisted-companies list: {len(delisted)} rows, {len(delist_date)} distinct tickers')
    say('')

    # ---- 1. NEW C2 --------------------------------------------------------
    say('## 1. New C2, by year')
    say('')
    say('Of the removed tickers that appear on the delisted-companies list, the share whose')
    say('price series runs to within 10 trading days of the delisting date recorded there.')
    say('This is the gate. The two shares beneath it are context and are not gates.')
    say('')

    on_list = [t for t in removed if t in delist_date]
    with_px = [t for t in removed if LAST_PX.get(t)]

    by_year = defaultdict(lambda: {'n': 0, 'ok': 0, 'nopx': 0})
    detail_miss = []
    for t in on_list:
        dd = delist_date[t]
        y = int(dd[:4])
        by_year[y]['n'] += 1
        last = LAST_PX.get(t)
        if not last:
            by_year[y]['nopx'] += 1
            detail_miss.append((t, dd, None))
            continue
        gap = sessions_between(last, dd)
        if gap <= DELIST_TOLERANCE_DAYS:
            by_year[y]['ok'] += 1
        else:
            detail_miss.append((t, dd, last))

    say('| year | on delisted list | runs to delisting | % | ≥90%? |')
    say('|---|---:|---:|---:|---|')
    c2_by_year: dict[int, float] = {}
    for y in sorted(by_year):
        v = by_year[y]
        pct = 100.0 * v['ok'] / max(1, v['n'])
        c2_by_year[y] = pct
        say(f"| {y} | {v['n']} | {v['ok']} | {pct:.1f}% | {'yes' if pct >= C2_MIN else 'no'} |")
    say('')
    tot_ok = sum(v['ok'] for v in by_year.values())
    tot_n = sum(v['n'] for v in by_year.values())
    say(f'- overall: **{tot_ok} of {tot_n} ({100.0*tot_ok/max(1,tot_n):.1f}%)**')
    say('')
    say('### The failures split in two directions, and they mean different things')
    say('')
    late, early = [], []
    for t, dd, last in detail_miss:
        if not last:
            continue
        gap = (date.fromisoformat(dd) - date.fromisoformat(last)).days
        (early if gap > 0 else late).append((abs(gap), t, dd, last))
    early.sort(reverse=True); late.sort(reverse=True)
    say(f'- **series stops BEFORE the delisting date: {len(early)}** — a coverage gap. '
        'FMP holds a delisting date it has no prices up to.')
    say(f'- **series continues AFTER the delisting date: {len(late)}** — not a coverage gap. '
        'A price series that keeps going past its own delisting is the signature of a '
        'ticker being reused by a different company, which is the PARA class in section 4 '
        'arriving by a second route.')
    say('')
    if early:
        say('Worst stops-early, days:')
        say('')
        say('| ticker | delisted | last price | days short |')
        say('|---|---|---|---:|')
        for g, t, dd, last in early[:12]:
            say(f'| `{t}` | {dd} | {last} | {g} |')
        say('')
    if late:
        say('Worst continues-after, days — check each for reuse before using the series:')
        say('')
        say('| ticker | delisted | last price | days past |')
        say('|---|---|---|---:|')
        for g, t, dd, last in late[:12]:
            say(f'| `{t}` | {dd} | {last} | {g} |')
        say('')
    say('### Context, not gates')
    say('')
    say(f'- removed tickers in the constituent history: **{len(removed)}**')
    say(f'- of those, appearing on the delisted-companies list: **{len(on_list)} '
        f'({100.0*len(on_list)/max(1,len(removed)):.1f}%)** — the rest left the index '
        f'without delisting, which is why the superseded C2 could not pass')
    say(f'- of those, with any price rows: **{len(with_px)} '
        f'({100.0*len(with_px)/max(1,len(removed)):.1f}%)**')
    say('')

    # ---- 2. C3 by year ----------------------------------------------------
    say('## 2. C3, by year')
    say('')

    def membership_months(sym: str) -> set[str]:
        adds = sorted(r['date'][:10] for r in hist
                      if (r.get('symbol') or '').strip() == sym and r.get('date'))
        rems = sorted(r['date'][:10] for r in hist
                      if (r.get('removedTicker') or '').strip() == sym and r.get('date'))
        spans = []
        if sym in CURRENT:
            spans.append((adds[-1] if adds else hist_dates[0][:10], today))
        for rem in rems:
            prior = [a for a in adds if a < rem]
            spans.append((prior[-1] if prior else hist_dates[0][:10], rem))
        months = set()
        for a, b in spans:
            ya, ma = int(a[:4]), int(a[5:7])
            yb, mb = int(b[:4]), int(b[5:7])
            while (ya, ma) <= (yb, mb):
                months.add(f'{ya:04d}-{ma:02d}')
                ma += 1
                if ma > 12:
                    ma, ya = 1, ya + 1
        return months

    union = sorted({r['symbol'].strip() for r in hist
                    if isinstance(r.get('symbol'), str) and r['symbol'].strip()}
                   | {r['removedTicker'].strip() for r in hist
                      if isinstance(r.get('removedTicker'), str) and r['removedTicker'].strip()}
                   | CURRENT)

    year_members = defaultdict(int)
    year_covered = defaultdict(int)
    for sym in union:
        need = membership_months(sym)
        if not need:
            continue
        have = MCAP_MONTHS.get(sym, set())
        by_y = defaultdict(set)
        for m in need:
            by_y[int(m[:4])].add(m)
        for y, months in by_y.items():
            year_members[y] += 1
            if len(months & have) / len(months) >= C3_MONTH_MIN:
                year_covered[y] += 1

    say('A decade is too coarse to bind: 81.3% for the 2010s could be 60% early and 95% late,')
    say('and those are different windows.')
    say('')
    say('| year | members | ≥90% month coverage | % | ≥90%? |')
    say('|---|---:|---:|---:|---|')
    c3_by_year: dict[int, float] = {}
    for y in sorted(year_members):
        if y < 1990:
            continue
        n, ok = year_members[y], year_covered[y]
        pct = 100.0 * ok / max(1, n)
        c3_by_year[y] = pct
        say(f"| {y} | {n} | {ok} | {pct:.1f}% | {'yes' if pct >= C3_MEMBER_MIN else 'no'} |")
    say('')

    # ---- 3. the two windows ----------------------------------------------
    say('## 3. The two windows')
    say('')

    members_at = {}
    m = set(CURRENT)
    rows_desc = sorted([(r['date'][:10], (r.get('symbol') or '').strip(),
                         (r.get('removedTicker') or '').strip())
                        for r in hist if r.get('date')], reverse=True)
    i = 0
    for y in range(Y1, 1989, -1):
        ye = f'{y}-12-31'
        while i < len(rows_desc) and rows_desc[i][0] > ye:
            _, add, rem = rows_desc[i]
            if add:
                m.discard(add)
            if rem:
                m.add(rem)
            i += 1
        members_at[y] = len(m)

    def count_ok(y): return abs(members_at.get(y, 0) - len(CURRENT)) <= CURRENT_SIZE_TOLERANCE

    def density_ok_from(start):
        if any(per_year.get(y, 0) == 0 for y in range(start, Y1 + 1)):
            return False
        for y in range(start, Y1 - ROLLING_WINDOW_YEARS + 2):
            if sum(per_year.get(k, 0) for k in range(y, y + ROLLING_WINDOW_YEARS)) < ROLLING_MIN_ROWS:
                return False
        return True

    returns_window = None
    for start in range(1990, Y1 + 1):
        if (all(count_ok(y) for y in range(start, Y1 + 1))
                and density_ok_from(start)
                and all(c2_by_year.get(y, 0.0) >= C2_MIN
                        for y in range(start, Y1 + 1) if y in c2_by_year)):
            returns_window = start
            break

    mcap_window = None
    for start in range(1990, Y1 + 1):
        if all(c3_by_year.get(y, 0.0) >= C3_MEMBER_MIN
               for y in range(start, Y1 + 1) if y in c3_by_year):
            mcap_window = start
            break

    say('| window | rule | starts |')
    say('|---|---|---|')
    say(f'| **returns** | year-end count within {CURRENT_SIZE_TOLERANCE} of {len(CURRENT)}; '
        f'rolling {ROLLING_WINDOW_YEARS}-year ≥{ROLLING_MIN_ROWS} rows, no zero year; '
        f'new C2 ≥{C2_MIN:.0f}% | **{returns_window or "no solution"}** |')
    say(f'| **market cap** | ≥{C3_MEMBER_MIN:.0f}% of members with ≥90% month coverage '
        f'| **{mcap_window or "no solution"}** |')
    say('')
    say('Equal-weighted results run on the returns window. Anything value-weighted or')
    say('benchmark-relative runs on the market-cap window. Both are named constants in')
    say('Project B and both appear in the same sentence as every number computed under them.')
    say('')
    if returns_window:
        silent = [y for y in range(returns_window, Y1 + 1) if y not in c2_by_year]
        if silent:
            say(f'**Read the returns window with this caveat.** {len(silent)} years inside it '
                f'have no removed ticker on the delisted list at all '
                f'({", ".join(str(y) for y in silent)}), so the new C2 imposes no constraint '
                'on them. They pass vacuously rather than on evidence. The window is as '
                'strong as the years that carry data, not as the count of years that pass.')
            say('')
    if mcap_window and (Y1 - mcap_window + 1) < 15:
        say(f'**The market-cap window is {Y1 - mcap_window + 1} years, under 15.** The')
        say('authorised fallback applies: reconstruct market capitalisation as price times')
        say('`weightedAverageShsOut` from the income statements already pulled, quarterly,')
        say('forward-filled to month ends, used only where FMP\'s own market cap is missing.')
        say('Validate first on symbol-months where both exist: median absolute relative')
        say('difference below 2% and correlation above 0.99. Where it fails validation it is')
        say('not used and the window stands as measured. Project B\'s work, not extraction\'s.')
        say('')

    # ---- 4. the PARA-class detector ---------------------------------------
    say('## 4. Reused tickers: the PARA-class detector')
    say('')
    say('Two detectors over the whole union. A ticker cannot have been added to the index')
    say('before the company it now points at existed.')
    say('')

    first_seen = {}
    for r in hist:
        d = (r.get('date') or '')[:10]
        for f in ('symbol', 'removedTicker'):
            t = (r.get(f) or '').strip()
            if t and d and (t not in first_seen or d < first_seen[t]):
                first_seen[t] = d

    cur_cik = {r['symbol'].strip(): str(r.get('cik') or '').lstrip('0')
               for r in cur if r.get('symbol')}

    # The history's own name for each ticker, most recent mention.
    hist_name = {}
    for r in sorted(hist, key=lambda r: r.get('date') or ''):
        a, rm = (r.get('symbol') or '').strip(), (r.get('removedTicker') or '').strip()
        if a and r.get('addedSecurity'):
            hist_name[a] = r['addedSecurity']
        if rm and r.get('removedSecurity'):
            hist_name[rm] = r['removedSecurity']

    STOP = {'inc', 'corp', 'corporation', 'co', 'company', 'companies', 'plc', 'ltd',
            'limited', 'group', 'holding', 'holdings', 'the', 'class', 'a', 'b', 'c',
            'common', 'stock', 'etf', 'sa', 'nv', 'ag', 'lp', 'trust', 'international',
            'and', 'of', 'new', 'series', 'shares', 'fund', 'reit', 'plc.', 'sab', 'de',
            'cv', 'ab', 'as', 'spa', 'nva'}

    def toks(name):
        return {w for w in re.sub(r'[^a-z0-9 ]', ' ', (name or '').lower()).split()
                if w and w not in STOP and len(w) > 1}

    flag_name, flag_ipo, flag_cik = [], [], []
    for sym in union:
        p = PROFILE.get(sym)
        if not isinstance(p, dict):
            continue
        pname = p.get('companyName') or ''
        hname = hist_name.get(sym) or ''
        tp, th = toks(pname), toks(hname)
        name_clash = bool(tp and th and not (tp & th))
        if name_clash:
            flag_name.append((sym, hname[:38], pname[:38], first_seen.get(sym, '')))
        ipo = (p.get('ipoDate') or '')[:10]
        fs = first_seen.get(sym)
        if ipo and fs and ipo > fs:
            flag_ipo.append((sym, fs, ipo, pname[:40], name_clash))
        pc = str(p.get('cik') or '').lstrip('0')
        cc = cur_cik.get(sym)
        if cc and pc and cc != pc:
            flag_cik.append((sym, cc, pc, pname[:40]))

    say('### Detector A: the history\'s name and the profile\'s name share no word')
    say('')
    say('A name clash on its own is weak: it fires on rebrands and abbreviations of the same')
    say('company — Apache to APA, Allegheny Technologies to ATI, Brinks to Brink\'s — as well')
    say('as on genuine reuses. So it is reported in two tiers, split by whether independent')
    say('evidence corroborates it.')
    say('')

    FUNDISH = ('etf', 'fund', 'trust', 'shares', 'index', 'portfolio', 'ucits')
    continues_after = {t for _, t, _, _ in late}

    tier1, tier2 = [], []
    for sy, hn, pn, fs in sorted(flag_name):
        why = []
        if sy in continues_after:
            why.append('price runs past its delisting')
        if any(w in pn.lower() for w in FUNDISH) and not any(w in hn.lower() for w in FUNDISH):
            why.append('profile is a fund or ETF')
        (tier1 if why else tier2).append((sy, hn, pn, fs, '; '.join(why)))

    say(f'**Tier 1, corroborated: {len(tier1)}.** A name clash plus at least one of — the')
    say('price series continuing past its own delisting date, or an operating company in the')
    say('history replaced by a fund or ETF in the profile. These are the ones to act on.')
    say('')
    if tier1:
        say('| symbol | name in history | name in profile | first in history | corroboration |')
        say('|---|---|---|---|---|')
        for sy, hn, pn, fs, why in tier1:
            say(f'| `{sy}` | {hn} | {pn} | {fs} | {why} |')
    else:
        say('None.')
    say('')
    say(f'**Tier 2, name clash alone: {len(tier2)}.** Contains genuine reuses and ordinary')
    say('rebrands in unknown proportion, and is not separable without a per-name judgement.')
    say('Listed so nothing is hidden, but it is a queue to work through rather than a finding.')
    say('')
    if tier2:
        say('| symbol | name in history | name in profile | first in history |')
        say('|---|---|---|---|')
        for sy, hn, pn, fs, _ in tier2:
            say(f'| `{sy}` | {hn} | {pn} | {fs} |')
    say('')

    say('### Detector B: profile IPO date after the ticker\'s first appearance in the history')
    say('')
    ipo_floor = defaultdict(int)
    for pp in PROFILE.values():
        if pp.get('ipoDate'):
            ipo_floor[pp['ipoDate']] += 1
    top_floor = sorted(ipo_floor.items(), key=lambda kv: -kv[1])[:3]
    say(f'**Read this one with caution: it is mostly artifact.** FMP\'s `ipoDate` is often')
    say('the start of its own price history rather than a listing date. The most common')
    say('values across all profiles are '
        + ', '.join(f'`{d}` ({n} profiles)' for d, n in top_floor) + ', which are floors,')
    say('not IPOs. Abbott and Archer-Daniels both carry 1980-03-17 and neither is a reuse.')
    say('')
    both = [f for f in flag_ipo if f[4]]
    say(f'- flagged by this test alone: **{len(flag_ipo)}** — too many to act on')
    say(f'- flagged by this test AND the name test: **{len(both)}** — these are the ones')
    say('  worth looking at, and they are listed below')
    say('')
    if both:
        say('| symbol | first in history | profile ipoDate | profile company |')
        say('|---|---|---|---|')
        for sy, fs, ipo, nm, _ in sorted(both):
            say(f'| `{sy}` | {fs} | {ipo} | {nm} |')
    say('')

    say('### Detector C: current list CIK disagrees with the profile CIK')
    say('')
    if not flag_cik:
        say('None flagged.')
    else:
        say('| symbol | CIK in current list | CIK in profile | profile company |')
        say('|---|---|---|---|')
        for s, cc, pc, nm in sorted(flag_cik):
            say(f'| `{s}` | {cc} | {pc} | {nm} |')
    say('')
    say(f'**{len(flag_cik)} flagged.**')
    say('')
    no_profile = [s for s in union if s not in PROFILE]
    say('Reported, not repaired. No detector can see a reuse where the profile carries the')
    say('older company\'s name and dates, and none can see one for a symbol with no')
    say(f'profile at all — **{len(no_profile)} of {len(union)} union symbols returned none**.')
    say('Both counts are floors, not counts.')
    say('')

    # ---- write ------------------------------------------------------------
    out = root / f'APPENDIX_handover_back_{today}.md'
    if out.exists():
        out = out.with_name(out.stem + datetime.now(timezone.utc).strftime('__%H%M%SZ') + '.md')
    out.write_text('\n'.join(L))

    print('\n'.join(L))
    print('\n\nwritten to:', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
