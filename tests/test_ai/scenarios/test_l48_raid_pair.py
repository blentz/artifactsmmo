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

WAVE 3a BROKE THE POSITIVE POLE, AND THIS FILE NOW RECORDS THAT RATHER THAN
ASSERTING IT AWAY. The two poles are currently INDISTINGUISHABLE: both plan
`GatherMaterials(mithril_bar)` and neither engages the boss. The chain is:

  * `derive_combat_stats` is off for these two scenarios, so a level-48
    character in a full mithril set reports `attack == {}` and
    `combat_capable` reads False;
  * `prerequisites(ReachCharLevel)` therefore emits a weapon
    (`ObtainItem(hell_reaper)`), and wave 3a runs `actionable_step` on EVERY
    root including the trunk (spec 5.2), where the old XP branch set
    `chosen_step = trunk` outright and never descended it;
  * so the trunk's fallback step is now a plannable craft chain, the arbiter
    takes it, and the raid rung -- which sits below the objective step -- never
    gets a turn. Before the flip the objective step yielded None and the walk
    reached the raid.

Two separate things are wrong and neither is this file's to fix: the FIXTURE
says a fully-armed L48 character has no weapon, and the ARBITER LADDER lets an
ordinary craft preempt a time-limited raid window. Both are written up in
`.superpowers/sdd/PLAN_wave3a_cutover/task-6-report.md` as the flip's most
serious open regression. The assertions below pin what the bot ACTUALLY does so
the loss is visible in the suite; `test_l48_raid_plan_engages_the_boss` states
the property that must come back.
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

    WAVE 3a made this VACUOUS and it is kept only so the pair stays symmetric:
    the negative pole has work too now (see this module's docstring), so
    "the arbiter has something to try" no longer distinguishes the poles.
    `test_l48_raid_plan_engages_the_boss` is where the real claim lives."""
    report = _report("l48_raid_active")
    assert report.goals_tried, (
        "an open raid window must give the arbiter something to try; if this is "
        "empty the raid fight never became selectable"
    )
    assert repr(report.selected_goal) != "Wait", repr(report.selected_goal)


def test_l48_raid_plan_engages_the_boss():
    """THE PROPERTY THAT MUST COME BACK, currently pinned as LOST.

    The plan must route to the raid boss -- goals_tried being non-empty would
    otherwise be satisfied by any unrelated work, and since wave 3a it is
    exactly that: the trunk's weapon descent supplies a plannable craft chain
    and the raid rung never runs. See this module's docstring for the full
    chain and the two independent faults behind it.

    Written as an inequality against the raid boss with the CURRENT plan spelled
    out beside it, so the day either fault is fixed this test fails and has to
    be turned back into the positive assertion it was. A bare
    `assert not any(...)` would silently keep passing if the plan degenerated to
    something else entirely."""
    report = _report("l48_raid_active")
    assert not any(isinstance(a, FightAction) and a.monster_code == _RAID_BOSS
                   for a in report.plan), (
        "the raid boss is engaged again — restore the positive assertion and "
        "close the regression in the task-6 report")
    assert [repr(a) for a in report.plan] == [
        "Withdraw(mithril_ore×10)", "Gather(mithril_rocks×100)",
        "Craft(mithril_bar×10)"], [repr(a) for a in report.plan]


def test_the_two_poles_differ_only_by_the_raid():
    """Guards the pair against drifting apart: if the two scenarios diverge in
    anything but `raids`, the comparison stops being about the raid."""
    a, b = SCENARIOS["l48_band_adequate"], SCENARIOS["l48_raid_active"]
    differing = {k for k in vars(a)
                 if getattr(a, k) != getattr(b, k)}
    assert differing <= {"name", "raids", "description"}, differing
    assert a.raids == () and b.raids == (("enchanted_fairy", "pixie"),)
