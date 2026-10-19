"""The L48 wall, both poles (epic P5).

The bundle's L47-50 fight window is event-and-raid-only content: 14 of its 58
monsters have no static map tile, and `duskworm` -- named by test_band_liveness as
an L48-window monster -- is among them. Two of the fourteen are the raid bosses
`pixie` and `sonnengott`.

So a band-adequate L48 character has NOTHING PERMANENT TO FIGHT. That is not a
bug in the scenario and not a difficulty problem; it is the wall, and it was
hidden for a long time because CRAFT_POTIONS fired on a bare stock deficit and
gave the arbiter potion busywork to do. Once potion stocking became
combat-justified (7004f450) the busywork stopped and the wall surfaced as an
empty `goals_tried`.

This pair makes the wall a property of the WORLD STATE rather than an unexplained
dead end:

    no raid active -> the bot provably cannot plan; Wait is CORRECT
    raid active    -> the bot plans raid participation

Both poles are needed. The negative one passes trivially -- it passed before any
raid capability existed at all -- so only the paired positive pole is evidence
that the planner gained anything.

WAVE 3a BROKE THE POSITIVE POLE AND FIX-ROUND 1 REPAIRED IT. For one commit
both poles planned `GatherMaterials(mithril_bar)` and neither engaged the boss.
The chain was: `derive_combat_stats` is off here (deliberately — see
`scenario.py`), so `combat_capable` reads False and
`prerequisites(ReachCharLevel)` emits a weapon; wave 3a runs `actionable_step`
on EVERY root including the trunk, so that weapon became a plannable fallback
step; `_resolve_step_goal` promoted it into the STEP slot; and raids sat at
`BAND_DISCRETIONARY`, below everything. Two fixes, both in
`ai/arbiter_select.py` / `ai/strategy_driver.py` and both independently
justified:

  * raids moved to their own `BAND_RAID`, above the fallback steps. The
    liveness census had ALREADY classified `ParticipateRaidGoal` unreachable
    for this reason, before the flip made it visible here.
  * a step goal promoted out of the fallbacks when the walk named a WALL
    (`chosen_root is None`) is filed at `BAND_FALLBACK_STEP`, not `BAND_STEP`.
    A fallback promoted because there was no step is not an objective step.

Giving this scenario real combat stats instead does NOT work and is not a
matter of taste: at real stats `expected_damage_per_fight` against `pixie`
returns 1,844,857 against a 1570-hp character, so `raid_survivable_pure`
refuses and the raid candidate is never built at all. That number is its own
defect and is reported separately.

RE-DERIVED 2026-10-18 (ruling R): the pair now runs on real combat stats. A
sheet whose totals lack its worn mithril set is a world the API never serves,
and the gear objective raises on it, so both scenarios derive their stats. The
positive pole therefore fails exactly as the paragraph above predicted:
`expected_damage_per_fight(pixie)` reads 1,844,857 against 1570 hp, the raid
candidate is never built, and BOTH poles Wait (with `L*` missing pieces and no
task, no fight is chosen for XP either: spec 2026-10-18 §6.2). The pins below
state that derived outcome; the pair cannot separate the poles again until the
pixie damage defect is fixed.

RE-DERIVED Task 5 (ruling Z, global gear objective): an `L*` piece outranks an
active raid (USER: gear before fights; spec 2026-10-18 §2.4: no fight is
chosen for XP while `L*` is incomplete). Both poles' root is the first missing
piece, `goblin_guard_shield`, and both plan exactly its acquisition:
`UpgradeEquipment(goblin_guard_shield->shield_slot)`. A raid fights only when
it is the route of the chosen piece or once `L*` is held.
`test_a_survivable_raid_still_yields_to_the_missing_piece` shows the raid
yields to the piece even when it IS survivable.

RE-DERIVED ruling AJ (final review F2): filing the raid behind the step only
ORDERED it, so a piece step that failed to plan, or had spent its rotation
turn, handed the cycle to the boss. The raid is now not offered at all while a
piece is missing (`strategy_driver.raid_may_fight`); the last two tests pin
both paths.
"""

from pathlib import Path

import pytest

import artifactsmmo_cli.ai.strategy_driver as strategy_driver
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from tests.test_ai.shared_world import shared_world

_RAID_BOSS = "pixie"
_SHIELD = ObtainItem(code="goblin_guard_shield", quantity=1, slot="shield_slot")
"""Both poles' first missing `L*` piece."""
_SHIELD_STEP = "UpgradeEquipment(goblin_guard_shield->shield_slot)"
"""The step goal that acquires `_SHIELD`."""
BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def _gd():
    return shared_world(BUNDLE)


