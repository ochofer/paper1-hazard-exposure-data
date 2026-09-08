"""
POWER COMPARISON: cross-sectional premium against hazard event study.

WHY THIS EXISTS
---------------
The minimum detectable effect for the planned Fama-MacBeth design came out at
roughly 6.6% a year, against published physical climate risk premia that are
usually under 3% a year. If that holds, the design cannot detect the effect it
is looking for, and no amount of careful data work fixes it.

Before abandoning or redesigning anything, the alternative should be costed the
same way. This script compares two designs on power, using the same firms and
the same exposure measure.

THE TWO DESIGNS
---------------
A. CROSS-SECTIONAL PREMIUM. Monthly Fama-MacBeth regressions of returns on
   hazard exposure. Asks whether exposed firms earn a persistent premium.
   Power scales with the square root of the NUMBER OF MONTHS.

B. HAZARD EVENT STUDY. Abnormal returns of exposed against unexposed firms in
   short windows around realised hazard events. Asks whether news about
   physical risk moves prices.
   Power scales with the square root of the NUMBER OF INDEPENDENT EVENTS.

WHY THE SECOND IS NOT SIMPLY "MORE OBSERVATIONS"
-------------------------------------------------
The obvious objection is that an event study has firms times events
observations, which sounds enormous. It does not get to use them. A hurricane
hits many firms at once, so residuals are correlated across firms within an
event. The effective sample size is close to the number of independent events,
not the number of firm-event pairs. This script uses the number of events, which
is the conservative and correct choice.

THE HONEST COMPARISON
---------------------
The two designs are measured in different units. A monthly premium in percent
per month is not comparable to an abnormal return in percent per event. So
rather than forcing a conversion, each design is scored against its own
plausible effect size from the literature:

    POWER RATIO = minimum detectable effect / plausible effect size

    ratio below 1.0  -> the design can detect a plausible effect
    ratio above 1.0  -> it cannot, and a null result is uninformative

ASSUMPTIONS, ALL CHANGEABLE BELOW, ALL FLAGGED AS ASSUMPTIONS
--------------------------------------------------------------
None of the four numbers in ASSUMPTIONS is measured from our data. They are
taken from typical magnitudes in the asset pricing literature and should be
replaced with measured values once blocking test 2 returns real factor data.
The conclusion is not sensitive to small changes in them, but check.

RUN
    python 05_power_comparison.py

Writes: outputs/power_comparison.txt
"""

import os
import math

# Provenance. Scripts 10, 11 and 05 were the last three with no RUN_PROVENANCE
# record, found by the gate 5 register on 7 September 2026. See _release.py.
import _release


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# ASSUMPTIONS. Every one of these is a judgement, not a measurement.
# ---------------------------------------------------------------------------

# Standard deviation of the monthly Fama-MacBeth coefficient, in percent per
# month. Typical range in cross-sectional studies is 1.5 to 2.5. Lower is
# better for power. With 175 to 328 well-measured firms this could sit at the
# low end, which is why the script reports a range rather than one number.
SD_GAMMA_MONTHLY = 2.0

# Standard deviation of the exposed-minus-unexposed portfolio's cumulative
# abnormal return over the event window, in percent. Long-short cancels most
# market risk. A five-day window on a diversified long-short leg is typically
# 1.5 to 3.0 percent.
SD_CAR_PER_EVENT = 2.0

# Plausible true effects, from the published literature.
# Physical climate risk premia are usually reported well under 3% a year.
PLAUSIBLE_PREMIUM_ANNUAL = 2.0            # percent per year
# Event studies on disaster news typically find 0.5 to 2 percent for exposed
# firms against unexposed.
PLAUSIBLE_CAR_PER_EVENT = 1.0             # percent per event

# Harvey, Liu and Zhu argue the conventional 1.96 hurdle is far too low given
# how many factors have been tested. 3.0 is their recommendation and is the
# bar this project committed to in advance.
T_HURDLE = 3.0
T_CONVENTIONAL = 1.96


def mde(t_hurdle, sd, n):
    """Smallest effect detectable at a given t hurdle with n observations.

    Both designs reduce to a mean against its own standard error, so the same
    formula serves both. Only the meaning of n changes: months in design A,
    independent events in design B.
    """
    return t_hurdle * sd / math.sqrt(n)


