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

This also discharges shipping gate 5 of 6 September: every figure traceable
to an output file carrying its release filename and SHA-256. Appendix D is that
register, generated from the same files.

STRUCTURE, per decision B of 7 September
----------------------------------------
Main text, two to four pages, executive summary first. A reader who stops at the
end of the main text has every finding and every qualifier.
Appendix A  the release ladder, the two files called August 2026, the truncation trap
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
F["restatement_n"] = P("change_decomposition.txt",
                       r"-- RESTATEMENT TOTAL\s+([\d,]+)")
# conventions
# U3's count and the three-universe table's bioenergy row are read from the
# file.
F["u3_n"] = P("bioenergy_check.txt", r"U3, (\d+) panel firms\s+[\d.]+\s+[\d.]+")
F["u3_zero"] = P("bioenergy_check.txt", r"U3, \d+ panel firms\s+([\d.]+)\s")
F["u3_imp"] = P("bioenergy_check.txt", r"U3, \d+ panel firms\s+[\d.]+\s+([\d.]+)")
F["u3_fossil_both_zero"] = P("bioenergy_check.txt", r"coal or gas capacity above zero in both, blank=zero\s+(\d+)")
F["u3_fossil_both_imp"] = P("bioenergy_check.txt", r"coal or gas capacity above zero in both, blank=impute\s+(\d+)")
F["u3_bio_alone"] = P("bioenergy_check.txt", r"bioenergy alone in both releases, blank=impute\s+(\d+)")
F["bio_n"] = P("bioenergy_check.txt", r"(\d+) firms with bioenergy in both\s+[\d.]+\s+[\d.]+")
F["bio_raw_zero"] = P("bioenergy_check.txt", r"\d+ firms with bioenergy in both\s+([\d.]+)\s+[\d.]+")
F["bio_raw_imp"] = P("bioenergy_check.txt", r"\d+ firms with bioenergy in both\s+[\d.]+\s+([\d.]+)")
F["u2_zero"] = P("bioenergy_check.txt", r"U2, as defined\s+blank=zero\s+n=\s*604\s+Spearman ([\d.]+)")
F["u2_imp"] = P("bioenergy_check.txt", r"U2, as defined\s+blank=impute\s+n=\s*604\s+Spearman ([\d.]+)")
F["bio_zero"] = P("bioenergy_check.txt", r"bioenergy in both, worldwide\s+blank=zero\s+n=\s*\d+\s+Spearman ([\d.]+)")
F["bio_imp"] = P("bioenergy_check.txt", r"bioenergy in both, worldwide\s+blank=impute\s+n=\s*\d+\s+Spearman ([\d.]+)")
F["n_zerocap"] = P("bioenergy_check.txt", r"Under blank=zero, (\d+) of the \d+ March 2025 firms")
F["n_march"] = P("bioenergy_check.txt", r"Under blank=zero, \d+ of the (\d+) March 2025 firms")
# the 576 of the 604 above zero in both releases with a blank share read as zero, under both readings, and
# the 28 at zero (added 20 November 2026); the 145 firms with bioenergy in both releases under the imputed
# reading (added 20 November 2026); the pair on the 34 panel firms with bioenergy in both
F["u2_zero576"] = P("bioenergy_check.txt", r"of the 604, at zero in March 2025 with a blank share read as zero\s+(\d+)")
F["u2_pos_n"] = P("bioenergy_check.txt", r"above zero in both under the zero reading\s+blank=zero\s+n=\s*(\d+)")
F["u2_pos_zero"] = P("bioenergy_check.txt", r"above zero in both under the zero reading\s+blank=zero\s+n=\s*\d+\s+Spearman ([\d.]+)")
F["u2_pos_imp"] = P("bioenergy_check.txt", r"above zero in both under the zero reading\s+blank=impute\s+n=\s*\d+\s+Spearman ([\d.]+)")
F["bio_imp_n"] = P("bioenergy_check.txt", r"bioenergy above zero in both releases with blanks imputed: (\d+) firms")
F["bio_imp_fs"] = P("bioenergy_check.txt", r"bioenergy in both \(imputed\), worldwide blank=impute\s+n=\s*\d+\s+Spearman ([\d.]+)")
F["bio_imp_raw"] = P("bioenergy_check.txt", r"bioenergy in both \(imputed\), worldwide blank=impute\s+n=\s*\d+\s+Spearman [\d.]+\s+top-quintile overlap [^\n]*\n\s+like-for-like, RAW fossil MW, same firms\s+n=\s*\d+\s+Spearman ([\d.]+)")
F["bio34_n"] = P("bioenergy_check.txt", r"bioenergy in both, the 328 panel blank=zero\s+n=\s*(\d+)")
F["bio34_zero"] = P("bioenergy_check.txt", r"bioenergy in both, the 328 panel blank=zero\s+n=\s*\d+\s+Spearman ([\d.]+)")
F["bio34_imp"] = P("bioenergy_check.txt", r"bioenergy in both, the 328 panel blank=impute\s+n=\s*\d+\s+Spearman ([\d.]+)")
# the entrants, from script 25 (added 20 November 2026): their August 2026 capacity split unit by unit
# by what the March 2025 file held of each unit, a measure set after the script's first run
F["ent_n"] = P("panel_entrants.txt", r"entrants (\d+) \| August 2026 capacity")
F["ent_mw"] = P("panel_entrants.txt", r"\| August 2026 capacity ([\d,.]+) MW, split unit by unit")
F["ent_i_mw"], F["ent_i_pc"] = P("panel_entrants.txt",
                                 r"the entrant not then listed and identified\s+([\d,.]+) MW, ([\d.]+) per cent")
F["ent_ii_mw"], F["ent_ii_pc"] = P("panel_entrants.txt",
                                   r"the rest of the units the March 2025 file carried\s+([\d,.]+) MW, ([\d.]+) per cent")
F["ent_iii_mw"], F["ent_iii_pc"] = P("panel_entrants.txt",
                                     r"units the March 2025 file did not carry\s+([\d,.]+) MW, ([\d.]+) per cent")
(F["ent_top1"], _, F["ent_top1_pc"], F["ent_top2"], _, F["ent_top2_pc"]) = P(
    "panel_entrants.txt", r"of \(i\), the two largest: (.+?) ([\d,.]+) MW, ([\d.]+) per cent of \(i\); "
                          r"(.+?) ([\d,.]+) MW, ([\d.]+) per cent of \(i\)\n")
F["fs_zero"] = P("bioenergy_check.txt", r"fossil share, blank=zero\s+n=\s*\d+\s+Spearman ([\d.]+)")
F["fs_imp"] = P("bioenergy_check.txt", r"fossil share, blank=impute\s+n=\s*\d+\s+Spearman ([\d.]+)")
# The top-quintile overlap of fossil share on the panel has no one figure: since
# 20 November 2026 the scripts print the lowest and the highest count that the
# firms tied at each cut allow, with the tie counts, and the note reads the
# counts. An overlap the note gives as one figure must come from a line that
# says no tie at either cut; a range there aborts the build.
_NO_TIE = r"top-quintile overlap (\d+) of (\d+) \(([\d.]+)%\), no tie at either cut"
_TIED = (r"top-quintile overlap (\d+) to (\d+) of (\d+) \([\d.]+% to [\d.]+%\) over every order of the firms "
         r"tied at the cut: (\d+) firms tied at (\S+) for (\d+) places? in March 2025; "
         r"(\d+) firms tied at (\S+) for (\d+) places? in August 2026")
for _rule in ("zero", "imp"):
    _line = P("bioenergy_check.txt",
              r"(fossil share, blank=" + {"zero": "zero", "imp": "impute"}[_rule] + r"\s+n=\s*\d+\s+Spearman [\d.]+\s+top-quintile overlap [^\n]*)")
    F[f"fs_n_{_rule}"] = re.search(r"n=\s*(\d+)", _line).group(1)
    _m = re.search(_TIED, _line)
    if _m is None:
        sys.exit("BUILD ABORTED: the fossil-share overlap line of bioenergy_check.txt does not carry the tie bounds")
    (F[f"fs_ov_lo_{_rule}"], F[f"fs_ov_hi_{_rule}"], F[f"fs_k_{_rule}"], F[f"fs_tied_mar_{_rule}"], F[f"fs_cut_mar_{_rule}"],
     F[f"fs_places_mar_{_rule}"], F[f"fs_tied_aug_{_rule}"], F[f"fs_cut_aug_{_rule}"], F[f"fs_places_aug_{_rule}"]) = _m.groups()
    if not (F[f"fs_cut_mar_{_rule}"] == "1" and F[f"fs_cut_aug_{_rule}"] == "1"
            and F[f"fs_ov_lo_{_rule}"] == "0" and F[f"fs_ov_hi_{_rule}"] == F[f"fs_k_{_rule}"]
            and F[f"fs_places_mar_{_rule}"] == F[f"fs_k_{_rule}"] == F[f"fs_places_aug_{_rule}"]):
        sys.exit("BUILD ABORTED: the fossil-share tie counts are not what the sentence on them says")
F["bio_ov_zero"] = P("bioenergy_check.txt", r"bioenergy in both, worldwide\s+blank=zero\s+n=\s*\d+\s+Spearman [\d.]+\s+" + _NO_TIE, group=1)[2]
F["bio_ov_imp"] = P("bioenergy_check.txt", r"bioenergy in both, worldwide\s+blank=impute\s+n=\s*\d+\s+Spearman [\d.]+\s+" + _NO_TIE, group=1)[2]
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
_sp = re.findall(r"Spearman, \d+ active firms\s+([\d.]+)", body("panel_join_summary.txt"))
_ov = re.findall(r"TOP-QUINTILE OVERLAP\s+\d+ of \d+ \(([\d.]+)%\), no tie at either cut", body("panel_join_summary.txt"))
if len(_sp) != 2 or len(_ov) != 2:
    sys.exit("BUILD ABORTED: expected two Spearman and two overlap figures in panel_join_summary.txt")
