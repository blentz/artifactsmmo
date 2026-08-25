"""GearLatch: set on level-up or predicted-winnable fight loss; clear when gear is
level-appropriate; monotone (stays set until clear holds)."""
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_latch import GearLatch
from artifactsmmo_cli.ai.task_horizon import (
    HORIZON_GEAR,
    HORIZON_LEVEL_UP,
    HORIZON_OUT_OF_REACH,
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
    assert GearLatch().active is False


def test_sets_on_level_up():
    latch = GearLatch()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok",
                 game_data=_gd_with_boots(), winnable_alternative=True)
    assert latch.active is True


def test_sets_on_fight_loss():
    latch = GearLatch()
    latch.update(prev_level=4, state=make_state(level=4), last_outcome="error:fight_lost",
                 game_data=_gd_with_boots(), winnable_alternative=True)
    assert latch.active is True


def test_clears_when_no_craftable_upgrade():
    latch = GearLatch()
    empty_gd = GameData()
    empty_gd._item_stats = {}
    empty_gd._crafting_recipes = {}
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok",
                 game_data=empty_gd, winnable_alternative=True)
    assert latch.active is False  # set by level-up but immediately cleared: nothing to craft


def test_monotone_stays_set_until_clear():
    latch = GearLatch()
    gd = _gd_with_boots()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok",
                 game_data=gd, winnable_alternative=True)
    assert latch.active is True
    # next cycle, no level-up, no loss, upgrade still available → stays set
    latch.update(prev_level=5, state=make_state(level=5), last_outcome="ok",
                 game_data=gd, winnable_alternative=True)
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


def test_an_unwinnable_task_arms_the_latch_without_a_loss(monkeypatch) -> None:
    """C3P0's live shape: no loss this cycle (because the fight is refused now),
    no OTHER monster worth fighting either, and the gear is still what stands
    between it and its task."""
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: _GEAR_CLOSES)
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), None, GameData(), winnable_alternative=False)

    assert latch.active is True


def test_no_deficit_and_no_loss_leaves_the_latch_alone(monkeypatch) -> None:
    """The fact must not arm it unconditionally — a character with a winnable
    task has no gear emergency."""
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: None)
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), None, GameData(), winnable_alternative=False)

    assert latch.active is False


# ---------------------------------------------------------------------------
# The deficit is a reason to review gear only when it BLOCKS.
#
# The fact-arm above was written for C3P0's shape — an unwinnable task AND
# nothing else worth fighting, four consecutive `Wait`s with an empty
# `goal_rank`. It shipped gated on the deficit alone, which is a strictly
# broader condition, and the difference is not academic: GEAR_REVIEW is a GUARD,
# so it preempts the objective step outright (`arbiter_select.select_pure`
# returns the first candidate that plans, and the guard's goal always plans).
#
# Live R2D2 2026-08-21/22: held `monsters/pig 0/137` at combat_margin -2 for 38
# hours. The deficit was real, so the latch re-armed every cycle, so GEAR_REVIEW
# preempted `GrindCharacterXP(skeleton)` — winnable, 37 xp/kill — for 981
# consecutive cycles. Character XP frozen 31.6 hours at 1861/8200; 808 of those
# cycles were `LevelSkill(woodcutting->20)` chasing a weaponcrafting-20 whip.
# No level-up and no `error:fight_lost` occurred in the whole run, so the EDGE
# latch was never set: the fact-arm was the sole cause.
#
# USER: "not being able to win against a pig is fine. but that shouldn't block
# us from fighting other, winnable monsters."
# ---------------------------------------------------------------------------


def test_an_unwinnable_task_does_not_arm_the_latch_when_another_fight_is_winnable(
        monkeypatch) -> None:
    """R2D2's live shape: the pig is unwinnable, the skeleton is not."""
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: _GEAR_CLOSES)
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), None, GameData(), winnable_alternative=True)

    assert latch.active is False


def test_the_deficit_arm_releases_when_a_winnable_fight_appears(monkeypatch) -> None:
    """The deficit is a STANDING condition, so it must disarm as well as arm.

    A sticky deficit-arm would leave a character that is already frozen frozen —
    R2D2 held its latch across 981 cycles with no edge to re-trigger it, so a fix
    that only stops the RE-arming would need a restart to take effect.
    """
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: _GEAR_CLOSES)
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), None, GameData(), winnable_alternative=False)
    assert latch.active is True

    latch.update(5, make_state(level=5), None, GameData(), winnable_alternative=True)

    assert latch.active is False


def test_a_lost_fight_arms_the_latch_even_when_another_fight_is_winnable(
        monkeypatch) -> None:
    """The loss->upgrade link is an EDGE and must survive this gate.

    Gating the edge arms on `winnable_alternative` too would switch the link off
    for every character that has anything at all to fight — which is every
    character that ever loses one.
    """
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: None)
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), "error:fight_lost", GameData(),
                 winnable_alternative=True)

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


def test_a_futile_deficit_does_not_arm_the_latch(monkeypatch) -> None:
    """`l32_held_task_open`'s live shape: the lich is unwinnable and NOTHING in
    the catalogue closes it. Reviewing gear for that fight is the ten-hour
    `iron_boots` failure with the monster scoped in; the latch must stay off so
    the cancel rung — which sits above the objective step already — is reached."""
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: TaskHorizon(
        monster="lich", verdict=HORIZON_OUT_OF_REACH, gear_target=None))
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), None, GameData(), winnable_alternative=False)

    assert latch.active is False


def test_a_level_up_verdict_does_not_arm_the_standing_arm(monkeypatch) -> None:
    """The other conjunct decides this one, not a preference.

    The standing arm only reaches here when `winnable_alternative` is False — no
    monster worth fighting — so a LEVEL_UP verdict reached HERE has nothing to
    fight for the level, and `map_guard`'s LEVEL_UP arm would map to a goal whose
    `relevant_actions` contain no beatable monster. That verdict is served from
    the EDGE arm instead (see `test_the_gear_review_guard_takes_the_level`)."""
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: TaskHorizon(
        monster="mushmush", verdict=HORIZON_LEVEL_UP, gear_target=None))
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), None, GameData(), winnable_alternative=False)

    assert latch.active is False
