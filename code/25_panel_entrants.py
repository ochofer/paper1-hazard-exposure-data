"""
THE FIRMS THAT ENTER THE PANEL BETWEEN THE TWO RELEASES: WHAT THE EARLIER FILE HELD OF THEIR CAPACITY

Added 20 November 2026, after the results were known. Script 10 counts the panel firms at zero
attributable capacity in March 2025 with blanks imputed and above zero in August 2026: they enter the
panel between the two releases. That is a statement about attributed capacity. This script asks what the
March 2025 file held of that capacity, and under which listed entity it held it. A subsidiary that gained
a listed flag between the releases (section 3 of the note shows one) enters the panel with units the
earlier file held under its parent.

The entrants' August 2026 capacity is split, unit by unit, into three parts that add up to it. Each unit
counts with the megawatts attributed to the entrant from it in August 2026 (09_exposure_proxy.py's
attribution, blanks imputed):
  (i)   the mechanism of section 3: units the March 2025 file attributed to a listed and identified
        entity that owns the entrant in August 2026, through the ownership edges at any depth, while the
        entrant was not itself a listed and identified entity in March 2025;
  (ii)  the rest of the units the March 2025 file carried;
  (iii) units the March 2025 file did not carry.
A unit counts in (i) when any of the listed entities the March 2025 attribution gave it to owns the
entrant in August 2026. The two entrants that carry most of (i) are named from the data, with their
share of it.

Expected before this script first ran, written 20 November 2026 from the committed tables
(outputs/panel_exposure.csv and outputs/exposure_proxy_by_firm.csv): 36 entrants holding 36,157.5 MW in
August 2026, the two largest Entergy Louisiana (11,121.4 MW, 27 units) and Union Electric (6,991.2 MW,
42 units), 18,112.6 MW together, 50.1 per cent of the 36. Union Electric's 42 units and capacity are
Ameren's of March 2025 to the decimal (section 3 of the note). Entergy holds 52 units and 22,462.5 MW in
March 2025 and 22 units and 8,720.9 MW in August 2026, when Entergy Louisiana appears with 27, so Entergy
Louisiana is expected to be the same case; no committed file shows its units. Whether any of the other 34
entrants is such a case is not known from the committed tables.

The measure by the capacity of units was set on 20 November 2026, after the script's first run. On it,
of the 36,157.5 MW, (i) is 17,790.8 MW, 49.2 per cent, (ii) 15,098.4 MW, 41.8 per cent, and (iii)
3,268.3 MW, 9.0 per cent; Entergy Louisiana (26 of its 27 units, 10,529.6 MW) and Union Electric (42 of
42, 6,991.2 MW) carry 59.2 and 39.3 per cent of (i).

Reads the two pinned releases through 09_exposure_proxy.py's loader and attribution (blanks imputed, the
reading that defines the entrants), and outputs/panel_exposure.csv for the panel.

Run:  python3 25_panel_entrants.py   (from code/, after 09 and 10)
Out:  outputs/panel_entrants.csv, outputs/panel_entrants.txt,
      outputs/RUN_PROVENANCE_25_panel_entrants.json
"""

import importlib.util
import os

import pandas as pd

import _release

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "outputs")
DATA = os.path.join(HERE, "..", "Data", "GEM Data")
OLD, NEW = "March 2025", "August 2026"
PARTS = ("(i) units the March 2025 file attributed to a listed entity that owns the entrant in August 2026, "
         "the entrant not then listed and identified",
         "(ii) the rest of the units the March 2025 file carried",
         "(iii) units the March 2025 file did not carry")

_lines = []


def say(s=""):
    print(s)
    _lines.append(s)