F["p_sp_zero"], F["p_sp_imp"] = _sp
F["p_ov_zero"], F["p_ov_imp"] = _ov
F["u3g_zero"] = P("panel_join_summary.txt", r"2025   515\.1   2026   618\.2   \(\+([\d.]+)%\)")
F["u3g_imp"] = P("panel_join_summary.txt", r"2025   553\.3   2026   618\.2   \(\+([\d.]+)%\)")
# The firms with exposure in both releases, from script 10's block of
# 19 November 2026, under each reading of a blank share.
F["both_units"] = P("panel_join_summary.txt", r"coal or gas units in both releases\s+(\d+)")
F["one_only"] = P("panel_join_summary.txt", r"in one release only\s+(\d+)")
F["entered"] = P("panel_join_summary.txt", r"entered between the two releases (\d+), left \d+")
F["left"] = P("panel_join_summary.txt", r"entered between the two releases \d+, left (\d+)")
_pj = body("panel_join_summary.txt")
_bs = re.findall(r"Spearman, the \d+ firms with units in both releases\s+([\d.]+)", _pj)
_bo = re.findall(r"top quintile kept, the \d+\s+(\d+ of \d+) \([\d.]+%\), no tie at either cut", _pj)
_bg = re.findall(r"total GW, the \d+\s+2025\s+[\d,.]+\s+2026\s+[\d,.]+\s+\(([+-][\d.]+)%\)", _pj)
_bb = re.findall(r"of the \d+, at zero in March 2025 under this reading\s+(\d+)", _pj)
_bz = re.findall(r"at zero in March 2025 and above zero in August 2026\s+(\d+)\s+\(entered the panel (\d+); "
                 r"at zero in March 2025 under this reading because every path from them to a unit crosses "
                 r"a blank share (\d+)\)", _pj)
if any(len(x) != 2 for x in (_bs, _bo, _bg, _bb, _bz)):
    sys.exit("BUILD ABORTED: expected one block per blank-share reading in panel_join_summary.txt")
F["both_sp_zero"], F["both_sp_imp"] = _bs
F["both_ov_zero"], F["both_ov_imp"] = _bo
F["both_g_zero"], F["both_g_imp"] = _bg
F["both_blank_zero"], F["both_blank_imp"] = _bb
(F["rose_zero"], F["rose_entered_zero"], F["rose_blank_zero"]), (F["rose_imp"], _, _) = _bz
_bp = re.findall(r"Spearman, the (\d+) of them above zero in March 2025 under both readings\s+([\d.]+)", _pj)
if len(_bp) != 2 or _bp[0][0] != _bp[1][0]:
    sys.exit("BUILD ABORTED: expected the Spearman on the firms above zero under both readings, once per reading")
F["pos_n"] = _bp[0][0]; F["pos_sp_zero"], F["pos_sp_imp"] = _bp[0][1], _bp[1][1]
F["gap_both"] = f"{float(F['both_sp_imp']) - float(F['both_sp_zero']):.3f}"
F["gap_pos"] = f"{float(F['pos_sp_imp']) - float(F['pos_sp_zero']):.3f}"
_i = lambda x: int(str(x).replace(",", ""))
_f = lambda x: float(str(x).replace(",", ""))
if not (F["both_units"] == F["u3_fossil_both_imp"]
        and _i(F["u3_n"]) == _i(F["u3_fossil_both_imp"]) + _i(F["u3_bio_alone"])
        and _i(F["panel_eff"]) == _i(F["both_units"]) + _i(F["one_only"])
        and _i(F["one_only"]) == _i(F["entered"]) + _i(F["left"])
        and _i(F["rose_zero"]) == _i(F["rose_entered_zero"]) + _i(F["rose_blank_zero"])
        and F["both_blank_zero"] == F["rose_blank_zero"] and F["both_blank_imp"] == "0"
        and _i(F["pos_n"]) == _i(F["both_units"]) - _i(F["both_blank_zero"])
        and F["ent_n"] == F["entered"]
        and abs(sum(_f(F[k]) for k in ("ent_i_mw", "ent_ii_mw", "ent_iii_mw")) - _f(F["ent_mw"])) < 0.05
        and abs(sum(_f(F[k]) for k in ("ent_i_pc", "ent_ii_pc", "ent_iii_pc")) - 100.0) < 0.05
        and _f(F["ent_top1_pc"]) >= _f(F["ent_top2_pc"]) and _f(F["ent_top1_pc"]) + _f(F["ent_top2_pc"]) <= 100.05
        and _i(F["u2_pos_n"]) == 604 - _i(F["u2_zero576"])):
    sys.exit("BUILD ABORTED: the counts of scripts 10, 15 and 25 do not reconcile")
# The summary says in words on which side of 0.95 four rank correlations fall; the build stops if one moves.
if not (float(F["u3_zero"]) < 0.95 <= float(F["u3_imp"])
        and float(F["both_sp_zero"]) < 0.95 < float(F["pos_sp_zero"])):
    sys.exit("BUILD ABORTED: a rank correlation the summary places against 0.95 has moved to the other side")
# The turnover of the extreme portfolio on the wider panel, from the overlaps.
_turn = sorted(100 - float(x) for x in (F["p_ov_zero"], F["p_ov_imp"]))
F["turn_lo"], F["turn_hi"] = f"{_turn[0]:.0f}", f"{_turn[1]:.0f}"
# returns
# --- the four return figures, computed from the monthly series ---------------
# These were typed as literals until 15 September 2026, and one was extracted
# from vintage_return_spread.txt, a summary of the series rather than the series
# itself. The copy of that summary supplied for the version 1.1 build was from
# before the release was pinned on 3 September 2026, and its August 2026 rows did
# not agree with the .csv; the summary beside the series does agree with it. The
# .csv is the file of record, its checksum is unchanged since the first published
# version, and every figure below is derived from it at build time.
def _return_figures(fn="vintage_return_spread.csv", lag=6):
    p = os.path.join(OUT, fn)
    if not os.path.exists(p):
        sys.exit(f"BUILD ABORTED: missing output file {fn}")
    d = pd.read_csv(p)
    arms = [c for c in d.columns if c != "ym"]
    if not arms:
        sys.exit(f"BUILD ABORTED: {fn} carries no return arms")
    ts, ses, mdes, mdes80, stat = [], [], [], [], {}
    for a in arms:
        x = d[a].dropna().to_numpy(dtype=float)
        n = len(x)
        mean = x.mean()
        e = x - mean
        # Newey-West, Bartlett kernel, `lag` lags, as reported by script 11.
        s = (e @ e) / n
        for l in range(1, lag + 1):
            s += 2 * (1 - l / (lag + 1)) * ((e[l:] @ e[:-l]) / n)
        nw = (s / n) ** 0.5
        ols = mean / (x.std(ddof=1) / (n ** 0.5))
        ts += [abs(ols), abs(mean / nw)]
        ses.append(nw * 12 * 100)
        mdes.append(3.0 * nw * 12 * 100)   # Harvey, Liu and Zhu hurdle
        # At the hurdle the expected t-statistic equals 3.0, so the effect is
        # detected half the time; at 80 per cent power the hurdle is 3.0 + 0.84.
        mdes80.append((3.0 + 0.84) * nw * 12 * 100)
        stat[a] = (mean, nw, d[a])
    out = {"t_max": f"{max(ts):.2f}",
           "se_lo": f"{min(ses):.2f}", "se_hi": f"{max(ses):.2f}",
           "mde_lo": f"{min(mdes):.2f}", "mde_hi": f"{max(mdes):.2f}",
           "mde80_lo": f"{min(mdes80):.2f}", "mde80_hi": f"{max(mdes80):.2f}"}
    # The rule in the header of script 11, read from the series: ROBUST if the
    # two releases' spreads differ by less than one standard error and the two
    # monthly series correlate above 0.95, FRAGILE if they differ by more or
    # correlate below 0.90, mixed otherwise. Added 19 November 2026, after the
    # results were known; computed here as script 11 computes it.
    for rule in ("zero", "impute"):
        A, B = stat.get(f"2025_{rule}"), stat.get(f"2026_{rule}")
        if A is None or B is None:
            sys.exit(f"BUILD ABORTED: {fn} lacks the 2025_{rule} or 2026_{rule} arm")
        diff = abs(B[0] - A[0])
        pooled = max(A[1], B[1])
        both = pd.concat([A[2], B[2]], axis=1).dropna()
        corr = both.iloc[:, 0].corr(both.iloc[:, 1])
        within = diff < pooled
        verdict = ("ROBUST" if (within and corr > 0.95) else
                   "FRAGILE" if ((not within) or corr < 0.90) else "MIXED")
        out[f"rule_d_{rule}"] = f"{diff / pooled:.2f}"
        out[f"rule_c_{rule}"] = f"{corr:.4f}"
        out[f"rule_v_{rule}"] = verdict.lower()
        # The Newey-West standard error of the difference of the two monthly series, with the same
        # kernel and lags, and the difference over it: added 20 November 2026 after the results were
        # known, in no verdict; computed here as script 11 computes it.
        dser = (both.iloc[:, 1] - both.iloc[:, 0]).to_numpy()
        ed = dser - dser.mean()
        nd = len(ed)
        sd_ = (ed @ ed) / nd
        for l in range(1, lag + 1):
            sd_ += 2 * (1 - l / (lag + 1)) * ((ed[l:] @ ed[:-l]) / nd)
        nw_d = (sd_ / nd) ** 0.5
        out[f"dse_{rule}"] = f"{nw_d * 12 * 100:.2f}"
        out[f"dt_{rule}"] = f"{abs(dser.mean()) / nw_d:.2f}"
    if out["rule_v_zero"] == out["rule_v_impute"]:
        out["rule_phrase"] = f"{out['rule_v_zero']} under both readings of a blank share"
    else:
        out["rule_phrase"] = (f"{out['rule_v_zero']} with blanks read as zero and "
                              f"{out['rule_v_impute']} with blanks imputed")
    return out


F.update(_return_figures())
# The summary and section 6 say in words that the difference is statistically significant at the 5 per cent
# level, if only just, under the imputed reading and not under the zero reading. The build stops if the
# verdict or the two ratios move from the figures those words were checked against.
if not (F["rule_v_zero"] == F["rule_v_impute"] == "mixed"
        and 1.96 <= float(F["dt_impute"]) < 2.10 and float(F["dt_zero"]) < 1.96
        and float(F["t_max"]) < 1.96):
    sys.exit("BUILD ABORTED: the typed sentence on the two readings of a blank share no longer matches "
             f"the figures ({F['rule_v_zero']}, {F['rule_v_impute']}, {F['dt_zero']}, {F['dt_impute']})")
# The months of the power calculation, from script 05 (computed there since 20 November 2026).
F["pw_months"] = P("power_comparison.txt", r"months needed to detect a 2.0%/year premium at t=3.0: ([\d,]+)")
F["pw_months_1pct"] = P("power_comparison.txt", r"at a monthly standard deviation of 1% instead: ([\d,]+)")
F["pw_months_80"] = P("power_comparison.txt", r"at 80 per cent power, t=3.0 plus 0.84: ([\d,]+)")
# The size of each arm, from the run log of script 11. The log is withheld with
# the series, and the counts are not price data.
for _v, _r, _k in (("2025", "zero", "arm_25z"), ("2025", "impute", "arm_25i"),
                   ("2026", "zero", "arm_26z"), ("2026", "impute", "arm_26i")):
    F[_k] = P("vintage_return_spread.txt",
              rf"{_v} blank={_r}\s+priceable firms with exposure\s+(\d+)")
