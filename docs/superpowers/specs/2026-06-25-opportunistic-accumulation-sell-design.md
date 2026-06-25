# Opportunistic Accumulation-Sell — Design

**Status:** approved-pending-review (brainstorm 2026-06-25)
**Scope:** Part 2 of the "opportunistic trading" request. Part 1 (combat-effect-aware
dominance keep — keep a low-tier poison weapon that is situationally best) is a
SEPARATE later spec; this spec does not touch combat scoring.

## Goal

Sell down accumulated multiples of an item **without waiting for bag pressure**.
Today selling is purely space-driven (nothing sheds below 85% bag), so Robby's
14 wooden_shields just sit there. Add a sell trigger driven by the **ratio of
held quantity to the item's keep-cap**, with priority rising geometrically with
that ratio, escalating above progression only for extreme hoards.

## Key existing facts (grounding)

- `useful_quantity_cap(code, state, game_data)` (`ai/inventory_caps.py`) is the
  single keep-cap — already folds dominance (previous-tier gear → cap 0/1),
  currency/consumable floors, and the level-distance ceiling. Reuse it verbatim.
- `overstocked_items` / `overstock_excess` are SPACE-DRIVEN (return 0 below the
  0.85 watermark). They are NOT changed here; this adds an orthogonal, ratio-driven
  path.
- `_has_sellable(state, game_data)` (`tiers/guards.py`) = an item with an NPC
  buyer (reachable, not a dormant event merchant) that is `tradeable`.
- Sell ladder: `SELL_PRESSURED` (collect-reward band, fires ≥0.85 used, ABOVE the
  objective step) and `SELL_IDLE` (discretionary band, fires <0.85 used). Both map
  to `SellInventoryGoal`. `SellInventoryGoal.value()` is **0 when not bank-locked**
  — which is exactly why the 14 shields never sell at low pressure.
- Arbiter precedence: guards > collect-reward > objective-step > discretionary,
  top-plannable within a band by goal `value()`.

## Components

### 1. `ai/accumulation_sell.py` — pure core (proof boundary)

Integer-exact, no float (formal-friendly).

```
ACCUM_MULT = 5      # fire when held >= ACCUM_MULT * cap
SEVERE_STEPS = 5    # steps >= this => escalate above progression (r >= 32)

def accumulation_steps(held: int, cap: int) -> int:
    """Geometric severity: the largest k >= 0 with eff_cap * 2**k <= held
    (= floor(log2(held / eff_cap))), where eff_cap = max(cap, 1). 0 if held
    is below eff_cap."""

def accumulation_excess(held: int, cap: int) -> int:
    """held - max(cap, 0) when held >= ACCUM_MULT * max(cap, 1), else 0.
    eff_cap = max(cap,1) only gates the RATIO; the amount kept is the true
    cap, so a DOMINATED item (cap 0) past the gate sells down to 0 (all of
    it), while a kept item (cap 1) sells down to 1. 0 below the ratio gate."""
```

A shell `sellable_accumulation(state, game_data) -> dict[str, int]` maps each
**sellable** (`_has_sellable`-eligible) over-ratio item to its `accumulation_excess`,
using `cap = useful_quantity_cap(code)`. A companion
`worst_accumulation_steps(state, game_data) -> int` = max `accumulation_steps`
over those items (0 if none) — the severity signal.

Theorem roles (Lean `Formal/AccumulationSell.lean`):
- `excess_monotone` — `accumulation_excess` non-decreasing in `held`.
- `fires_implies_excess_positive` — `held >= ACCUM_MULT*cap ∧ cap>0 ⇒ excess > 0`.
- `excess_sells_down_to_cap` — `held - accumulation_excess(held,cap) = cap` when firing.
- `steps_threshold` — `accumulation_steps(held,cap) >= SEVERE_STEPS ⇒ held >= cap*32`.
- `below_gate_quiet` — `held < ACCUM_MULT*cap ⇒ excess = 0`.

### 2. `SellInventoryGoal` changes (`goals/sell_inventory.py`)

- `value()` gains an **accumulation term** so it is positive un-pressured:
  `accum_value = min(ACCUM_BASE + steps*ACCUM_STEP, DISCRETIONARY_CEIL)` where
  `steps = worst_accumulation_steps(...)`, clamped strictly below the progression
  band (≤ 50, below survival 70) — moderate hoards fire during idle without
  derailing leveling. `value() = max(existing_pressure_value, accum_value, seize_window)`.
