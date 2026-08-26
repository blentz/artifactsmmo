"""RegearEdge: set on level-up or predicted-winnable fight loss; clear when gear is
level-appropriate; monotone (stays set until clear holds)."""
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.regear_edge import RegearEdge
from artifactsmmo_cli.ai.task_horizon import (
    HORIZON_GEAR,
    TaskHorizon,
)
from tests.test_ai.fixtures import make_state

_GEAR_CLOSES = TaskHorizon(monster="pig", verdict=HORIZON_GEAR,
                           gear_target=("iron_sword", "weapon_slot"))
"""A held task the character loses AND a gear chain that closes the fight.

The latch's standing arm reads the VERDICT, not the bare "this fight is lost"
fact it used to read, so a stub has to name which of the three answers it is
standing in for. `_GEAR_CLOSES` is the only one that arms it — see
`test_a_futile_deficit_does_not_arm_the_latch`."""


def _gd_with_boots():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    return gd


def test_starts_inactive():
    assert RegearEdge().active is False


def test_sets_on_level_up():
    latch = RegearEdge()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok",
                 game_data=_gd_with_boots())
    assert latch.active is True


def test_sets_on_fight_loss():
    latch = RegearEdge()
    latch.update(prev_level=4, state=make_state(level=4), last_outcome="error:fight_lost",
                 game_data=_gd_with_boots())
    assert latch.active is True


def test_clears_when_no_craftable_upgrade():
    latch = RegearEdge()
    empty_gd = GameData()
    empty_gd._item_stats = {}
    empty_gd._crafting_recipes = {}
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok",
                 game_data=empty_gd)
    assert latch.active is False  # set by level-up but immediately cleared: nothing to craft


def test_monotone_stays_set_until_clear():
    latch = RegearEdge()
    gd = _gd_with_boots()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok",
                 game_data=gd)
    assert latch.active is True
    # next cycle, no level-up, no loss, upgrade still available → stays set
    latch.update(prev_level=5, state=make_state(level=5), last_outcome="ok",
                 game_data=gd)
    assert latch.active is True


# ---------------------------------------------------------------------------
# The latch is FACT-driven, not event-driven.
#
# It armed on "a fight was just lost". Closing the tier-1 bypass (6a) stopped the
# bot taking fights it loses — which removed the very event the CURE depended on.
# Measured live 40 minutes after that shipped: C3P0 held an unwinnable pig task,
# `gear: {"adequate": false}`, a deficit target of `king_slime_sword` available,
# a craftable upgrade available — and the latch INACTIVE, `gear_review` firing in
# 7 of 30 cycles instead of all 30, `goal_rank` empty, four consecutive `Wait`s.
#
# Same error class as the countdown this epic replaced, one layer up: an EVENT
# standing in for a FACT. A deficit that exists is the reason to review gear,
# whether or not we just walked into it.
# ---------------------------------------------------------------------------






def test_a_lost_fight_arms_the_latch_even_when_another_fight_is_winnable(
        monkeypatch) -> None:
    """The loss->upgrade link is an EDGE and must survive this gate.

    Gating the edge arms on `winnable_alternative` too would switch the link off
    for every character that has anything at all to fight — which is every
    character that ever loses one.
    """
    import artifactsmmo_cli.ai.regear_edge as mod
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: None)
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = RegearEdge()

    latch.update(5, make_state(level=5), "error:fight_lost", GameData())

    assert latch.active is True


# ---------------------------------------------------------------------------
# ...AND ONLY WHEN GEAR IS WHAT STANDS IN THE WAY.
#
# The fact-arm above reads "this fight is lost". That is strictly broader than
# the latch's own contract ("prioritizes the gear chain WHILE GEAR IS WHAT STANDS
# IN THE WAY"), and after `e6a2e37c` taught `deficit_upgrade_target` to honour
# `closes` the difference became the majority case: measured over the offline
# corpus' derive_combat_stats characters, 1,375 of 1,493 losing (character,
# monster) pairs have NO chain that closes the fight, and every one of them armed
# this latch. GEAR_REVIEW then preempts the objective step and falls through to
# the monster-blind value scan — `iron_boots`, ten hours.
#
# USER (2026-08-25): "cancel tasks that we can't meet through gear upgrade, or
# (level-up by exactly 1 level and gear upgrade). anything beyond a 1-level
# horizon is too far out to be a reasonable near-term planning target."
# ---------------------------------------------------------------------------



