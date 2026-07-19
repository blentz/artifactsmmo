"""GamePlayer owns the per-cycle gear-focus aging ledger (arbiter
anti-starvation epic, Task 6): bump the chosen gear root each cycle it is
COMMITTED (fresh decide OR cache-hit reuse of a still-active plan), reset
the whole ledger on real progress (level-up or a successful craft of a
non-consumable EQUIPPABLE item)."""
from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers import ObtainItem, StrategyDecision
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.tiers.progression_tree_core import FOCUS_FLAT
from tests.test_ai.fixtures import make_state


def _bare_player() -> GamePlayer:
    return GamePlayer(character="hero")


def _obtain_item(code: str, slot: str) -> ObtainItem:
    return ObtainItem(code=code, quantity=1, slot=slot)


def _reach_char_level(level: int) -> ReachCharLevel:
    return ReachCharLevel(level=level)


def _decision_with_root(root, aged_pick: bool = False) -> StrategyDecision:
    return StrategyDecision(
        interrupt=None, chosen_root=root, chosen_step=root, desired_state={},
        aged_pick=aged_pick,
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


def test_seat_bump_gated_on_aged_pick_false_does_not_touch_seats():
    """Task 12 fix: `_bump_focus` bumps the FOCUS ledger every committed cycle
    but the d'Hondt SEAT only when `decision.aged_pick` is True (this decision's
    gear pick went through the interleave). A fast-path decision (aged_pick
    False) advances focus but leaves seats empty — even when the ledger already
    holds an aged entry, so a stale ledger cannot pollute the schedule."""
    p = _bare_player()
    # stale aged entry (e.g. a root that has since left the candidate set) —
    # a whole-ledger `any(> FOCUS_FLAT)` scan would falsely bump here.
    p._gear_focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT + 50}
    p._interleave_seats = {}
    p._bump_focus(_decision_with_root(_obtain_item("iron_ring", "ring2_slot"),
                                      aged_pick=False))
    assert p._gear_focus[("ring2_slot", "iron_ring")] == 1  # focus still bumps
    assert p._interleave_seats == {}  # but no seat consumed on a fast-path cycle


def test_seat_bump_advances_on_aged_pick():
    """Task 12: when the decision's gear pick came from the interleave
    (`aged_pick` True), `_bump_focus` advances one d'Hondt seat for the
    committed SLOT in lockstep with the focus bump."""
    p = _bare_player()
    p._gear_focus = {}
    p._interleave_seats = {}
    p._bump_focus(_decision_with_root(_obtain_item("iron_ring", "ring2_slot"),
                                      aged_pick=True))
    assert p._interleave_seats == {"ring2_slot": 1}  # keyed by the committed slot


def test_bump_focus_non_gear_root_is_noop():
    """Coverage: a non-gear committed root (ReachCharLevel — no slot/code)
    yields `_gear_root_key is None`, so `_bump_focus` early-returns without
    touching either ledger, regardless of `aged_pick`."""
    p = _bare_player()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 5}
    p._interleave_seats = {"helmet_slot": 2}
    p._bump_focus(_decision_with_root(_reach_char_level(20), aged_pick=True))
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 5}
    assert p._interleave_seats == {"helmet_slot": 2}


def test_reset_on_level_up_preserves_ledger_when_no_decision_yet():
    """No decide() has run this session yet (`_last_decision is None`, e.g. a
    session resumed from history before the first cycle) — the level-up
    branch has nothing to prune against, so it abstains and PRESERVES the
    ledger rather than guessing or clearing."""
    p = _bare_player()
    assert p._last_decision is None
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    p._interleave_seats = {"helmet_slot": 5}
    p._maybe_reset_focus(prev_level=14, cur_level=15, executed_action=None, outcome="ok")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}
    assert p._interleave_seats == {"helmet_slot": 5}