def _state(name: str):
    """The scenario's state on the bundle catalogue."""
    return scenario_state(SCENARIOS[name], _gd())


def _report(name: str):
    """Same offline full-stack seam test_band_liveness uses."""
    gd = _gd()
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name], gd), gd)
    return player.plan_from_state()


# ─── negative pole: no raid, provably nothing to do ──────────────────────────

def test_l48_without_a_raid_fights_only_for_its_missing_piece():
    """RENAMED Task 5 fix round 1 (was `..._cannot_fight`): the pole now plans
    an ACQUISITION fight for its first missing `L*` piece, never an XP fight.

    The wall, RE-DERIVED BY WAVE 3a. No raid window and no permanent L47-50
    monster, so the character still cannot FIGHT its way out — that is the pole
    this pair is about and it is unchanged.

    What changed is that the pole is no longer "nothing to try". The old XP
    branch set `chosen_step = trunk` outright and `objective_step_goal` answers
    None for a `ReachCharLevel` with no combat monster, so the arbiter reached
    nothing and idled on `Wait`; `goals_tried` was empty. The resolution walk
    runs `actionable_step` on every root including the trunk, so the trunk
    descends to its weapon prerequisite and a real craft chain becomes
    reachable. The character is not blocked, it is just not fighting.

    So the assertion moved from "no work at all" to "no COMBAT work", which is
    the claim the raid pole actually contrasts with — and it is asserted
    positively, on the tried goals, not by exempting this scenario from
    anything."""
    report = _report("l48_band_adequate")
    assert report.goals_tried, "the walled pole must still reach a bounded means"
    assert not any("Grind" in str(g.get("goal")) or "Raid" in str(g.get("goal"))
                   for g in report.goals_tried), (
        "l48_band_adequate is the no-XP-fight pole: if the arbiter tried a "
        "grind or a raid, the wall has moved and this pair needs re-deriving"
    )
    # RE-DERIVED Task 5 (ruling Z): the root is the first missing `L*` piece,
    # and the pole plans its acquisition — an acquisition fight, not one chosen
    # for XP.
    assert repr(report.selected_goal) == "UpgradeEquipment(goblin_guard_shield->shield_slot)", (
        repr(report.selected_goal), report.plan)
    assert report.decision.chosen_root == _SHIELD


def test_l48_without_a_raid_emits_no_raid_fight():
    """Non-vacuity for the pair: the boss is absent because the WINDOW is shut,
    not because the fixture lacks the boss."""
    report = _report("l48_band_adequate")
    assert not any(isinstance(a, FightAction) and a.monster_code == _RAID_BOSS
                   for a in report.plan)


# ─── positive pole: raid open, participation is plannable ────────────────────

def test_l48_with_an_active_raid_can_plan():
    """Same state, one difference: the raid window is open. The arbiter now has
    work, so the wall is a property of the world rather than a dead end.

    The negative pole now also reaches a means (a mithril_bar craft chain, see
    `test_l48_without_a_raid_fights_only_for_its_missing_piece`), so "has something to try" alone no
    longer separates the poles — the SELECTED GOAL does, and it is asserted
    below. `test_l48_raid_plan_engages_the_boss` carries the positive claim.

    RE-DERIVED 2026-10-18 (ruling R): on real stats the raid candidate is
    refused as unsurvivable (see the module docstring), so the open window
    adds nothing: the raid pole tries exactly the walled pole's goals.

    RE-DERIVED Task 5 (ruling Z): both poles plan exactly the first missing
    `L*` piece's acquisition."""
    report = _report("l48_raid_active")
    walled = _report("l48_band_adequate")
    assert [g.get("goal") for g in report.goals_tried] == \
        [g.get("goal") for g in walled.goals_tried]
    assert repr(report.selected_goal) == "UpgradeEquipment(goblin_guard_shield->shield_slot)", (
        repr(report.selected_goal), [g.get("goal") for g in report.goals_tried])
    assert report.decision.chosen_root == _SHIELD


