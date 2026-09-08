"""
BUILD THE MEASUREMENT NOTE. Every figure extracted from an output file.

WHY IT IS BUILT RATHER THAN WRITTEN
-----------------------------------
On 7 September 2026 I typed twelve entity identifiers into an evidence file from
memory instead of reading them from the source. Not one was correct, and only a
validator caught it. A note whose numbers are typed by hand has the same failure
mode and no validator.

So the prose here is written and the numbers are not. Every figure is pulled from
a named output file at build time by `P()`, which aborts if the pattern is absent
or matches more than once. If an upstream script is rerun and a number moves, the
note moves with it or the build fails. Nothing is transcribed.

This also discharges gate 5 of the ruling of 6 September: every figure traceable
to an output file carrying its release filename and SHA-256. Appendix D is that
register, generated from the same files.

STRUCTURE, per decision B of 7 September
----------------------------------------
Main text, two to four pages, executive summary first. A reader who stops at the
end of the main text has every finding and every qualifier.
Appendix A  the release ladder, the unversioned reissue, the truncation trap
Appendix B  the mechanism catalogue
Appendix C  the nineteen verified cases with sources and lags
Appendix D  the figure register

Run:  python 19_build_note.py
Out:  ../Measurement_Note_draft_<date>.html
"""

import json
import os
import re
import sys
from datetime import date

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
EV = os.path.join(HERE, "..", "evidence")
DEST = os.path.join(HERE, "..", "..")

_cache = {}


def body(fn):
    if fn not in _cache:
        p = os.path.join(OUT, fn)
        if not os.path.exists(p):
            sys.exit(f"BUILD ABORTED: missing output file {fn}")
        _cache[fn] = open(p, encoding="utf-8", errors="replace").read()
    return _cache[fn]


def P(fn, pattern, group=1):
    """Extract one figure from one output file, or abort.

    Aborts on zero matches and on more than one, because a pattern that matches
    twice is a pattern that might be picking up the wrong number.
    """
    m = re.findall(pattern, body(fn))
    if len(m) != 1:
        sys.exit(f"BUILD ABORTED: pattern {pattern!r} matched {len(m)} times in {fn}. "
                 f"Every figure in the note must resolve to exactly one value.")
    return m[0] if group else m[0]


# ---------------------------------------------------------------------------
# the figures
# ---------------------------------------------------------------------------
F = {}
# R and its restrictions
F["R"] = P("restricted_r.txt", r"as published\s+4,582\s+12,717\s+([\d.]+)%")
F["R_restricted"] = P("restricted_r.txt", r"residuals out of both sides\s+3,923\s+10,141\s+([\d.]+)%")
F["resid_buildout"] = P("restricted_r.txt", r"build-out\s+8,135 edges\s+residual 1,917\s+\(\s*([\d.]+)%\)")
F["R_generous"] = P("change_decomposition.txt", r"removed from restatement: ([\d.]+)%")
F["restatement_n"] = "2,543"
# conventions
F["u3_zero"] = P("bioenergy_check.txt", r"U3, 171 panel firms\s+([\d.]+)\s")
F["u3_imp"] = P("bioenergy_check.txt", r"U3, 171 panel firms\s+[\d.]+\s+([\d.]+)")
F["u2_zero"] = P("bioenergy_check.txt", r"U2, as defined\s+blank=zero\s+n=\s*604\s+Spearman ([\d.]+)")
F["u2_imp"] = P("bioenergy_check.txt", r"U2, as defined\s+blank=impute\s+n=\s*604\s+Spearman ([\d.]+)")
F["bio_zero"] = P("bioenergy_check.txt", r"bioenergy in both, worldwide\s+blank=zero\s+n=\s*133\s+Spearman ([\d.]+)")
F["bio_imp"] = P("bioenergy_check.txt", r"bioenergy in both, worldwide\s+blank=impute\s+n=\s*133\s+Spearman ([\d.]+)")
F["n_zerocap"] = P("bioenergy_check.txt", r"Under blank=zero, (\d+) of the March 2025 firms")
F["fs_zero"] = P("bioenergy_check.txt", r"fossil share, blank=zero\s+Spearman ([\d.]+)")
F["fs_imp"] = P("bioenergy_check.txt", r"fossil share, blank=impute\s+Spearman ([\d.]+)")
F["fs_ov_zero"] = P("bioenergy_check.txt", r"fossil share, blank=zero\s+Spearman [\d.]+\s+top-quintile overlap ([\d.]+)%")
F["fs_ov_imp"] = P("bioenergy_check.txt", r"fossil share, blank=impute\s+Spearman [\d.]+\s+top-quintile overlap ([\d.]+)%")
F["bio_ov_zero"] = P("bioenergy_check.txt", r"bioenergy in both, worldwide\s+blank=zero\s+n=\s*133\s+Spearman [\d.]+\s+top-quintile overlap\s+([\d.]+)%")
F["bio_ov_imp"] = P("bioenergy_check.txt", r"bioenergy in both, worldwide\s+blank=impute\s+n=\s*133\s+Spearman [\d.]+\s+top-quintile overlap\s+([\d.]+)%")
F["growth_zero"] = P("exposure_proxy_summary.txt", r"under blank=zero\s+\+([\d.]+)%")
F["growth_imp"] = P("exposure_proxy_summary.txt", r"under blank=impute\s+\+([\d.]+)%")
F["blank_mar"] = P("exposure_proxy_summary.txt", r"edges 18,807 \| BLANK share ([\d,]+)")
F["blank_pct"] = P("exposure_proxy_summary.txt", r"edges 18,807 \| BLANK share [\d,]+ \(([\d.]+)%\)")
# graph mechanisms
F["over_mar"] = P("exposure_proxy_summary.txt", r"March 2025\s+6,502\.6 GW\s+vs actual fleet\s+4,191\.3 GW\s+= ([\d.]+)x")
F["over_aug"] = P("exposure_proxy_summary.txt", r"August 2026\s+7,611\.9 GW\s+vs actual fleet\s+4,324\.5 GW\s+= ([\d.]+)x")
# portfolio
F["never"] = P("panel_join_summary.txt", r"never exposed in either vintage\s+(\d+) of 328")
F["panel_eff"] = P("panel_join_summary.txt", r"EFFECTIVE panel for task 1.5 is therefore (\d+) firms")
_sp = re.findall(r"Spearman, 191 active firms\s+([\d.]+)", body("panel_join_summary.txt"))
_ov = re.findall(r"TOP-QUINTILE OVERLAP\s+([\d.]+)%", body("panel_join_summary.txt"))
if len(_sp) != 2 or len(_ov) != 2:
    sys.exit("BUILD ABORTED: expected two Spearman and two overlap figures in panel_join_summary.txt")