def test_reset_on_level_up_preserves_focus_of_live_chosen_root():
    """The bug: the bot levels up BY GRINDING the stuck monster the fall-off
    is decaying (e.g. wolves for wolf_ears). A level-up must not wipe that
    root's accumulated fall-off while it is still the live `chosen_root` —
    otherwise the anti-starvation fix resets every level-up, exactly the
    reported bug (robby 16->17->18, wolf_ears still dominates)."""
    p = _bare_player()
    root = _obtain_item("wolf_ears", "helmet_slot")
    p._last_decision = _decision_with_root(root)
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    p._interleave_seats = {"helmet_slot": 5}
    p._maybe_reset_focus(prev_level=16, cur_level=17, executed_action=None, outcome="ok")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}
    assert p._interleave_seats == {"helmet_slot": 5}


def test_reset_on_level_up_preserves_focus_of_live_fallback_root():
    """A root need not be the TOP `chosen_root` to be "live" — any of
    `decision.fallback_roots` (the arbiter's ranked alternatives) also
    counts, and its accumulated fall-off must survive the level-up too."""
    p = _bare_player()
    chosen = _obtain_item("iron_ring", "ring2_slot")
    fallback = _obtain_item("wolf_ears", "helmet_slot")
    decision = StrategyDecision(
        interrupt=None, chosen_root=chosen, chosen_step=chosen, desired_state={},
        fallback_roots=[fallback],
    )
    p._last_decision = decision
    p._gear_focus = {
        ("helmet_slot", "wolf_ears"): 40,
        ("ring2_slot", "iron_ring"): 3,
    }
    p._maybe_reset_focus(prev_level=16, cur_level=17, executed_action=None, outcome="ok")
    assert p._gear_focus == {
        ("helmet_slot", "wolf_ears"): 40,
        ("ring2_slot", "iron_ring"): 3,
    }


def test_reset_on_level_up_drops_focus_of_non_live_root():
    """A stale ledger entry for a root NOT among the current decision's live
    gear candidates (its slot was filled/superseded — e.g. equipping owned
    gear filled the slot with no reset) is PRUNED on level-up; it is no
    longer being pursued so its fall-off is meaningless going forward."""
    p = _bare_player()
    live_root = _obtain_item("iron_ring", "ring2_slot")
    p._last_decision = _decision_with_root(live_root)
    p._gear_focus = {
        ("helmet_slot", "wolf_ears"): 40,   # stale: not chosen_root/fallback_roots
        ("ring2_slot", "iron_ring"): 3,      # live: chosen_root
    }
    p._interleave_seats = {"helmet_slot": 5, "ring2_slot": 1}
    p._maybe_reset_focus(prev_level=16, cur_level=17, executed_action=None, outcome="ok")
    assert p._gear_focus == {("ring2_slot", "iron_ring"): 3}
    assert p._interleave_seats == {"ring2_slot": 1}  # pruned in lockstep with focus


def test_reset_on_level_up_prunes_seats_for_a_slot_with_no_live_root():
    """Interleave seats are keyed by SLOT, not (slot, code); a slot with no
    live root left in either `_gear_focus` or the decision's candidates is
    pruned from `_interleave_seats` even if the slot itself had no ledger
    entry (seats and focus are tracked independently but must stay in
    lockstep after a prune)."""
    p = _bare_player()
    live_root = _obtain_item("iron_ring", "ring2_slot")
    p._last_decision = _decision_with_root(live_root)
    p._gear_focus = {("ring2_slot", "iron_ring"): 3}
    p._interleave_seats = {"boots_slot": 9, "ring2_slot": 1}
    p._maybe_reset_focus(prev_level=16, cur_level=17, executed_action=None, outcome="ok")
    assert p._interleave_seats == {"ring2_slot": 1}


def test_reset_on_equippable_craft_clears_ledger():
    p = _player_with_items()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    p._interleave_seats = {"helmet_slot": 5}
    craft = _craft_action("iron_ring")  # iron_ring is a ring (equippable)
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
    assert p._gear_focus == {}
    assert p._interleave_seats == {}  # seats reset in lockstep with focus


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


