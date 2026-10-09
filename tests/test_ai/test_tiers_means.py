"""Tests for the means bands (collect-reward + discretionary)."""



from artifactsmmo_cli.ai.accumulation_sell import sell_targets
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.task_accept import accept_due
from artifactsmmo_cli.ai.task_decision import PURSUE, task_decision
from artifactsmmo_cli.ai.task_worth import held_task_cancel_due
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import (
    COLLECT_REWARD_ORDER,
    DISCRETIONARY_ORDER,
    INTERRUPT_MEANS,
    MeansKind,
    active_means,
    means_fires,
)
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _ctx(**kw) -> SelectionContext:
    # `draw_owed=True`: ACCEPT_TASK's gate since its promotion above the
    # objective step (S-051). Before the gate it fired on `not task_code` alone,
    # so this is the default these fixtures already assumed.
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                draw_owed=True)
    base.update(kw)
    return SelectionContext(**base)


def _gd() -> GameData:
    return GameData()


def _fires(kind: MeansKind, state, game_data, ctx: SelectionContext) -> bool:
    return means_fires(kind, state, game_data, None, ctx)


def test_accept_task_is_due_when_a_draw_is_owed():
    """It left the discretionary band on 2026-08-19 (S-051): below the objective
    step it was unreachable, and the fleet held a task in 0 of 63,310 cycles."""
    state = make_state(task_code=None)
    assert accept_due(state, _ctx()) is True


def test_accept_task_is_quiet_when_no_draw_is_owed():
    """The no-immediate-redraw gate: an ungated redraw would spin between
    accept and discard at a coin a cycle."""
    state = make_state(task_code=None)
    assert accept_due(state, _ctx(draw_owed=False)) is False


def test_accept_task_does_not_wait_on_target_gear():
    """USER 2026-10-06: no gear-chain deferral. Target gear owned-unequipped,
    or craftable at the current skill, no longer holds the draw back — live,
    a "craftable" `hard_leather_boots` nobody worked kept three characters
    taskless for over a day."""
    state = make_state(task_code=None, inventory={"copper_dagger": 1})
    ctx = _ctx(target_gear=frozenset({"copper_dagger", "iron_sword"}))
    assert accept_due(state, ctx) is True


def test_claim_pending_fires_with_pending_items():
    state = make_state(pending_items=(("id1", "copper_ore"),))
    collect, _ = active_means(state, GameData(), None, _ctx())
    assert MeansKind.CLAIM_PENDING in collect


def _sells_copper_ore() -> GameData:
    gd = GameData()
    gd._npc_sell_prices = {"merchant": {"copper_ore": 5}}
    gd._npc_locations = {"merchant": (1, 2)}   # located, and non-event => tradeable now
    return gd


def test_sell_pressured_vs_idle_mutually_exclusive_on_bag():
    """The two sell rungs split the fill axis, and BOTH need a hoard the goal
    would actually sell — so the idle state carries the same 18 copies at a
    roomier cap rather than a trickle."""
    gd = _sells_copper_ore()
    pressured = make_state(inventory={"copper_ore": 18}, inventory_max=20, task_code="t",
                           task_total=1, task_progress=0)  # 0.90 fill; task held so ACCEPT_TASK off
    idle = make_state(inventory={"copper_ore": 18}, inventory_max=200, task_code="t",
                      task_total=1, task_progress=0)        # 0.09 fill, same hoard
    pc, pd = active_means(pressured, gd, None, _ctx())
    ic, idd = active_means(idle, gd, None, _ctx())
    assert MeansKind.SELL_PRESSURED in pc
    assert MeansKind.SELL_IDLE not in pd          # exclusivity: not both at high fill
    assert MeansKind.SELL_IDLE in idd
    assert MeansKind.SELL_PRESSURED not in ic     # exclusivity: not both at low fill


