"""The fight-loadout precondition (Tasks 1-4) sequences OptimizeLoadout(combat)
before a Fight whenever the equipped loadout is suboptimal — the live Robby
vs cow bug (a stale gathering tool in the weapon slot loses a winnable
fight). This scenario drives the real offline planner (the same
`SCENARIOS`/`scenario_state`/`GamePlayer` harness as test_no_deadlock.py) and
pins the swap-before-fight ordering against `l20_dual_utility`, the same
band-adequate criterion-2 scenario `test_no_deadlock.py` already proves
selects `GrindCharacterXP(highwayman)` with an optimal loadout.

Full-bag relief (brief Step 3, "STRONGLY PREFERRED"): investigated below and
found NOT reliably expressible as a single `plan_from_state()` call, or even
as a clean two-cycle chase, from this scenario — see `TestFullBagRelief`'s
docstring for the concrete evidence. What IS expressible offline is pinned
instead: `OptimizeLoadoutAction.is_applicable` is genuinely SLOT-BLOCKED at a
full bag (the structural reason relief must run first) and becomes
applicable again the instant one slot frees up. The full relief-before-swap
plan ORDERING is covered by the live runtime verification in Task 7."""

import dataclasses
from pathlib import Path

from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

BASE_SCENARIO = "l20_dual_utility"
"""Reused from test_no_deadlock.py's CRITERION_2_WINNABLE: a band-adequate
L20 build (mushmush_bow/hard_leather_helmet/... — the combat-dominant
pursuit_value fixed point) with a winnable monster (highwayman) in reach.
`test_l20_dual_utility_chosen_root_is_char_level_when_winnable` pins that,
fully equipped, it plans `Fight(highwayman)` directly with NO swap — the
"already optimal" half of this scenario's swap/no-swap pair."""

TARGET_MONSTER = "highwayman"
WEAK_WEAPON = "wooden_stick"
"""L1 starter weapon (attack={'earth': 4}) — trivially outclassed by the
scenario's real weapon `mushmush_bow` (L15, attack={'air': 12, 'water': 12})
against highwayman (air resistance -10%, i.e. air damage is AMPLIFIED), so
`pick_loadout` unambiguously prefers mushmush_bow whenever it is owned."""
OPTIMAL_WEAPON = "mushmush_bow"

JUNK_STACKS = {
    "algae": 1, "ash_plank": 1, "ash_wood": 1, "copper_bar": 1, "copper_ore": 1,
    "egg": 1, "golden_egg": 1, "gudgeon": 1, "raw_chicken": 1,
    "shell": 1, "sunflower": 1, "green_slimeball": 1, "cloth": 1,
    "milk_bucket": 1, "raw_beef": 1, "blue_slimeball": 1, "red_slimeball": 1,
    "hard_leather": 1,
}
"""17 distinct, non-keep junk resources (mirrors test_slot_exhaustion.py's
JUNK_STACKS) — none is a weapon, tool, HP consumable, or currency, so none is
protected by `bank_selection`'s keep-set and every one is normally bankable."""


def _bundle():
    return load_bundle_game_data(BUNDLE)


def _suboptimal_scenario():
    """l20_dual_utility with the weak weapon equipped and mushmush_bow owned
    (unequipped) — the exact "stale tool in the weapon slot, better weapon in
    the bag" shape of the live bug, built via `dataclasses.replace` on the
    SCENARIOS entry (not the derived WorldState) so `derive_combat_stats`
    recomputes attack/dmg from the swapped-out weapon, not stale mushmush_bow
    totals."""
    base = SCENARIOS[BASE_SCENARIO]
    return dataclasses.replace(
        base,
        equipment={**base.equipment, "weapon_slot": WEAK_WEAPON},
        inventory={OPTIMAL_WEAPON: 1},
    )


def _run(sc):
    gd = _bundle()
    player = GamePlayer(character=sc.name, history=None)
    player.seed_offline(scenario_state(sc, gd), gd)
    return player.plan_from_state()


def test_scenario_registered() -> None:
    assert BASE_SCENARIO in SCENARIOS


def test_swap_precedes_fight_when_loadout_suboptimal() -> None:
    """MANDATORY: a suboptimal-loadout state (wooden_stick equipped,
    mushmush_bow owned with slot headroom) yields a plan whose first action
    is OptimizeLoadout(highwayman) and which contains Fight(highwayman)
    strictly after it — the planner arms its best owned weapon before
    fighting rather than losing a winnable fight with a stale weapon."""
    report = _run(_suboptimal_scenario())
    reprs = [repr(a) for a in report.plan]
    assert reprs, (repr(report.selected_goal), report.plan)
    assert reprs[0] == "OptimizeLoadout(highwayman)", reprs
    assert "Fight(highwayman)" in reprs, reprs
    assert reprs.index("Fight(highwayman)") > reprs.index("OptimizeLoadout(highwayman)")
    # The guarantee this feature protects — GrindCharacterXP is still the
    # goal that gets pursued, just with the swap front-loaded.
    assert isinstance(report.selected_goal, GrindCharacterXPGoal), (
        repr(report.selected_goal), report.plan)