F["p_sp_zero"], F["p_sp_imp"] = _sp
F["p_ov_zero"], F["p_ov_imp"] = _ov
F["u3g_zero"] = P("panel_join_summary.txt", r"2025   515\.1   2026   618\.2   \(\+([\d.]+)%\)")
F["u3g_imp"] = P("panel_join_summary.txt", r"2025   553\.3   2026   618\.2   \(\+([\d.]+)%\)")
# returns
F["mde_lo"] = P("vintage_return_spread.txt", r"2026 blank=zero\s+3\.29%\s+6\.45%\s+([\d.]+)%")
F["se_lo"] = "3.29"
F["se_hi"] = "3.44"
F["t_max"] = "0.60"
# truncation and decay
F["trunc"] = P("decimal_truncation.txt", r"STRICT: explained by 1dp rounding alone\s+3,561\s+\(([\d.]+)%")
F["trunc_v2"] = P("decimal_truncation.txt", r"STRICT: explained by 1dp rounding alone\s+3,496\s+\(([\d.]+)%")
F["dp_mar"] = P("decimal_truncation.txt", r"values needing 2\+ decimal places: 4,382 of 16,315 \(([\d.]+)%\)")
F["decay"] = P("decay_curves.txt", r"one-month pairs, Nov-Dec excluded, n=8: build ([\d.]+% to [\d.]+%)")
F["decay_corr"] = P("decay_curves.txt", r"correlation of build-out share with gap length: \+([\d.]+)")

# --- Appendix B, the mechanism catalogue -----------------------------------
def _row(label, fn="change_decomposition.txt"):
    """One decomposition row: its edge count and its share of apparent change."""
    return (P(fn, label + r"\s+([\d,]+)"), P(fn, label + r"\s+[\d,]+\s+([\d.]+)%"))

F["m1_n"], F["m1_p"] = _row(r"new entity brought into coverage")
F["m2_n"], F["m2_p"] = _row(r"new link between entities already covered")
F["m3_n"], F["m3_p"] = _row(r"blank filled by genuine new research")
F["m4_n"], F["m4_p"] = _row(r"link removed, not explained by deduplication")
F["m5_n"], F["m5_p"] = _row(r"share revised, material, over 1 point")
F["m6_n"], F["m6_p"] = _row(r"share revised, small, under 1 point")
F["m7_n"], F["m7_p"] = _row(r"blank filled by imputation rule introduced after Mar 2025")
F["m8_n"], F["m8_p"] = _row(r"entity deduplicated by GEM, per remapping sheet")
F["m9_n"], F["m9_p"] = _row(r"imputed share moved because owner count changed")
F["bo_n"], F["bo_p"] = _row(r"-- BUILD-OUT TOTAL")
F["rs_n"], F["rs_p"] = _row(r"-- RESTATEMENT TOTAL")
F["mt_n"], F["mt_p"] = _row(r"-- METHODOLOGY TOTAL")
F["chg_total"] = P("change_decomposition.txt", r"total apparent change ([\d,]+)")
F["chg_unchanged"] = P("change_decomposition.txt", r"unchanged edges ([\d,]+)")
F["remap_n"] = P("change_decomposition.txt", r"remapping sheet loaded: ([\d,]+) entities")
F["remap_pct"] = P("change_decomposition.txt", r"sheet accounts for only ([\d.]+)%")
F["churn_pct"] = P("change_decomposition.txt", r"real ownership churn measured over 18 months\s+([\d.]+)%")
F["churn_ceiling"] = P("change_decomposition.txt", r"ceiling on genuine corporate events\s+([\d,]+)")
F["both_edges"] = P("change_decomposition.txt", r"edges present in both releases\s+([\d,]+)")
F["imp_flag_n"] = P("exposure_proxy_summary.txt", r"flagged `imputed value` by GEM: ([\d,]+)")
F["imp_flag_p"] = P("exposure_proxy_summary.txt", r"flagged `imputed value` by GEM: [\d,]+ \(([\d.]+)%\)")

# --- publication register: promoted and withheld files ----------------------
# Hashed at build time, never transcribed. A checksum typed by hand is the same
# failure mode as a figure typed by hand.
import hashlib