- `relevant_actions()` sizes each `NpcSellAction` to **sell down to the cap**
  (`accumulation_excess` quantity) for over-ratio sellable items, in addition to
  its existing under-pressure behavior. Sell-only — never deletes.

### 3. Ladder firing — `SELL_PRESSURED` disjunct (`tiers/means.py`)

Extend `_fires(SELL_PRESSURED)`:
`used_fraction >= 0.85` **OR** `worst_accumulation_steps(...) >= SEVERE_STEPS`,
AND `_has_sellable`. Severe hoards thus fire in the collect-reward band (above the
objective step) and preempt progression until cleared. `SELL_IDLE` is unchanged
(its goal value now carries the moderate accumulation term).

## Data flow

inventory + game_data → `useful_quantity_cap` per code → `accumulation_excess` /
`accumulation_steps` (gated on `_has_sellable`) → (a) `SellInventoryGoal.value()`
moderate term, (b) `SELL_PRESSURED` severe disjunct, (c) `relevant_actions`
sell-down-to-cap quantities.

## Error handling / safety

- Sell-only: an item with no reachable buyer is never touched here (left to the
  space-driven discard + bank-drain). No un-pressured deletion.
- Currencies/consumables: cap is 999 → ratio never reaches 5 → never fires. Safe.
- Far-gated mats: cap is the level-distance ceiling (≤5/≤10) → a 200-of-cap-5
  stock (r=40) fires and sells down to 5 (only if a buyer exists).
- Termination/liveness: `accumulation_excess` strictly decreases `held` toward
  `cap`; once `held = cap` the gate is quiet — bounded, cannot re-trigger. The
  reach-50 liveness model treats it as a bounded collect means (sell terminates),
  same shape as the existing `SELL_PRESSURED`.

## Testing

- Unit (`tests/test_ai/test_accumulation_sell.py`): steps/excess math (14/1→excess
  13 steps 3; 11/2→excess 9 steps 2; 4/1→0 below gate; cap 0 handling), shell over
  a real GameData (sellable gate, currency/consumable never fire, far-gated mat),
  `SellInventoryGoal.value()` moderate vs severe vs satisfied, `relevant_actions`
  sells down to cap, `SELL_PRESSURED` severe disjunct fires un-pressured. 100% cov.
- Formal lockstep: `AccumulationSell.lean` def + the 5 role theorems + Contracts
  pin; differential `test_accumulation_sell_diff.py` (real core vs oracle, incl.
  the geometric steps); extend `test_ladder_fires_diff.py` for the SELL_PRESSURED
  disjunct (new `severeAccumulation`/`worstAccumulationSteps` State field, oracle
  arg, sim mirror); mutation anchors (drop ratio gate, weaken ACCUM_MULT, drop
  severe disjunct, off-by-one in steps). Full `formal/gate.sh` green.

## Constants (confirmed)

| Constant | Value | Meaning |
|---|---|---|
| `ACCUM_MULT` | 5 | fire when `held >= 5*cap` |
| `SEVERE_STEPS` | 5 | `steps>=5` (r≥32) escalates above progression |
| `accumulation_steps` | `floor(log2(held/eff_cap))` | geometric severity |
| `ACCUM_BASE` | 18 | moderate idle-sell base value (between DRAIN_BANK_JUNK 15 and RECYCLE_SURPLUS 20) |
| `ACCUM_STEP` | 3 | value added per geometric step |
| `DISCRETIONARY_CEIL` | 48 | moderate value clamp, strictly below progression 50 / survival 70 |

Moderate accumulation value = `min(ACCUM_BASE + steps*ACCUM_STEP, DISCRETIONARY_CEIL)`
(steps 2 → 24, steps 4 → 30; severe steps≥5 routes via the SELL_PRESSURED band
instead, so the value mapping only governs the moderate/idle regime).

## Out of scope (explicit)

- Part 1: combat-effect-aware dominance (keep a situationally-best low-tier
  weapon). Separate spec.
- A SINGLE previous-tier item (e.g. one dominated wooden_stick after a copper_dagger
  upgrade) is NOT sold by this trigger — it needs a multiple (`held >= 5*eff_cap`).
  Single-item previous-tier sell is Part 1 / the existing space-driven path. A
  dominated MULTIPLE (14 dominated shields, cap 0) DOES sell fully here.
- Changing the space-driven `overstocked_items` / discard watermark.
- Un-pressured deletion of non-sellable items.
