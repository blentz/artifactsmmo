"""Pure cost cores extracted from Action.cost methods.

The Phase-2 Dijkstra-optimality proof (`formal/Formal/PlannerAdmissibility.lean`,
backed by `planner.py:81`) requires every Action.cost(...) to return a
non-negative value in every reachable state. These helpers isolate the
structural arithmetic so the Lean model in `formal/Formal/ActionCostNonneg.lean`
can prove `cost ≥ 0` once per structural form and have it apply to every
concrete Action that delegates here.

Three structural forms cover all 26 concrete Action subclasses:

1. **Constant** cost (`Rest`, `Equip`, `Unequip`, `Transition`, `Claim`,
   `MoveSemantic`): trivially ≥ 0 — no helper needed; the constant in the
   action's `cost` method already lives in the source.

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