def test_a_sell_rung_still_fires_below_its_goal_ratio_gate():
    """PINS A KNOWN RESIDUAL, not a desired behaviour.

    Two copies are below `sellable_accumulation`'s ratio gate, so SELL_IDLE's
    goal would report itself satisfied — yet the rung fires, because the shared
    predicate is licence-blind on purpose. All three sell rungs map to goals with
    DIFFERENT licences (idle and pressured to `relief=False`, the guard to
    `relief=True` under `deposit_context`), and one predicate cannot be all of
    them. Splitting it needs a SECOND opaque Bool in the Lean ladder state, whose
    33-slot vector `cycle_step_d` reuses by index for the composed liveness
    capstone.

    Harmless in the selection — a satisfied candidate is skipped — and it is the
    record that suffers: a fired-but-unselectable rung is indistinguishable from
    one the band suppressed, which is the measurement the band epic turns on."""
    gd = _sells_copper_ore()
    trickle = make_state(inventory={"copper_ore": 2}, inventory_max=200,
                         task_code="t", task_total=1, task_progress=0)
    _, discretionary = active_means(trickle, gd, None, _ctx())
    assert MeansKind.SELL_IDLE in discretionary
    # What the goal would actually do with it: nothing.
    assert sell_targets(trickle, gd, _ctx()) == {}


def test_a_sell_rung_does_not_fire_when_no_buyer_can_trade_now():
    """Same hoard, buyer behind a SHUT event window. Every NPC in the game that
    buys items is an event NPC, so this is the usual case and not an edge one."""
    gd = _sells_copper_ore()
    gd.world.npc_event_codes["merchant"] = "merchant_visit"
    hoard = make_state(inventory={"copper_ore": 18}, inventory_max=200,
                       task_code="t", task_total=1, task_progress=0,
                       active_events={})
    _, discretionary = active_means(hoard, gd, None, _ctx())
    assert MeansKind.SELL_IDLE not in discretionary


def test_band_order_matches_declared_order():
    state = make_state(task_code=None, pending_items=(("id", "x"),))
    collect, discretionary = active_means(state, GameData(), None, _ctx())
    assert collect == [m for m in COLLECT_REWARD_ORDER if m in collect]
    assert discretionary == [m for m in DISCRETIONARY_ORDER if m in discretionary]


# ---------------------------------------------------------------------------
# The held task's CANCEL verdict (`task_worth.held_task_cancel_due`): the
# TASK_CANCEL rung's question until Phase 5-2c-iii-c-2 #5 retired the rung into
# the task objective's step. Its S-048 arm (no XP, no other reason) and its
# PIVOT arm are now the worth verdict; the coin gate and the horizon carried over.
# ---------------------------------------------------------------------------


def test_task_cancel_discards_a_task_that_advances_nothing():
    """A grey draw with no gold or drop reason is worthless and goes back, and
    the verdict needs no learning store to know it."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    gd._task_gold_rewards = {"chicken": 150}
    state = make_state(level=30, task_code="chicken", task_type="monsters",
                       task_total=10, task_progress=0,
                       inventory={"tasks_coin": 1})
    assert held_task_cancel_due(state, gd, _ctx(), None) is True


def test_a_paying_task_is_not_discarded():
    """The negative arm: the chicken pays XP at level 1, and character level is
    demanded (c-2 #5: the XP must be DAG-demanded), so it is kept.

    `attack` is REQUIRED here. A character's base combat stats are zero (the
    server reports totals = base 0 + gear), so a state with no attack loses to
    EVERY monster — and since the one-level horizon (`ai/task_horizon.py`) reads
    the fight rather than the monster's level, a zero-attack fixture reads OUT OF
    REACH and would be discarded for a reason that has nothing to do with what
    the test is asserting."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    gd._task_gold_rewards = {"chicken": 150}
    state = make_state(level=1, attack={"earth": 5}, task_code="chicken",
                       task_type="monsters",
                       task_total=10, task_progress=0,
                       inventory={"tasks_coin": 1})
    assert held_task_cancel_due(state, gd, _ctx(level_demanded=True), None) is False


def test_without_a_coin_a_grey_task_is_worked_not_discarded():
    """S-052, the USER's resolution of the bootstrap: discarding costs a coin and
    coins come only from COMPLETING tasks, so the first draw of a character's life
    is undiscardable. It is worked. `TaskCancelAction.is_applicable` spends a
    POCKET coin."""
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)
    gd._task_gold_rewards = {"chicken": 150}
    grey = dict(level=30, task_code="chicken", task_type="monsters",
                task_total=10, task_progress=0)
    assert held_task_cancel_due(make_state(**grey, inventory={}), gd, _ctx(), None) is False
    # A BANKED coin is not spendable at the taskmaster either.
    assert held_task_cancel_due(
        make_state(**grey, inventory={}, bank_items={"tasks_coin": 9}),
        gd, _ctx(), None) is False


def test_accept_task_not_in_discretionary_when_task_held():
    state = make_state(task_code="cyclops", task_type="monsters", task_total=5, task_progress=3)
    assert accept_due(state, _ctx()) is False


