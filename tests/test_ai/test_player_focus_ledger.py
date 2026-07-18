"""GamePlayer owns the per-cycle gear-focus aging ledger (arbiter
anti-starvation epic, Task 6): bump the chosen gear root each cycle it is
COMMITTED (fresh decide OR cache-hit reuse of a still-active plan), reset
the whole ledger on real progress (level-up or a successful craft of a
non-consumable EQUIPPABLE item)."""
from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers import ObtainItem, StrategyDecision
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from tests.test_ai.fixtures import make_state


def _bare_player() -> GamePlayer:
    return GamePlayer(character="hero")


def _obtain_item(code: str, slot: str) -> ObtainItem:
    return ObtainItem(code=code, quantity=1, slot=slot)


def _reach_char_level(level: int) -> ReachCharLevel:
    return ReachCharLevel(level=level)


def _decision_with_root(root: ObtainItem) -> StrategyDecision:
    return StrategyDecision(
        interrupt=None, chosen_root=root, chosen_step=root, desired_state={},
    )


def _craft_action(code: str) -> CraftAction:
    return CraftAction(code=code, quantity=1, workshop_location=(3, 0))


def _game_data_with_items() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_ring": ItemStats(code="iron_ring", level=10, type_="ring"),
        "small_health_potion": ItemStats(
            code="small_health_potion", level=1, type_="utility"),
    }
    return gd


def _player_with_items() -> GamePlayer:
    p = _bare_player()
    p.game_data = _game_data_with_items()
    return p


def test_gear_root_key_extracts_slot_code():
    key = GamePlayer._gear_root_key(_obtain_item("iron_ring", "ring2_slot"))
    assert key == ("ring2_slot", "iron_ring")


def test_gear_root_key_none_for_non_gear_root():
    assert GamePlayer._gear_root_key(_reach_char_level(20)) is None


def test_bump_increments_chosen_gear_root():
    p = _bare_player()
    p._gear_focus = {}
    p._bump_focus(_decision_with_root(_obtain_item("wolf_ears", "helmet_slot")))
    p._bump_focus(_decision_with_root(_obtain_item("wolf_ears", "helmet_slot")))
    assert p._gear_focus[("helmet_slot", "wolf_ears")] == 2


def test_reset_on_level_up_clears_ledger():
    p = _bare_player()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    p._maybe_reset_focus(prev_level=14, cur_level=15, executed_action=None, outcome="ok")
    assert p._gear_focus == {}


def test_reset_on_equippable_craft_clears_ledger():
    p = _player_with_items()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("iron_ring")  # iron_ring is a ring (equippable)
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
    assert p._gear_focus == {}


def test_no_reset_on_consumable_craft():
    p = _player_with_items()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("small_health_potion")  # utility/consumable -> NOT a reset
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}


def test_no_reset_on_failed_craft():
    p = _player_with_items()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("iron_ring")
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="error")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}


@dataclass
class _FakeGoal:
    """Minimal Goal stand-in for `_plan_or_reuse` (its collaborator
    `_decide_band` is stubbed below, per the pattern already used in
    tests/test_ai/test_plan_or_reuse.py — a real fixture in shape, not a
    mock of the unit under test)."""

    def is_satisfied(self, state):
        return False

    def __repr__(self):
        return "FakeGoal()"


@dataclass
class _FakeAct:
    def is_applicable(self, state, game_data):
        return True

    def __repr__(self):
        return "FakeAct()"


def test_cache_hit_cycle_still_bumps_committed_gear_root():
    """Fix 2: a cache-hit cycle (should_replan=False, so `_decide_band`/
    `decide()` is NOT called) is still a cycle the cached plan's gear root
    is committed to and being pursued. `_plan_or_reuse` is the real seam
    that owns the fresh-decide/cache-hit branch — drive it across three
    calls (1 replan + 2 cache-hit reuses of the same 3-step plan) and assert
    the ledger ages every cycle, not just on the one that actually
    replanned."""
    root = _obtain_item("wolf_ears", "helmet_slot")
    decision = _decision_with_root(root)
    goal = _FakeGoal()
    plan = [_FakeAct(), _FakeAct(), _FakeAct()]
    player = _bare_player()
    player.dry_run = True
    player._gear_latch._active = False

    def _fake_decide_band(state, game_data, actions, ctx_combat_monster):
        # Mirrors what the real `_decide_band` does to `_last_decision`
        # before returning — the collaborator being stubbed, not the
        # `_plan_or_reuse`/`_bump_committed_focus` logic under test.
        player._last_decision = decision
        return goal, list(plan), [{"goal": repr(goal)}]

    player._decide_band = _fake_decide_band  # type: ignore[attr-defined]
    state = make_state()
    key = ("helmet_slot", "wolf_ears")

    player._plan_or_reuse(state, None, [], None)  # cycle 1: fresh decide
    assert player._gear_focus[key] == 1

    player._plan_cache.advance()
    player._last_outcome = "ok"
    player._plan_or_reuse(state, None, [], None)  # cycle 2: cache hit
    assert player._gear_focus[key] == 2

    player._plan_cache.advance()
    player._plan_or_reuse(state, None, [], None)  # cycle 3: cache hit
    assert player._gear_focus[key] == 3