F["arm_25"] = (F["arm_25z"] if F["arm_25z"] == F["arm_25i"]
               else f"{F['arm_25z']} and {F['arm_25i']}")
F["arm_26"] = (F["arm_26z"] if F["arm_26z"] == F["arm_26i"]
               else f"{F['arm_26z']} and {F['arm_26i']}")
# truncation and decay
F["trunc"] = P("decimal_truncation.txt", r"STRICT: explained by 1dp rounding alone\s+3,561\s+\(([\d.]+)%")
F["trunc_v2"] = P("decimal_truncation.txt", r"STRICT: explained by 1dp rounding alone\s+3,496\s+\(([\d.]+)%")
F["dp_mar"] = P("decimal_truncation.txt", r"values needing 2\+ decimal places: 4,382 of 16,315 \(([\d.]+)%\)")
F["decay"] = P("decay_curves.txt", r"one-month pairs, Nov-Dec excluded, n=8: build ([\d.]+% to [\d.]+%)")
F["decay_corr"] = P("decay_curves.txt", r"correlation of build-out share with gap length: \+([\d.]+)")
# The tests of 19 November 2026 on the eight pairs and on the twelve.
F["welch_p"] = P("decay_curves.txt", r"Welch t-test, first four pairs against last four: t [-\d.]+, df [\d.]+, p ([\d.]+)")
F["trend_p"] = P("decay_curves.txt", r"straight trend across the eight pairs: slope [+-][\d.]+ points a pair, t [-\d.]+, p ([\d.]+)")
F["gap_n"] = P("decay_curves.txt", r"correlation of build-out share with gap length on (\d+) pairs: [+-][\d.]+, p [\d.]+")
F["gap_p"] = P("decay_curves.txt", r"correlation of build-out share with gap length on \d+ pairs: [+-][\d.]+, p ([\d.]+)")
# The ladder's rows of 19 November 2026: the rule's own figure, the figure
# before the correction, and the readings with the unclear case counted as real.
F["R_rule"] = P("release_ladder.txt", r"by the rule, strict V = [\d.]+\s+([\d.]+)% \w+")
F["R_rule_v2"] = P("release_ladder.txt", r"by the rule, strict V = [\d.]+\s+[\d.]+% \w+\s+([\d.]+)% \w+")
F["V_strict"] = P("release_ladder.txt", r"by the rule, strict V = ([\d.]+)")
F["V_k"] = P("release_ladder.txt", r"V, strict literal\s+(\d+)/\d+")
F["R_before"] = P("release_ladder.txt", r"before the correction, V not applied\s+([\d.]+)% \w+")
F["V_hi"] = P("release_ladder.txt", r"strict V at its 95% upper bound ([\d.]+), the unclear case counted as not real")
_up = P("release_ladder.txt", r"the unclear case counted as not real\s+([\d.]+)% (\w+)\s+([\d.]+)% (\w+)")
F["R_up_v1"], F["verdict_up_v1"], F["R_up_v2"], F["verdict_up_v2"] = _up
F["V_all_k"] = P("release_ladder.txt", r"counted as real, (\d+) of \d+ = [\d.]+\s+[\d.]+% \w+")
F["V_all_hi"] = P("release_ladder.txt", r"counted as real, at its 95% upper bound ([\d.]+)\s+[\d.]+%")
_upr = P("release_ladder.txt", r"counted as real, at its 95% upper bound [\d.]+\s+([\d.]+)% (\w+)\s+([\d.]+)% (\w+)")
F["R_upr_v1"], F["verdict_upr_v1"], F["R_upr_v2"], F["verdict_upr_v2"] = _upr
_ne = P("release_ladder.txt", r"NO EVENT share, same interval\s+\d+/\d+ = ([\d.]+)\s+95% Wilson ([\d.]+) to ([\d.]+)")
F["noev_pct"], F["noev_lo"], F["noev_hi"] = (f"{float(x) * 100:.0f}" for x in _ne)
# The lags counted from the first release that could have carried each change,
# from script 18's block of 19 November 2026.
F["pre_n"] = P("salience_lag.txt", r"the (\d) cases with transactions before March 2025")
_pf = P("salience_lag.txt", r"transactions before March 2025, (\w+ \d{4}) to (\w+ \d{4}):")
F["pre_from"], F["pre_to"] = _pf
_af = P("salience_lag.txt", r"carried ([\d,]+) to ([\d,]+) days after the first release that")
F["after_lo"], F["after_hi"] = _af
F["first_possible"] = P("salience_lag.txt", r"could have carried them, (\w+ \d{4}), in")
F["after_months"] = P("salience_lag.txt", r"could have carried them, \w+ \d{4}, in (.+?); their lags")
_fl = P("salience_lag.txt", r"their lags could not be under ([\d,]+) to ([\d,]+) days")
F["floor_lo"], F["floor_hi"] = _fl
F["inw_n"] = P("salience_lag.txt", r"the (\d) cases with transactions inside the window")
F["inw_pos"] = P("salience_lag.txt", r"carried in the (\w+ and \w+) release after the transaction")
F["ceil"] = P("salience_lag.txt", r"their lags could not exceed ([\d,]+ and [\d,]+) days")
# The summary and section 6 say in words that no spread is statistically significant at the 5 per cent
# level, and section 6 says the same of the decay tests; the build stops if a p-value moves under 0.05.
if not all(float(F[k]) >= 0.05 for k in ("welch_p", "trend_p", "gap_p")):
    sys.exit("BUILD ABORTED: a decay test is now statistically significant at the 5 per cent level, "
             "against the typed sentence in section 6")
_w = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six"}
F["pre_w"], F["inw_w"] = _w[F["pre_n"]], _w[F["inw_n"]]

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
F["appear_n"] = f"{int(F['m1_n'].replace(',', '')) + int(F['m2_n'].replace(',', '')):,}"
F["rs_n"], F["rs_p"] = _row(r"-- RESTATEMENT TOTAL")
F["mt_n"], F["mt_p"] = _row(r"-- METHODOLOGY TOTAL")
F["chg_total"] = P("change_decomposition.txt", r"total apparent change (\d[\d,]*\d)")
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

# --- the presigned-source-URL finding -------------------------------------
# Admitted to the note on 8 September 2026 under six conditions. The two numbers
# the conditions allow come from 23_presigned_source_urls.py, which by construction
# cannot emit a key, a token, a signature or a whole URL.
F["presigned_n"] = P("presigned_source_urls.txt",
                     r"RELEASES CARRYING PRESIGNED SOURCE URLS: (\d+) of \d+")
F["presigned_total"] = P("presigned_source_urls.txt",
                         r"RELEASES CARRYING PRESIGNED SOURCE URLS: \d+ of (\d+)")
F["presigned_expiry"] = P("presigned_source_urls.txt",
                          r"The shortest declared expiry is (\d+) seconds")
F["panel_2026"] = P("panel_join_summary.txt",
                    r"August 2026   firms with any exposure  (\d+) of 328")

# Condition 6: drafted now, HELD until Global Energy Monitor has had the draft
# and either replies or ten working days pass. Put the date they were sent it
# here to release the subsection. None means held, and the note ships without it.
GEM_DRAFT_SENT = None

PRESIGNED_BLOCK = "" if GEM_DRAFT_SENT is None else f"""
<h3>A source citation that expires before it can be read</h3>
<p>The mechanisms above all move a number. This one moves none, and it belongs here nonetheless, because
it goes to whether a reader can check anything at all.</p>
<p>{F['presigned_n']} of the {F['presigned_total']} release files held here carry source citations written
as presigned links, that is, a document path followed by an authorisation the link carries in itself and
that lapses on a timer. Since the shortest timer declared in these files is {F['presigned_expiry']}
seconds, a reader who follows such a citation at any point after the minute it was made receives an
authentication failure rather than the document.</p>
<p><strong>Nothing is exposed, and this is not a security finding.</strong> The authorisations in the files
examined lapsed on issue, the earliest observed here in 2024, and none is quoted. What is reported is the
shape and the count, on the releases in hand, checked on the date in the figure register; no claim is made
about releases not held, since the archive here is the fourteen files the vendor supplied.</p>
<p>The consequence is the one this note has been making throughout, reached from a direction I was not
looking in. A citation is a promise that a reader can go and check, and a citation that cannot resolve is
not a weaker promise but a different kind of object, sitting in a dataset published under a licence whose
purpose is that others can verify the work. I found it because a machine scanned a file of mine and told
me what was in it, which is not a method I can take credit for.</p>
"""

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
# The grades the file gives its no-event verdicts, in its own words, and the
# subtypes the draw was stratified across. Read since 19 November 2026.
cases["grade"] = (cases.note.str.extract(r"(?i)(strong kind|weak kind: absence of evidence)")[0]
                  .str.lower().fillna("not graded"))
_noev = cases[cases.verdict.str.strip().str.upper() == "NO EVENT"]
F["n_strong"] = str(int((_noev.grade == "strong kind").sum()))
F["n_weak"] = str(int((_noev.grade == "weak kind: absence of evidence").sum()))
F["n_ungraded"] = str(int((_noev.grade == "not graded").sum()))
F["n_graded"] = str(int(F["n_strong"]) + int(F["n_weak"]))
_st = cases.subtype.str.strip().value_counts().to_dict()
F["st_removed"] = str(_st.get("link removed", 0))
F["st_material"] = str(_st.get("share revised, material", 0))
F["st_small"] = str(_st.get("share revised, small", 0))
if int(F["st_removed"]) + int(F["st_material"]) + int(F["st_small"]) != len(cases):
    sys.exit("BUILD ABORTED: the three subtypes do not account for every case")
_wn = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
       8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
F["n_strong_w"], F["n_weak_w"] = _wn[int(F["n_strong"])], _wn[int(F["n_weak"])]
F["n_graded_w"], F["n_ungraded_w"] = _wn[int(F["n_graded"])], _wn[int(F["n_ungraded"])]
F["n_noevent_w"] = _wn[int(F["n_noevent"])]
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
TODAY_WORDS = date.today().strftime("%d %B %Y").lstrip("0")

# Version of the published note. Bump this and add the version's date to VERSIONS
# below before tagging a new release; the repository's history holds every change
# between versions. The current version carries the day of the build, which is
# the day of the commit that is tagged, so that the version line, the byline and
# the file's name give one date.
VERSION = "1.5"
VERSIONS = {
    "1.0": "9 September 2026",
    "1.1": "15 September 2026",
    "1.2": "2 October 2026",
    "1.3": "20 November 2026",
    "1.4": "24 November 2026",
    "1.5": TODAY_WORDS,
}
CHANGELOG_LINE = ("Versions: " + "; ".join(f"{k}, {v}" for k, v in sorted(VERSIONS.items()))
                  + ". The repository's history holds every change between versions.")

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