def test_bank_expand_fires_when_conditions_met():
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    # 19/20 = 0.95 fill, gold - cost >= ctx reserve (default 0), accessible
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=200)
    collect, _ = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND in collect


def test_bank_expand_absent_when_bank_not_accessible():
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=100)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=False))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_absent_when_capacity_zero():
    gd = GameData()
    # _bank_capacity defaults to 0
    state = make_state(bank_items={"iron_ore": 1}, gold=100)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_absent_when_fill_below_threshold():
    gd = GameData()
    gd._bank_capacity = 100
    gd._next_expansion_cost = 10
    # Only 5 items in a 100-slot bank → 5% fill, far below 95%
    state = make_state(bank_items={f"item{i}": 1 for i in range(5)}, gold=100)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_absent_when_insufficient_gold():
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 1000
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=5)
    _, discretionary = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_absent_when_purchase_would_break_gold_reserve():
    """The means guard must apply the SAME reserve gate as the proven
    should_expand_bank core the goal uses (gold - cost >= reserve_floor).
    The old guard fired on bare gold >= cost — the exact SAFETY-HOLE the
    core closed — admitting a candidate the goal then values 0 (drift
    flagged 2026-07-06). The player threads reserve_floor(state, gd, None)
    as ctx.gold_reserve: gold 100, cost 10, reserve 100 → 90 < 100 → no
    fire."""
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=100)
    _, discretionary = active_means(
        state, gd, None, _ctx(bank_accessible=True, gold_reserve=100))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_fires_when_reserve_survives_purchase():
    """gold - cost >= reserve (200 - 10 = 190 >= 100) → fires."""
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=200)
    collect, _ = active_means(
        state, gd, None, _ctx(bank_accessible=True, gold_reserve=100))
    assert MeansKind.BANK_EXPAND in collect


