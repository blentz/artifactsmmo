"""GearLatch: set on level-up or predicted-winnable fight loss; clear when gear is
level-appropriate; monotone (stays set until clear holds)."""
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_latch import GearLatch
from tests.test_ai.fixtures import make_state


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
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=_gd_with_boots())
    assert latch.active is True


def test_sets_on_fight_loss():
    latch = GearLatch()
    latch.update(prev_level=4, state=make_state(level=4), last_outcome="error:fight_lost",
                 game_data=_gd_with_boots())
    assert latch.active is True


def test_clears_when_no_craftable_upgrade():
    latch = GearLatch()
    empty_gd = GameData()
    empty_gd._item_stats = {}
    empty_gd._crafting_recipes = {}
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=empty_gd)
    assert latch.active is False  # set by level-up but immediately cleared: nothing to craft


def test_monotone_stays_set_until_clear():
    latch = GearLatch()
    gd = _gd_with_boots()
    latch.update(prev_level=4, state=make_state(level=5), last_outcome="ok", game_data=gd)
    assert latch.active is True
    # next cycle, no level-up, no loss, upgrade still available → stays set
    latch.update(prev_level=5, state=make_state(level=5), last_outcome="ok", game_data=gd)
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
    but the gear is still what stands between it and its task."""
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "has_combat_deficit", lambda s, g: True)
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), None, GameData())

    assert latch.active is True


def test_no_deficit_and_no_loss_leaves_the_latch_alone(monkeypatch) -> None:
    """The fact must not arm it unconditionally — a character with a winnable
    task has no gear emergency."""
    import artifactsmmo_cli.ai.gear_latch as mod
    monkeypatch.setattr(mod, "has_combat_deficit", lambda s, g: False)
    monkeypatch.setattr(mod, "has_craftable_upgrade_any_slot", lambda s, g: True)
    latch = GearLatch()

    latch.update(5, make_state(level=5), None, GameData())

    assert latch.active is False
