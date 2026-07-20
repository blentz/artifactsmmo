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

def test_l48_without_a_raid_cannot_plan():
    """The wall. No raid window, no permanent L47-50 monster -> the arbiter has
    nothing to try, and Wait is the honest outcome.

    Asserted POSITIVELY (goals_tried is empty) rather than by exempting this
    scenario from the bounded-search net: a scenario that provably has no work
    is a fact worth pinning, not an exception worth hiding."""
    report = _report("l48_band_adequate")
    assert report.goals_tried == [], (
        "l48_band_adequate is the no-work pole: if the arbiter found something "
        "to try, the wall has moved and this pair needs re-deriving"
    )
    assert repr(report.selected_goal) == "Wait", repr(report.selected_goal)


def test_l48_without_a_raid_emits_no_raid_fight():
    """Non-vacuity for the pair: the boss is absent because the WINDOW is shut,
    not because the fixture lacks the boss."""
    report = _report("l48_band_adequate")
    assert not any(isinstance(a, FightAction) and a.monster_code == _RAID_BOSS
                   for a in report.plan)


# ─── positive pole: raid open, participation is plannable ────────────────────

def test_l48_with_an_active_raid_can_plan():
    """Same state, one difference: the raid window is open. The arbiter now has
    work, so the wall is a property of the world rather than a dead end."""
    report = _report("l48_raid_active")
    assert report.goals_tried, (
        "an open raid window must give the arbiter something to try; if this is "
        "empty the raid fight never became selectable"
    )
    assert repr(report.selected_goal) != "Wait", repr(report.selected_goal)


def test_l48_raid_plan_engages_the_boss():
    """The plan must actually route to the raid boss -- goals_tried being
    non-empty would otherwise be satisfied by any unrelated work."""
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
    assert a.raids == () and b.raids == ("enchanted_fairy",)