def test_no_reset_when_game_data_unloaded():
    """A successful gear craft cannot classify the item (equippable vs
    consumable) without game data, so `_maybe_reset_focus` abstains rather
    than clear on an unclassifiable action — the bare player has no
    game_data yet (`self.game_data is None`)."""
    p = _bare_player()
    assert p.game_data is None
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("iron_ring")
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}


def test_no_reset_on_craft_of_item_without_stats():
    """A successful craft whose code has no item stats (unknown to the
    catalog) is unclassifiable, so the ledger is left intact rather than
    cleared."""
    p = _player_with_items()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("phantom_widget")  # not in the item catalog -> stats None
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
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


def test_focus_key_str_encodes_slot_and_code():
    assert GamePlayer._focus_key_str(("ring2_slot", "iron_ring")) == "ring2_slot|iron_ring"


def test_cycle_snapshot_carries_focus_fields_with_defaults():
    """CycleSnapshot's new fields are OPTIONAL — omitted, they default to
    empty/False so existing construction call sites (tests, offline tools)
    keep working unchanged."""
    snap = CycleSnapshot(
        cycle_index=0, timestamp="2026-07-18T00:00:00Z", character="hero",
        x=0, y=0, level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        selected_goal="X", action="Y", outcome="ok",
    )
    assert snap.gear_focus == {}
    assert snap.aged_pick is False
    assert snap.interleave_seats == {}


def test_cycle_snapshot_serializes_focus_fields_when_supplied():
    snap = CycleSnapshot(
        cycle_index=0, timestamp="2026-07-18T00:00:00Z", character="hero",
        x=0, y=0, level=17, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        selected_goal="X", action="Y", outcome="ok",
        gear_focus={"helmet_slot|wolf_ears": 40, "ring2_slot|iron_ring": 3},
        aged_pick=True,
        interleave_seats={"helmet_slot": 5},
    )
    dumped = snap.model_dump()
    assert dumped["gear_focus"] == {"helmet_slot|wolf_ears": 40, "ring2_slot|iron_ring": 3}
    assert dumped["aged_pick"] is True
    assert dumped["interleave_seats"] == {"helmet_slot": 5}


def test_notify_observer_populates_focus_fields_from_player_ledger():
    """`_notify_observer` (the real CycleSnapshot construction site) threads
    the player's runtime `_gear_focus`/`_interleave_seats` ledgers and the
    committed decision's `aged_pick` onto the snapshot, string-encoding the
    `(slot, code)` ledger keys."""
    calls: list[CycleSnapshot] = []
    player = GamePlayer(character="hero", cycle_observer=calls.append)
    player.state = make_state(level=17)
    player._gear_focus = {
        ("helmet_slot", "wolf_ears"): 40,
        ("ring2_slot", "iron_ring"): 3,
    }
    player._interleave_seats = {"helmet_slot": 5}
    root = _obtain_item("wolf_ears", "helmet_slot")
    player._last_decision = _decision_with_root(root, aged_pick=True)
    player._notify_observer(
        "FarmMonster(wolf)", "Fight(wolf)", "ok",
        goal_rank_trace=[],
    )
    assert len(calls) == 1
    snap = calls[0]
    assert snap.gear_focus == {"helmet_slot|wolf_ears": 40, "ring2_slot|iron_ring": 3}
    assert snap.aged_pick is True
    assert snap.interleave_seats == {"helmet_slot": 5}


def test_notify_observer_aged_pick_false_when_no_decision_yet():
    calls: list[CycleSnapshot] = []
    player = GamePlayer(character="hero", cycle_observer=calls.append)
    player.state = make_state(level=1)
    assert player._last_decision is None
    player._notify_observer("X", "Y", "ok", goal_rank_trace=[])
    assert calls[0].aged_pick is False