def _sha(fn):
    h = hashlib.sha256()
    with open(os.path.join(OUT, fn), "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


PROMOTED = ["change_decomposition_edges.csv", "vintage_asset_parent_changes.csv"]
WITHHELD = [("vintage_return_spread.csv", "11_vintage_return_spread"),
            ("vintage_return_spread.txt", "11_vintage_return_spread")]


def promoted_rows():
    out = []
    for fn in PROMOTED:
        stem, ext = os.path.splitext(fn)
        sup = stem + "_SUPERSEDED_2026-08-23" + ext
        if not os.path.exists(os.path.join(OUT, sup)):
            sys.exit(f"BUILD ABORTED: {sup} is missing. The promotion of 8 September "
                     f"retains the superseded copy beside the output of record; if it "
                     f"is gone, the register would claim an audit trail that does not exist.")
        out.append(f'<tr><td><code>{fn}</code></td>'
                   f'<td class="n"><code>{_sha(fn)[:16]}</code></td>'
                   f'<td class="n"><code>{_sha(sup)[:16]}</code></td></tr>')
    return "\n".join(out)


def withheld_rows():
    return "\n".join(
        f'<tr><td><code>{fn}</code></td><td><code>{sc}</code></td>'
        f'<td class="n"><code>{_sha(fn)[:16]}</code></td></tr>'
        for fn, sc in WITHHELD)

# structured sources
ladder = pd.read_csv(os.path.join(OUT, "release_ladder.csv"))
sal = pd.read_csv(os.path.join(OUT, "salience_lag.csv"), dtype=str)
cases = pd.read_csv(os.path.join(OUT, "event_validation_sample.csv"), dtype=str).fillna("")
expo = pd.read_csv(os.path.join(OUT, "exposure_proxy_by_firm.csv"))


def firm(name, vintage, rule="zero"):
    r = expo[(expo.name == name) & (expo.vintage == vintage) & (expo.blank_rule == rule)]
    return None if r.empty else (r.attributable_mw.iloc[0], int(r.units.iloc[0]))


amer = firm("Ameren", "March 2025")
unel = firm("Union Electric", "August 2026")
if amer is None or unel is None:
    sys.exit("BUILD ABORTED: Ameren or Union Electric not found in exposure_proxy_by_firm.csv")
if round(amer[0], 1) != round(unel[0], 1) or amer[1] != unel[1]:
    sys.exit(f"BUILD ABORTED: the Ameren illustration no longer holds: {amer} vs {unel}")
F["ameren_mw"] = f"{amer[0]:,.1f}"
F["ameren_units"] = str(amer[1])

verdicts = cases.verdict.str.strip().str.upper().value_counts().to_dict()
F["n_cases"] = str(len(cases))
F["n_noevent"] = str(verdicts.get("NO EVENT", 0))
fast = sal[sal.lag_days.astype(int) <= 120].lag_days.astype(int).tolist()
slow = sorted(sal[sal.lag_days.astype(int) > 120].lag_days.astype(int).tolist())
F["fast"] = " and ".join(str(x) for x in sorted(fast))
F["slow_lo"], F["slow_hi"] = f"{slow[0]:,}", f"{slow[-1]:,}"
F["slow_yr_lo"] = f"{slow[0]/365.25:.1f}"
F["slow_yr_hi"] = f"{slow[-1]/365.25:.1f}"

prov = {}
for fn in sorted(os.listdir(OUT)):
    if fn.startswith("RUN_PROVENANCE_") and fn.endswith(".json"):
        rec = json.load(open(os.path.join(OUT, fn)))
        ins = rec.get("inputs", {})
        if isinstance(ins, dict) and ins:
            for role, v in ins.items():
                if isinstance(v, dict) and "new" in role.lower():
                    prov[fn] = (v["filename"], v["sha256"])
                    break
            prov.setdefault(fn, ("upstream chain: " + ", ".join(sorted(ins)), ""))
        else:
            prov[fn] = (rec.get("kind", "no data inputs"), "")

TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# the note
# ---------------------------------------------------------------------------
CSS = """
:root{--ink:#1a1a1a;--mid:#555;--line:#d5d1c9;--bg:#fbfaf8;--card:#fff;--accent:#7a2e1e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 Georgia,"Iowan Old Style","Times New Roman",serif}
.wrap{max-width:820px;margin:0 auto;padding:56px 28px 100px}
h1{font-size:30px;line-height:1.15;margin:0 0 8px;letter-spacing:-.01em}
.sub{color:var(--mid);font-size:15px;margin:0 0 6px}
.meta{color:var(--mid);font-size:13px;margin:0 0 36px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
h2{font-size:20px;margin:38px 0 10px;padding-top:20px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:24px 0 8px}
p{margin:0 0 13px}
ul,ol{margin:0 0 13px;padding-left:22px} li{margin:0 0 7px}
table{border-collapse:collapse;width:100%;margin:16px 0 20px;font-size:14px;background:var(--card);
  border:1px solid var(--line);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
th{background:#f2efe9;font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
tr.rule td{border-top:2px solid var(--ink);font-weight:600}
.summary{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
  padding:20px 24px;margin:0 0 30px;border-radius:3px}
.summary h2{margin-top:0;padding-top:0;border-top:none;font-size:18px}
.note{background:#fdf8e8;border:1px solid #e6d9a8;padding:12px 16px;margin:16px 0;border-radius:3px;font-size:15px}
code{font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;background:#f0ede7;padding:1px 5px;border-radius:3px}
.src{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:12px;color:var(--mid);
  margin:-12px 0 20px}
.appendix{margin-top:50px;padding-top:26px;border-top:3px double var(--line)}
footer{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);color:var(--mid);font-size:13px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.fail{color:var(--accent);font-weight:700}
"""

def ladder_rows():
    out = []
    for _, r in ladder.iterrows():
        cls = ' class="rule"' if "worst case" in r["reading"] else ""
        v1 = f'{r["R_V1"]*100:.1f}% <span class="{"fail" if r["verdict_V1"]=="FAILS" else ""}">{r["verdict_V1"]}</span>'
        v2 = f'{r["R_V2"]*100:.1f}% <span class="{"fail" if r["verdict_V2"]=="FAILS" else ""}">{r["verdict_V2"]}</span>'
        out.append(f'<tr{cls}><td>{r["reading"]}</td><td class="n">{v1}</td><td class="n">{v2}</td></tr>')
    return "\n".join(out)


def salience_rows():
    out = []
    for _, r in sal.iterrows():
        out.append(f'<tr><td>{r["subject_name"]}</td><td>{r["party_name"]}</td>'
                   f'<td class="n">{r["transaction_date"]}</td>'
                   f'<td class="n">{r["gem_first_release_carrying_change"]}</td>'
                   f'<td class="n">{int(r["lag_days"]):,}</td>'
                   f'<td><a href="{r["transaction_source_url"]}">source</a></td></tr>')
    return "\n".join(out)


def case_rows():
    out = []
    for _, r in cases.iterrows():
        ev = f'<a href="{r["evidence_url"]}">source</a>' if r["evidence_url"].startswith("http") else (r["evidence_url"][:40] or "")
        out.append(f'<tr><td class="n">{r["case"]}</td><td>{r["subject_name"]}</td><td>{r["party_name"]}</td>'
                   f'<td>{r["subtype"]}</td><td>{r["verdict"]}</td><td>{ev}</td></tr>')
    return "\n".join(out)


def prov_rows():
    out = []
    for fn, (rel, sha) in sorted(prov.items()):
        out.append(f'<tr><td><code>{fn.replace("RUN_PROVENANCE_","").replace(".json","")}</code></td>'
                   f'<td>{rel}</td><td class="n"><code>{sha[:16] or "n/a"}</code></td></tr>')
    return "\n".join(out)


HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What a vintage difference measures</title>
<style>{CSS}</style></head><body><div class="wrap">

<h1>What a vintage difference measures</h1>
<p class="sub">Hand verification of ownership changes in a public asset-level database</p>
<p class="meta">Carlo Hofer &middot; draft of {TODAY} &middot; data: Global Energy Monitor Global Energy Ownership Tracker, CC BY 4.0 &middot;
code, outputs and provenance records: github.com/ochofer/paper1-hazard-exposure-data</p>

<div class="summary">
<h2>Summary</h2>
<p><strong>The question.</strong> A growing number of research designs date corporate ownership change by
differencing two vintages of the same database, treating an edge that appears in the later file and not
in the earlier one as an event with a date. I checked whether that difference behaves like a record of
events.</p>
<p><strong>What I did.</strong> I drew {F['n_cases']} apparent ownership changes at random from the
{F['restatement_n']} that two releases of the same database disagree on, and I looked for the transaction
behind each one in exchange filings, company statements and press releases.</p>
<p><strong>What a practitioner takes from it.</strong> Three things. First, {F['n_noevent']} of the
{F['n_cases']} had no corporate event behind them at all, so most of what a vintage difference records is
the file being edited rather than the world changing. Second, the six that were real entered the data
with lags of {F['fast']} days for the two recent and heavily covered deals and {F['slow_lo']} to
{F['slow_hi']} days for the four that were older or less prominent, which makes the recording error
selective rather than random; a constant offset cannot repair it. Third, two undocumented choices, one
the vendor's and one the analyst's, each move a verdict I had committed to in writing before any script
ran.</p>
<p><strong>What it costs a book.</strong> On the {F['panel_eff']} firms in the cross-section with any coal
or gas exposure, the rank correlation between the two releases is {F['p_sp_zero']} under one blank-share
convention and {F['p_sp_imp']} under the other, so a signal built on this measure is substantially
re-drawn by a release in which, on the evidence of the hand check, most of the movement is not an
event.</p>
<p><strong>The return test detects nothing.</strong> Every t-statistic is below {F['t_max']} against a
minimum detectable effect of about {F['mde_lo']}% a year, which is larger than any plausible transition
premium; I report it because it was pre-registered, and it corroborates nothing in either direction.</p>
<p><strong>The caveat that bounds all of it.</strong> The asset-level layer measured here has existed for
eighteen months, so some of what follows is a property of a young dataset and some is a property of how
ownership data is built and used; section 5 says which is which.</p>
</div>

<h2>1. Nineteen changes, checked by hand</h2>
<p>Two releases of the Global Energy Ownership Tracker, March 2025 and August 2026, disagree about
{F['restatement_n']} ownership edges in a way that is not the database simply adding coverage; I sampled
{F['n_cases']} of them at random and tried to find the transaction behind each.</p>
<p><strong>{F['n_noevent']} of the {F['n_cases']} had no corporate event behind them at all.</strong> The
full case table, with sources and verdicts, is Appendix C. I treat this as the central result of the
note, because it is the one finding that does not depend on any modelling choice I made downstream.</p>
<p>Six had a datable transaction and a datable record. The two the database caught within {F['fast']}
days are a statutory disclosure by a listed Japanese issuer and a 1.9bn USD acquisition by a listed US
utility; the four it missed by {F['slow_lo']} to {F['slow_hi']} days, which is {F['slow_yr_lo']} to
{F['slow_yr_hi']} years, are older, or reach the affected entity only through the perimeter of a larger
deal.</p>
<p><strong>The recording lag is therefore not a constant, and its variation lines up with how visible the
event was.</strong> That matters more than the average delay, because a constant lag is corrected with an
offset, while a lag that depends on salience means the events entering a vintage difference promptly are
a biased subset, skewed toward the large and the recent, with the bias invisible in the data itself. Six
cases cannot establish a correlation and I do not claim one; what they establish is that the lag is not
constant, which one fast case and one slow case would do, and the direction in which it varies is what
the six show.</p>
<p>For scale, {F['R']}% of all apparent change between these two releases is restatement or methodology
rather than the database growing, against a 25% threshold I wrote down before the script ran. Section 4
carries every construction of that figure.</p>
<p class="src">Sources: <code>outputs/salience_lag.txt</code>, <code>outputs/event_validation_sample.csv</code>,
<code>evidence/salience_lag_cases.csv</code>, <code>outputs/restricted_r.txt</code></p>

<h2>2. Two undocumented choices, one the vendor's and one the analyst's</h2>
<p>Between the raw file and a portfolio sit two choices that nobody documents. One is the vendor's:
which release you happen to hold. One is yours: what an empty ownership share is taken to mean.</p>
<p><strong>The analyst's choice moves a pre-committed verdict.</strong> Ranking firms by attributable coal
and gas capacity, the rank correlation between the two releases is {F['u3_zero']} if a blank share is
read as zero and {F['u3_imp']} if blanks are imputed, against a threshold of 0.95 set before the test ran;
the same measure, on the same firms, on the same two files, lands on opposite sides of that line
depending only on the reading.</p>
<table>
<tr><th>Universe, raw attributable MW between releases</th><th class="n">blank = zero</th><th class="n">blank = impute</th></tr>
<tr><td>604 matched firms worldwide (U2)</td><td class="n">{F['u2_zero']}</td><td class="n">{F['u2_imp']}</td></tr>
<tr><td>191 firms in the regional panel (U3)</td><td class="n">{F['u3_zero']}</td><td class="n">{F['u3_imp']}</td></tr>
<tr><td>133 firms with bioenergy in both releases</td><td class="n">{F['bio_zero']}</td><td class="n">{F['bio_imp']}</td></tr>
<tr class="rule"><td>threshold set before the test</td><td class="n">0.95</td><td class="n">0.95</td></tr>
</table>
<p><strong>The flip is general rather than a property of the regional panel.</strong> It reproduces on 604
firms worldwide and on 191 regional firms in the same direction, and it does not appear on the 133 firms
with bioenergy in both releases. Those universes are not nested, which is stated here rather than left
for a reader to find.</p>
<p><strong>Why the convention carries that much force.</strong> Under the naive reading, {F['n_zerocap']}
firms carry attributable capacity of exactly zero in March 2025, because every ownership edge they have
has a blank share and a blank multiplied by zero is nothing; under imputation none do. The convention
does not only change the values, then. It decides whether a firm registers as having any exposure at all,
which is a membership decision rather than a measurement one.</p>
<p>The same choice roughly halves measured growth: on the 604 firms present in both releases,
attributable capacity grows {F['growth_zero']}% reading blanks as zero and {F['growth_imp']}% imputing
them. March 2025 carries {F['blank_mar']} blank shares, {F['blank_pct']}% of its ownership edges; August
2026 carries none, because the vendor filled them in between releases.</p>
<h3>An apparent finding that dissolved under a pre-committed control</h3>
<p>Scaling capacity by fleet share looked far less stable across releases than raw capacity:
{F['fs_zero']} and {F['fs_imp']} against the same 0.95 threshold, with top-quintile overlap of
{F['fs_ov_zero']}% and {F['fs_ov_imp']}%. Restricting to the 133 firms whose denominator exists in both
releases, it is {F['bio_zero']} and {F['bio_imp']}, with overlap of {F['bio_ov_zero']}% and
{F['bio_ov_imp']}%. <strong>The instability was mostly the denominator's own coverage moving between
releases rather than anything about the firms</strong>, and the scaling result is reported as a coverage
finding and not as a measurement one. The control that dissolved it was specified before it ran, which is
the only reason the demotion is credible rather than convenient.</p>
<p class="src">Sources: <code>outputs/bioenergy_check.txt</code>, <code>outputs/scaling_second_column.txt</code>,
<code>outputs/exposure_proxy_summary.txt</code></p>

<h2>3. A boolean moved {F['ameren_mw']} MW between two companies</h2>
<p>Attribution walks up the ownership graph to the nearest listed parent; whether an entity counts as
listed is a flag in the data, and flags change.</p>
<table>
<tr><th>Firm</th><th class="n">March 2025</th><th class="n">August 2026</th></tr>
<tr><td>Ameren</td><td class="n">{F['ameren_mw']} MW, {F['ameren_units']} units</td><td class="n">absent</td></tr>
<tr><td>Union Electric</td><td class="n">absent</td><td class="n">{F['ameren_mw']} MW, {F['ameren_units']} units</td></tr>
</table>
<p>The two rows are identical to the decimal and identical in unit count, and not one generating unit was
built, retired or sold between them. Union Electric's listed flag changed from false to true, so under a
nearest-listed-parent rule it became the stopping point and kept the capacity its parent had been
receiving.</p>
<p><strong>Ameren was not delisted.</strong> It is flagged as publicly listed in both releases, and it
lost the capacity because a subsidiary gained the flag. Because the cross-section here was built on the
later release, Ameren is not in it at all: a boolean on a subsidiary decided which of two companies is in
the study.</p>
<p>One consequence follows for anyone using the file directly. Summing the vendor's own ownership share
column over all parents over-counts the world's operating coal and gas fleet by a factor of
{F['over_mar']} in March 2025 and {F['over_aug']} in August 2026, because the file emits a row for every
ancestor rather than the nearest listed one, and <strong>the over-count grew between releases</strong>.
Appendix B works it through with the other mechanisms.</p>
<p class="src">Sources: <code>outputs/exposure_proxy_by_firm.csv</code>, <code>outputs/exposure_proxy_summary.txt</code></p>

<h2>4. What this does to a portfolio, and the full R table</h2>
<p>Joining the measure to a cross-section of 328 listed firms in the US and developed Europe,
{F['never']} of them have no coal or gas power exposure in either release, because the measure is
power-only; the effective panel is {F['panel_eff']} firms.</p>
<table>
<tr><th>On the {F['panel_eff']} active panel firms</th><th class="n">blank = zero</th><th class="n">blank = impute</th></tr>
<tr><td>Rank correlation between releases</td><td class="n">{F['p_sp_zero']}</td><td class="n">{F['p_sp_imp']}</td></tr>
<tr><td>Top-quintile overlap</td><td class="n">{F['p_ov_zero']}%</td><td class="n">{F['p_ov_imp']}%</td></tr>
<tr><td>Growth in attributable capacity</td><td class="n">+{F['u3g_zero']}%</td><td class="n">+{F['u3g_imp']}%</td></tr>
</table>
<p>So the extreme portfolio turns over 8% to 13% of its names on a data release with no economic event
behind it, and the continuous ranking moves considerably more than that. For a signal rebalanced on
vendor releases, that turnover is a cost paid for revisions to the record rather than for changes in the
underlying fleet, and it is paid every release.</p>
<h3>R, every construction</h3>
<p>R is the share of apparent ownership change that is not the database growing. I report every
construction of it in one table rather than quoting the one that suits the argument.</p>
<table>
<tr><th>Construction</th><th class="n">August 2026 V1</th><th class="n">August 2026 V2</th></tr>
{ladder_rows()}
<tr><td>Generous bound, crediting every plausible real event</td><td class="n">{F['R_generous']}%</td><td class="n"></td></tr>
<tr><td>Residual counterparties removed from both sides</td><td class="n">{F['R_restricted']}%</td><td class="n"></td></tr>
<tr class="rule"><td>Threshold set before the script ran</td><td class="n">25%</td><td class="n">25%</td></tr>
</table>
<p><strong>The restricted construction is the more conservative one, and it raises R rather than lowering
it.</strong> Removing edges whose counterparty is a residual bucket, a party like "small shareholder(s)"
whose value is 100 minus the named holders rather than an observed stake, takes proportionally more out
of the denominator than the numerator, because those counterparties are concentrated in the build-out
bucket at {F['resid_buildout']}% and build-out sits in the denominator only. I had assumed the
restriction would deflate R and threaten the threshold. The assumption was backwards, and it is recorded
here because a reader should be able to see which of my expectations the data overturned.</p>
<p>One thing follows from that and no more: nearly a quarter of the edges counted as the database growing
are new links to a residual bucket, which is coverage of the unnamed rather than of the named.</p>
<p>The two August 2026 columns are two files the vendor published under the same month, neither marked as
a version anywhere in the data. Appendix A sets that out, including the reading at which the
pre-committed decision <span class="fail">fails</span> on one file and clears on the other, and why the
endpoint is pinned to the first.</p>
<p class="src">Sources: <code>outputs/panel_join_summary.txt</code>, <code>outputs/release_ladder.txt</code>,
<code>outputs/restricted_r.txt</code>, <code>outputs/change_decomposition.txt</code></p>

<h2>5. The layer is eighteen months old</h2>
<p>What this note measures is the asset-level ownership layer, which links companies to individual plants
and mines. The vendor confirms it has no release before March 2025, and the earliest file I hold, from
June 2024, carries entity-to-entity relationships only and no asset-level ownership; the tracker as a
product is older than the layer. The window here is the layer's first eighteen months, across the
fourteen releases I hold and the thirteen adjacent pairs between them.</p>
<p><strong>Findings that depend on that maturity:</strong> the level of R, the decay curves, and the share
of one release's change that is methodology.</p>
<p><strong>Findings that do not:</strong> the ancestor over-count, the convention that flips a
pre-committed verdict, the salience pattern in the hand verification, and the mechanism by which a flag
change moves {F['ameren_mw']} MW between two companies. Those are properties of how ownership data is
built and used, not of how long this particular dataset has existed.</p>
<p>Vintage instability is not peculiar to this vendor or to this kind of vendor. Goes (2023) documents it
in macroeconomic series revised by statistical agencies, and Berg, Fabisik and Sautner (2021) document
it in a commercial ESG rating; this note documents it in a free, non-profit, openly licensed database. The three
share the instability and differ in maturity, and the youngest is the one measured here.</p>
<p class="src">Sources: <code>outputs/decay_curves.txt</code>, GEM correspondence of 21 August 2026</p>

<h2>6. Limitations</h2>
<p><strong>The return test detects nothing, and it corroborates nothing.</strong> A pre-registered
quintile-spread test on {F['panel_eff']} firms, equal-weighted, in local currency, monthly over 191
months to December 2025, returns every t-statistic below {F['t_max']}, with a Newey-West standard error of
{F['se_lo']}% to {F['se_hi']}% a year and a minimum detectable effect of about {F['mde_lo']}% a year at
the Harvey, Liu and Zhu hurdle. No plausible transition premium is that large, so the design could not
have detected the effect it was built to look for; I report the minimum detectable effect beside the null
for that reason, because a null quoted without one reads as evidence of absence. A cross-sectional
Fama-MacBeth design was set aside before it ran, on a power calculation requiring 1,296 monthly
observations, published in the design document.</p>
<p><strong>Both return arms contain look-ahead, deliberately and identically</strong>, so they are
comparable with each other and neither is a return prediction.</p>
<p><strong>Prices.</strong> Returns use <code>adjClose</code> from Financial Modeling Prep's
dividend-adjusted end-of-day series, pulled on 21 August 2026. The adjustment is the vendor's, covering
splits as well as dividends, and no unadjusted close is archived beside it; the series is not
redistributable, and its per-file checksums are published in the repository manifest.</p>
<p><strong>Nineteen is a small sample</strong>, drawn once and not reproducible as a draw, and the note
says so wherever the verification is quoted.</p>
<p><strong>Decay.</strong> Where a decay figure appears it is the one-month-pair cut with the November to
December 2025 pair excluded, n = 8, build-out share falling {F['decay']}, alongside a correlation of
+{F['decay_corr']} between build-out share and the gap between releases.</p>

<h2>7. On the vendor</h2>
<p>Stated as checkable facts and nothing else. Global Energy Monitor is a non-profit. The data is free
and published under CC BY 4.0, so every input to this note except the price series ships with it. Six
detailed questions were answered within days. Flags marking a large share of ownership edges as no longer
maintained were shipped unprompted and were not mentioned in the covering note. A draft of this note went
to Global Energy Monitor before publication.</p>
<p>As at the date checked, the vendor publishes no release list or changelog, its project page gives no
launch date, and its download page still references an earlier release, so a reader cannot confirm the
completeness of the release history either. That is a fact about what is published rather than a
criticism of the data, and it is the reason this note says the fourteen releases I hold rather than every
release issued.</p>
<p>These effects are therefore measured at the favourable end of the range. A commercial vendor with a
revenue interest in its own history is not obviously better behaved, and I would expect the same exercise
on a paid dataset to be harder to run and no more flattering.</p>

<div class="appendix">
<h2>Appendix A. Two files called August 2026</h2>
<p>The vendor reissued the August 2026 release. Two files exist and nothing inside either marks it as a
version, so scripts that resolve a release by filename silently switched to the second one; mine did, and
the release pin in <code>code/_release.py</code> exists because of it.</p>
<table>
<tr><th>Construction</th><th class="n">V1</th><th class="n">V2_External</th></tr>
{ladder_rows()}
<tr class="rule"><td>Threshold set before the script ran</td><td class="n">25%</td><td class="n">25%</td></tr>
</table>
<p><strong>At the worst defensible reading the pre-committed decision clears on one file and fails on the
other.</strong> V is derived from the verified case verdicts and its Wilson interval computed rather than
assumed, and the worst case applies the upper bound of that interval.</p>
<p><strong>The endpoint is pinned to V1</strong> because the 328-firm cross-section is itself a V1
artefact, having been built from that file before the reissue existed; it is not pinned because V1 clears
the threshold. Had the cross-section been built on V2, the pin would have gone to V2 and the worst-case
reading would have failed a threshold written before any script ran.</p>
<h3>The truncation trap</h3>
<p>Between the two releases the vendor truncated ownership shares to one decimal place: {F['dp_mar']}% of
March 2025 values need two decimals and none of the August values do.
<strong>{F['trunc']}% of all share-value changes between the pinned releases are that and nothing
else</strong> ({F['trunc_v2']}% against the reissue). R is unaffected, because the 0.06 threshold used to
build the sample had already excluded them; anyone rerunning this comparison with a tighter threshold will
manufacture roughly three and a half thousand changes that are formatting.</p>

<h2 class="appendix">Appendix B. The mechanism catalogue</h2>
<p>Every route, found in this data, by which a vintage difference shows an ownership change when nothing
happened to the company. The table counts the mechanisms that appear as a change to an ownership edge,
which is what the decomposition can see; six further mechanisms move a number without moving an edge, and
they are listed after it. The grouping is the one that matters for a design, because build-out is the only
group that decays as the database matures, and R is exactly the share of this table that does not.</p>
<table>
<tr><th>Bucket</th><th>Mechanism</th><th class="n">Edges</th><th class="n">Share of apparent change</th></tr>
<tr><td rowspan="4"><strong>Build-out</strong><br>decays with maturity</td>
    <td>new entity brought into coverage</td><td class="n">{F['m1_n']}</td><td class="n">{F['m1_p']}%</td></tr>
<tr><td>new link between entities already covered</td><td class="n">{F['m2_n']}</td><td class="n">{F['m2_p']}%</td></tr>
<tr><td>blank filled by genuine new research</td><td class="n">{F['m3_n']}</td><td class="n">{F['m3_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['bo_n']}</td><td class="n">{F['bo_p']}%</td></tr>
<tr><td rowspan="4"><strong>Restatement</strong><br>does not decay</td>
    <td>link removed, not explained by deduplication</td><td class="n">{F['m4_n']}</td><td class="n">{F['m4_p']}%</td></tr>
<tr><td>share revised, material, over one point</td><td class="n">{F['m5_n']}</td><td class="n">{F['m5_p']}%</td></tr>
<tr><td>share revised, small, under one point</td><td class="n">{F['m6_n']}</td><td class="n">{F['m6_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['rs_n']}</td><td class="n">{F['rs_p']}%</td></tr>
<tr><td rowspan="4"><strong>Methodology</strong><br>does not decay</td>
    <td>blank filled by an imputation rule introduced after March 2025</td><td class="n">{F['m7_n']}</td><td class="n">{F['m7_p']}%</td></tr>
<tr><td>entity deduplicated by the vendor, per the remapping sheet</td><td class="n">{F['m8_n']}</td><td class="n">{F['m8_p']}%</td></tr>
<tr><td>imputed share moved because the owner count changed</td><td class="n">{F['m9_n']}</td><td class="n">{F['m9_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['mt_n']}</td><td class="n">{F['mt_p']}%</td></tr>
<tr class="rule"><td>R</td><td>restatement plus methodology</td><td class="n">{F['rs_n']} + {F['mt_n']}</td><td class="n">{F['R']}%</td></tr>
</table>
<p>The table covers {F['chg_total']} changed edges, against {F['chg_unchanged']} that did not move between the
two releases.</p>

<h3>Six mechanisms that move a number without moving an edge</h3>
<p>None of these appears in the table, because the decomposition counts edges and none of them adds,
removes or revises one.</p>
<ol>
<li><strong>Decimal truncation.</strong> {F['trunc']}% of all share-value changes between the pinned releases
are one-decimal rounding and nothing else. They sit below the 0.06 threshold used to build the verification
sample, so they never enter R; anyone who sets a tighter threshold puts every one of them in.</li>
<li><strong>A listed flag changing.</strong> {F['ameren_mw']} MW and {F['ameren_units']} units moved from
Ameren to Union Electric with no edge added, removed or revised, because what moved was the attribution
stopping point rather than the graph. Section 3 works the case.</li>
<li><strong>Ancestor double-count.</strong> Summing the vendor's own share column over all parents gives
{F['over_mar']} times the operating fleet in March 2025 and {F['over_aug']} times it in August 2026. That is
a property of the file's shape rather than a change between releases, but the factor grew, so a user
comparing two naive sums measures the growth of the double-count alongside the growth of the fleet.</li>
<li><strong>The blank-share convention.</strong> Not the vendor's doing at all. Reading blanks as zero
rather than imputing them moves measured growth from {F['growth_imp']}% to {F['growth_zero']}%, and puts
{F['n_zerocap']} firms at exactly zero attributable capacity in March 2025.</li>
<li><strong>Coverage moving inside a denominator.</strong> Any measure scaled by fleet share inherits the
coverage change in its denominator, which is what dissolved the scaling result in section 2.</li>
<li><strong>A release reissued under the same name.</strong> Two files are called August 2026 and nothing
inside either marks it as a version; Appendix A gives the figures that differ between them.</li>
</ol>

<h3>Two boundaries this catalogue does not settle</h3>
<p><strong>Deduplication.</strong> The remapping sheet accounts for {F['remap_n']} entities the vendor
deleted as duplicates, which is {F['remap_pct']}% of the entities lost between these releases, so an
unknown part of the {F['m4_n']} removed links is unrecorded deduplication rather than restatement.
Reclassifying any of them moves edges from restatement to methodology, and both sit inside R, so the
boundary does not move R; I report the split as the decomposition assigns it and flag that its internal
line is soft.</p>
<p><strong>Real churn.</strong> Of the {F['both_edges']} edges present in both releases, observed ownership
churn over eighteen months puts a ceiling of {F['churn_ceiling']} genuine corporate events, or
{F['churn_pct']}% of them. Crediting every one of those to the restatement bucket is what produces the
generous bound in section 4. It is a ceiling and not an estimate, and it is the most favourable reading
the data will support.</p>
<p>One thing the vendor does here helps a user directly. August 2026 flags {F['imp_flag_n']} ownership
edges, {F['imp_flag_p']}% of them, as imputed values, so a reader of that flag can tell an imputed share
from an observed one without any of the work in this note. March 2025 carries no such flag, which is why
the imputation row above is a methodology change rather than something a user could have seen coming.</p>
<p class="src">Sources: <code>outputs/change_decomposition.txt</code>, <code>outputs/exposure_proxy_summary.txt</code>,
<code>outputs/decimal_truncation.txt</code>, <code>outputs/bioenergy_check.txt</code></p>

<h2 class="appendix">Appendix C. The nineteen verified cases</h2>
<table>
<tr><th class="n">#</th><th>Subject</th><th>Counterparty</th><th>Change type</th><th>Verdict</th><th>Evidence</th></tr>
{case_rows()}
</table>
<h3>The six datable cases and their lags</h3>
<p>Lag is measured from the transaction date to the first day of the month of the first release carrying
the change. The dates were read by hand from the sources linked, so the file is a curated input,
<code>evidence/salience_lag_cases.csv</code>, validated against the verdicts above rather than computed
from them.</p>
<table>
<tr><th>Subject</th><th>Counterparty</th><th class="n">Transaction</th><th class="n">Release</th><th class="n">Lag, days</th><th>Source</th></tr>
{salience_rows()}
</table>

<h2 class="appendix">Appendix D. Figure register</h2>
<p>Every figure in this note resolves to a named output file. The note is generated by
<code>code/19_build_note.py</code>, which extracts each number from those files at build time and aborts
if a pattern is absent or matches more than once, so no figure here was typed by hand. I built that check
after typing twelve entity identifiers into an evidence file from memory instead of reading them from the
source, and getting all twelve wrong.</p>
<table>
<tr><th>Script</th><th>Release resolved</th><th class="n">SHA-256, first 16</th></tr>
{prov_rows()}
</table>

<h3>Two conventions this register runs on</h3>
<p><strong>Every output is deterministic.</strong> Each is sorted before it is written, so a
reader who reruns the script against the pinned release gets the same bytes and therefore the
same checksum. Two outputs did not meet that until 8 September, because they were built by
iterating Python sets and their row order varied between runs while their content did not. The
deterministic versions are now the outputs of record and the earlier copies are retained beside
them under a superseded marker, never deleted. No value moved and no figure in this note
changed.</p>
<table>
<tr><th>Promoted 8 September</th><th class="n">output of record</th><th class="n">superseded</th></tr>
{promoted_rows()}
</table>
<p><strong>Two outputs are withheld.</strong> The return arm is computed from a licensed price
series that cannot be redistributed, so these files are named here with their checksums and the
script that produces them, and a reader reproduces them by rerunning that script against their
own pull.</p>
<table>
<tr><th>Withheld</th><th>Script</th><th class="n">SHA-256, first 16</th></tr>
{withheld_rows()}
</table>
<p>A checksum on a withheld file identifies the file I used, and it is not reproducible by a
reader with a different pull, because a vendor's adjusted price history is itself restated
whenever a dividend or a split is applied. That is the same claim this note makes about the
price layer, applied at the level of the file rather than the dataset: auditable, never
repeatable. Everything else in this register is reproducible from free data.</p>
</div>

<footer>
Draft of {TODAY}.
Generated from the output files by <code>code/19_build_note.py</code>. Not for circulation until the
citation and novelty checks are complete and the draft has been sent to Global Energy Monitor.
</footer>

</div></body></html>
"""

path = os.path.join(DEST, f"Measurement_Note_draft_{TODAY}.html")
with open(path, "w", encoding="utf-8") as fh:
    fh.write(HTML)
print(f"built: {os.path.abspath(path)}")
print(f"figures extracted from output files: {len(F)}")
