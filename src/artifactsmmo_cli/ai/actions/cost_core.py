"""Pure cost cores extracted from Action.cost methods.

The Phase-2 Dijkstra-optimality proof (`formal/Formal/PlannerAdmissibility.lean`,
backed by `planner.py:81`) requires every Action.cost(...) to return a
non-negative value in every reachable state. These helpers isolate the
structural arithmetic so the Lean model in `formal/Formal/ActionCostNonneg.lean`
can prove `cost ≥ 0` once per structural form and have it apply to every
concrete Action that delegates here.

Three structural forms cover all 26 concrete Action subclasses. Every walk an
action folds into its cost is priced in SECONDS by `travel_seconds` — the unit
`Move`, `Rest` and every learned edge are denominated in — so `dist` below is
always travel seconds, never a raw tile count:

1. **Constant** cost (`Equip`, `Unequip`, `Transition`, `Claim`,
   `MoveSemantic`): trivially ≥ 0 — no helper needed; the constant in the
   action's `cost` method already lives in the source.

1b. **HP-deficit-dependent** cost (`Rest`): the real server cooldown scales
   with the missing-HP fraction, so `Rest` is no longer constant. Use
   `rest_cost_pure(hp, max_hp)` = `rest_cooldown_seconds(...)` in seconds — 3.0
   at the floor, 100.0 at a full deficit, the same unit every learned edge is
   denominated in.

2. **Distance + positive constant** (`AcceptTask`, `BankExpansion`, `Craft`,
   `Recycle`, `DepositGold`, `DepositAll`, `Withdraw*`, `Npc*`,
   `TaskExchange`, `TaskCancel`, `TaskTrade`, `CompleteTask`,
   `OptimizeLoadout`, `Delete`, `Consumable`): formula is
   `base + qty*per_unit + dist` with all non-negative inputs, `dist` the
   walk's travel seconds. Use `distance_cost_pure(base, dist)` and
   `qty_cost_pure(base, qty, dist, per_unit)`.

3. **History-dependent** (`Fight`, `Gather`, `Move`): formula is either the
   static fallback or `learned / max(rate, 0.1)`. Use `learned_cost_pure`,
   which encapsulates the clamp and the rate switch. The static fallback's
   walk is travel seconds too (`Gather` charges it once per action, not per
   gather: `execute` walks once and gathers in place).

The non-negativity contract for `learned_cost_pure`:
* `learned ≥ 0` is guaranteed by every writer of
  `Cycle.actual_cooldown_seconds` (see writer audit in
  `formal/Formal/ActionCostNonneg.lean`):
  - `src/artifactsmmo_cli/ai/player.py:312` writes `0.0`
  - `src/artifactsmmo_cli/ai/player.py:362` writes `max(0.0, ...)`
  - The store returns `statistics.median(non_null)` over rows; median of
    non-negative values is non-negative.
* `rate ≥ 0` is guaranteed by `LearningStore.success_rate` returning either
  `1.0` (no samples) or a count-of-ok / total fraction in [0,1].
* `max(rate, 0.1) ≥ 0.1 > 0` ensures the divisor never vanishes.

`delete_cost` values (instance-parameterized `DeleteItemAction.cost_weight`):
all branches of `player_helpers.delete_cost` return a positive constant
(5.0 / 25.0 / 50.0).
"""

from artifactsmmo_cli.ai.rest_cooldown_core import rest_cooldown_seconds

MOVE_SECONDS_PER_TILE = 5
"""Seconds one tile of Manhattan walking is priced at — the one travel unit.

`MoveAction` priced a tile at 5 s while the 21 actions that fold a walk into
their own cost priced it at 1 and `Gather` charged it once PER GATHER, so a walk
hidden inside an action cost a fifth of the same walk taken as a `Move`, and a
recovery plan that left the tile (live 2026-10-09: R2D2 walking 15 tiles and a
transition to cook cheese) undercut a `Rest` in place it took 3.6x longer than.
Every walk now goes through `travel_seconds`, so they all agree with `Move` and
with the seconds `Rest` and every learned edge are denominated in.

The Lean cost models (`Formal.ActionCostNonneg`, `Formal.GatherCost`) take the
walk as an argument, so they receive these seconds and need no copy of the
constant.
"""


