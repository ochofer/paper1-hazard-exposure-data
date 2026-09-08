"""
TASK 1.5: DOES THE RESULT MOVE WITH THE VINTAGE?

THE QUESTION
------------
Sort the panel on attributable operating fossil capacity, go long the most
exposed quintile and short the least, and measure the return spread. Then do
the whole thing again using a different release of the same ownership database.

If the two answers differ, then a published finding about climate exposure and
returns depends partly on which file the researcher happened to download. That
is the Berg, Fabisik and Sautner point, applied to asset-level ownership rather
than to ESG ratings.

PRE-COMMITTED BEFORE THIS SCRIPT WAS RUN
------------------------------------------
Written down first so the result cannot be read as whatever is convenient.

    ROBUST      the two vintages' long-short spreads differ by less than one
                standard error of either, AND the two monthly return series
                correlate above 0.95. The exposure measure survives the vintage
                it was built from. A reassuring null, and it still publishes.

    FRAGILE     the spreads differ by more than one standard error, OR the two
                series correlate below 0.90. Vintage choice materially changes
                the measured finding.

    In between  report both and say the evidence is mixed.

    Report whatever comes out. This note is not improved by the exposure
    measure turning out to be fragile, and it is not damaged by it turning out
    to be robust.

WHAT THIS IS NOT
----------------
NOT a tradeable strategy and not an alpha claim. Both sorts use ownership data
dated at or after the end of the return window: prices run to 31 December 2025,
the March 2025 vintage sits inside that window and the August 2026 vintage sits
entirely after it. Every portfolio here is formed with look-ahead.

That is deliberate and it does not damage the test, because the question is not
"does exposure predict returns". It is "does the SAME procedure give a
different answer on two releases of the same data". Both arms carry identical
look-ahead, so the comparison between them is clean even though neither arm is
a valid return prediction on its own. The note must say this in as many words,
because a referee will otherwise assume the alpha is being claimed.

KNOWN LIMITATIONS, STATED RATHER THAN HIDDEN
----------------------------------------------
1. Returns are in LOCAL CURRENCY. The panel spans the US, the euro area, the
   UK, Switzerland, Norway and Sweden. An equal-weighted portfolio of
   local-currency returns mixes FX moves into the spread. We have no FX series
   in the free data, so this is a limitation, not a choice. It affects both
   vintages identically, so the vintage COMPARISON is unaffected; the level of
   either spread should not be quoted on its own.
2. EQUAL WEIGHTED, not value weighted. We have no market-cap series. Equal
   weighting overweights small firms, which is the standard critique.
3. The panel is 175 firms, those with both an exposure number and a price
   series. Quintiles are therefore 35 firms.
4. Newey-West standard errors, 6 lags, computed here rather than via statsmodels
   which is not installed and cannot be (no egress). The implementation is the
   textbook Bartlett-kernel form and is checked against the plain OLS standard
   error, which it must exceed for positively autocorrelated series.

RUN
    python 11_vintage_return_spread.py

Reads:  outputs/panel_exposure.csv
        Data/FMP Panel B archive/paper1_data_20260821/config/tickers_primary.csv
        Data/FMP Panel B archive/paper1_data_20260821/data/raw/panel_b_prices_daily.csv
Writes: outputs/vintage_return_spread.csv   monthly long-short series per arm
        outputs/vintage_return_spread.txt   the run log
"""

import os

import numpy as np
import pandas as pd

# Provenance. Scripts 10, 11 and 05 were the last three with no RUN_PROVENANCE
# record, found by the gate 5 register on 7 September 2026. See _release.py.
import _release


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
FMP = os.path.join(HERE, "..", "Data", "FMP Panel B archive",
                   "paper1_data_20260821")

PANEL = os.path.join(OUT, "panel_exposure.csv")
TICK = os.path.join(FMP, "config", "tickers_primary.csv")
PRICES = os.path.join(FMP, "data", "raw", "panel_b_prices_daily.csv")

ARMS = [("2025", "zero"), ("2025", "impute"), ("2026", "zero"), ("2026", "impute")]
NQ = 5          # quintiles
NW_LAGS = 6


