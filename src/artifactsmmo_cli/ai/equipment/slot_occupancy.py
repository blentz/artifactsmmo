"""ONE authority for slot OCCUPANCY: when may a non-picker goal displace an
incumbent?

`pick_loadout` (via `equipment.scoring`) decides which owned item occupies a
slot. It is MONSTER-RELATIVE. The acquisition path — the progression tree's gear
branch and `UpgradeEquipmentGoal` — ranks items on the MONSTER-INDEPENDENT
`pursuit_value`/`equip_value` ruler. Two rulers over the same slot is a livelock:
live 2026-08-04, Robby (level 21) wore `fire_and_earth_amulet` and owned
`life_amulet`; the tree scored the swap `+10000` and equipped `life_amulet`, the
next `OptimizeLoadout(wolf)` scored `fire_and_earth_amulet` 48000 vs 6000 and
equipped it back, and the pair alternated forever at one API request and one
cooldown per leg.

No monster-blind total order can agree with a monster-relative one on every
monster, so the split is closed by DEFERRING rather than by re-tuning: the
acquisition path may pre-empt the picker only when its answer is provably the
picker's answer too — i.e. when the candidate DOMINATES the incumbent on every
stat the picker's scorers read. Both scorers are then monotone, KERNEL-CHECKED:

* armor — `Formal.GearPolicy.armor_score_mono_in_resistance` takes exactly this
  hypothesis set (per-element resistance ≤, `flatUtil` ≤, and per element
  `2*(dmg + dmgElem[e]) + crit` ≤) and concludes `AScore a ≤ AScore b` for ANY
  `monsterAtk`/`monsterRes`/`playerAtk`;
* weapon — `Formal.GearPolicy.weapon_score_mono_of_dominates` (per-element
  attack ≤, `crit` ≤ ⇒ `WScore a ≤ WScore b` for any `monsterRes`), lifted
  through `PurposeRouting.combatScore`'s `nonToolBonus` by the tool clause
  below.

So dominance gives

    ∀ monster, ∀ wearer:  score(candidate) ≥ score(incumbent)

and `pick_loadout` swaps only on a STRICT improvement
(`EquipmentScoring.pickslot_ties_keep_current`) — so once the candidate is
equipped the incumbent can never strictly beat it and the swap is a FIXED POINT.
Non-dominating gear is not "rejected": its occupancy is simply left to the one
authority that can price it per monster, which equips it before the next fight
(`FightAction`'s optimal-loadout precondition) when it is genuinely better there.
"""

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import ItemStats


def _flat_utility(stats: ItemStats) -> int:
    """The monster-INDEPENDENT stat block the scorers carry unconverted.

    `armor_score`'s own `flat_utility` term plus `hp_restore`, which no scorer
    reads. Including it can only make `may_displace` STRICTER, never wronger:
    dominance is a sufficient condition, so a superset of stats keeps the
    fixed-point argument sound while also stopping the acquisition path from
    trading away a consumable's restore value behind the picker's back.
    """
    return (stats.hp_bonus + stats.wisdom + stats.prospecting
            + stats.inventory_space + stats.haste + stats.lifesteal
            + stats.combat_buff + stats.hp_restore)


def may_displace(candidate: ItemStats, incumbent: ItemStats) -> bool:
    """True iff equipping `candidate` over `incumbent` in the same slot is a
    fixed point of `pick_loadout` for EVERY monster and EVERY wearer.

    That is exactly stat-wise dominance over what the scorers read:

    * per element — `attack` (weapon_score), `resistance` (armor_score defense),
      and the combined damage percentage `dmg + dmg_elements[e]` (armor_score
      offense, which adds the global and the per-element percentage together);
    * `critical_strike` (both scorers);
    * the flat-utility block;
    * the non-tool tiebreaker — a tool may never displace a non-tool, because
      `weapon_score`'s `nonToolBonus` is +1 for the non-tool
      (`PurposeRouting.combatScore_tiebreaks_nontool_over_tool`).

    Equality is allowed: `pick_loadout` keeps the incumbent on a tie, so a
    tying candidate is still never swapped back. Callers keep their own
    strict-improvement rule (the tree's `gain > 0`, the goal's
    `_is_upgrade_over`) — this predicate answers only "may the picker be
    pre-empted", never "is this worth an action".
    """
    if _flat_utility(candidate) < _flat_utility(incumbent):
        return False
    if candidate.critical_strike < incumbent.critical_strike:
        return False
    if candidate.subtype == "tool" and incumbent.subtype != "tool":
        return False
    for elem in ELEMENTS:
        if candidate.attack.get(elem, 0) < incumbent.attack.get(elem, 0):
            return False
        if candidate.resistance.get(elem, 0) < incumbent.resistance.get(elem, 0):
            return False
        if (candidate.dmg + candidate.dmg_elements.get(elem, 0)
                < incumbent.dmg + incumbent.dmg_elements.get(elem, 0)):
            return False
    return True