def travel_seconds(src: tuple[int, int], dest: tuple[int, int]) -> int:
    """The walk from `src` to `dest`, in seconds: Manhattan tiles x
    `MOVE_SECONDS_PER_TILE`. Non-negative, zero exactly when `src == dest`."""
    return MOVE_SECONDS_PER_TILE * (abs(dest[0] - src[0]) + abs(dest[1] - src[1]))


def rest_cost_pure(hp: int, max_hp: int) -> float:
    """Rest edge cost = the real cooldown, in SECONDS.

    This used to divide by ten, on the claim that the planner's cost unit was
    10s. The live data refutes that claim: over 40k learning-DB cycles the
    median `predicted_cost / actual_cooldown_seconds` is 1.00 for Fight (25.8s)
    and 1.00 for Gather (29.8s) — the learned edges ARE seconds, because
    `learned_cost_pure` returns a median `actual_cooldown_seconds` raw — while
    Rest sat at 0.10 across 10,017 samples (38.9s real, priced 4.0). Only Rest
    carried the divisor, so only Rest was mispriced, and it was mispriced
    exactly tenfold in the bot's favour: the traces show Robby spending 215
    actions on Rest against 216 on Fight.

    Dividing was introduced to stop potion churn on shallow deficits, and that
    concern survives the fix without the lie: a consumable is a flat 3s
    (`CONSUMABLE_COOLDOWN_SECONDS`) and a Rest's own floor is 3s
    (`rest_cooldown_core.REST_MINIMUM_SECONDS`), so at the floor the two tie and
    above it the potion wins — which is true, since it really does save the
    whole 38.9s median. Whether the bot can
    AFFORD that potion is priced by the potion economy (`best_loadout`),
    not by understating what a Rest costs.

    The cooldown itself comes from `rest_cooldown_core`, which is also what the
    projection's loop model consults. This function used to restate the published
    formula inline while `fight_loop_cost` ignored it entirely, which is how one
    server rule came to be modelled two incompatible ways in one codebase."""
    return float(rest_cooldown_seconds(max_hp - hp, max_hp))


REST_COST_MAX = rest_cost_pure(0, 1)
"""The supremum of `rest_cost_pure` over every reachable HP shape (= 100.0s).

`missing <= max_hp` always, so `pct_ceil <= 100` and the cost peaks at
`max(3, 100)` -- independently of `max_hp`, which is why one constant covers
every character. Evaluated from the formula rather than written as a literal so
that rescaling the cost unit inside `rest_cost_pure` carries this with it, which
is exactly what happened when the bogus /10 came out of `rest_cost_pure`.
"""

CONSUMABLE_COOLDOWN_SECONDS = 3.0
"""The published cooldown of using a consumable — flat, whatever the quantity.

https://docs.artifactsmmo.com/concepts/resting_and_using_items/ ; the live
learning DB agrees at a 2.8s median over 974 `UseConsumableAction` cycles (clock
jitter accounts for the 0.2).

Held apart from `rest_cooldown_core.REST_MINIMUM_SECONDS`, which is also three
seconds, because the two are separate server rules that happen to coincide.
Folding them into one name would make a future divergence silent.
"""


def distance_cost_pure(base: float, dist: int) -> float:
    """Cost = base + dist. Non-negative when base >= 0 and dist >= 0.

    `dist` is the walk's travel SECONDS (`travel_seconds`), not tiles.

    Used by every "distance + constant" action (Accept/Complete/Cancel task,
    Craft, Recycle, Deposit*, Withdraw*, Npc*, TaskExchange, TaskTrade,
    BankExpansion, OptimizeLoadout).
    """
    return base + dist


def qty_cost_pure(base: float, qty: int, dist: int, per_unit: float) -> float:
    """Cost = base + per_unit * qty + dist. Non-negative when all inputs
    are non-negative (qty >= 1 from is_applicable / planner contract).
    """
    return base + per_unit * qty + dist


def learned_cost_pure(static: float, learned: float, rate: float,
                      *, confident_threshold: float = 0.95,
                      rate_floor: float = 0.1,
                      has_history: bool) -> float:
    """Pure history-augmented cost.

    Mirrors the structural form shared by Fight, Gather, and Move:

        if not has_history: return static
        if rate < confident_threshold: return learned / max(rate, rate_floor)
        return learned

    Non-negative when static, learned >= 0 and rate >= 0 (since the divisor
    is clamped to >= rate_floor > 0).
    """
    if not has_history:
        return static
    if rate < confident_threshold:
        return learned / max(rate, rate_floor)
    return learned
