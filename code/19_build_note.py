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
VERSION = "1.3"
VERSIONS = {
    "1.0": "9 September 2026",
    "1.1": "15 September 2026",
    "1.2": "2 October 2026",
    "1.3": TODAY_WORDS,
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
  .summary{break-inside:avoid;page-break-inside:avoid}
  a{color:inherit;text-decoration:none}
}
"""

def ladder_rows():
    out = []
    for _, r in ladder.iterrows():
        cls = ""
        v1 = f'{r["R_V1"]*100:.1f}% <span class="{"fail" if r["verdict_V1"]=="FAILS" else ""}">{r["verdict_V1"]}</span>'
        v2 = f'{r["R_V2"]*100:.1f}% <span class="{"fail" if r["verdict_V2"]=="FAILS" else ""}">{r["verdict_V2"]}</span>'
        out.append(f'<tr{cls}><td>{r["reading"]}</td><td class="n">{v1}</td><td class="n">{v2}</td></tr>')
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
                   f'<td>{r["subtype"]}</td><td>{r["verdict"]}</td><td>{r["grade"]}</td><td>{ev}</td></tr>')
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
in the earlier one as an event with a date. This note asks whether that difference behaves like a record
of events.</p>
<p><strong>What the existing evidence does not cover.</strong> Vintage instability is documented in
macroeconomic series revised by statistical agencies (Goes, 2023) and in a commercial ESG rating (Berg,
Fabisik and Sautner, 2021). Neither checks a revision against a dated event case by case: Goes (2023)
compares releases of the World Development Indicators and replicates three articles across data sources and releases, and
Berg, Fabisik and Sautner (2021) report that rewritten ESG scores relate to returns where the original
scores do not. An ownership change is different in that respect: it either happened or it did not, and
the transaction behind it sits on the public record, so a difference can be checked case by case.</p>
<p><strong>What I did.</strong> To answer it, I drew {F['n_cases']} apparent ownership changes at random
from the {F['restatement_n']} edges classed as restatement, of the {F['chg_total']} on which two releases
of the same database differ, and I searched for the transaction behind each one in exchange filings,
company statements, press releases and, where no filing could be found, market-data sites and the
vendor's own wiki and later file. One reader, myself, gave every verdict knowing the thresholds, and no
second reading is recorded; the file's note on case 13 says that its verdict was written down in project
documents outside the repository before the case was checked. The file grades {F['n_graded_w']} of the
{F['n_noevent_w']} no-event verdicts by one of two phrases, "strong kind", a positive finding that the
relationship still exists ({F['n_strong_w']}), and "weak kind: absence of evidence" ({F['n_weak_w']}); the
other {F['n_ungraded_w']} carry neither phrase, one of them, case 8, calling its verdict strong in other
words, and Appendix C prints the file's words.</p>
<p><strong>Why this database is an informative setting.</strong> The tracker is free and published under
CC BY 4.0, a licence that permits publishing the inputs beside the result, and this note does not
publish them. The fourteen past releases it compares were supplied by the vendor on request and are
neither on the vendor's site, which on 19 November 2026 offered the current release alone, nor in the
repository, which holds the code, the outputs and provenance records naming each release by filename and
checksum, so a reader can check the outputs against the code and cannot rerun the comparison from the
vendor's site. The asset-level layer is eighteen months old, so the window examined here is the whole of
its life.</p>
<p><strong>What a practitioner takes from it.</strong> Two findings carry the note. First,
{F['n_noevent']} of the {F['n_cases']}, drawn from the {F['restatement_n']} edges classed as restatement
of the {F['chg_total']} that differ, had no corporate event behind them, a share of {F['noev_pct']} per
cent with a 95 per cent Wilson interval of {F['noev_lo']} to {F['noev_hi']} per cent; edges that appear in
the later file, the kind the first paragraph names, were classified as the database growing and were not
verified. Second, an undocumented choice, the analyst's reading of a blank ownership share, moves a
verdict whose threshold was set before the run, in the header of the script that produced the result;
the public history cannot show the order. Of the six changes that were real, the {F['inw_w']} with
transactions inside the window were carried in the {F['inw_pos']} release after the transaction, and the
{F['pre_w']} with transactions before the first release, from {F['pre_from']} to {F['pre_to']}, were
carried {F['after_lo']} to {F['after_hi']} days after the first release that could have carried them, in
{F['after_months']}. The {F['pre_w']} long lags are fixed by the sampling frame, since no change can be
carried before the first release held; in these six cases how visible an event was cannot be told apart
from when it happened.</p>
<p><strong>What it costs a book.</strong> On the {F['panel_eff']} firms in the cross-section with any coal
or gas exposure in either release, the rank correlation between the two releases is {F['p_sp_zero']} under
one blank-share convention and {F['p_sp_imp']} under the other; on the {F['both_units']} firms with coal
or gas units in both releases it is {F['both_sp_zero']} with a blank share read as zero, below the 0.95
line of section 2, and {F['both_sp_imp']} with blanks imputed. The gap between the two pairs is firms that
enter the panel between the two releases: the panel is defined on the later release, {F['entered']} firms
entered and {F['left']} left. Of the {F['ent_mw']} MW the {F['entered']} hold in August 2026,
{F['ent_i_mw']} MW, {F['ent_i_pc']} per cent, is in units the March 2025 file attributed to a listed entity
that owns the entrant in August 2026, the entrant not then a listed and identified entity: subsidiaries
that gained a listed flag, the mechanism of section 3. Under the zero reading {F['both_blank_zero']} of the {F['both_units']} are at zero in March 2025 because every path
from them to a unit crosses a blank share; set aside, the {F['pos_n']} others give {F['pos_sp_zero']} and
{F['pos_sp_imp']}, a gap of {F['gap_pos']} against {F['gap_both']} on the {F['both_units']}. What a release
costs a book built on this measure is therefore mostly firms arriving in the panel, and
{F['ent_i_pc']} per cent of their capacity is in plants the earlier file held under a listed parent; among the firms both files cover the ranking is {F['both_sp_zero']} with a blank
read as zero, below the line, and {F['pos_sp_zero']} once the {F['both_blank_zero']} firms with blank
shares alone are set aside.</p>
<p><strong>The return test, read by its rule.</strong> The rule set before the run, in the header of
script 11, asks whether the two releases give the same answer: robust if the two quintile spreads differ
by less than one standard error and the two monthly series correlate above 0.95, fragile if they differ
by more or correlate below 0.90, mixed otherwise. The two spreads differ by {F['rule_d_zero']} and
{F['rule_d_impute']} standard errors of the larger of the two spreads under the two readings of a blank
share, the rule's measure and not the standard error of their difference, and the two series correlate at
{F['rule_c_zero']} and {F['rule_c_impute']}, so the verdict is {F['rule_phrase']}. The Newey-West standard
error of the difference of the two monthly series, added on 20 November 2026 after the results were known
and in no verdict, is {F['dse_zero']}% and {F['dse_impute']}% a year, and the difference over it
{F['dt_zero']} and {F['dt_impute']}. Beside it, every t-statistic is at most {F['t_max']}, the Newey-West
standard errors are {F['se_lo']}% to {F['se_hi']}% a
year, and the effect at which the expected t-statistic reaches the Harvey, Liu and Zhu hurdle of 3.0 is
{F['mde_lo']}% to {F['mde_hi']}% a year across the arms, an effect detected half the time; at a power of
80 per cent it is {F['mde80_lo']}% to {F['mde80_hi']}%. The test corroborates nothing in either
direction.</p>
<p><strong>The caveat that bounds all of it.</strong> The asset-level layer measured here has existed for
eighteen months, so some of what follows is plausibly a property of a young dataset and some is a property
of how ownership data is built and used; section 5 separates them.</p>
</div>

<h2>1. Nineteen changes, checked by hand</h2>
<p>Two releases of the Global Energy Ownership Tracker, March 2025 and August 2026, differ on
{F['chg_total']} ownership edges: {F['bo_n']} are classed as the database growing, {F['appear_n']} edges
that appear in the later file and {F['m3_n']} blanks filled by new research; {F['restatement_n']} are
links removed or shares revised, the restatement bucket; and {F['mt_n']} are methodology, {F['m7_n']}
blanks filled by an imputation rule, {F['m8_n']} edges of entities the vendor deduplicated and {F['m9_n']}
imputed shares moved because the owner count changed. Because a difference of the second kind is what a
vintage design would read as a set of events, I sampled {F['n_cases']} of the {F['restatement_n']} at
random, in proportion across the bucket's three subtypes, and traced each one back to the transaction it
would have to correspond to. The edges that appear, the kind the Summary's first sentence names, were
classified by rule and not verified by hand.</p>
<p><strong>{F['n_noevent']} of the {F['n_cases']} had no corporate event behind them</strong>,
{F['noev_pct']} per cent of the sample with a 95 per cent Wilson interval of {F['noev_lo']} to
{F['noev_hi']} per cent. The full case table, with sources, verdicts and the file's grades, is Appendix C.
This is the central result for the restatement bucket, because it is the one finding that does not depend
on any modelling choice made downstream.</p>
<p>Six of the {F['n_cases']} had a datable transaction and a datable record. The lag from the transaction
to the first release carrying the change is {F['fast']} days for the two whose transactions fall inside
the window, a statutory disclosure by a listed Japanese issuer and a 1.9bn USD acquisition by a listed US
utility, and {F['slow_lo']} to {F['slow_hi']} days for the four whose transactions predate the first
release, from {F['pre_from']} to {F['pre_to']}. Those four lags are fixed by the frame: a change sampled
from the difference between March 2025 and August 2026 cannot be carried before {F['first_possible']}, the
first release after March, so the four could not have had lags under {F['floor_lo']} to {F['floor_hi']}
days whatever the vendor did, and the two inside the window could not have had lags over {F['ceil']}.
Counted from the first release that could have shown them, the four were carried {F['after_lo']} to
{F['after_hi']} days later, in {F['after_months']}, and the two in the {F['inw_pos']} release after the
transaction. What the six show is a difference between records already out of date when the layer began
and events that happened while it was being watched; whether the lag varies with how visible the event
was cannot be told from them, since every less visible case is also a case from before the first
release. Six cases cannot establish a correlation and none is claimed here.</p>
<p>For scale, {F['R_rule']}% of all apparent change between these two releases is restatement or
methodology rather than the database growing, by the rule in the header of script 08, written after R
was known and before the sample was drawn, which revises R by the measured share of real cases when that
share lies between 0.25 and 0.50 (it is {F['V_k']} of {F['n_cases']}, {F['V_strict']}); before that
correction the figure is {F['R_before']}%, and the threshold of 25% is set before the run in the header
of script 06. The public history cannot show the order, since the scripts and their results entered the
repository in one commit of 8 September 2026, and the decomposition behind R stood in the findings file
at the commit of 22 August 2026, b012207. Section 4 sets out every construction of that figure.</p>
<p class="src">Sources: <code>outputs/salience_lag.txt</code>, <code>outputs/event_validation_sample.csv</code>,
<code>evidence/salience_lag_cases.csv</code>, <code>outputs/restricted_r.txt</code>,
<code>outputs/release_ladder.txt</code>, <code>outputs/change_decomposition.txt</code></p>

<h2>2. Two undocumented choices, one the vendor's and one the analyst's</h2>
<p>Between the raw file and a portfolio sit two choices that nobody documents. The first is the vendor's,
namely which release you happen to hold; the second is the analyst's, namely what an empty ownership share
is taken to mean. Neither is recorded anywhere in the data. The second moves a verdict; the first moves R
from {F['R_rule']} to {F['R_rule_v2']} per cent between the two files called August 2026 and leaves the
verdict where it is (Appendix A).</p>
<p><strong>The analyst's choice moves a verdict set before the run.</strong> Ranking firms by attributable
coal and gas capacity, the rank correlation between the two releases is {F['u3_zero']} if a blank share is
read as zero and {F['u3_imp']} if blanks are imputed, against a threshold of 0.95 set before the run, in
the header of script 13, where a measure whose rankings correlate above it between releases drops to a
footnote. Substantively, therefore, the same measure, on the same firms, on the same two files, lands on
opposite sides of that line depending only on the reading.</p>
<table>
<tr><th>Universe, raw attributable MW between releases</th><th class="n">blank = zero</th><th class="n">blank = impute</th></tr>
<tr><td>604 matched firms worldwide (U2)</td><td class="n">{F['u2_zero']}</td><td class="n">{F['u2_imp']}</td></tr>
<tr><td>{F['u3_n']} firms in the regional panel present in both releases (U3)</td><td class="n">{F['u3_zero']}</td><td class="n">{F['u3_imp']}</td></tr>
<tr><td>{F['bio_n']} firms with bioenergy in both releases</td><td class="n">{F['bio_raw_zero']}</td><td class="n">{F['bio_raw_imp']}</td></tr>
<tr class="rule"><td>threshold set before the run, in the script's header</td><td class="n">0.95</td><td class="n">0.95</td></tr>
</table>
<p><strong>The flip on the 604 matched firms worldwide.</strong> It reproduces there, at {F['u2_zero']} and
{F['u2_imp']}, straddling the same cut as the {F['u3_n']} regional firms present in both releases, and in
the same direction. The reading that a straddle on the 604 would carry is written in a sentence script 15
prints in its body, dated 7 September 2026, and not in its header; the same sentence records that a first
run, on the firms above zero in both releases, took the other branch. Without the firms at zero in March
2025 with a blank share read as zero, {F['u2_zero576']} of the 604 and {F['both_blank_zero']} of the
{F['both_units']} regional firms with coal or gas units in both releases, both readings clear the line on
both universes: {F['u2_pos_zero']} and {F['u2_pos_imp']} on
the {F['u2_pos_n']}, {F['pos_sp_zero']} and {F['pos_sp_imp']} on the {F['pos_n']}. On both universes the
flip is those firms. On the {F['bio_n']} firms with bioenergy in both releases, by contrast, raw capacity
does not flip, and that is the stated limit of the claim; those three universes are not nested. The
{F['u3_n']} are the panel firms with coal, gas or bioenergy units in both releases: {F['u3_fossil_both_imp']}
of them have coal or gas units in both, and {F['u3_bio_alone']} have bioenergy alone in both; section 4
returns to the {F['u3_fossil_both_imp']}.</p>
<p><strong>Why the convention carries that much force.</strong> Under the naive reading, {F['n_zerocap']}
of the {F['n_march']} listed firms with exposure in March 2025 carry attributable capacity of exactly
zero, because every path from them to a unit crosses a blank share and a blank read as zero is nothing;
under imputation none do. The convention
therefore decides whether a firm registers as having any exposure at all, which is a membership decision
rather than a measurement one.</p>
<p>The same choice roughly halves measured growth: on the 604 firms present in both releases, attributable
capacity grows {F['growth_zero']}% reading blanks as zero and {F['growth_imp']}% imputing them. The reason
the reading bites so hard is the distribution of blanks itself, since March 2025 carries {F['blank_mar']}
blank shares, {F['blank_pct']}% of its ownership edges, while August 2026 carries none because the vendor
filled them in between releases.</p>
<h3>An apparent finding that dissolved under a control set before the run</h3>
<p>Scaling capacity by fleet share looked far less stable across releases than raw capacity:
{F['fs_zero']} and {F['fs_imp']} against the same 0.95 threshold. Its top-quintile overlap has no one
figure: {F['fs_tied_mar_zero']} of the {F['fs_n_zero']} panel firms with a share in both releases tie at a
share of exactly 1 for the {F['fs_k_zero']} places of the top quintile in March 2025, and
{F['fs_tied_aug_zero']} in August 2026, under the zero reading ({F['fs_tied_mar_imp']} and
{F['fs_tied_aug_imp']} of {F['fs_n_imp']} for {F['fs_k_imp']} places under the impute reading), so the
count of names kept runs from none to all of them with the order of the tied firms, and no figure is given.
Those two pairs are on the panel firms with a share in both releases, {F['fs_n_zero']} and
{F['fs_n_imp']}. On the {F['bio_n']} firms worldwide whose denominator exists in both releases, chosen
with a blank share read as zero and then taken under both readings, it is {F['bio_zero']} and
{F['bio_imp']}, with overlap of {F['bio_ov_zero']}% and {F['bio_ov_imp']}%, no firm tied at either cut; on
the {F['bio34_n']} of them in the panel it is {F['bio34_zero']} and {F['bio34_imp']}; and with the firms
chosen under the imputed reading instead, {F['bio_imp_n']} worldwide, it is {F['bio_imp_fs']}, against
{F['bio_imp_raw']} for raw capacity on the same firms, so the control clears under either choice of the
firms. <strong>These figures indicate that the instability arises mostly from the
denominator's own coverage moving between releases rather than from anything about the firms</strong>,
and the scaling result accordingly stands
as a coverage finding and not as a measurement one. The control that dissolved it was set before the
run, in the header of script 15, which is the only reason the demotion is credible rather than
convenient.</p>
<p class="src">Sources: <code>outputs/bioenergy_check.txt</code>, <code>outputs/scaling_second_column.txt</code>,
<code>outputs/exposure_proxy_summary.txt</code></p>

<h2>3. A boolean moved {F['ameren_mw']} MW between two companies</h2>
<p>Attribution walks up the ownership graph to the nearest listed parent, so the attribution depends on
where the walk stops. Whether an entity counts as listed is a flag in the data, and flags change.</p>
<table>
<tr><th>Firm</th><th class="n">March 2025</th><th class="n">August 2026</th></tr>
<tr><td>Ameren</td><td class="n">{F['ameren_mw']} MW, {F['ameren_units']} units</td><td class="n">absent</td></tr>
<tr><td>Union Electric</td><td class="n">absent</td><td class="n">{F['ameren_mw']} MW, {F['ameren_units']} units</td></tr>
</table>
<p>The two rows are identical to the decimal and identical in unit count, and not one generating unit was
built, retired or sold between them. What changed instead was Union Electric's listed flag, from false to
true, so that under a nearest-listed-parent rule it became the stopping point and retained the capacity
its parent had previously been receiving.</p>
<p><strong>Ameren was not delisted.</strong> It is flagged as publicly listed in both releases, and it lost
the capacity because a subsidiary gained the flag. Since the cross-section here was built on the later
release, Ameren does not appear in it at all, and it follows that a boolean on a subsidiary decided which
of two companies entered the study.</p>
<p>A further consequence follows for anyone using the file directly. Summing the vendor's own ownership
share column over all parents over-counts the world's operating coal and gas fleet by a factor of
{F['over_mar']} in March 2025 and {F['over_aug']} in August 2026, because the file emits a row for every
ancestor rather than the nearest listed one, and <strong>the over-count grew between releases</strong>.
Appendix B works it through alongside the other mechanisms.</p>
<p class="src">Sources: <code>outputs/exposure_proxy_by_firm.csv</code>, <code>outputs/exposure_proxy_summary.txt</code></p>

<h2>4. What this does to a portfolio, and the full R table</h2>
<p>Joining the measure to a cross-section of 328 ownership entities in the US and developed Europe, 302 of
them listed companies with a price series, {F['never']} of the 328 have no coal or gas power exposure in
either release, because the measure is power-only; the effective panel is therefore {F['panel_eff']}
firms.</p>
<table>
<tr><th>On the {F['panel_eff']} firms with exposure in either release</th><th class="n">blank = zero</th><th class="n">blank = impute</th></tr>
<tr><td>Rank correlation between releases</td><td class="n">{F['p_sp_zero']}</td><td class="n">{F['p_sp_imp']}</td></tr>
<tr><td>Top-quintile overlap</td><td class="n">{F['p_ov_zero']}%</td><td class="n">{F['p_ov_imp']}%</td></tr>
<tr><td>Growth in attributable capacity</td><td class="n">+{F['u3g_zero']}%</td><td class="n">+{F['u3g_imp']}%</td></tr>
<tr><th>On the {F['both_units']} firms with coal or gas units in both releases</th><th class="n">blank = zero</th><th class="n">blank = impute</th></tr>
<tr><td>Rank correlation between releases</td><td class="n">{F['both_sp_zero']}</td><td class="n">{F['both_sp_imp']}</td></tr>
<tr><td>Top quintile kept</td><td class="n">{F['both_ov_zero']}</td><td class="n">{F['both_ov_imp']}</td></tr>
<tr><td>Growth in attributable capacity</td><td class="n">{F['both_g_zero']}%</td><td class="n">{F['both_g_imp']}%</td></tr>
<tr><td>Of them, at zero in March 2025 under the reading</td><td class="n">{F['both_blank_zero']}</td><td class="n">{F['both_blank_imp']}</td></tr>
<tr><td>Rank correlation on the {F['pos_n']} above zero in March 2025 under both readings</td><td class="n">{F['pos_sp_zero']}</td><td class="n">{F['pos_sp_imp']}</td></tr>
</table>
<p>On the {F['panel_eff']} firms with exposure in either release the extreme portfolio turns over
{F['turn_lo']}% to {F['turn_hi']}% of its names between the two releases, against rank correlations of
{F['p_sp_zero']} and {F['p_sp_imp']}; on the {F['both_units']} firms with coal or gas units in both
releases the correlations are {F['both_sp_zero']} with a blank share read as zero and {F['both_sp_imp']}
with blanks imputed, the first below the 0.95 line of section 2, and the top quintile keeps
{F['both_ov_zero']} and {F['both_ov_imp']} names. The difference between the two panels is firms that enter
the panel between the two releases, the panel being defined on the later release: {F['entered']} entered
and {F['left']} left. The {F['ent_mw']} MW the {F['entered']} hold in August 2026 split, unit by unit, into
three parts: {F['ent_i_mw']} MW, {F['ent_i_pc']} per cent, in units the March 2025 file attributed to a
listed entity that owns the entrant in August 2026, the entrant not then a listed and identified entity,
the mechanism of section 3; {F['ent_ii_mw']} MW, {F['ent_ii_pc']} per cent, in the rest of the units the
March 2025 file carried; and {F['ent_iii_mw']} MW, {F['ent_iii_pc']} per cent, in units it did not carry.
{F['ent_top1']} and {F['ent_top2']} carry {F['ent_top1_pc']} and {F['ent_top2_pc']} per cent of the first
part. The measure is by the capacity of units and was set on 20 November 2026, after the first run of
script 25 (<code>outputs/panel_entrants.txt</code>). The {F['panel_eff']} of this section are the {F['both_units']}
firms with coal or gas units in both releases plus the {F['one_only']} present in one release only, and the
{F['u3_n']} of section 2 are those {F['both_units']} plus {F['u3_bio_alone']} firms with bioenergy alone in
both releases. The figures on the {F['both_units']} and on the {F['pos_n']} below were added on 19 November
2026, after the results were known (Appendix D); the control of section 2 was set before its run. Under the
first reading {F['both_blank_zero']} of the {F['both_units']} are at zero in March 2025 because every path
from them to a unit crosses a blank share; on the {F['pos_n']} others the two readings give
{F['pos_sp_zero']} and {F['pos_sp_imp']}, a gap of {F['gap_pos']} against {F['gap_both']} on the
{F['both_units']}. Of the {F['rose_zero']} firms at zero in March 2025 and above it in August 2026 under the
first reading, {F['rose_entered_zero']} entered the panel and {F['rose_blank_zero']} are at zero in the
March 2025 file under that reading because every path from them to a unit crosses a blank share. For a
signal rebalanced on vendor releases, the turnover on the wider panel is paid for firms that enter the
panel; among the firms both files cover the ranking is {F['both_sp_zero']} with a blank read as zero, below
the line of section 2, and {F['pos_sp_zero']} once the {F['both_blank_zero']} firms with blank shares alone
are set aside.</p>
<h3>R, every construction</h3>
<p>R is the share of apparent ownership change that is not the database growing. Because the construction
of that share involves several defensible choices, every construction is set out in one table rather than
one preferred figure.</p>
<table>
<tr><th>Construction</th><th class="n">August 2026 V1</th><th class="n">August 2026 V2</th></tr>
{ladder_rows()}
<tr><td>Generous bound, crediting every plausible real event</td><td class="n">{F['R_generous']}%</td><td class="n"></td></tr>
<tr><td>Residual counterparties removed from both sides</td><td class="n">{F['R_restricted']}%</td><td class="n"></td></tr>
<tr class="rule"><td>Threshold set before the run, in the header of script 06</td><td class="n">25%</td><td class="n">25%</td></tr>
</table>
<p>The first row is the rule's own figure: the header of script 08, written after R was known and before
the sample was drawn, revises R by the share of real cases when that share lies between 0.25 and 0.50. The
second row is the figure before that correction, which the bucket table of Appendix B sums to. The two
rows with the unclear case counted as real were added on 19 November 2026, after the results were known.</p>
<p><strong>The restricted construction is the more conservative one, and it raises R rather than lowering
it.</strong> Removing edges whose counterparty is a residual bucket, a party like "small shareholder(s)"
whose value is 100 minus the named holders rather than an observed stake, takes proportionally more out of
the denominator than the numerator, because those counterparties are concentrated in the build-out bucket
at {F['resid_buildout']}% and build-out sits in the denominator only. I had assumed the restriction would
deflate R and threaten the threshold. The assumption was backwards.</p>
<p>One further inference follows from that concentration and no more: nearly a quarter of the edges counted
as the database growing are new links to a residual bucket, which is coverage of the unnamed rather than
of the named.</p>
<p>The two August 2026 columns are two files I hold for the same month, one of them sent to me by the
vendor on 26 August 2026 and not a public reissue, neither marked as a version anywhere in the data.
Appendix A sets that out, including the reading at which the decision <span class="fail">fails</span> on
one file and clears on the other, together with the reason the endpoint is pinned to the first.</p>
<p class="src">Sources: <code>outputs/panel_join_summary.txt</code>, <code>outputs/release_ladder.txt</code>,
<code>outputs/restricted_r.txt</code>, <code>outputs/change_decomposition.txt</code></p>

<h2>5. The layer is eighteen months old</h2>
<p>What this note measures is the asset-level ownership layer, which links companies to individual plants
and mines, and the age of that layer bounds several of the findings above. The vendor confirms it has no
release before March 2025, and the earliest file I hold, from June 2024, carries entity-to-entity
relationships only and no asset-level ownership; the tracker as a product is therefore older than the
layer measured here. The window is accordingly the layer's first eighteen months, across the fourteen
releases I hold and the thirteen adjacent pairs between them.</p>
<p>Those releases were supplied by the vendor on request. Because no public archive of past releases
exists, this comparison is auditable from the files themselves and cannot be reproduced by a reader who
starts from the vendor's site.</p>
<p><strong>Findings that depend on that maturity:</strong> the level of R, the decay curves, and the share
of one release's change that is methodology.</p>
<p><strong>Findings that do not:</strong> the ancestor over-count, the convention that flips a verdict
set before the run, and the mechanism by which a flag change moves {F['ameren_mw']} MW between two
companies. Those are properties of how ownership data is
built and used, not of how long this particular dataset has existed.</p>
<p class="src">Sources: <code>outputs/decay_curves.txt</code>, GEM correspondence of 21 August 2026</p>

<h2>6. Limitations</h2>
<p><strong>The return test, read by its rule, corroborates nothing.</strong> A quintile-spread test whose
rule was set before the run, in the header of script 11, on the firms with exposure above zero in each
release and a price series ({F['arm_25']} firms in the March 2025 arm and {F['arm_26']} in the August
2026 arm), equal-weighted, in local currency, run monthly to December 2025, asks whether the two releases
give the same answer. The two spreads differ by {F['rule_d_zero']} and {F['rule_d_impute']} standard
errors of the larger of the two spreads under the two readings of a blank share, the rule's measure and
not the standard error of their difference, and the two monthly series correlate at {F['rule_c_zero']}
and {F['rule_c_impute']}, so the verdict is {F['rule_phrase']}; the Newey-West standard error of the
difference of the two series, added on 20 November 2026 after the results were known and in no verdict,
is {F['dse_zero']}% and {F['dse_impute']}% a year, the difference over it {F['dt_zero']} and
{F['dt_impute']}. The test returns every t-statistic at most {F['t_max']}, with Newey-West standard errors
of {F['se_lo']}% to {F['se_hi']}% a year;
the effect at which the expected t-statistic reaches the Harvey, Liu and Zhu hurdle of 3.0 is
{F['mde_lo']}% to {F['mde_hi']}% a year across the arms, an effect detected half the time, and at a power
of 80 per cent it is {F['mde80_lo']}% to {F['mde80_hi']}%. An effect smaller than that is detected less
than half the time, so the null is a statement about the power of the test rather than about the world. A
null quoted without a minimum detectable effect reads as evidence of absence. A cross-sectional
Fama-MacBeth design was set aside before it ran, on a power calculation requiring {F['pw_months']} monthly
observations at an assumed monthly standard deviation of 2 per cent ({F['pw_months_1pct']} at 1 per cent;
{F['pw_months_80']} at 80 per cent power), in <code>outputs/power_comparison.txt</code>.</p>
<p><strong>Both return arms contain look-ahead, deliberately and identically</strong>, so they are
comparable with each other and neither is a return prediction.</p>
<p><strong>Prices.</strong> Returns use <code>adjClose</code> from Financial Modeling Prep's
dividend-adjusted end-of-day series, pulled on 21 August 2026. The adjustment is the vendor's, covering
splits as well as dividends, and no unadjusted close is archived beside it; the series is not
redistributable, and its per-file checksums are published in the repository manifest.</p>
<p><strong>Nineteen is a small sample</strong>, drawn once and not reproducible as a draw, so the
{F['n_noevent']} no-event verdicts support a statement about the proportion only through their Wilson
interval, {F['noev_lo']} to {F['noev_hi']} per cent, computed as the interval of V is in Appendix A rather
than assumed. How the verdicts divide by subtype is a question these nineteen cases cannot answer, since
the sample was drawn from the restatement bucket, {F['restatement_n']} of the {F['chg_total']} edges that
differ, stratified in proportion across its three subtypes ({F['st_removed']}, {F['st_material']} and
{F['st_small']} cases of links removed, shares revised by more than one point and shares revised by less,
the rounding of 20 times each share giving {F['n_cases']}), and nineteen are too few to report by
subtype.</p>
<p><strong>Decay.</strong> Where a decay figure appears it is the one-month-pair cut with the November to
December 2025 pair excluded, n = 8, build-out share {F['decay']} from the first four pairs to the last
four, a difference the eight pairs do not distinguish from zero (Welch p {F['welch_p']}, a straight trend
p {F['trend_p']}), alongside a correlation of +{F['decay_corr']} between build-out share and the gap
between releases on {F['gap_n']} pairs (p {F['gap_p']}).</p>

<h2>7. On the vendor</h2>
<p>Global Energy Monitor is a non-profit, and the conditions under which this note could be written at all
follow from that. The data is free and published under CC BY 4.0; the past releases compared here were
sent on request and are not in the repository, whose provenance records name them by filename and
checksum; six detailed questions were answered within days; and the vendor undertook in writing to
document the imputation rule in future releases. At the same time, flags marking a large share of
ownership edges as no longer maintained were shipped unprompted and were not mentioned in the covering
note. A draft of this note went to Global Energy Monitor before publication.</p>
<p>As at 19 November 2026 the vendor publishes no release list or changelog and its project page gives no
launch date, and as at the date of the first version its download page still referenced an earlier
release, so a reader cannot independently confirm the completeness of the release history. That
observation concerns what is published around the data rather than the quality of the data itself, and it
is recorded because the release history is the one input to this note that a reader cannot reconstruct.</p>
<p>The licence permits publishing the inputs beside the result, and this note does not publish them: the
fourteen past releases are not in the repository, and the vendor's site, read on 19 November 2026, offers
the current release alone. The effects reported here are therefore checkable against the code and the
outputs, and the comparison itself cannot be rerun from what is published.</p>

<h2>8. What this measures, and what it does not</h2>
<p>The natural comparison is with the settings in which vintage instability has already been documented.
Goes (2023) reports it in macroeconomic series revised by statistical agencies, and Berg, Fabisik and
Sautner (2021) report it in a commercial ESG rating. This note reports it in a free, non-profit, openly
licensed database, and in a layer eighteen months old, so the three differ in maturity and in whether a
revision is checked against a dated event.</p>
<p>For a user of the file, the implication is that a difference between two releases in the restatement
bucket is not a usable event indicator, since {F['n_noevent']} of the {F['n_cases']} sampled differences,
{F['noev_lo']} to {F['noev_hi']} per cent at the 95 per cent level, had no transaction behind them; of
the six that did, the {F['inw_w']} whose transactions fell inside the window entered the file in the
{F['inw_pos']} release after the transaction, and the {F['pre_w']} whose transactions predate the first
release entered it {F['after_lo']} to {F['after_hi']} days after the first release that could have carried
them; what the edges that appear contain was not verified. For a signal built on the measure, the
estimates in section 4 suggest that a single release re-draws the ranking at rank correlations of
{F['p_sp_zero']} and {F['p_sp_imp']} on the panel defined on the later release, and at
{F['both_sp_zero']} and {F['both_sp_imp']} under the two readings of a blank share on the firms both
releases cover, so that most of the movement is firms that enter the panel between the two releases.</p>
<p>The limits that bear on that claim are set out in section 6. The one that bounds it most is that
nineteen cases were drawn once from one bucket, in proportion across its three subtypes, so how the
verdicts divide by subtype, or in the build-out and methodology buckets, is a question these data cannot
answer.</p>
<p>What would settle the questions left open is a longer archive and a larger draw across every bucket. A
release history covering several years would show whether R decays as the layer matures, which fourteen
releases across eighteen months cannot; and a sample large enough within each bucket and subtype would
give verdict shares by mechanism rather than in aggregate.</p>
<p>Against this evidence, the claim here is narrow. A difference between two vintages of this file in the
restatement bucket recorded, in {F['n_noevent']} of the {F['n_cases']} cases sampled, the file being edited. Where it records an event, it can
do so years late, and in the six cases dated the four longest delays belong to transactions that predate
the first release the layer had. And an undocumented convention, the analyst's reading of a blank share,
moves a verdict whose threshold was set before the run, in the header of the script; by the rule's figure
both files called August 2026 clear the 25% threshold, at {F['R_rule']} and {F['R_rule_v2']} per
cent.</p>

<div class="appendix">
<h2>Appendix A. Two files called August 2026</h2>
<p>Two files in my archive carry August 2026. The second was sent later than the first and holds columns
the public release does not, including one the vendor describes as internal, which indicates that it is a
variant supplied to me rather than a public reissue. Because nothing inside either file identifies which is
which, scripts that resolve a release by filename switch silently to the second one; mine did, and the
release pin in <code>code/_release.py</code> exists for that reason.</p>
<table>
<tr><th>Construction</th><th class="n">V1</th><th class="n">V2_External</th></tr>
{ladder_rows()}
<tr class="rule"><td>Threshold set before the run, in the header of script 06</td><td class="n">25%</td><td class="n">25%</td></tr>
</table>
<p><strong>At the upper bound of V's interval the decision clears on one file and fails on the other with
the unclear case counted as not real, and fails on both with it counted as real.</strong> V is derived
from the verified case verdicts, and its Wilson interval is computed rather than assumed, so the readings
at the bound apply the upper end of that interval ({F['V_hi']} with {F['V_k']} of {F['n_cases']} real,
{F['V_all_hi']} with {F['V_all_k']}) rather than a pessimistic figure chosen by hand; the rule's own
figure, strict V at its point value, clears on both files.</p>
<p><strong>The endpoint is pinned to V1</strong> because the cross-section of 328 ownership entities is itself a V1
artefact, having been built from that file before the second one arrived; it is not pinned because
V1 clears the threshold. Had the cross-section been built on V2, the pin would have gone to V2, and at the
upper bound of V's interval the figure on that file falls below the threshold set in the header of
script 06.</p>
<h3>The truncation trap</h3>
<p>Between the two releases the vendor truncated ownership shares to one decimal place, so that
{F['dp_mar']}% of March 2025 values need two decimals and none of the August values do.
<strong>{F['trunc']}% of all share-value changes between the pinned releases are that and nothing
else</strong> ({F['trunc_v2']}% against the second file). R is unaffected, because the 0.06 threshold used
to build the sample had already excluded them; it follows, however, that anyone rerunning this comparison
with a tighter threshold will manufacture roughly three and a half thousand changes that are
formatting.</p>

<h2 class="appendix">Appendix B. The mechanism catalogue</h2>
<p>This appendix catalogues every route, found in this data, by which a vintage difference shows an
ownership change when nothing happened to the company. The table counts the mechanisms that appear as a
change to an ownership edge, which is what the decomposition can see; six further mechanisms move a number
without moving an edge, and they are listed after it. The grouping is the one that matters for a design,
because build-out is the group expected to decay as the database matures, and R is the share of this
table that is not expected to; whether it decays is not shown by eighteen months (section 6).</p>
<table>
<tr><th>Bucket</th><th>Mechanism</th><th class="n">Edges</th><th class="n">Share of apparent change</th></tr>
<tr><td rowspan="4"><strong>Build-out</strong><br>expected to decay with maturity</td>
    <td>new entity brought into coverage</td><td class="n">{F['m1_n']}</td><td class="n">{F['m1_p']}%</td></tr>
<tr><td>new link between entities already covered</td><td class="n">{F['m2_n']}</td><td class="n">{F['m2_p']}%</td></tr>
<tr><td>blank filled by genuine new research</td><td class="n">{F['m3_n']}</td><td class="n">{F['m3_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['bo_n']}</td><td class="n">{F['bo_p']}%</td></tr>
<tr><td rowspan="4"><strong>Restatement</strong><br>not expected to decay</td>
    <td>link removed, not explained by deduplication</td><td class="n">{F['m4_n']}</td><td class="n">{F['m4_p']}%</td></tr>
<tr><td>share revised, material, over one point</td><td class="n">{F['m5_n']}</td><td class="n">{F['m5_p']}%</td></tr>
<tr><td>share revised, small, under one point</td><td class="n">{F['m6_n']}</td><td class="n">{F['m6_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['rs_n']}</td><td class="n">{F['rs_p']}%</td></tr>
<tr><td rowspan="4"><strong>Methodology</strong><br>not expected to decay</td>
    <td>blank filled by an imputation rule introduced after March 2025</td><td class="n">{F['m7_n']}</td><td class="n">{F['m7_p']}%</td></tr>
<tr><td>entity deduplicated by the vendor, per the remapping sheet</td><td class="n">{F['m8_n']}</td><td class="n">{F['m8_p']}%</td></tr>
<tr><td>imputed share moved because the owner count changed</td><td class="n">{F['m9_n']}</td><td class="n">{F['m9_p']}%</td></tr>
<tr class="rule"><td>total</td><td class="n">{F['mt_n']}</td><td class="n">{F['mt_p']}%</td></tr>
<tr class="rule"><td>R</td><td>restatement plus methodology, before the correction by V</td><td class="n">{F['rs_n']} + {F['mt_n']}</td><td class="n">{F['R']}%</td></tr>
</table>
<p>The table covers {F['chg_total']} changed edges, against {F['chg_unchanged']} that did not move between the
two releases.</p>

<h3>Six mechanisms that move a number without moving an edge</h3>
<p>None of these appears in the table above, because the decomposition counts edges and none of these
mechanisms adds, removes or revises one. They are set out here because a user who reconciles two releases
by comparing values rather than edges will meet them first.</p>
<ol>
<li><strong>Decimal truncation.</strong> {F['trunc']}% of all share-value changes between the pinned releases
are one-decimal rounding and nothing else. They sit below the 0.06 threshold used to build the verification
sample, so they never enter R; anyone who sets a tighter threshold puts every one of them in.</li>
<li><strong>A listed flag changing.</strong> {F['ameren_mw']} MW and {F['ameren_units']} units moved from
Ameren to Union Electric with no edge added, removed or revised, because what moved was the attribution
stopping point rather than the graph. Section 3 works the case.</li>
<li><strong>Ancestor double-count.</strong> Summing the vendor's own share column over all parents gives
{F['over_mar']} times the operating fleet in March 2025 and {F['over_aug']} times it in August 2026. That
is a property of the file's shape rather than a change between releases; the factor nonetheless grew, and
it follows that a user comparing two naive sums measures the growth of the double-count alongside the
growth of the fleet.</li>
<li><strong>The blank-share convention.</strong> This one is the analyst's and not the vendor's. Reading
blanks as zero rather than imputing them moves measured growth from {F['growth_imp']}% to
{F['growth_zero']}%, and puts {F['n_zerocap']} of the {F['n_march']} listed firms with exposure in March
2025 at exactly zero attributable capacity, because every path from them to a unit crosses a blank
share.</li>
<li><strong>Coverage moving inside a denominator.</strong> Any measure scaled by fleet share inherits the
coverage change in its denominator, which is what dissolved the scaling result in section 2.</li>
<li><strong>Two files carrying the same month.</strong> Two files are called August 2026 and nothing inside
either identifies which is which, so a script that resolves a release by filename may read either of them;
Appendix A gives the figures that differ between them.</li>
</ol>

<h3>Two boundaries this catalogue does not settle</h3>
<p><strong>Deduplication.</strong> The remapping sheet accounts for {F['remap_n']} entities the vendor
deleted as duplicates, which is {F['remap_pct']}% of the entities lost between these releases, and it
follows that an unknown part of the {F['m4_n']} removed links is unrecorded deduplication rather than
restatement. Reclassifying any of them moves edges from restatement to methodology, and both sit inside R,
so the boundary does not move R, though its internal line is soft.</p>
<p><strong>Real churn.</strong> Of the {F['both_edges']} edges present in both releases, observed ownership
churn over eighteen months puts a ceiling of {F['churn_ceiling']} genuine corporate events, or
{F['churn_pct']}% of them. Crediting every one of those to the restatement bucket is what produces the
generous bound in section 4, which is accordingly a ceiling and not an estimate, and the most favourable
reading the data will support.</p>
<p>One thing the vendor does here helps a user directly. August 2026 flags {F['imp_flag_n']} ownership
edges, {F['imp_flag_p']}% of them, as imputed values, so a reader of that flag can tell an imputed share
from an observed one directly. March 2025 carries no such flag, and it is for that reason that the
imputation row above counts as a methodology change rather than as something a user could have seen
coming.</p>
{PRESIGNED_BLOCK}
<p class="src">Sources: <code>outputs/change_decomposition.txt</code>, <code>outputs/exposure_proxy_summary.txt</code>,
<code>outputs/decimal_truncation.txt</code>, <code>outputs/bioenergy_check.txt</code></p>

<h2 class="appendix">Appendix C. The nineteen verified cases</h2>
<table>
<tr><th class="n">#</th><th>Subject</th><th>Counterparty</th><th>Change type</th><th>Verdict</th><th>Grade, the file's words</th><th>Evidence</th></tr>
{case_rows()}
</table>
<p>One reader gave every verdict. The grade column prints the file's own words where it grades a no-event
verdict by one of two phrases, "strong kind" or "weak kind: absence of evidence", and "not graded"
otherwise; case 8's note calls its verdict strong in other words and is printed as not graded; no grade
was added for this version. Where the evidence is the vendor's own material, the column says so.</p>
<h3>The six datable cases and their lags</h3>
<p>Lag is measured from the transaction date to the first day of the month of the first release carrying
the change. Because the dates were read by hand from the sources linked, the file behind this table,
<code>evidence/salience_lag_cases.csv</code>, is a curated input validated against the verdicts above
rather than computed from them. The frame fixes a floor under the lag of a transaction before March 2025
and a ceiling over one inside the window; the last two columns give the first release that could have
carried the change and the days from it to the carrying release. The transaction date of the State Street
case is the reporting date of a 13G filing as listed by an aggregator.</p>
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
months and six questions; the register of script 16 checks that a string is present in a file and cannot
tell that a number is correct. That check exists because I had previously typed twelve
entity identifiers into an evidence file from memory instead of reading them from the source, and got all
twelve wrong.</p>
<table>
<tr><th>Script</th><th>Release resolved</th><th class="n">SHA-256, first 16</th></tr>
{prov_rows()}
</table>

<h3>What was added after the results were known</h3>
<p>Added on 19 November 2026, after the results of the earlier versions were known: the figures on the
{F['both_units']} firms both releases cover and on the {F['pos_n']} above zero under both readings (script
10), the count of the {F['u3_n']} (script 15), the two ladder rows with the unclear case counted as real
and the interval of the {F['n_noevent']} of {F['n_cases']} (script 17), the frame of the lags (script 18), the three
tests on the decay (script 07) and the effect at a power of 80 per cent (script 11). Added on 20 November
2026: the bounds of an overlap under ties (scripts 10, 13 and 15), the pair on the {F['u2_pos_n']} and the
pair on the firms with bioenergy in both releases under the imputed reading (script 15), the units of the
firms that enter the panel and the measure of their capacity by units, set after the script's first run
(script 25), the months of the power calculation (script 05) and the standard
error of the difference of the two return series (script 11). Each carries its date where it is printed.</p>
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
<p><strong>Two outputs are withheld.</strong> Because the return arm is computed from a licensed price
series that cannot be redistributed, these two files are named here with their checksums and with the
script that produces them, and a reader reproduces them by rerunning that script against their own
pull.</p>
<p>Of those two, the note draws its return figures from the <code>.csv</code> alone. The
<code>.txt</code> is a summary of the same series, and a summary is a derived object that
can move while the series does not, which is the claim this note makes about the vendor's
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
is applied. That is the same claim this note makes about the price layer, applied at the level of the file
rather than of the dataset, and the resulting record is therefore auditable and never repeatable.
Everything else in this register is computed from the releases named in the provenance records, which
are not in the repository, and from the committed files.</p>

<h2 class="appendix">References</h2>
<p>Berg, F., Fabisik, K. and Sautner, Z. (2021). Is history repeating itself? The (un)predictable past of
ESG ratings. ECGI Finance Working Paper 708/2020, version of August 2021 (SSRN 3722087).</p>
<p>Goes, I. (2023). New data, new results? How data sources and vintages affect the replicability of
research. <em>Research &amp; Politics</em>, 10(2). doi 10.1177/20531680231170502.</p>
<p>Harvey, C. R., Liu, Y. and Zhu, H. (2016). ... and the cross-section of expected returns. <em>Review of
Financial Studies</em>, 29(1), 5-68.</p>
</div>

<footer>
Draft of {TODAY}, version {VERSION}.
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