def test_bank_expand_fill_gate_is_an_exact_integer_boundary():
    """The gate is `items * DEN >= capacity * NUM`, decided on the exact
    integers, and the boundary is a TIE-fires `>=`.

    29/39 is 74.36% and 30/39 is 76.92%, straddling the 75% trigger: the exact
    compare is 2900 < 2925 then 3000 >= 2925.

    HONEST NOTE ON WHAT THIS NO LONGER SHOWS. At the old 95% trigger this test
    used 37/39 = 0.9487, a ratio a float division can round up across 0.95 —
    so it pinned exact-vs-float, not merely the boundary. That premise does not
    survive the 2026-09-13 retrigger: 3/4 is exactly representable in binary, so
    a float-divergent pair near 75% needs a denominator above ~4.5e15 and no
    realistic state can exhibit one. The test now pins the BOUNDARY and its
    tie-inclusive `>=`; the no-float property is still carried by
    `should_expand_bank`'s own differential and its Lean model."""
    gd = GameData()
    gd._bank_capacity = 39
    gd._next_expansion_cost = 10
    below = make_state(bank_items={f"item{i}": 1 for i in range(29)}, gold=500)
    collect_below, _ = active_means(below, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND not in collect_below
    at = make_state(bank_items={f"item{i}": 1 for i in range(30)}, gold=500)
    collect_at, _ = active_means(at, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND in collect_at


def test_bank_expand_fill_gate_fires_on_an_exact_tie():
    """`>=`, not `>`: 3/4 hits the 75/100 trigger exactly and must fire."""
    gd = GameData()
    gd._bank_capacity = 4
    gd._next_expansion_cost = 10
    state = make_state(bank_items={f"item{i}": 1 for i in range(3)}, gold=500)
    collect, _ = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND in collect


# ---------------------------------------------------------------------------
# THE ONE-LEVEL PLANNING HORIZON (USER 2026-08-25) in the held task's cancel
# verdict (the TASK_CANCEL rung's until Phase 5-2c-iii-c-2 #5).
#
# The old rung's combat arm was `task_decision(...) == PIVOT`, and `task_decision`'s
# combat arm is `task_feasibility`'s LEVEL PROXY: a monster more than
# MONSTER_LEVEL_MARGIN (2) levels above the character. A level proxy is the wrong
# question in both directions — measured on the scenario corpus,
# `l32_held_task_open` holds a level-30 `lich` at character level 32 (IN BAND, so
# PURSUE) that nothing in the catalogue can beat, while a high-level monster the
# character's gear already beats would be discarded.
#
# `ai/task_horizon.py` asks the fight instead:
#   gear closes it             -> keep it, build the gear
#   one level + gear closes it -> keep it, take the level
#   neither                    -> out of reach; discard it if a coin is in the
#                                 pocket, otherwise carry it INERT and do other
#                                 work.
# ---------------------------------------------------------------------------


def _horizon_world() -> GameData:
    """A catalogue with ONE monster and NO equippable items.

    No items means no chain can ever close a fight, which is what makes the
    out-of-reach arm reachable from a hand-built world at all."""
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._monster_level = {"rat": 1}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"rat": 60}
    gd._monster_attack = {"rat": {"earth": 6}}
    gd._monster_resistance = {"rat": {}}
    gd._task_gold_rewards = {"rat": 150}
    return gd


def test_task_cancel_fires_for_a_fight_outside_the_one_level_horizon():
    """Clause 3, and it needs NO learning store.

    Whether a fight is winnable is a fact about game data and the character —
    the same reason S-048's grey arm above is asked without `history`. The old
    combat arm required one (`history is not None and task_decision(...)`), so a
    fresh character could never discard an unwinnable draw at all."""
    gd = _horizon_world()
    state = make_state(level=1, hp=20, max_hp=20, attack={"earth": 1},
                       task_code="rat", task_type="monsters",
                       task_total=10, task_progress=0,
                       inventory={"tasks_coin": 1})
    assert held_task_cancel_due(state, gd, _ctx(), None) is True


def test_an_out_of_horizon_task_is_carried_inert_without_a_coin():
    """S-052 is NOT broken by the horizon: the coin gate is asked first.

    USER (2026-08-25): "It is a known condition that Tasks might be uncancelable
    until we get a coin. Tasks can remain inert until that condition is met." So
    the coinless character does not cancel, and does not gear-review for the
    fight either (`RegearEdge`); it carries the task and does other work. USER
    again: "we can attempt cancel_task iff we have a task_coin, but if we have
    no coins we shouldn't waste the cycles" — a verdict that held here would put
    a goal in front of the planner that `TaskCancelAction.is_applicable` refuses,
    which is a planning budget spent to rediscover what the bag already said."""
    gd = _horizon_world()
    bare = dict(level=1, hp=20, max_hp=20, attack={"earth": 1},
                task_code="rat", task_type="monsters",
                task_total=10, task_progress=0)
    assert held_task_cancel_due(make_state(**bare, inventory={}), gd, _ctx(), None) is False
    # A BANKED coin cannot be spent at the taskmaster either.
    assert held_task_cancel_due(
        make_state(**bare, inventory={}, bank_items={"tasks_coin": 9}),
        gd, _ctx(), None) is False


def test_a_fight_gear_closes_is_kept_however_far_above_the_character_it_is():
    """Clause 1 from the verdict's side, and the direction the LEVEL PROXY got wrong.

    The rat is nine levels above this character, so `task_feasibility` reports a
    combat requirement and `task_decision` answers PIVOT — the old arm discarded
    it. A `bronze_sword` in the catalogue closes the fight, so the horizon keeps
    the task and the gear chain is what gets built."""
    gd = _horizon_world()
    gd._monster_level = {"rat": 10}
    gd._item_stats = {"bronze_sword": ItemStats(
        code="bronze_sword", level=1, type_="weapon", attack={"earth": 40})}
    state = make_state(level=1, hp=200, max_hp=200, attack={"earth": 1},
                       task_code="rat", task_type="monsters",
                       task_total=10, task_progress=0,
                       inventory={"tasks_coin": 1})
    assert held_task_cancel_due(state, gd, _ctx(level_demanded=True), None) is False


def test_the_verdict_and_the_goal_it_emits_report_the_same_answer():
    """ONE PRODUCER OF THE CANCEL REASON.

    The retired TASK_CANCEL rung had three independent reasons to fire — S-048,
    the one-level horizon, and `task_decision == PIVOT` for the items arm — and
    `TaskCancelGoal.value` used to re-derive only the third. So a rung that fired
    for either of the first two emitted a goal reporting `0.0`, which is what the
    arbiter records as the trace's `goal_rank` and what both TUI consumers of
    that panel filter out (`strategy_driver.py:820`, written when that panel last
    rendered empty for exactly this reason).

    Measured on the offline corpus before this was unified: three of three cells
    where the arbiter SELECTED `TaskCancel` (`l32_held_task_open` on the horizon
    arm, `l32_held_task_closable` and `l32_held_task_workable` on S-048) reported
    a value of 0.0.

    The state below is the horizon arm's own witness — a level-1 character
    holding a level-1 `rat` task in a world with no items, so `task_decision`
    answers PURSUE (the monster is IN BAND) while the horizon answers
    out-of-reach. It is the exact shape `l32_held_task_open` has live."""
    gd = _horizon_world()
    state = make_state(level=1, hp=20, max_hp=20, attack={"earth": 1},
                       task_code="rat", task_type="monsters",
                       task_total=10, task_progress=0,
                       inventory={"tasks_coin": 1})
    assert task_decision(state, gd, None) == PURSUE
    assert held_task_cancel_due(state, gd, _ctx(), None) is True
    assert TaskCancelGoal().value(state, gd, None) > 0.0


def test_bank_expand_fires_on_account_gold_not_pocket_alone():
    """Live Robby 2026-09-12: bank 50/50, cost 3500, pocket 3797, bank 12553,
    reserve 5100. The reserve is an ACCOUNT floor, so the buy is reserve-safe
    (16350-3500=12850 >= 5100) even though the pocket alone reads 297 < 5100.
    Refusing here left him wedged at 157/158 with no shed route for 10 hours."""
    gd = GameData()
    gd._bank_capacity = 50
    gd._next_expansion_cost = 3500
    state = make_state(bank_items={f"item{i}": 1 for i in range(50)},
                       gold=3797, bank_gold=12553)
    collect, _ = active_means(state, gd, None,
                              _ctx(bank_accessible=True, gold_reserve=5100))
    assert MeansKind.BANK_EXPAND in collect


def test_bank_expand_absent_when_pocket_cannot_pay_cost():
    """The account is reserve-safe but the pocket cannot fund the buy, and no
    withdraw-gold edge exists, so BuyBankExpansionAction.is_applicable would
    refuse — firing here emits a rung the planner cannot serve."""
    gd = GameData()
    gd._bank_capacity = 50
    gd._next_expansion_cost = 3500
    state = make_state(bank_items={f"item{i}": 1 for i in range(50)},
                       gold=100, bank_gold=20000)
    _, discretionary = active_means(state, gd, None,
                                    _ctx(bank_accessible=True, gold_reserve=0))
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_is_a_collect_rung_not_a_discretionary_one():
    """BANK_EXPAND sits ABOVE the objective step (2026-09-13).

    Below it the rung was unreachable — a character essentially always has a
    step, so `audit/liveness_completeness.py` carried it as
    `unreachable: MeansKind.BANK_EXPAND is in the discretionary band`. Measured
    live: the rung fired for two characters against a 50/50 bank and was never
    once selected, while every inventory climbed with no deposit sink.
    """
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    state = make_state(bank_items={f"item{i}": 1 for i in range(19)}, gold=200)
    collect, discretionary = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND in collect
    assert MeansKind.BANK_EXPAND not in discretionary


def test_bank_expand_is_an_interrupt_after_the_claim():
    """Phase 5-2c-ii: buying a bank slot keeps the deposit sink open, a
    precondition of continuing, so BANK_EXPAND is an interrupt. Position, not
    just membership: it closes the interrupt group, right after CLAIM_PENDING,
    so the collect means (task bookings, supply, turn-in) all follow it."""
    assert MeansKind.BANK_EXPAND in INTERRUPT_MEANS
    order = list(COLLECT_REWARD_ORDER)
    assert order.index(MeansKind.BANK_EXPAND) == order.index(MeansKind.CLAIM_PENDING) + 1
    assert all(m in INTERRUPT_MEANS for m in order[:order.index(MeansKind.BANK_EXPAND) + 1])


def test_bank_expand_fires_at_the_three_quarter_fill_mark():
    """USER 2026-09-13: expanding is good to do whenever we have the money, so
    the trigger moved 95% -> 75%. 15/20 = exactly 0.75 fires (>=)."""
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    state = make_state(bank_items={f"item{i}": 1 for i in range(15)}, gold=200)
    collect, _ = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND in collect


def test_bank_expand_silent_below_the_three_quarter_mark():
    """14/20 = 0.70 < 0.75: still nothing to do."""
    gd = GameData()
    gd._bank_capacity = 20
    gd._next_expansion_cost = 10
    state = make_state(bank_items={f"item{i}": 1 for i in range(14)}, gold=200)
    collect, _ = active_means(state, gd, None, _ctx(bank_accessible=True))
    assert MeansKind.BANK_EXPAND not in collect
