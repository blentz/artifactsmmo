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
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState


def _flat_utility(stats: ItemStats) -> int:
    """The monster-INDEPENDENT stat block the scorers carry unconverted —
    EXACTLY `armor_score`'s own `flat_utility` term, `hp_restore` included.

    `hp_restore` used to be listed here as a deliberate superset ("plus
    hp_restore, which no scorer reads"), because `armor_score` omitted it while
    the acquisition path's ruler counted it. Unifying Rank onto `armor_score`
    closed that gap at the source: `hp_restore` is now IN `flat_utility`, so
    this block is the scorer's block rather than a hand-maintained superset of
    it, and the two can no longer drift apart.
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


def defers_to_picker(code: str, slot: str, state: WorldState,
                     game_data: GameData) -> bool:
    """True iff the acquisition path must leave `slot` to `pick_loadout`.

    THE TARGET-NAMING GATE, shared by the two walks that name gear roots —
    `progression_tree._structural_candidates` and
    `CharacterObjective.gear_targets_with_blockers`. It is stated once here
    because they had drifted: the 2026-08-04 fix pinned the tree leg, and the
    objective walk — whose winner `obtain_item_routing._equippable_goal` turns
    into a COMMITTED `UpgradeEquipmentGoal` with no occupancy question asked —
    never had the gate at all. Live HAL ran
    `Equip(hard_leather_pants->leg_armor_slot)` 1,464 times between 2026-09-08
    and 2026-09-20 through that hole, 790 of them in one 94.7-hour session
    (16.5% of his cycles), with `OptimizeLoadout(pig)` restoring
    `adventurer_pants` after every one.

    The two ACTION-side gates in `goals/progression.py`
    (`_find_inventory_upgrade`, `_committed_upgrade_if_ready`) call
    `may_displace` directly and deliberately keep their own ownership rules —
    the first because every pick it makes is owned by construction, the second
    because it gates an as-yet-UNOWNED committed target too. Folding them in
    here would widen this predicate's contract, not narrow theirs.

    Three conjuncts, and each one is load-bearing:

    * OWNED (bag or bank). An unowned candidate is real, terminating work —
      acquiring it — and this gate applies by the time it lands. A BANKED copy
      is one Withdraw from the same contested equip, so the bank counts.
    * OCCUPIED. An empty slot has no incumbent to disagree about; whatever the
      acquisition path names is strictly additive and the picker keeps it.
    * NOT DOMINATING. `may_displace` is the deferral proper — see this module's
      docstring for why stat-wise dominance is exactly the condition that makes
      the swap a fixed point of `pick_loadout` for EVERY monster.

    An incumbent whose stats do not resolve is NOT deferred to: `pick_loadout`
    displaces an unknown incumbent unconditionally, so there is no disagreement
    to defer to (same handling as `_is_upgrade_over_impl`, not a third policy).
    """
    owned = (state.inventory.get(code, 0) > 0
             or (state.bank_items or {}).get(code, 0) > 0)
    if not owned:
        return False
    incumbent = state.equipment.get(slot)
    if incumbent is None:
        return False
    incumbent_stats = game_data.item_stats(incumbent)
    candidate_stats = game_data.item_stats(code)
    if incumbent_stats is None or candidate_stats is None:
        return False
    return not may_displace(candidate_stats, incumbent_stats)