def load_nine():
    p = os.path.join(HERE, "09_exposure_proxy.py")
    spec = importlib.util.spec_from_file_location("exposure_proxy", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def split_capacity(unit_mw, march_units, holders_of, owners, listed_in_march):
    """The three parts of one entrant's August 2026 capacity, in MW, as (i, ii, iii).

    unit_mw maps each unit attributed to the entrant in August 2026 to the megawatts attributed to it
    from that unit; march_units is the set of units the March 2025 file carried; holders_of maps a unit
    to the listed and identified entities, other than the entrant, that the March 2025 attribution gave
    it to; owners is the set of entities that own the entrant in August 2026 at any depth;
    listed_in_march says whether the entrant was a listed and identified entity in March 2025. A unit is
    in (i) when it is in the March 2025 file, the entrant was not listed and identified then, and one of
    its March 2025 holders owns the entrant; in (ii) when it is in the March 2025 file otherwise; in
    (iii) when the March 2025 file did not carry it. Every unit is in exactly one part, so the three add
    up to the entrant's capacity."""
    parts = [0.0, 0.0, 0.0]
    for u in sorted(unit_mw):
        if u not in march_units:
            parts[2] += unit_mw[u]
        elif not listed_in_march and holders_of.get(u, set()) & owners:
            parts[0] += unit_mw[u]
        else:
            parts[1] += unit_mw[u]
    return tuple(parts)


def main():
    nine = load_nine()
    old_f, new_f = _release.RELEASES[OLD], _release.RELEASES[NEW]
    say("THE FIRMS THAT ENTER THE PANEL BETWEEN THE TWO RELEASES, added 20 November 2026")
    say("  entrants: panel firms at zero attributable capacity in March 2025 with blanks imputed")
    say("  and above zero in August 2026, as script 10 counts them")
    say("  measure: their August 2026 capacity, unit by unit, by what the March 2025 file held of each unit;")
    say("  set on 20 November 2026, after the script's first run")
    panel = pd.read_csv(os.path.join(OUT, "panel_exposure.csv"), dtype={"entity_id": str})
    entrants = panel[(panel.mw_2025_impute == 0) & (panel.mw_2026_impute > 0)].copy()
    say(f"  entrants counted from panel_exposure.csv   {len(entrants)}")

    quiet = []
    loaded = {lbl: nine.load_vintage(lbl, fn, quiet.append) for lbl, fn in ((OLD, old_f), (NEW, new_f))}
    units_old, units_new, unit_mw_new = {}, {}, {}
    nine.build(OLD, loaded[OLD], "impute", quiet.append, keep_units=units_old)
    nine.build(NEW, loaded[NEW], "impute", quiet.append, keep_units=units_new, keep_unit_mw=unit_mw_new)
    march_unit_ids = {u for (u, _own) in loaded[OLD]["units"]}
    names_old = loaded[OLD]["name"]
    listed_old = loaded[OLD]["listed"]
    holders_by_unit = {}
    for a, us in units_old.items():
        for u in us:
            holders_by_unit.setdefault(u, set()).add(a)
    owners_new = {}
    for subj, party, _share in loaded[NEW]["edges"]:
        owners_new.setdefault(subj, set()).add(party)

    def ancestors(e):
        """Every entity that owns e in August 2026 through the ownership edges, at any depth."""
        seen, stack = set(), [e]
        while stack:
            x = stack.pop()
            for o in owners_new.get(x, ()):
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        return seen

    rows = []
    for _, r in entrants.iterrows():
        e = r.entity_id
        aug = units_new.get(e, set())
        umw = unit_mw_new.get(e, {})
        if set(umw) != aug:
            raise SystemExit(f"{e}: the units and the megawatts by unit disagree")
        if abs(sum(umw.values()) - float(r.mw_2026_impute)) >= 0.01:
            raise SystemExit(f"{e}: the units add to {sum(umw.values()):.4f} MW against "
                             f"{float(r.mw_2026_impute):.2f} in panel_exposure.csv")
        carried = aug & march_unit_ids
        holders_of = {u: holders_by_unit.get(u, set()) - {e} for u in carried}
        holders = sorted(set().union(*holders_of.values())) if holders_of else []
        owners = ancestors(e)
        listed_then = e in listed_old
        p1, p2, p3 = split_capacity(umw, march_unit_ids, holders_of, owners, listed_then)
        n1 = sum(1 for u in carried if not listed_then and holders_of[u] & owners)
        rows.append({"entity_id": e, "name": r["name"], "august_2026_mw": float(r.mw_2026_impute),
                     "august_2026_units": len(aug), "units_in_march_2025_file": len(carried),
                     "march_2025_listed_holders": "; ".join(f"{a} {names_old.get(a, '')}" for a in holders),
                     "listed_and_identified_in_march_2025": listed_then,
                     "owned_in_august_2026_by_a_march_2025_holder": bool(set(holders) & owners),
                     "units_part_i": n1,
                     "mw_part_i_held_under_a_listed_owner": p1,
                     "mw_part_ii_rest_carried_in_march_2025": p2,
                     "mw_part_iii_not_carried_in_march_2025": p3})
    tab = pd.DataFrame(rows).sort_values(["august_2026_mw", "entity_id"], ascending=[False, True])
    tab.to_csv(os.path.join(OUT, "panel_entrants.csv"), index=False, float_format="%.2f")

    say()
    say(f"  {'entrant':<40} {'Aug 2026 MW':>12} {'units':>6} {'in March file':>14} {'listed Mar':>10} "
        f"{'owned Aug':>9} {'(i) MW':>10} {'(ii) MW':>10} {'(iii) MW':>10}  March 2025 listed holder")
    for _, r in tab.iterrows():
        say(f"  {str(r['name'])[:40]:<40} {r.august_2026_mw:>12,.1f} {r.august_2026_units:>6} "
            f"{r.units_in_march_2025_file:>14} {str(bool(r.listed_and_identified_in_march_2025)):>10} "
            f"{str(bool(r.owned_in_august_2026_by_a_march_2025_holder)):>9} "
            f"{r.mw_part_i_held_under_a_listed_owner:>10,.1f} {r.mw_part_ii_rest_carried_in_march_2025:>10,.1f} "
            f"{r.mw_part_iii_not_carried_in_march_2025:>10,.1f}  {r.march_2025_listed_holders}")

    total = float(tab.august_2026_mw.sum())
    mw = [float(tab[c].sum()) for c in ("mw_part_i_held_under_a_listed_owner",
                                        "mw_part_ii_rest_carried_in_march_2025",
                                        "mw_part_iii_not_carried_in_march_2025")]
    shown_mw = [round(x, 1) for x in mw]
    shown_pc = [round(100 * x / total, 1) for x in mw]
    if abs(sum(shown_mw) - round(total, 1)) > 1e-6 or abs(sum(shown_pc) - 100.0) > 1e-6:
        raise SystemExit(f"the three parts as printed do not add up: {shown_mw} against {total:,.1f} MW, "
                         f"{shown_pc} per cent")
    say()
    say(f"entrants {len(tab)} | August 2026 capacity {total:,.1f} MW, split unit by unit into three parts")
    for label, x, pc in zip(PARTS, mw, shown_pc):
        say(f"  {label}   {x:,.1f} MW, {pc:.1f} per cent")
    say(f"  the three parts add up to   {sum(shown_mw):,.1f} MW, {sum(shown_pc):.1f} per cent")
    first = tab[tab.mw_part_i_held_under_a_listed_owner > 0].sort_values(
        ["mw_part_i_held_under_a_listed_owner", "entity_id"], ascending=[False, True])
    top = first.head(2)
    say(f"  entrants with capacity in (i) {len(first)}; of (i), the two largest: "
        + "; ".join(f"{t['name']} {t.mw_part_i_held_under_a_listed_owner:,.1f} MW, "
                    f"{100 * t.mw_part_i_held_under_a_listed_owner / mw[0]:.1f} per cent of (i)"
                    for _, t in top.iterrows()))
    for _, r in first.iterrows():
        say(f"  {r['name']}: {r.units_part_i} of {r.august_2026_units} units, "
            f"{r.mw_part_i_held_under_a_listed_owner:,.1f} of {r.august_2026_mw:,.1f} MW in (i), held in "
            f"March 2025 by {r.march_2025_listed_holders}")

    _release.write_provenance(
        OUT, "25_panel_entrants",
        {"old": os.path.join(DATA, old_f), "new_pinned": os.path.join(DATA, new_f)},
        extra={"derived_from": ["panel_exposure.csv"], "entrants": int(len(tab)),
               "august_2026_mw": round(total, 2), "mw_part_i": round(mw[0], 2),
               "mw_part_ii": round(mw[1], 2), "mw_part_iii": round(mw[2], 2)})
    say()
    say(f"  written to {os.path.relpath(OUT, os.path.join(HERE, '..'))}")
    with open(os.path.join(OUT, "panel_entrants.txt"), "w") as fh:
        fh.write("\n".join(_lines) + "\n")


if __name__ == "__main__":
    main()