def main():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    say("POWER COMPARISON: cross-sectional premium against hazard event study")
    say(f"assumptions: sd(gamma)={SD_GAMMA_MONTHLY}%/month, "
        f"sd(CAR)={SD_CAR_PER_EVENT}%/event, t hurdle={T_HURDLE}")
    say()

    # -- Design A ------------------------------------------------------------
    say("DESIGN A. Cross-sectional premium, Fama-MacBeth")
    say(f"  plausible true effect: {PLAUSIBLE_PREMIUM_ANNUAL}%/year "
        f"= {PLAUSIBLE_PREMIUM_ANNUAL/12:.3f}%/month")
    say()
    say(f"  {'sample':>10} {'months':>7} {'MDE %/mth':>11} {'MDE %/yr':>10} "
        f"{'power ratio':>12}  verdict")
    for yrs in (5, 8, 10, 12, 15, 20, 30):
        n = yrs * 12
        m = mde(T_HURDLE, SD_GAMMA_MONTHLY, n)
        ratio = m / (PLAUSIBLE_PREMIUM_ANNUAL / 12)
        verdict = "can detect" if ratio <= 1 else "CANNOT detect"
        say(f"  {str(yrs)+' years':>10} {n:>7} {m:>11.3f} {m*12:>10.2f} "
            f"{ratio:>12.1f}  {verdict}")

    need = (T_HURDLE * SD_GAMMA_MONTHLY / (PLAUSIBLE_PREMIUM_ANNUAL / 12)) ** 2
    say()
    say(f"  months needed to detect a {PLAUSIBLE_PREMIUM_ANNUAL}%/year premium "
        f"at t={T_HURDLE}: {need:,.0f}")
    say(f"  which is {need/12:,.0f} years.")

    # -- Design B ------------------------------------------------------------
    say()
    say("DESIGN B. Hazard event study")
    say(f"  plausible true effect: {PLAUSIBLE_CAR_PER_EVENT}% CAR per event")
    say()
    say(f"  {'events':>10} {'MDE % CAR':>11} {'power ratio':>12}  verdict")
    for n in (20, 30, 50, 75, 100, 150, 200):
        m = mde(T_HURDLE, SD_CAR_PER_EVENT, n)
        ratio = m / PLAUSIBLE_CAR_PER_EVENT
        verdict = "can detect" if ratio <= 1 else "CANNOT detect"
        say(f"  {n:>10} {m:>11.3f} {ratio:>12.1f}  {verdict}")

    need_ev = (T_HURDLE * SD_CAR_PER_EVENT / PLAUSIBLE_CAR_PER_EVENT) ** 2
    say()
    say(f"  events needed to detect a {PLAUSIBLE_CAR_PER_EVENT}% CAR "
        f"at t={T_HURDLE}: {need_ev:,.0f}")

    # -- Sensitivity ---------------------------------------------------------
    say()
    say("SENSITIVITY. The assumed standard deviations are the soft inputs,")
    say("so both designs are re-scored across a plausible range.")
    say()
    say(f"  Design A, 10 years (120 months), against "
        f"{PLAUSIBLE_PREMIUM_ANNUAL}%/year:")
    for sd in (1.0, 1.5, 2.0, 2.5):
        m = mde(T_HURDLE, sd, 120)
        say(f"    sd={sd}%/month -> MDE {m*12:>5.2f}%/year, "
            f"power ratio {m/(PLAUSIBLE_PREMIUM_ANNUAL/12):>4.1f}")
    say()
    say(f"  Design B, 75 events, against {PLAUSIBLE_CAR_PER_EVENT}% CAR:")
    for sd in (1.5, 2.0, 2.5, 3.0):
        m = mde(T_HURDLE, sd, 75)
        say(f"    sd={sd}%/event -> MDE {m:>5.2f}%, "
            f"power ratio {m/PLAUSIBLE_CAR_PER_EVENT:>4.1f}")

    # -- Conclusion ----------------------------------------------------------
    a10 = mde(T_HURDLE, SD_GAMMA_MONTHLY, 120) / (PLAUSIBLE_PREMIUM_ANNUAL / 12)
    b75 = mde(T_HURDLE, SD_CAR_PER_EVENT, 75) / PLAUSIBLE_CAR_PER_EVENT
    say()
    say("CONCLUSION")
    say(f"  Design A at 10 years: power ratio {a10:.1f}. Underpowered by "
        f"roughly {a10:.0f}x.")
    say(f"  Design B at 75 events: power ratio {b75:.1f}.")
    if b75 <= 1 < a10:
        say("  The event study can detect a plausible effect on this data. The")
        say("  cross-sectional premium cannot, and would need decades to.")
    say()
    say("  Both use the same 328 firms and the same exposure measure, so this")
    say("  is a change of question rather than a change of dataset.")

    # -----------------------------------------------------------------------
    # DOES A BIGGER CROSS-SECTION RESCUE DESIGN A?
    #
    # Carlo asked on 21 August whether widening the sample from Europe plus the
    # United States to Ken French's full developed-market list would help. It is
    # a fair question because more firms per month does reduce sd(gamma).
    #
    # Measured firm counts from the GEM cross-section, running the traversal
    # over every country:
    #     Europe 16 plus US ....... 328 firms, 175 with five or more assets
    #     Ken French Developed 23 . 541 firms, 266 with five or more assets
    #
    # The optimistic bound is that ALL of sd(gamma) is diversifiable, so it
    # scales with 1/sqrt(number of firms). Reality is worse than that, because
    # a common component does not diversify away, so treat the improvement
    # below as a ceiling rather than an estimate.
    # -----------------------------------------------------------------------
    say()
    say("DOES A BIGGER CROSS-SECTION RESCUE DESIGN A?")
    say("  measured firm counts, from running the traversal over every country:")
    say("    Europe 16 + US ......... 328 firms, 175 with 5+ assets, 5,115 assets")
    say("    Ken French Developed ... 541 firms, 266 with 5+ assets, 7,695 assets")
    say("    excluded rest of world . 960 firms, 315 with 5+ assets, 8,997 assets")
    say()
    shrink = math.sqrt(328 / 541)
    say(f"  optimistic bound: sd(gamma) falls by at most a factor of "
        f"sqrt(328/541) = {shrink:.3f}")
    say(f"  so sd(gamma) {SD_GAMMA_MONTHLY:.1f}%/month becomes at best "
        f"{SD_GAMMA_MONTHLY*shrink:.2f}%/month")
    say()
    say(f"  {'sample':>10} {'MDE %/yr now':>13} {'MDE %/yr expanded':>19} "
        f"{'ratio now':>10} {'ratio exp':>10}")
    for yrs in (10, 15, 20):
        n = yrs * 12
        m0 = mde(T_HURDLE, SD_GAMMA_MONTHLY, n)
        m1 = mde(T_HURDLE, SD_GAMMA_MONTHLY * shrink, n)
        p = PLAUSIBLE_PREMIUM_ANNUAL / 12
        say(f"  {str(yrs)+' years':>10} {m0*12:>13.2f} {m1*12:>19.2f} "
            f"{m0/p:>10.1f} {m1/p:>10.1f}")
    say()
    say("  VERDICT: expanding to developed markets does NOT rescue design A.")
    say("  Even on the optimistic bound the power ratio at 10 years falls from")
    say(f"  {mde(T_HURDLE, SD_GAMMA_MONTHLY,120)/(PLAUSIBLE_PREMIUM_ANNUAL/12):.1f} to "
        f"{mde(T_HURDLE, SD_GAMMA_MONTHLY*shrink,120)/(PLAUSIBLE_PREMIUM_ANNUAL/12):.1f}, "
        "which is still far above 1.0.")
    say()
    say("  It helps DESIGN B considerably more, and for a different reason.")
    say("  Adding Japan, Australia, Hong Kong and Singapore adds typhoon and")
    say("  cyclone exposure, so it raises the EVENT COUNT rather than only the")
    say("  firm count, and event count is what drives design B's power.")
    say("  Japan alone adds 103 firms and 1,488 operating assets.")
    say()
    say("  COST, measured. The identifier crosswalk degrades badly:")
    say("    ISINs in the ANNA file by country prefix")
    say("      Canada 0, Hong Kong 0, Singapore 0, New Zealand 0")
    say("      Japan 3,640, Australia 7,104")
    say("      against United States 2,281,221 and Germany 4,232,134")
    say("    So 73 of the 213 new firms have no ANNA route at all, and Japan's")
    say("    103 firms rest on a very thin file. The three-lane crosswalk would")
    say("    need a fourth lane before expansion is usable.")

    say()
    say("WHAT DESIGN B STILL NEEDS, none of it free of difficulty")
    say("  1. An event list. NOAA storm data is free. EM-DAT is free for")
    say("     academic use. Both need cleaning to asset-relevant events.")
    say("  2. Events must be UNANTICIPATED. Hurricanes are forecast days")
    say("     ahead, so the event date should be the forecast or track")
    say("     announcement, not landfall. Getting this wrong destroys the")
    say("     design more quietly than getting the returns wrong.")
    say("  3. Asset coordinates, to know which firm was in the path. This is")
    say("     the SAME blocker as design A: the GEM sector trackers.")
    say("  4. Independence. Two hurricanes in one season hitting the same")
    say("     coast are not independent events. Cluster or drop.")

    # This script reads NO data. It is a closed-form power calculation over
    # assumptions stated in its own docstring, so it has no release and no input
    # checksums. Gate 5 asks that every figure be traceable to an output file
    # carrying its release; the honest record here is that there is no release
    # to carry, stated explicitly rather than left as an empty field that reads
    # like an omission.
    _release.write_provenance(
        OUT, "05_power_comparison", {},
        extra={"data_inputs": "none",
               "kind": "closed-form power calculation, no dataset read",
               "note": "Figures from this script are design decisions computed "
                       "from stated assumptions, not measurements of any GEM or "
                       "FMP release. Cite it as such."})

    path = os.path.join(OUT, "power_comparison.txt")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    say()
    say(f"written to {os.path.abspath(path)}")


if __name__ == "__main__":
    main()