def test_l48_raid_plan_engages_the_boss():
    """The plan must actually route to the raid boss -- goals_tried being
    non-empty would otherwise be satisfied by any unrelated work.

    RESTORED in wave 3a fix-round 1. For one commit this asserted the negation;
    see the module docstring for what broke it and the two fixes that brought
    it back.

    RE-DERIVED 2026-10-18 (ruling R): on real stats the boss reads
    unsurvivable (`raid_survivable_pure`: the expected damage exceeds the hp
    pool), so the plan engages nothing.

    RE-DERIVED Task 5 (ruling Z): the plan is the `L*` piece's acquisition —
    down to the goblin_guard, fight it for its shield, equip it — and no
    action fights the raid boss."""
    report = _report("l48_raid_active")
    assert [repr(a) for a in report.plan] == [
        "Transition((5,-3,overworld)->(5,-3,underground))", "Fight(goblin_guard)",
        "Equip(goblin_guard_shield->shield_slot)"]
    assert not any(isinstance(a, FightAction) and a.monster_code == _RAID_BOSS
                   for a in report.plan)
    # The cause of the refusal, not its magnitude: the estimate exceeds the
    # character's whole hp pool, so the raid is unsurvivable.
    state = _state("l48_raid_active")
    assert expected_damage_per_fight(state, _gd(), _RAID_BOSS) > state.max_hp


def test_the_two_poles_differ_only_by_the_raid():
    """Guards the pair against drifting apart: if the two scenarios diverge in
    anything but `raids`, the comparison stops being about the raid."""
    a, b = SCENARIOS["l48_band_adequate"], SCENARIOS["l48_raid_active"]
    differing = {k for k in vars(a)
                 if getattr(a, k) != getattr(b, k)}
    assert differing <= {"name", "raids", "description"}, differing
    assert a.raids == () and b.raids == (("enchanted_fairy", "pixie"),)


def test_a_survivable_raid_still_yields_to_the_missing_piece(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling Z, with the pixie damage defect patched away: the raid IS
    survivable, so its candidate is built (the survivability gate is asked of
    the boss) — and still the root is the missing `L*` piece, the selected goal
    is that piece's acquisition, and no action fights the boss. While a piece
    is missing the raid is not offered at all (`strategy_driver.raid_may_fight`,
    ruling AJ): only once `L*` is held, or as the chosen piece's route."""
    asked: list[float] = []

    def survivable(hp: int, max_hp: int, damage: float) -> bool:
        asked.append(damage)
        return True

    monkeypatch.setattr(strategy_driver, "raid_survivable_pure", survivable)
    report = _report("l48_raid_active")
    assert asked, "the raid candidate was never built"
    assert report.decision.chosen_root == _SHIELD
    assert repr(report.selected_goal) == "UpgradeEquipment(goblin_guard_shield->shield_slot)"
    assert not any(isinstance(a, FightAction) and a.monster_code == _RAID_BOSS
                   for a in report.plan)


def _survivable(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Patch the pixie damage defect away: the raid reads survivable, so its
    candidate gate is asked. Returns the damages it was asked with."""
    asked: list[float] = []

    def survivable(hp: int, max_hp: int, damage: float) -> bool:
        asked.append(damage)
        return True

    monkeypatch.setattr(strategy_driver, "raid_survivable_pure", survivable)
    return asked


def _raid_tried(report) -> bool:
    return any("Raid" in str(g.get("goal")) for g in report.goals_tried)


def test_an_unplannable_piece_step_does_not_open_the_raid(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling AJ (final review F2): the piece's step fails to plan, and the raid
    is still not a fight the character may choose — a raid fights only once
    `L*` is held or when it is the chosen piece's route. Before the fix the
    raid sat right behind the step, so an unplannable step handed the cycle to
    the boss."""
    _survivable(monkeypatch)
    real = strategy_driver.StrategyArbiter._plans

    def no_plan_for_the_piece(self, goal, *args, **kwargs):
        if repr(goal) == _SHIELD_STEP:
            return []
        return real(self, goal, *args, **kwargs)

    monkeypatch.setattr(strategy_driver.StrategyArbiter, "_plans", no_plan_for_the_piece)
    report = _report("l48_raid_active")
    assert report.decision.chosen_root == _SHIELD
    assert not _raid_tried(report), [g.get("goal") for g in report.goals_tried]
    assert not any(isinstance(a, FightAction) and a.monster_code == _RAID_BOSS
                   for a in report.plan)


def test_a_spent_piece_turn_does_not_open_the_raid(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling AJ (final review F2): the piece's step has spent its rotation
    turn, so `rotate` demotes it to the end of the fallback band — behind the
    raid's band. The raid still is not built while a piece is missing."""
    _survivable(monkeypatch)
    gd = _gd()
    player = GamePlayer(character="l48_raid_active", history=None)
    player.seed_offline(scenario_state(SCENARIOS["l48_raid_active"], gd), gd)
    player._turns = {_SHIELD_STEP: 1}
    report = player.plan_from_state()
    assert report.decision.chosen_root == _SHIELD
    assert not _raid_tried(report), [g.get("goal") for g in report.goals_tried]
    assert not any(isinstance(a, FightAction) and a.monster_code == _RAID_BOSS
                   for a in report.plan)