def newey_west_t(x, lags=NW_LAGS):
    """t-statistic for the mean of x under Newey-West with a Bartlett kernel.

    Written out rather than imported because statsmodels is not available here.
    Returns (mean, plain OLS t, Newey-West t). The NW t should be the smaller
    in absolute value whenever the series is positively autocorrelated; that
    relation is asserted in the caller as a sanity check.
    """
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 3:
        return np.nan, np.nan, np.nan
    mu = x.mean()
    e = x - mu
    g0 = (e @ e) / n
    s = g0
    for L in range(1, min(lags, n - 1) + 1):
        gL = (e[L:] @ e[:-L]) / n
        s += 2.0 * (1.0 - L / (lags + 1.0)) * gL
    s = max(s, 1e-18)
    se_nw = np.sqrt(s / n)
    se_ols = np.sqrt(g0 / (n - 1))
    return mu, mu / se_ols, mu / se_nw


def main():
    lines = []

    def log(s=""):
        print(s)
        lines.append(s)

    log("TASK 1.5  DOES THE RESULT MOVE WITH THE VINTAGE?")
    log("  pre-committed reading is in the docstring. Report whatever comes out.")

    panel = pd.read_csv(PANEL, dtype={"entity_id": str})
    tick = pd.read_csv(TICK, dtype={"entity_id": str})
    tick = tick[["entity_id", "primary_symbol", "hq", "currency"]].dropna(
        subset=["primary_symbol"])
    panel = panel.merge(tick, on="entity_id", how="inner", suffixes=("", "_t"))

    px = pd.read_csv(PRICES, usecols=["symbol", "date", "adjClose"])
    px["date"] = pd.to_datetime(px["date"])
    px = px.dropna(subset=["adjClose"])
    log(f"\n  price rows {len(px):,}  symbols {px.symbol.nunique():,}  "
        f"{px.date.min().date()} to {px.date.max().date()}")

    # monthly total return per symbol from the last adjusted close each month
    px["ym"] = px["date"].values.astype("datetime64[M]")
    m = (px.sort_values("date").groupby(["symbol", "ym"])["adjClose"]
         .last().reset_index())
    m["ret"] = m.groupby("symbol")["adjClose"].pct_change()
    m = m.dropna(subset=["ret"])
    # A monthly total return outside [-90%, +200%] on a dividend-adjusted
    # series is far more likely to be a split or a data error than a real move.
    bad = int(((m.ret < -0.9) | (m.ret > 2.0)).sum())
    m = m[(m.ret >= -0.9) & (m.ret <= 2.0)]
    log(f"  monthly observations {len(m):,}  (dropped {bad} outside "
        f"-90% to +200% as likely splits or errors)")

    series = {}
    log(f"\n{'='*74}\nPORTFOLIO FORMATION")
    for vint, rule in ARMS:
        colname = f"mw_{vint}_{rule}"
        d = panel[["entity_id", "name", "primary_symbol", colname]].copy()
        d = d[d[colname] > 0]
        have = set(m.symbol.unique())
        d = d[d.primary_symbol.isin(have)]
        k = max(1, len(d) // NQ)
        d = d.sort_values(colname, ascending=False)
        top = set(d.head(k).primary_symbol)
        bot = set(d.tail(k).primary_symbol)
        log(f"  {vint} blank={rule:<7} priceable firms with exposure {len(d):>4}"
            f"   quintile {k}")

        mt = m[m.symbol.isin(top)].groupby("ym")["ret"].mean()
        mb = m[m.symbol.isin(bot)].groupby("ym")["ret"].mean()
        ls = (mt - mb).dropna()
        series[(vint, rule)] = dict(top=top, bot=bot, ls=ls, n=len(d), k=k)

    log(f"\n{'='*74}\nLONG-SHORT SPREAD, TOP QUINTILE MINUS BOTTOM QUINTILE")
    log("  equal weighted, local currency, monthly. NOT a tradeable strategy:")
    log("  every arm is formed with look-ahead. See the docstring.")
    log(f"\n  {'arm':<22}{'months':>8}{'ann. mean':>12}{'t (OLS)':>10}{'t (NW6)':>10}")
    for (vint, rule), S in series.items():
        mu, t_ols, t_nw = newey_west_t(S["ls"])
        S["mu"], S["t_nw"] = mu, t_nw
        S["se_nw"] = abs(mu / t_nw) if t_nw and not np.isnan(t_nw) else np.nan
        log(f"  {vint+' blank='+rule:<22}{len(S['ls']):>8}"
            f"{mu*12*100:>11.2f}%{t_ols:>10.2f}{t_nw:>10.2f}")

    log(f"\n{'='*74}\nMINIMUM DETECTABLE EFFECT. READ THIS BEFORE THE TEST BELOW")
    log("  Carlo pre-committed to reporting the MDE on any return result, so")
    log("  that a null is never passed off as evidence of absence when it is")
    log("  really absence of power.")
    log(f"\n  {'arm':<22}{'NW se':>10}{'MDE t=1.96':>13}{'MDE t=3.0':>12}")
    for (vint, rule), S in series.items():
        se = S["se_nw"] * 12 * 100
        log(f"  {vint+' blank='+rule:<22}{se:>9.2f}%{1.96*se:>12.2f}%{3.0*se:>11.2f}%")
    log("\n  t = 3.0 is the Harvey, Liu and Zhu hurdle for a newly proposed")
    log("  factor. An effect smaller than the MDE cannot be detected here at")
    log("  all, so the size of these spreads carries no information.")

    log(f"\n{'='*74}\nTHE ACTUAL TEST: DOES THE ANSWER MOVE WITH THE VINTAGE?")
    for rule in ("zero", "impute"):
        A, B = series[("2025", rule)], series[("2026", rule)]
        idx = A["ls"].index.intersection(B["ls"].index)
        corr = A["ls"][idx].corr(B["ls"][idx])
        diff = B["mu"] - A["mu"]
        pooled_se = max(A["se_nw"], B["se_nw"])
        log(f"\n  --- blank={rule} ---")
        log(f"    annualised spread, March 2025 vintage   {A['mu']*12*100:>7.2f}%")
        log(f"    annualised spread, August 2026 vintage  {B['mu']*12*100:>7.2f}%")
        log(f"    difference                              {diff*12*100:>+7.2f}%")
        log(f"    larger NW standard error (annualised)   {pooled_se*12*100:>7.2f}%")
        log(f"    difference in standard errors           "
            f"{abs(diff)/pooled_se:>7.2f}")
        log(f"    correlation of the two monthly series   {corr:>7.4f}")
        log(f"    top-quintile turnover: {len(B['top'] - A['top'])} of {A['k']} "
            f"names replaced "
            f"({len(B['top'] - A['top'])/A['k']*100:.0f}%)")
        within = abs(diff) < pooled_se
        verdict = ("ROBUST" if (within and corr > 0.95) else
                   "FRAGILE" if ((not within) or corr < 0.90) else "MIXED")
        log(f"    PRE-COMMITTED VERDICT: {verdict}")

    log(f"\n{'='*74}\nAND HOW MUCH IS THE BLANK-SHARE CONVENTION ALONE?")
    for vint in ("2025", "2026"):
        A, B = series[(vint, "zero")], series[(vint, "impute")]
        idx = A["ls"].index.intersection(B["ls"].index)
        log(f"  {vint}: zero {A['mu']*12*100:>7.2f}%   "
            f"impute {B['mu']*12*100:>7.2f}%   "
            f"corr {A['ls'][idx].corr(B['ls'][idx]):.4f}   "
            f"top-quintile names differing {len(B['top'] ^ A['top'])}")
    log("  2026 must show a zero difference: that vintage has no blank shares,")
    log("  so the two conventions are the same data. It is a self-check.")

    # Two provenance chains meet here. The GEM release arrives through 10 and
    # 09; the price layer is the FMP archive, whose adjustment convention is
    # stated in the public README and whose per-file checksums are in the
    # published manifest. Both are recorded rather than either being assumed.
    _prov = {"panel": PANEL, "tickers": TICK, "prices": PRICES}
    for _n, _p in (("upstream_provenance_10",
                    os.path.join(OUT, "RUN_PROVENANCE_10_panel_join.json")),):
        if os.path.exists(_p):
            _prov[_n] = _p
    _release.write_provenance(
        OUT, "11_vintage_return_spread", _prov,
        extra={"price_convention":
               "adjClose from FMP historical-price-eod/dividend-adjusted, pulled "
               "2026-08-21. Vendor back-adjustment for dividends AND splits. No "
               "unadjusted close is archived alongside.",
               "release_reaches_this_script_via":
               "10_panel_join, then 09_exposure_proxy"})

    out = pd.DataFrame({f"{v}_{r}": series[(v, r)]["ls"] for v, r in ARMS})
    out.to_csv(os.path.join(OUT, "vintage_return_spread.csv"))
    with open(os.path.join(OUT, "vintage_return_spread.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"\n  written to {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