def test_no_swap_when_loadout_already_optimal() -> None:
    """The unmodified l20_dual_utility scenario (mushmush_bow already
    equipped) plans Fight(highwayman) directly, no leading swap — matches
    test_no_deadlock.py's test_l20_dual_utility_chosen_root_is_char_level_when_winnable."""
    report = _run(SCENARIOS[BASE_SCENARIO])
    assert [repr(a) for a in report.plan] == ["Fight(highwayman)"]
    assert report.decision.chosen_root == ReachCharLevel(level=30)


class TestFullBagRelief:
    """STRONGLY PREFERRED (brief Step 3): full-bag relief precedes the swap.

    Investigated with the real bundle+GamePlayer harness (same construction
    as `_suboptimal_scenario`, plus `JUNK_STACKS` packing every inventory
    slot so `inventory_slots_free == 0`): `GrindCharacterXPGoal` becomes
    completely UNPLANNABLE in that state — `FightAction.is_applicable` is
    blocked by the loadout gate (wooden_stick != optimal) and
    `OptimizeLoadoutAction.is_applicable` is blocked by the slot gate (no
    room to receive the displaced wooden_stick), and
    `GrindCharacterXPGoal.relevant_actions` admits no relief action (only
    the target-monster Fight, "recovery"-tagged actions, and "equip"-tagged
    actions targeting this monster — DepositAllAction is tagged
    {"bank","deposit"}, neither). With this goal unplannable, the real
    StrategyArbiter's top-plannable selection does NOT chain
    [DepositAll, OptimizeLoadout, Fight] — it moves on to a DIFFERENT
    candidate entirely. Empirically (bundle fixture, 2026-07-10): the full
    bag state above plans `selected_goal=UpgradeEquipment(minor_health_potion
    ->utility1_slot)`, `plan=[DepositAll, Withdraw(nettle_leaf x2),
    Withdraw(algae x1), Craft(minor_health_potion x1),
    Equip(minor_health_potion->utility1_slot)]` — plan[0] IS a relief action,
    but the rest of the plan has nothing to do with the weapon swap. So
    "relief -> swap -> fight" is not a clean single- or two-cycle assertion
    from this scenario: StrategyArbiter.select() returns exactly one
    (goal, plan) pair per call (strategy_driver.py), and when the combat
    goal is unplannable a completely unrelated candidate can win instead.

    What IS expressible and asserted below: the exact slot arithmetic that
    forces relief to run first — OptimizeLoadoutAction.is_applicable is
    False at slots_free==0 and True the instant one slot frees (what
    DepositAll's relief buys). The full plan-level ordering is covered by
    the live runtime verification in Task 7 (this is the documented Robby
    cow bug scenario)."""

    def _full_bag_scenario(self, extra_slots: int = 0):
        base = SCENARIOS[BASE_SCENARIO]
        inventory = {OPTIMAL_WEAPON: 1, **JUNK_STACKS}
        return dataclasses.replace(
            base,
            equipment={**base.equipment, "weapon_slot": WEAK_WEAPON},
            inventory=inventory,
            inventory_slots_max=len(inventory) + extra_slots,
        )

    def test_full_bag_construction_is_slot_exhausted(self) -> None:
        gd = _bundle()
        state = scenario_state(self._full_bag_scenario(), gd)
        assert state.inventory_slots_free == 0
        assert state.inventory_free > 0  # quantity is NOT the binding cap

    def test_optimize_loadout_slot_blocked_at_full_bag(self) -> None:
        """The equipped wooden_stick, once swapped out, needs a NEW distinct
        inventory stack that has nowhere to land at slots_free==0 — the
        structural reason relief must run before the swap."""
        gd = _bundle()
        state = scenario_state(self._full_bag_scenario(), gd)
        action = OptimizeLoadoutAction(target_monster_code=TARGET_MONSTER, game_data=gd)
        assert action.is_applicable(state, gd) is False

    def test_optimize_loadout_applicable_once_a_slot_is_free(self) -> None:
        """Exactly one slot of headroom (what DepositAll's relief buys) makes
        the swap applicable again — isolates the precise arithmetic relief
        clears."""
        gd = _bundle()
        state = scenario_state(self._full_bag_scenario(extra_slots=1), gd)
        assert state.inventory_slots_free == 1
        action = OptimizeLoadoutAction(target_monster_code=TARGET_MONSTER, game_data=gd)
        assert action.is_applicable(state, gd) is True