/* Print. The PDF is a build output, not a manual Ctrl-P, so its pagination is
   fixed here rather than left to whoever prints it. Without this the page count
   depends on the operator's scale and margin settings, which is an unrecorded
   input to a published artefact. */
@page{size:A4;margin:17mm 15mm}
@media print{
  body{background:#fff;font-size:10pt;line-height:1.42}
  .wrap{max-width:none;margin:0;padding:0}
  h1{font-size:21pt} h2{font-size:14pt;margin:20pt 0 6pt;padding-top:10pt}
  h3{font-size:11.5pt;margin:13pt 0 5pt}
  p{margin:0 0 7pt} li{margin:0 0 4pt}
  table{font-size:8.5pt;margin:8pt 0 11pt} th,td{padding:4pt 6pt}
  .summary{padding:11pt 13pt;margin:0 0 16pt} .summary h2{font-size:12.5pt}
  .src{font-size:7.5pt} .meta{font-size:8.5pt;margin-bottom:18pt}
  footer{margin-top:22pt;font-size:8.5pt}
  h1,h2,h3{break-after:avoid;page-break-after:avoid}
  tr{break-inside:avoid;page-break-inside:avoid}
  thead{display:table-header-group}
  .summary{-webkit-box-decoration-break:clone;box-decoration-break:clone}
  .summary p{break-inside:avoid;page-break-inside:avoid}
  a{color:inherit;text-decoration:none}
}
"""

# The ladder's readings as the note names them: the rule is script 08's, and V
# not applied is R before the adjustment by V.
LADDER_LABELS = (("by the rule, ", "by the rule of script 08, "),
                 ("before the correction, V not applied", "before the adjustment by V"))


def ladder_label(reading):
    for old, new in LADDER_LABELS:
        reading = reading.replace(old, new)
    return reading


def ladder_rows():
    out = []
    for _, r in ladder.iterrows():
        cls = ""
        v1 = f'{r["R_V1"]*100:.1f}% <span class="{"fail" if r["verdict_V1"]=="FAILS" else ""}">{r["verdict_V1"]}</span>'
        v2 = f'{r["R_V2"]*100:.1f}% <span class="{"fail" if r["verdict_V2"]=="FAILS" else ""}">{r["verdict_V2"]}</span>'
        out.append(f'<tr{cls}><td>{ladder_label(r["reading"])}</td><td class="n">{v1}</td><td class="n">{v2}</td></tr>')
    return "\n".join(out)


def salience_rows():
    out = []
    for _, r in sal.iterrows():
        src = ("EDINET, front page" if "edinet" in r["transaction_source_url"].lower()
               and r["transaction_source_url"].rstrip("/").count("/") <= 2 else "source")
        out.append(f'<tr><td>{r["subject_name"]}</td><td>{r["party_name"]}</td>'
                   f'<td class="n">{r["transaction_date"]}</td>'
                   f'<td class="n">{r["gem_first_release_carrying_change"]}</td>'
                   f'<td class="n">{int(r["lag_days"]):,}</td>'
                   f'<td class="n">{r["first_release_that_could_carry"]}</td>'
                   f'<td class="n">{int(r["days_after_first_possible"]):,}</td>'
                   f'<td><a href="{r["transaction_source_url"]}">{src}</a></td></tr>')
    return "\n".join(out)


def case_rows():
    out = []
    for _, r in cases.iterrows():
        u = r["evidence_url"]
        if "gem.wiki" in u:
            ev = f'<a href="{u}">vendor\'s wiki</a>'
        elif u.startswith("internal to GEM"):
            ev = "vendor\'s later file"
        elif u.startswith("http"):
            ev = f'<a href="{u}">source</a>'
        else:
            ev = u[:60] or ""
        out.append(f'<tr><td class="n">{r["case"]}</td><td>{r["subject_name"]}</td><td>{r["party_name"]}</td>'
                   f'<td>{r["subtype"].replace("link removed", "edge removed")}</td><td>{r["verdict"]}</td><td>{r["grade"]}</td><td>{ev}</td></tr>')
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
<p class="meta">Carlo Hofer &middot; version {VERSION}, {TODAY_WORDS} &middot; data: Global Energy Monitor Global Energy Ownership Tracker, CC BY 4.0 &middot;
code, outputs and provenance records: github.com/ochofer/paper1-hazard-exposure-data</p>

<div class="summary">
<h2>Summary</h2>
<p>A growing number of research designs date corporate ownership change by differencing two releases of
the same database, reading an ownership link, an edge, that appears in the later release and not in the
earlier one as an event with a date. Vintage instability is documented in macroeconomic series (Goes, 2023) and
in a commercial ESG rating (Berg, Fabisik and Sautner, 2021), and neither study checks a revision against
a dated event case by case, which an ownership change allows, since the transaction behind it sits on
the public record. I ask whether such a difference behaves like a record of events, on two releases of
Global Energy Monitor's free Global Energy Ownership Tracker, March 2025 and August 2026.</p>
<p>I first sort every edge on which the two releases differ into three buckets: build-out, i.e., the
database growing, restatement, i.e., edges removed and shares revised, and methodology, i.e., changes in
the vendor's procedure. I
then draw {F['n_cases']} of the restatement changes at random and search the public record for the
transaction behind each one. Next, I rank firms by the coal and gas capacity their ownership stakes give
them, under two readings of an ownership share the earlier release leaves blank, as zero or imputed, and
compare the two releases' rankings. Finally, I compare the two releases' quintile spreads of monthly
returns on a cross-section of US and developed-European firms. A power calculation set the planned return
test, a cross-sectional design, aside.</p>
<p>Of the {F['n_cases']} restatement changes checked by hand, {F['n_noevent']} had no corporate event
behind them. Of the six that had one, the {F['inw_w']} whose transactions came after March 2025 are carried
in the {F['inw_pos']} release after their transactions. The {F['pre_w']} whose transactions predate March
2025 are carried in {F['after_months']}, lags that the frame of the sample fixes, so these six cases cannot
tell how visible an event was from when it happened.</p>
<p>Ranking firms by their coal and gas capacity, the
rank correlation between the two releases is below 0.95, the threshold above which a ranking counts as
stable, when a blank share is read as zero and above it when blanks are imputed, so a choice the analyst
makes and nobody documents decides the verdict. On the cross-section, the ranking changes between the two
releases mostly through firms that hold coal or gas units only in the later release. Among the firms both
releases cover, the ranking is below the 0.95 threshold when a blank share is read as zero, and above it
once the firms at zero only through blank shares are set aside.</p>
<p>The quintile-spread comparison's rule gives
the verdict {F['rule_phrase']}: the two releases' spreads are within one standard error of each other, and
their monthly series correlate too weakly for the verdict to be robust. On the standard
error of the difference between the two monthly series, the difference is statistically significant at the
5 per cent level, if only just, when blanks are imputed, and not when they are read as zero. No quintile spread is
statistically significant at the 5 per cent level, and the comparison has too little power for that null
to show an absence of effect, so it corroborates nothing in either direction.</p>
<p>The asset-level layer of the database is eighteen months old, so some of these findings are plausibly
properties of a young dataset and some of how ownership data is built and used; section 5 separates
them.</p>
</div>

<h2>Terms</h2>
<ul>
<li><strong>Release.</strong> One dated file of the Global Energy Ownership Tracker, the database of who
owns energy assets that Global Energy Monitor, the vendor, publishes. I compare March 2025 with
August 2026, for which I hold two files, V1 and V2 (Appendix A); figures are on V1 unless the text gives
both.</li>
<li><strong>Asset-level layer.</strong> The part of the tracker that links owners to individual plants
and mines. Its first release is March 2025.</li>
<li><strong>Edge.</strong> One ownership link in a release, from an owner to an entity or a unit it owns,
with the owner's share. The edges of a release form its ownership graph.</li>
<li><strong>Vintage difference.</strong> The edges on which two releases differ, i.e., the apparent
ownership change between them.</li>
<li><strong>Build-out, restatement and methodology.</strong> The three buckets into which I sort a
vintage difference (Appendix B). Build-out is the database growing: edges that appear in the later
release and blanks filled by new research. Restatement is edges removed and shares revised. Methodology is
a change in the vendor's procedure: blanks filled by an imputation rule, edges of entities the vendor
deduplicated and imputed shares moved because the owner count changed.</li>
<li><strong>R.</strong> The share of a vintage difference that is restatement or methodology, i.e., not
build-out.</li>
<li><strong>No event, real and unclear.</strong> My verdict on a sampled change: no corporate transaction
lies behind it, a transaction does, or neither could be established. The case table of Appendix C grades
some no-event verdicts "strong kind", a positive finding that the relationship still exists, or "weak
kind: absence of evidence".</li>
<li><strong>V.</strong> The share of the {F['n_cases']} sampled cases judged real. Strict V counts the six
real cases, in-window V only the {F['inw_w']} whose transactions fall inside the window, and two constructions of R
count the unclear case as real.</li>
<li><strong>Window and frame.</strong> The window runs from the first release, March 2025, to August
2026. The frame is what the sample can contain: a change that differs between those two releases can be
carried no earlier than the first release after March 2025, which sets a floor under the lag of a
transaction before the window and a ceiling over the lag of one inside it.</li>
<li><strong>The rule of script 08.</strong> It adjusts R by V when V lies between 0.25 and 0.50.</li>
<li><strong>The 25 per cent threshold.</strong> The level R must reach, in script 06, for the finding to
stand against the objection that the layer is young. A construction of R clears it or fails it.</li>
<li><strong>Blank share, zero reading and imputed reading.</strong> A blank share is an ownership share a
release leaves empty: March 2025 has many and August 2026 none. Under the zero reading a blank counts for
nothing. Under the imputed reading the owners whose shares are blank split equally whatever the known
shares of the same entity or unit leave, as the vendor's imputation rule does in August 2026.</li>
<li><strong>Attribution walk.</strong> The route from a unit up the ownership graph to the nearest owner
that the release flags as publicly listed and that carries an LEI or PermID identifier, a listed and
identified entity. The walk stops there, and that owner receives the unit's capacity.</li>
<li><strong>Attributable capacity.</strong> The megawatts of operating coal and gas power units an owner
receives through the attribution walk, each unit taken at the owner's share and summed.</li>
<li><strong>Firm.</strong> An owner whose attributable capacity I rank: worldwide, a listed and
identified entity at which the attribution walk stops; in the cross-section, one of its 328 ownership
entities.</li>
<li><strong>Cross-section, panel and entrant.</strong> The cross-section is 328 ownership entities in the
US and developed Europe, 302 of them listed companies with a price series, built on the August 2026
release. The panel is the {F['panel_eff']} firms of the cross-section with coal or gas units in either
release. An entrant is a firm of the panel with coal or gas units in August 2026 and none in March
2025.</li>
<li><strong>Rank correlation and the 0.95 threshold.</strong> The rank correlation is Spearman's, between
a measure's ranking of the same firms in the two releases. Above the 0.95 threshold of script 13 a
measure's ranking counts as stable between releases, and the measure drops to a footnote.</li>
<li><strong>Top-quintile overlap.</strong> The firms in the top fifth of a ranking in one release that are
also in the top fifth in the other, as a count or a share.</li>
<li><strong>Fossil share.</strong> A firm's coal and gas capacity as a share of its coal, gas and
bioenergy capacity, the only fleet share the tracker allows.</li>
<li><strong>Residual counterparty.</strong> A party such as "small shareholder(s)" whose share is 100
minus the named holders' shares rather than an observed stake.</li>
<li><strong>Over-count.</strong> The ratio of the sum of the vendor's own share column over all owners to
the world's operating coal and gas fleet.</li>
<li><strong>Pair and build-out share.</strong> A pair is two adjacent releases of the fourteen I hold. Its
build-out share is the share of its vintage difference that is build-out.</li>
<li><strong>Arm, quintile spread and the rule of script 11.</strong> An arm is the firms of one release
that enter the quintile-spread comparison. The quintile spread is the monthly return of the fifth of an
arm's firms with the most attributable capacity less that of the fifth with the least. The rule of script
11 compares the two releases' spreads: robust if they differ by less than one standard error and their
monthly series correlate above 0.95, fragile if they differ by more or correlate below 0.90, and mixed
otherwise.</li>
<li><strong>Newey-West standard error and minimum detectable effect.</strong> A Newey-West standard error
allows for autocorrelation in a monthly series. The minimum detectable effect is the effect at which the
expected t-statistic reaches the Harvey, Liu and Zhu (2016) hurdle of 3.0, an effect detected half the
time.</li>
<li><strong>Wilson interval.</strong> A confidence interval for a proportion that stays between zero and
one in a small sample.</li>
<li><strong>Script and provenance record.</strong> A script is a numbered program in the repository's
code folder. Each writes a provenance record naming the release it read by file name and checksum, its
pinned release (Appendix D).</li>
</ul>
<p>The thresholds and rules these comparisons are read against were written in the headers of the scripts
before they ran: the 25 per cent threshold of script 06, the 0.95 threshold of script 13, the control of
script 15 and the rule of script 11; the rule of script 08 was written after R was known and before the
sample was drawn.</p>

<h2>1. Nineteen changes, checked by hand</h2>
<p>March 2025 and August 2026 differ on {F['chg_total']} edges, and I sort them by rule into the three
buckets: {F['bo_n']} are build-out, {F['appear_n']} edges that appear in the later release and
{F['m3_n']} blanks filled by new research; {F['restatement_n']} are restatement, edges removed or shares
revised; and {F['mt_n']} are methodology, {F['m7_n']} blanks filled by an imputation rule, {F['m8_n']}
edges of entities the vendor deduplicated and {F['m9_n']} imputed shares moved because the owner count
changed. Because a vintage design would read a restatement change as an event, I drew {F['n_cases']} of
the {F['restatement_n']} at random, in proportion across the bucket's three subtypes, and traced each one
back to the transaction it would have to correspond to. I searched exchange filings, company statements
and press releases and, where no filing could be found, market-data sites and the vendor's own wiki and
later file. I classified the edges that appear by rule and did not verify them by hand.</p>
<p>I gave every verdict myself, knowing the thresholds, and no verdict by a second reader is recorded; the case
table's note on case 13 says that its verdict was written down in project documents outside the
repository before the case was checked. The case table grades {F['n_graded_w']} of the
{F['n_noevent_w']} no-event verdicts by one of its two phrases, {F['n_strong_w']} "strong kind" and
{F['n_weak_w']} "weak kind: absence of evidence"; the other {F['n_ungraded_w']} carry neither phrase, one
of them, case 8, calling its verdict strong in other words, and Appendix C prints the table's words.</p>
<p><strong>{F['n_noevent']} of the {F['n_cases']} had no corporate event behind them</strong>,
{F['noev_pct']} per cent of the sample, with a 95 per cent Wilson interval of {F['noev_lo']} to
{F['noev_hi']} per cent. Appendix C gives the full case table, with sources, verdicts and grades. This is
the central result for the restatement bucket, because it is the one finding that does not depend on any
modelling choice made downstream.</p>
<p>Six of the {F['n_cases']} had a datable transaction and a datable record. The lag from the transaction
to the first release carrying the change is {F['fast']} days for the two whose transactions fall inside
the window, a statutory disclosure by a listed Japanese issuer and a 1.9bn USD acquisition by a listed US
utility, and {F['slow_lo']} to {F['slow_hi']} days for the four whose transactions predate it, from
{F['pre_from']} to {F['pre_to']}. The frame fixes those four lags: a change sampled from the difference
between March 2025 and August 2026 cannot be carried before {F['first_possible']}, the first release after
March, so the four could not have had lags under {F['floor_lo']} to {F['floor_hi']} days whatever the
vendor did, and the two inside the window could not have had lags over {F['ceil']}. Counted from the first
release that could have carried them, the four were carried {F['after_lo']} to {F['after_hi']} days later,
in {F['after_months']}, and the two in the {F['inw_pos']} release after their transactions. What the six
show is a difference between records already out of date when the layer began and events that happened
while it was being watched. Whether the lag varies with how visible the event was cannot be told from
them, since every less visible case is also a case from before the first release. Six cases cannot
establish a correlation and I claim none.</p>
<p>For scale, {F['R_rule']}% of the vintage difference between these two releases is restatement or
methodology, by the rule of script 08 (V is {F['V_k']} of {F['n_cases']}, {F['V_strict']}); before the
adjustment by V, R is {F['R_before']}%, against the 25 per cent threshold of script 06. Section 4 sets out
every construction of R.</p>
<p class="src">Sources: <code>outputs/salience_lag.txt</code>, <code>outputs/event_validation_sample.csv</code>,
<code>evidence/salience_lag_cases.csv</code>, <code>outputs/restricted_r.txt</code>,
<code>outputs/release_ladder.txt</code>, <code>outputs/change_decomposition.txt</code></p>

<h2>2. Two undocumented choices, one the vendor's and one the analyst's</h2>
<p>Between the raw release and a portfolio sit two choices that nobody documents. The first is the
vendor's, namely which release you happen to hold; the second is the analyst's, namely what a blank share
is taken to mean. Neither is recorded anywhere in the data. The second moves a verdict; the first moves R
from {F['R_rule']} to {F['R_rule_v2']} per cent between V1 and V2 and leaves the verdict where it is
(Appendix A).</p>
<p><strong>The analyst's choice moves a verdict.</strong> Ranking the {F['u3_n']} firms of the
cross-section present in both releases by attributable capacity, the rank correlation between the two
releases is {F['u3_zero']} under the zero reading and {F['u3_imp']} under the imputed reading, against the
0.95 threshold of script 13. The same measure, on the same firms, on the same two releases, therefore
lands on opposite sides of the threshold depending only on the reading.</p>
<table>
<tr><th>Firms, rank correlation of attributable capacity between releases</th><th class="n">zero reading</th><th class="n">imputed reading</th></tr>
<tr><td>604 firms worldwide present in both releases</td><td class="n">{F['u2_zero']}</td><td class="n">{F['u2_imp']}</td></tr>
<tr><td>{F['u3_n']} firms of the cross-section present in both releases</td><td class="n">{F['u3_zero']}</td><td class="n">{F['u3_imp']}</td></tr>
<tr><td>{F['bio_n']} firms worldwide with bioenergy in both releases</td><td class="n">{F['bio_raw_zero']}</td><td class="n">{F['bio_raw_imp']}</td></tr>
<tr class="rule"><td>the 0.95 threshold of script 13</td><td class="n">0.95</td><td class="n">0.95</td></tr>
</table>
<p><strong>The flip on the 604 firms worldwide.</strong> It reproduces there, at {F['u2_zero']} and
{F['u2_imp']}, on either side of the 0.95 threshold as on the {F['u3_n']} firms of the cross-section, and
in the same direction. Without the firms at zero in March 2025 under the zero reading, {F['u2_zero576']}
of the 604 and {F['both_blank_zero']} of the {F['both_units']} firms of the cross-section with coal or gas
units in both releases, both readings clear the threshold on both sets of firms: {F['u2_pos_zero']} and
{F['u2_pos_imp']} on the {F['u2_pos_n']}, {F['pos_sp_zero']} and {F['pos_sp_imp']} on the
{F['pos_n']}. On both sets the flip is those firms. On the {F['bio_n']} firms with bioenergy in both
releases, by contrast, attributable capacity does not flip, and that is the stated limit of the claim;
the three sets of firms are not nested. The {F['u3_n']} are the firms of the cross-section with coal, gas
or bioenergy units in both releases: {F['u3_fossil_both_imp']} of them have coal or gas units in both, and
{F['u3_bio_alone']} have bioenergy alone in both; section 4 returns to the
{F['u3_fossil_both_imp']}.</p>
<p><strong>Why the reading carries that much force.</strong> Under the zero reading, {F['n_zerocap']} of
the {F['n_march']} firms worldwide with coal or gas units in March 2025 carry attributable capacity of
exactly zero, because every path from them to a unit crosses a blank share and a blank read as zero is
nothing; under the imputed reading none do. The reading therefore decides whether a firm registers as
having any capacity at all, which is a membership decision rather than a measurement one.</p>
<p>The same choice roughly halves measured growth: on the 604 firms present in both releases,
attributable capacity grows {F['growth_zero']}% under the zero reading and {F['growth_imp']}% under the
imputed reading. The reading bites this hard because of the distribution of blanks itself: March 2025
carries {F['blank_mar']} blank shares, {F['blank_pct']}% of its edges, while August 2026 carries none,
because the vendor filled them in between releases.</p>
<h3>An apparent finding that dissolved under a control</h3>
<p>Ranked by fossil share, firms looked far less stable across releases than ranked by attributable
capacity: {F['fs_zero']} and {F['fs_imp']} against the same 0.95 threshold. The top-quintile overlap of
fossil share has no one figure: {F['fs_tied_mar_zero']} of the {F['fs_n_zero']} firms of the
cross-section with a share in both releases tie at a share of exactly 1 for the {F['fs_k_zero']} places
of the top quintile in March 2025, and {F['fs_tied_aug_zero']} in August 2026, under the zero reading
({F['fs_tied_mar_imp']} and {F['fs_tied_aug_imp']} of {F['fs_n_imp']} for {F['fs_k_imp']} places under
the imputed reading), so the count of firms kept runs from none to all of them with the order of the tied
firms, and I give no figure. Those two pairs are on the firms of the cross-section with a share in both
releases, {F['fs_n_zero']} and {F['fs_n_imp']}. The control of script 15 restricts
the comparison to the {F['bio_n']} firms worldwide whose denominator exists in both releases, i.e., with
bioenergy in both, chosen under the zero reading and then taken under both readings. On them the rank
correlation is {F['bio_zero']} and {F['bio_imp']}, with top-quintile overlaps of {F['bio_ov_zero']}% and
{F['bio_ov_imp']}% and no firm tied at the boundary of the top quintile in either release; on the
{F['bio34_n']} of them in the cross-section it is {F['bio34_zero']} and {F['bio34_imp']}; and with the
firms chosen under the imputed reading instead, {F['bio_imp_n']} worldwide, it is {F['bio_imp_fs']},
against {F['bio_imp_raw']} for attributable capacity on the same firms, so the control clears under either
choice of the firms. <strong>These figures indicate that the instability arises mostly from the
denominator's own coverage moving between releases rather than from anything about the firms</strong>,
and the scaling result accordingly stands as a coverage finding and not as a measurement one.</p>
<p class="src">Sources: <code>outputs/bioenergy_check.txt</code>, <code>outputs/scaling_second_column.txt</code>,
<code>outputs/exposure_proxy_summary.txt</code></p>

<h2>3. A boolean moved {F['ameren_mw']} MW between two companies</h2>
<p>A unit's capacity goes to the owner at which the attribution walk stops, so the attribution depends on
where the walk stops, and whether an entity counts as listed is a flag in the data. Flags change.</p>
<table>
<tr><th>Firm</th><th class="n">March 2025</th><th class="n">August 2026</th></tr>
<tr><td>Ameren</td><td class="n">{F['ameren_mw']} MW, {F['ameren_units']} units</td><td class="n">absent</td></tr>
<tr><td>Union Electric</td><td class="n">absent</td><td class="n">{F['ameren_mw']} MW, {F['ameren_units']} units</td></tr>
</table>
<p>The two rows are identical to the decimal and identical in unit count, and not one generating unit was
built, retired or sold between them. What changed instead was Union Electric's listed flag, from false to
true, so that the attribution walk stopped at it and it retained the capacity its parent had been
receiving.</p>
<p><strong>Ameren was not delisted.</strong> It is flagged as publicly listed in both releases, and it
lost the capacity because a subsidiary gained the flag. Since the cross-section is built on the later
release, Ameren does not appear in it at all, and it follows that a boolean on a subsidiary decided which
of two companies entered the study.</p>
<p>A further consequence follows for anyone using a release directly. Summing the vendor's own ownership
share column over all owners over-counts the world's operating coal and gas fleet by a factor of
{F['over_mar']} in March 2025 and {F['over_aug']} in August 2026, because the release emits a row for
every ancestor of a unit rather than for the owner at which the attribution walk stops, and <strong>the
over-count grew between releases</strong>. Appendix B works it through alongside the other
mechanisms.</p>
<p class="src">Sources: <code>outputs/exposure_proxy_by_firm.csv</code>, <code>outputs/exposure_proxy_summary.txt</code></p>

<h2>4. What this does to a portfolio, and the full R table</h2>
<p>I join the measure to the cross-section, 328 ownership entities in the US and developed Europe, 302 of
them listed companies with a price series. {F['never']} of the 328 hold no coal or gas power units in
either release, because the measure covers power only, so the panel is {F['panel_eff']} firms.</p>
<table>
<tr><th>On the {F['panel_eff']} firms of the panel</th><th class="n">zero reading</th><th class="n">imputed reading</th></tr>
<tr><td>Rank correlation between releases</td><td class="n">{F['p_sp_zero']}</td><td class="n">{F['p_sp_imp']}</td></tr>
<tr><td>Top-quintile overlap</td><td class="n">{F['p_ov_zero']}%</td><td class="n">{F['p_ov_imp']}%</td></tr>
<tr><td>Growth in attributable capacity</td><td class="n">+{F['u3g_zero']}%</td><td class="n">+{F['u3g_imp']}%</td></tr>
<tr><th>On the {F['both_units']} firms with coal or gas units in both releases</th><th class="n">zero reading</th><th class="n">imputed reading</th></tr>
<tr><td>Rank correlation between releases</td><td class="n">{F['both_sp_zero']}</td><td class="n">{F['both_sp_imp']}</td></tr>
<tr><td>Top-quintile overlap</td><td class="n">{F['both_ov_zero']}</td><td class="n">{F['both_ov_imp']}</td></tr>
<tr><td>Growth in attributable capacity</td><td class="n">{F['both_g_zero']}%</td><td class="n">{F['both_g_imp']}%</td></tr>
<tr><td>Of them, at zero in March 2025 under the reading</td><td class="n">{F['both_blank_zero']}</td><td class="n">{F['both_blank_imp']}</td></tr>
<tr><td>Rank correlation on the {F['pos_n']} above zero in March 2025 under both readings</td><td class="n">{F['pos_sp_zero']}</td><td class="n">{F['pos_sp_imp']}</td></tr>
</table>
<p>On the panel the top quintile turns over {F['turn_lo']}% to {F['turn_hi']}% of its firms between the
two releases, against rank correlations of {F['p_sp_zero']} and {F['p_sp_imp']}. On the
{F['both_units']} firms with coal or gas units in both releases the rank correlations are
{F['both_sp_zero']} under the zero reading and {F['both_sp_imp']} under the imputed reading, the first
below the 0.95 threshold, and the top quintile keeps {F['both_ov_zero']} and {F['both_ov_imp']} firms. The
difference between the two sets of firms is the {F['one_only']} firms present in one release only,
{F['entered']} entrants and {F['left']} that left, the cross-section being built on the later release. The
{F['ent_mw']} MW the {F['entered']} entrants hold in August 2026 split, unit by unit, into three parts:
{F['ent_i_mw']} MW, {F['ent_i_pc']} per cent, in units the March 2025 release attributed to a listed
entity that owns the entrant in August 2026, the entrant not then a listed and identified entity, the
mechanism of section 3; {F['ent_ii_mw']} MW, {F['ent_ii_pc']} per cent, in the rest of the units the March
2025 release carried; and {F['ent_iii_mw']} MW, {F['ent_iii_pc']} per cent, in units it did not carry.
{F['ent_top1']} and {F['ent_top2']} hold {F['ent_top1_pc']} and {F['ent_top2_pc']} per cent of the first
part.</p>
<p>The {F['panel_eff']} firms of the panel are the {F['both_units']} with coal or gas units in both
releases plus the {F['one_only']} present in one release only, and the {F['u3_n']} of section 2 are those
{F['both_units']} plus {F['u3_bio_alone']} firms with bioenergy alone in both releases. Under the zero
reading {F['both_blank_zero']} of the {F['both_units']} are at zero in March 2025 because every path from
them to a unit crosses a blank share; on the {F['pos_n']} others the two readings give {F['pos_sp_zero']}
and {F['pos_sp_imp']}, a gap of {F['gap_pos']} against {F['gap_both']} on the {F['both_units']}. Of the
{F['rose_zero']} firms at zero in March 2025 and above it in August 2026 under the zero reading,
{F['rose_entered_zero']} are entrants and {F['rose_blank_zero']} are at zero in the March 2025 release
under that reading because every path from them to a unit crosses a blank share. For a signal rebalanced
on vendor releases, the turnover on the panel is paid for entrants; among the firms both releases cover
the ranking is {F['both_sp_zero']} under the zero reading, below the 0.95 threshold, and
{F['pos_sp_zero']} once the {F['both_blank_zero']} firms with blank shares alone are set aside.</p>
<h3>R, every construction</h3>
<p>R is the share of the vintage difference that is not build-out. Because its construction involves
several defensible choices, I set every construction out in one table rather than one preferred
figure.</p>
<table>
<tr><th>Construction</th><th class="n">August 2026, V1</th><th class="n">August 2026, V2</th></tr>
{ladder_rows()}
<tr><td>Generous bound, crediting every plausible real event</td><td class="n">{F['R_generous']}%</td><td class="n"></td></tr>
<tr><td>Residual counterparties removed from both sides</td><td class="n">{F['R_restricted']}%</td><td class="n"></td></tr>
<tr class="rule"><td>The 25 per cent threshold of script 06</td><td class="n">25%</td><td class="n">25%</td></tr>
</table>
<p>The first row is the figure by the rule of script 08. The second row is R before the adjustment by V,
which the bucket table of Appendix B sums to.</p>
<p><strong>The restricted construction is the more conservative one, and it raises R rather than lowering
it.</strong> Removing the edges of residual counterparties takes proportionally more out of the
denominator than the numerator, because those counterparties are concentrated in build-out, at
{F['resid_buildout']}%, and build-out sits in the denominator only. I had assumed the restriction would
deflate R and threaten the threshold. The assumption was backwards.</p>
<p>One further inference follows from that concentration and no more: nearly a quarter of the edges
counted as build-out are new edges to a residual counterparty, which is coverage of the unnamed rather
than of the named.</p>
<p>The two August 2026 columns are V1 and V2, two files I hold for the same month, one of them sent to me
by the vendor on 26 August 2026 and not a public reissue, neither marked as a version anywhere in the data.
Appendix A sets that out, including the construction at which R <span class="fail">fails</span> the 25 per
cent threshold on one file and clears it on the other, together with the reason the comparison is pinned
to V1.</p>
<p class="src">Sources: <code>outputs/panel_join_summary.txt</code>, <code>outputs/panel_entrants.txt</code>,
<code>outputs/release_ladder.txt</code>, <code>outputs/restricted_r.txt</code>, <code>outputs/change_decomposition.txt</code></p>

<h2>5. The layer is eighteen months old</h2>
<p>What I measure is the asset-level layer, and its age bounds several of the findings above. The vendor
confirms it has no release before March 2025, and the earliest file I hold, from June 2024, carries
entity-to-entity relationships only and no asset-level ownership; the tracker as a product is therefore
older than the layer measured here. The window is accordingly the layer's first eighteen months, across
the fourteen releases I hold and the thirteen pairs between them.</p>
<p>The vendor supplied those releases on request. Because no public archive of past releases exists, the
comparison is auditable from the files themselves and cannot be reproduced by a reader who starts from the
vendor's site.</p>
<p><strong>Findings that depend on that maturity:</strong> the level of R, the decay curves, and the share
of one release's vintage difference that is methodology.</p>
<p><strong>Findings that do not:</strong> the over-count, the blank-share reading that flips a verdict,
and the mechanism by which a flag change moves {F['ameren_mw']} MW between two companies. Those are
properties of how ownership data is built and used, not of how long this particular dataset has
existed.</p>
<p class="src">Sources: <code>outputs/decay_curves.txt</code>, GEM correspondence of 21 August 2026</p>

<h2>6. Limitations</h2>
<p><strong>The quintile-spread comparison corroborates nothing.</strong> Each release gives one arm, the
firms with attributable capacity above zero in that release and a price series ({F['arm_25']} firms in the
March 2025 arm and {F['arm_26']} in the August 2026 arm). I compute each arm's quintile spread,
equal-weighted, in local currency, monthly to December 2025, and the rule of script 11 asks whether the
two releases give the same answer. The two spreads differ by {F['rule_d_zero']} and {F['rule_d_impute']}
times the larger of their two standard errors under the zero and the imputed reading, the rule's measure
and not the standard error of their difference, and the two monthly series correlate at
{F['rule_c_zero']} and {F['rule_c_impute']}, so the verdict is {F['rule_phrase']}. The Newey-West standard
error of the difference of the two series, which is not part of the rule's verdict, is {F['dse_zero']}%
and {F['dse_impute']}% a year, and the difference over it {F['dt_zero']} and {F['dt_impute']}. Under the
imputed reading the difference is statistically significant at the 5 per cent level on the standard error
of the difference, if only just, and under the zero reading it is not. Every t-statistic of the comparison is at most
{F['t_max']}, with Newey-West standard errors of {F['se_lo']}% to {F['se_hi']}% a year. The minimum
detectable effect at the Harvey, Liu and Zhu hurdle of 3.0 is {F['mde_lo']}% to {F['mde_hi']}% a year
across the arms, an effect detected half the time, and at a power of 80 per cent it is {F['mde80_lo']}% to
{F['mde80_hi']}%. An effect smaller than that is detected less than half the time, so the null is a
statement about the power of the comparison rather than about the world. A null quoted without a minimum
detectable effect reads as evidence of absence. I set the planned return test, a cross-sectional
Fama-MacBeth design, aside before it ran, on a power calculation requiring {F['pw_months']} monthly
observations at an assumed monthly standard deviation of 2 per cent ({F['pw_months_1pct']} at 1 per cent;
{F['pw_months_80']} at 80 per cent power), in <code>outputs/power_comparison.txt</code>.</p>
<p><strong>Both arms contain look-ahead, deliberately and identically</strong>, so they are comparable
with each other and neither is a return prediction.</p>
<p><strong>Prices.</strong> Returns use <code>adjClose</code> from Financial Modeling Prep's
dividend-adjusted end-of-day series, pulled on 21 August 2026. The adjustment is the vendor's, covering
splits as well as dividends, and no unadjusted close is archived beside it; the series is not
redistributable, and its per-file checksums are published in the repository manifest.</p>
<p><strong>Nineteen is a small sample</strong>, drawn once and not reproducible as a draw, so the
{F['n_noevent']} no-event verdicts support a statement about the proportion only through their Wilson
interval, {F['noev_lo']} to {F['noev_hi']} per cent, computed as the interval of V is in Appendix A rather
than assumed. How the verdicts divide by subtype is a question these nineteen cases cannot answer, since I
drew the sample from the restatement bucket, {F['restatement_n']} of the {F['chg_total']} edges that
differ, stratified in proportion across its three subtypes ({F['st_removed']}, {F['st_material']} and
{F['st_small']} cases of edges removed, shares revised by more than one point and shares revised by less,
the rounding of 20 times each share giving {F['n_cases']}), and nineteen are too few to report by
subtype.</p>
<p><strong>Decay.</strong> Where a decay figure appears it is the subset of pairs one month apart with the
November to December 2025 pair excluded, n = 8, build-out share {F['decay']} from the first four pairs to
the last four. That difference is not statistically significant at the 5 per cent level, on a Welch t-test
of the first four pairs against the last four (p {F['welch_p']}) or on a straight trend (p
{F['trend_p']}). The correlation of +{F['decay_corr']} between build-out share and the gap between
releases, on {F['gap_n']} pairs, is not statistically significant at the 5 per cent level either (p
{F['gap_p']}).</p>

<h2>7. On the vendor</h2>
<p>Global Energy Monitor is a non-profit, and the conditions under which I could write the note at all
follow from that. The data is free and published under CC BY 4.0; the vendor sent the past releases
compared here on request, and they are not in the repository, whose provenance records name them by file
name and checksum; the vendor answered six detailed questions of mine within days and undertook in writing
to document the imputation rule in future releases. At the same time, it shipped, unprompted, flags
marking a large share of edges as no longer maintained, and did not mention them in its covering note. I
sent a draft of the note to Global Energy Monitor before publication.</p>
<p>As at 19 November 2026 the vendor publishes no release list or changelog and its project page gives no
launch date, and on 9 September 2026 its download page still referenced an earlier release, so a reader
cannot independently confirm the completeness of the release history. That observation concerns what is
published around the data rather than the quality of the data itself, and it matters because the release
history is the one input to the note that a reader cannot reconstruct.</p>
<p>The licence permits publishing the inputs beside the result, and I do not publish them: the fourteen
past releases are not in the repository, and the vendor's site, read on 19 November 2026, offers the
current release alone. The effects reported here are therefore checkable against the code and the
outputs, and the comparison itself cannot be rerun from what is published.</p>

<h2>8. What this measures, and what it does not</h2>
<p>The natural comparison is with the settings in which vintage instability has already been documented.
Goes (2023) reports it in macroeconomic series revised by statistical agencies, comparing releases of the
World Development Indicators and replicating three articles across data sources and releases. Berg,
Fabisik and Sautner (2021) report it in a commercial ESG rating, where rewritten scores relate to returns
and the original scores do not. Neither checks a revision against a dated event case by case. An ownership
change either happened or it did not, and the transaction behind it sits on the public record, so a
difference can be checked case by case. I report vintage instability in a free, non-profit, openly
licensed database, and in a layer eighteen months old, so the three settings differ in maturity and in
whether a revision is checked against a dated event.</p>
<p>For a user of the tracker, the implication is that a difference between two releases in the restatement
bucket is not a usable event indicator, since {F['n_noevent']} of the {F['n_cases']} sampled differences,
{F['noev_lo']} to {F['noev_hi']} per cent at the 95 per cent level, had no transaction behind them. Of the
six that did, the {F['inw_w']} whose transactions fell inside the window were carried in the
{F['inw_pos']} release after their transactions, and the {F['pre_w']} whose transactions predate the first
release were carried {F['after_lo']} to {F['after_hi']} days after the first release that could have
carried them. I did not verify what the edges that appear contain. For a signal built on the measure, the
estimates in section 4 suggest that a single release re-draws the ranking at rank correlations of
{F['p_sp_zero']} and {F['p_sp_imp']} on the panel, and at {F['both_sp_zero']} and {F['both_sp_imp']} under
the two readings on the firms both releases cover, so that most of the movement is entrants.</p>
<p>The limits that bear on that claim are set out in section 6. The one that bounds it most is that I drew
nineteen cases once from one bucket, in proportion across its three subtypes, so how the verdicts divide
by subtype, or in the build-out and methodology buckets, is a question these data cannot answer.</p>
<p>What would settle the questions left open is a longer archive and a larger draw across every bucket. A
release history covering several years would show whether R decays as the layer matures, which fourteen
releases across eighteen months cannot; and a sample large enough within each bucket and subtype would
give verdict shares by mechanism rather than in aggregate.</p>
<p>Against this evidence, the claim here is narrow. A difference between two releases of this tracker in
the restatement bucket recorded, in {F['n_noevent']} of the {F['n_cases']} cases sampled, the vendor
editing the tracker. Where it records an event, it can do so years late, and in the six cases dated the
four longest delays belong to transactions that predate the first release the layer had. And an
undocumented choice, the analyst's reading of a blank share, moves a verdict; by the rule of script 08
both V1 and V2 clear the 25 per cent threshold, at {F['R_rule']} and {F['R_rule_v2']} per cent.</p>

<div class="appendix">
<h2>Appendix A. Two files called August 2026</h2>
<p>Two files in my archive carry August 2026, V1 and V2. V2 was sent later than V1 and holds columns the
public release does not, including one the vendor describes as internal, which indicates that it is a
variant supplied to me rather than a public reissue. Because nothing inside either file identifies which
is which, a script that resolves a release by file name can switch silently to V2, and the release pin in
<code>code/_release.py</code> prevents it.</p>
<table>
<tr><th>Construction</th><th class="n">V1</th><th class="n">V2</th></tr>
{ladder_rows()}
<tr class="rule"><td>The 25 per cent threshold of script 06</td><td class="n">25%</td><td class="n">25%</td></tr>
</table>
<p><strong>At the upper bound of V's interval R clears the threshold on one file and fails it on the
other with the unclear case counted as not real, and fails it on both with the unclear case counted as
real.</strong> I derive V from the verified case verdicts and compute its Wilson interval rather than
assume it, so the constructions at the bound apply the upper end of that interval ({F['V_hi']} with
{F['V_k']} of {F['n_cases']} real, {F['V_all_hi']} with {F['V_all_k']}) rather than a pessimistic figure
chosen by hand; the figure by the rule of script 08, strict V at its point value, clears on both
files.</p>
<p><strong>The comparison is pinned to V1</strong> because the cross-section of 328 ownership entities is
itself built from V1, before V2 arrived; it is not pinned to V1 because V1 clears the threshold. Had the
cross-section been built on V2, the pin would have gone to V2, and at the upper bound of V's interval the
figure on that file falls below the 25 per cent threshold.</p>
<h3>The truncation trap</h3>
<p>Between the two releases the vendor truncated ownership shares to one decimal place, so that
{F['dp_mar']}% of March 2025 values need two decimals and none of the August values do.
<strong>{F['trunc']}% of all share-value changes between March 2025 and V1 are that and nothing
else</strong> ({F['trunc_v2']}% against V2). R is unaffected, because the 0.06 threshold used to build the
sample had already excluded them; it follows, however, that anyone rerunning this comparison with a
tighter threshold will manufacture roughly three and a half thousand changes that are formatting.</p>

<h2 class="appendix">Appendix B. The mechanism catalogue</h2>
<p>This appendix catalogues every route, found in this data, by which a vintage difference shows an
ownership change when nothing happened to the company. The table counts the mechanisms that appear as a
change to an edge, which is what the decomposition can see; six further mechanisms move a number without
moving an edge, and they are listed after it. The grouping is the one that matters for a design, because
build-out is the bucket expected to decay as the database matures, and R is the share of this table that
is not expected to; eighteen months do not show whether it decays (section 6).</p>
<table>
<tr><th>Bucket</th><th>Mechanism</th><th class="n">Edges</th><th class="n">Share of the vintage difference</th></tr>
<tr><td rowspan="4"><strong>Build-out</strong><br>expected to decay with maturity</td>
    <td>new entity brought into coverage</td><td class="n">{F['m1_n']}</td><td class="n">{F['m1_p']}%</td></tr>
<tr><td>new edge between entities already covered</td><td class="n">{F['m2_n']}</td><td class="n">{F['m2_p']}%</td></tr>
<tr><td>blank filled by genuine new research</td><td class="n">{F['m3_n']}</td><td class="n">{F['m3_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['bo_n']}</td><td class="n">{F['bo_p']}%</td></tr>
<tr><td rowspan="4"><strong>Restatement</strong><br>not expected to decay</td>
    <td>edge removed, not explained by deduplication</td><td class="n">{F['m4_n']}</td><td class="n">{F['m4_p']}%</td></tr>
<tr><td>share revised, material, over one point</td><td class="n">{F['m5_n']}</td><td class="n">{F['m5_p']}%</td></tr>
<tr><td>share revised, small, under one point</td><td class="n">{F['m6_n']}</td><td class="n">{F['m6_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['rs_n']}</td><td class="n">{F['rs_p']}%</td></tr>
<tr><td rowspan="4"><strong>Methodology</strong><br>not expected to decay</td>
    <td>blank filled by an imputation rule introduced after March 2025</td><td class="n">{F['m7_n']}</td><td class="n">{F['m7_p']}%</td></tr>
<tr><td>entity deduplicated by the vendor, per the remapping sheet</td><td class="n">{F['m8_n']}</td><td class="n">{F['m8_p']}%</td></tr>
<tr><td>imputed share moved because the owner count changed</td><td class="n">{F['m9_n']}</td><td class="n">{F['m9_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['mt_n']}</td><td class="n">{F['mt_p']}%</td></tr>
<tr class="rule"><td>R</td><td>restatement plus methodology, before the adjustment by V</td><td class="n">{F['rs_n']} + {F['mt_n']}</td><td class="n">{F['R']}%</td></tr>
</table>
<p>The table covers {F['chg_total']} changed edges, against {F['chg_unchanged']} that did not move between the
two releases.</p>

<h3>Six mechanisms that move a number without moving an edge</h3>
<p>None of these appears in the table above, because the decomposition counts edges and none of these
mechanisms adds, removes or revises one. They are set out here because a user who reconciles two releases
by comparing values rather than edges will meet them first.</p>
<ol>
<li><strong>Decimal truncation.</strong> {F['trunc']}% of all share-value changes between March 2025 and
V1 are one-decimal rounding and nothing else. They sit below the 0.06 threshold used to build the
verification sample, so they never enter R; anyone who sets a tighter threshold puts every one of them
in.</li>
<li><strong>A listed flag changing.</strong> {F['ameren_mw']} MW and {F['ameren_units']} units moved from
Ameren to Union Electric with no edge added, removed or revised, because what moved was the point at which
the attribution walk stops rather than the graph. Section 3 works the case.</li>
<li><strong>The over-count.</strong> Summing the vendor's own share column over all owners gives
{F['over_mar']} times the operating fleet in March 2025 and {F['over_aug']} times it in August 2026. That
is a property of the release's shape rather than a change between releases; the factor nonetheless grew,
and it follows that a user comparing two naive sums measures the growth of the over-count alongside the
growth of the fleet.</li>
<li><strong>The blank-share reading.</strong> This one is the analyst's and not the vendor's. The zero
reading in place of the imputed reading moves measured growth from {F['growth_imp']}% to
{F['growth_zero']}%, and puts {F['n_zerocap']} of the {F['n_march']} firms worldwide with coal or gas
units in March 2025 at exactly zero attributable capacity, because every path from them to a unit crosses
a blank share.</li>
<li><strong>Coverage moving inside a denominator.</strong> Any measure scaled by fossil share inherits the
coverage change in its denominator, which is what dissolved the scaling result in section 2.</li>
<li><strong>Two files carrying the same month.</strong> V1 and V2 both carry August 2026 and nothing inside
either identifies which is which, so a script that resolves a release by file name may read either of
them; Appendix A gives the figures that differ between them.</li>
</ol>

<h3>Two boundaries this catalogue does not settle</h3>
<p><strong>Deduplication.</strong> The remapping sheet accounts for {F['remap_n']} entities the vendor
deleted as duplicates, which is {F['remap_pct']}% of the entities lost between these releases, and it
follows that an unknown part of the {F['m4_n']} removed edges is unrecorded deduplication rather than
restatement. Reclassifying any of them moves edges from restatement to methodology, and both sit inside R,
so the boundary does not move R, though its internal line is soft.</p>
<p><strong>Real churn.</strong> Of the {F['both_edges']} edges present in both releases, observed ownership
churn over eighteen months puts a ceiling of {F['churn_ceiling']} genuine corporate events, or
{F['churn_pct']}% of them. Crediting every one of those to the restatement bucket is what produces the
generous bound in section 4, which is accordingly a ceiling and not an estimate, and the most favourable
account the data will support.</p>
<p>One thing the vendor does here helps a user directly. August 2026 flags {F['imp_flag_n']} edges,
{F['imp_flag_p']}% of them, as imputed values, so a reader of that flag can tell an imputed share from an
observed one directly. March 2025 carries no such flag, and it is for that reason that the imputation row
above counts as methodology rather than as something a user could have seen coming.</p>
{PRESIGNED_BLOCK}
<p class="src">Sources: <code>outputs/change_decomposition.txt</code>, <code>outputs/exposure_proxy_summary.txt</code>,
<code>outputs/decimal_truncation.txt</code>, <code>outputs/bioenergy_check.txt</code></p>

<h2 class="appendix">Appendix C. The nineteen verified cases</h2>
<table>
<tr><th class="n">#</th><th>Subject</th><th>Counterparty</th><th>Change type</th><th>Verdict</th><th>Grade, the case table's words</th><th>Evidence</th></tr>
{case_rows()}
</table>
<p>I gave every verdict. The grade column prints the case table's own words where it grades a no-event
verdict by one of its two phrases, "strong kind" or "weak kind: absence of evidence", and "not graded"
otherwise; case 8's note calls its verdict strong in other words and is printed as not graded. Where the
evidence is the vendor's own material, the column says so.</p>
<h3>The six datable cases and their lags</h3>
<p>I measure the lag from the transaction date to the first day of the month of the first release
carrying the change. Because I read the dates by hand from the sources linked, the file behind this table,
<code>evidence/salience_lag_cases.csv</code>, is a curated input that I validated against the verdicts
above rather than computed from them. The frame fixes a floor under the lag of a transaction before March
2025 and a ceiling over the lag of one inside the window; the last two columns give the first release that
could have carried the change and the days from it to the carrying release. The transaction date of the
State Street case is the reporting date of a 13G filing as listed by an aggregator.</p>
<table>
<tr><th>Subject</th><th>Counterparty</th><th class="n">Transaction</th><th class="n">Release</th><th class="n">Lag, days</th><th class="n">First release that could have carried it</th><th class="n">Days after it</th><th>Source</th></tr>
{salience_rows()}
</table>

<h2 class="appendix">Appendix D. Figure register</h2>
<p>Every result figure in this note resolves to a named output file. The note is generated by
<code>code/19_build_note.py</code>, which extracts each result figure from those files at build time and
aborts if a pattern is absent or matches more than once, so no result figure here was typed by hand. The
labels and settings are typed: the universe count 604 in a table's label and the 328 and 302 of the
cross-section, the thresholds 0.95, 25% and 0.06, the bounds 0.25 and 0.50 of script 08's rule, the 0.90 of
script 11's rule and its hurdle of 3.0 standard errors, the 2 per cent behind the power calculation, n = 8
and the 1.9bn USD of one case, and the counts written as words, fourteen releases, thirteen pairs, eighteen
months, six questions, nineteen cases and the six of them with a datable transaction; the register of script 16 checks that a string is present in a file and cannot
tell that a number is correct. The check guards against an identifier typed from memory.</p>
<table>
<tr><th>Script</th><th>Release resolved</th><th class="n">SHA-256, first 16</th></tr>
{prov_rows()}
</table>

<h3>Two conventions this register runs on</h3>
<p><strong>Every data output is deterministic.</strong> Each is sorted before it is written, so a reader
who reruns the script against the pinned release obtains the same bytes and therefore the same checksum.
Two outputs are built from Python sets, whose order differs from one process to the next, and the two
scripts sort their rows before writing; the sorted files are the outputs of record, and the copies beside
them under a superseded marker hold the same rows in another order. The run logs, the <code>.txt</code>
summaries, print the path of the output folder relative to the repository, so their checksums do not depend
on where the script ran.</p>
<table>
<tr><th>Two outputs and their earlier copies</th><th class="n">output of record</th><th class="n">earlier copy</th></tr>
{promoted_rows()}
</table>
<p><strong>Two outputs are withheld.</strong> Because the arms of the quintile-spread comparison are
computed from a licensed price series that cannot be redistributed, these two files are named here with
their checksums and with the script that produces them, and a reader reproduces them by rerunning that
script against their own pull.</p>
<p>Of those two, the note draws its return figures from the <code>.csv</code> alone. The
<code>.txt</code> is a summary of the same series, and a summary is a derived object that
can move while the series does not, which is the claim I make about the vendor's
own files. Every return figure quoted here is therefore computed from the monthly series at
build time, the verdict of the rule included; the <code>.txt</code> supplies the size of each
arm, which is a count of firms and not a return figure, and appears in this register as an
output of the script otherwise.</p>
<table>
<tr><th>Withheld</th><th>Script</th><th class="n">SHA-256, first 16</th></tr>
{withheld_rows()}
</table>
<p>A checksum on a withheld file identifies the file I used, and it is not reproducible by a reader with a
different pull, since a vendor's adjusted price history is itself restated whenever a dividend or a split
is applied. That is the same claim I make about the price layer, applied at the level of the file rather
than of the dataset, and the resulting record is therefore auditable and never repeatable. Everything else
in this register is computed from the releases named in the provenance records, which are not in the
repository, and from the committed files.</p>

<h2 class="appendix">References</h2>
<p>Berg, F., Fabisik, K. and Sautner, Z. (2021). Is history repeating itself? The (un)predictable past of
ESG ratings. ECGI Finance Working Paper 708/2020, August 2021 (SSRN 3722087).</p>
<p>Goes, I. (2023). New data, new results? How data sources and vintages affect the replicability of
research. <em>Research &amp; Politics</em>, 10(2). doi 10.1177/20531680231170502.</p>
<p>Harvey, C. R., Liu, Y. and Zhu, H. (2016). ... and the cross-section of expected returns. <em>Review of
Financial Studies</em>, 29(1), 5-68.</p>
</div>

<footer>
Version {VERSION}, {TODAY_WORDS}.
Generated from the output files by <code>code/19_build_note.py</code>.
{CHANGELOG_LINE}
</footer>

</div></body></html>
"""

path = os.path.join(DEST, f"Measurement_Note_draft_{TODAY}.html")
with open(path, "w", encoding="utf-8") as fh:
    fh.write(HTML)
print(f"built: {os.path.abspath(path)}")
print(f"figures extracted from output files: {len(F)}")
