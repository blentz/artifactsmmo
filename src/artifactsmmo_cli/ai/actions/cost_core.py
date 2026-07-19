"""Pure cost cores extracted from Action.cost methods.

The Phase-2 Dijkstra-optimality proof (`formal/Formal/PlannerAdmissibility.lean`,
backed by `planner.py:81`) requires every Action.cost(...) to return a
non-negative value in every reachable state. These helpers isolate the
structural arithmetic so the Lean model in `formal/Formal/ActionCostNonneg.lean`
can prove `cost ≥ 0` once per structural form and have it apply to every
concrete Action that delegates here.

Three structural forms cover all 26 concrete Action subclasses:

1. **Constant** cost (`Equip`, `Unequip`, `Transition`, `Claim`,
   `MoveSemantic`): trivially ≥ 0 — no helper needed; the constant in the
   action's `cost` method already lives in the source.

1b. **HP-deficit-dependent** cost (`Rest`): the real server cooldown scales
   with the missing-HP fraction, so `Rest` is no longer constant. Use
   `rest_cost_pure(hp, max_hp)` = `max(3, ceil(missing_HP%)) / 10` — a full-HP
   rest stays 10.0 (matching the prior flat constant) while small deficits are
   cheap (≥ 0.3), so the planner rests instead of churning consumables.

2. **Distance + positive constant** (`AcceptTask`, `BankExpansion`, `Craft`,
   `Recycle`, `DepositGold`, `DepositAll`, `Withdraw*`, `Npc*`,
   `TaskExchange`, `TaskCancel`, `TaskTrade`, `CompleteTask`,
   `OptimizeLoadout`, `Delete`, `Consumable`): formula is
   `base + qty*per_unit + dist` with all non-negative inputs. Use
   `distance_cost_pure(base, dist)` and `qty_cost_pure(base, qty, dist,
   per_unit)`.

3. **History-dependent** (`Fight`, `Gather`, `Move`): formula is either the
   static fallback or `learned / max(rate, 0.1)`. Use `learned_cost_pure`,
   which encapsulates the clamp and the rate switch.

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


def rest_cost_pure(hp: int, max_hp: int) -> float:
    """Rest edge cost = real cooldown seconds / 10 (cost unit = 10s, so a
    full-HP rest = 100s = 10.0, matching the prior flat constant). Server
    cooldown = max(3, ceil(missing_HP%)) seconds (1s per 1% missing HP, min 3s;
    https://docs.artifactsmmo.com/concepts/resting_and_using_items/). Dynamic so
    a small deficit rests cheaply (beating a fitting consumable's 2.0) instead of
    the old flat 10.0 that made Rest always look expensive and drove wasteful
    potion crafting."""
    missing = max(0, max_hp - hp)
    pct_ceil = -(-(missing * 100) // max_hp)   # ceil(missing*100/max_hp); max_hp>0
    return max(3, pct_ceil) / 10.0


REST_COST_MAX = rest_cost_pure(0, 1)
"""The supremum of `rest_cost_pure` over every reachable HP shape (= 10.0).

`missing <= max_hp` always, so `pct_ceil <= 100` and the cost peaks at
`max(3, 100)/10` -- independently of `max_hp`, which is why one constant covers
every character. Evaluated from the formula rather than written as a literal so
that rescaling the cost unit inside `rest_cost_pure` carries this with it.
"""

OVERHEAL_REST_MULTIPLE = 10
"""How many times the dearest possible Rest the overheal sentinel must cost.

Single-name int-literal assignment ON PURPOSE: this is the exact shape the Lean
extractor (`scripts/extract_lean.py`, `_extract_constants`) accepts, so this knob
is generated into `formal/Formal/Extracted/CostCore.lean` and consumed by
`ActionCostNonneg.consumableCostOverheal`. Both languages therefore derive the
sentinel from ONE integer, and `extract_lean.py --check` fails the gate if they
drift. Do not inline this into the expression below -- that breaks extraction.
"""

OVERHEAL_CONSUMABLE_COST = OVERHEAL_REST_MULTIPLE * REST_COST_MAX
"""Cost `UseConsumableAction` returns when the only consumable it can pick
overshoots the deficit (see `consumable.py`).

The point is to make the planner prefer Rest over wasting an overhealing item,
which is only sound while this STRICTLY exceeds every possible Rest cost -- so it
is derived from `REST_COST_MAX` rather than hardcoded next to a comment asserting
the relationship. The order-of-magnitude margin keeps it dominant over a plausible
multi-step rest-and-move alternative too.

Value is 100.0. The Lean mirror derives the same product from the same extracted
multiplier, and an Oracle-backed differential asserts the two agree -- so neither
a Python edit nor a Lean edit can move one side alone.
"""


def distance_cost_pure(base: float, dist: int) -> float:
    """Cost = base + dist. Non-negative when base >= 0 and dist >= 0.

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
