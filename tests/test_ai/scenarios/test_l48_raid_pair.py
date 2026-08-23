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
"""

from pathlib import Path

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state

_RAID_BOSS = "pixie"
BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def _report(name: str):
    """Same offline full-stack seam test_band_liveness uses."""
    gd = load_bundle_game_data(BUNDLE)
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name], gd), gd)
    return player.plan_from_state()


# ─── negative pole: no raid, provably nothing to do ──────────────────────────

def test_l48_without_a_raid_cannot_fight():
    """The wall, RE-DERIVED BY WAVE 3a. No raid window and no permanent L47-50
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
    assert not any("Fight" in str(g.get("goal")) or "Grind" in str(g.get("goal"))
                   or "Raid" in str(g.get("goal"))
                   for g in report.goals_tried), (
        "l48_band_adequate is the no-COMBAT pole: if the arbiter found a fight "
        "to try, the wall has moved and this pair needs re-deriving"
    )
    assert repr(report.selected_goal) == "GatherMaterials(mithril_bar, {mithril_bar:11})", (
        repr(report.selected_goal), report.plan)


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
    `test_l48_without_a_raid_cannot_fight`), so "has something to try" alone no
    longer separates the poles — the SELECTED GOAL does, and it is asserted
    below. `test_l48_raid_plan_engages_the_boss` carries the positive claim."""
    report = _report("l48_raid_active")
    assert report.goals_tried, (
        "an open raid window must give the arbiter something to try; if this is "
        "empty the raid fight never became selectable"
    )
    assert repr(report.selected_goal) == "ParticipateRaid(enchanted_fairy)", (
        repr(report.selected_goal), [g.get("goal") for g in report.goals_tried])


def test_l48_raid_plan_engages_the_boss():
    """The plan must actually route to the raid boss -- goals_tried being
    non-empty would otherwise be satisfied by any unrelated work.

    RESTORED in wave 3a fix-round 1. For one commit this asserted the negation;
    see the module docstring for what broke it and the two fixes that brought
    it back."""
    report = _report("l48_raid_active")
    assert any(isinstance(a, FightAction) and a.monster_code == _RAID_BOSS
               for a in report.plan), [repr(a) for a in report.plan]


def test_the_two_poles_differ_only_by_the_raid():
    """Guards the pair against drifting apart: if the two scenarios diverge in
    anything but `raids`, the comparison stops being about the raid."""
    a, b = SCENARIOS["l48_band_adequate"], SCENARIOS["l48_raid_active"]
    differing = {k for k in vars(a)
                 if getattr(a, k) != getattr(b, k)}
    assert differing <= {"name", "raids", "description"}, differing
    assert a.raids == () and b.raids == (("enchanted_fairy", "pixie"),)
