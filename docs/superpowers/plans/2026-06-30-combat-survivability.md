# Combat Survivability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop one avoidable low-HP fight loss from stranding Robby's only XP grind into a zero-XP gear grind, by healing before fights, relaxing the combat veto, and bringing win-rate-scaled health potions to marginal fights.

**Architecture:** Three independent changes on branch `feat/combat-survivability`. (1) Raise the HP-rest threshold so fights start near-full. (2) Lower the combat learned-loss veto so marginal-but-grindable monsters stay valid targets (already implemented; commit it). (3) A proven integer pure core maps observed win-rate → potion quantity, a new goal equips that many potions into a utility slot before marginal fights, and the existing consumable-supply goal scales its stock target to feed the stack.

**Tech Stack:** Python 3.13, `uv`, pytest (100% coverage gate), Lean 4 + Lake (formal proofs), `formal/diff` differential + `formal/diff/mutate.py` mutation gate.

## Global Constraints

- Run every Python command via `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- Coverage gate: 0 errors, 0 warnings, 0 skipped, 100% coverage. Run subsets with `--no-cov`; the final task runs the full gate.
- ONE behavioral class per file. No inline imports. No `if TYPE_CHECKING`. Never catch `Exception`. Use only API data or fail.
- Decision cores are proven: pure core (float-free, integer/rational) + Lean mirror + `formal/diff` differential test + `formal/diff/mutate.py` anchor. Mirror the `consumable_selection` example exactly.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Spec: `docs/superpowers/specs/2026-06-30-combat-survivability-design.md`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/combat.py` | (done) `WIN_RATE_THRESHOLD = 0.4` |
| `src/artifactsmmo_cli/ai/thresholds.py` | `CRITICAL_HP_FRACTION = 0.75`; new provisioning constants |
| `formal/Formal/Liveness/ProductionLadder.lean` | `CRITICAL_HP_NUM := 75` mirror |
| `formal/diff/mutate.py` | CRITICAL_HP anchor; new pure-core mutation anchors |
| `src/artifactsmmo_cli/ai/actions/equip.py` | `EquipAction.quantity` (utility stacking) |
| `src/artifactsmmo_cli/ai/marginal_potion_qty.py` | NEW pure core `marginal_potion_qty_pure` |
| `formal/Formal/MarginalPotionQty.lean` | NEW Lean mirror + theorems |
| `formal/diff/test_marginal_potion_qty_diff.py` | NEW differential test |
| `src/artifactsmmo_cli/ai/goals/provision_marginal_fight.py` | NEW `ProvisionMarginalFightGoal` |
| `src/artifactsmmo_cli/ai/consumable_supply.py` | scale heal-stock target |
| `src/artifactsmmo_cli/ai/strategy_driver.py` | route to provision goal before grind |

---

## Task 1: Commit the completed veto change (Part 2)

`WIN_RATE_THRESHOLD 0.9 → 0.4` plus its two tests are already in the working tree from a prior session. Verify and commit so the branch has a clean baseline.

**Files:**
- Modify (already changed): `src/artifactsmmo_cli/ai/combat.py:30`
- Modify (already changed): `tests/test_ai/test_combat.py` (`test_is_winnable_keeps_marginal_grindable_winrate`, `test_is_winnable_vetoes_genuine_loser`)

- [ ] **Step 1: Verify the veto tests pass**

Run: `uv run pytest tests/test_ai/test_combat.py tests/test_ai/test_combat_targets.py -q --no-cov`
Expected: PASS (50 passed).

- [ ] **Step 2: Confirm the constant value**

Run: `grep -n "WIN_RATE_THRESHOLD = " src/artifactsmmo_cli/ai/combat.py`
Expected: `30:WIN_RATE_THRESHOLD = 0.4`

- [ ] **Step 3: Commit**

```bash
git add src/artifactsmmo_cli/ai/combat.py tests/test_ai/test_combat.py
git commit -m "$(cat <<'EOF'
fix(combat): lower learned-loss veto 0.9->0.4 so marginal grinds survive

0.9 stranded L3 Robby: green_slime (~80% win, only in-window XP source) got
vetoed after one loss, combat_picker returned None, ReachCharLevel stood down,
arbiter fell to a zero-XP gear grind. Veto now fires only when a monster is lost
more than it wins. Pure-Python constant; picker/cascade proofs are abstract over
the Bool verdict, so no Lean/diff impact.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Heal before fighting (`CRITICAL_HP_FRACTION 0.25 → 0.75`)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/thresholds.py:20`
- Modify: `formal/Formal/Liveness/ProductionLadder.lean:67-69`
- Modify: `formal/diff/mutate.py:3136-3137`
- Test: `tests/test_ai/test_goals.py:55-75` (RestoreHP threshold)

**Interfaces:**
- Produces: `CRITICAL_HP_FRACTION = 0.75` (float) consumed by `goals/restore_hp.py`, `tiers/guards.py`, `tiers/strategy.py`.

- [ ] **Step 1: Add a failing boundary test**

Read `tests/test_ai/test_goals.py:55-75`. Add this test after the existing RestoreHP value test:

```python
def test_restore_hp_critical_value_at_70_percent():
    """At 70% HP (below the 0.75 rest threshold) RestoreHP returns its ceiling so
    the bot heals to full before fighting. Guards low-HP fight starts."""
    goal = RestoreHPGoal()
    state = make_state(hp=70, max_hp=100)  # 70% < 0.75
    assert goal.value(state, _game_data()) == RestoreHPGoal.CRITICAL_HP_VALUE
```

(Match the file's existing `make_state` / game-data fixture names; read lines 1-40 for the imports and helper names.)

- [ ] **Step 2: Run it — expect FAIL**

Run: `uv run pytest tests/test_ai/test_goals.py::test_restore_hp_critical_value_at_70_percent -q --no-cov`
Expected: FAIL — at 0.25 threshold, 70% is above critical so value is `(1-0.70)*100 = 30.0`, not 110.0.

- [ ] **Step 3: Raise the constant**

In `src/artifactsmmo_cli/ai/thresholds.py:20`:

```python
# HP-critical preempt threshold (hp / max_hp). Below this the HP-critical guard
# preempts every other means and RestoreHPGoal returns its ceiling value. Set to
# 0.75 (was 0.25) so the bot rests to full before fighting: low-HP fight starts
# were the avoidable-loss source that tripped the combat veto (see spec
# 2026-06-30). _is_winnable (player.py) projects HP to max before the winnability
# check, so the 2026-06-06 "parked at 76/130" deadlock does not recur.
CRITICAL_HP_FRACTION = 0.75
```

- [ ] **Step 4: Update the Lean mirror**

In `formal/Formal/Liveness/ProductionLadder.lean:67-68`:

```lean
/-- `CRITICAL_HP_FRACTION = 0.75` (thresholds.py). Raised from 0.25; every proof
using this mirror is an "HP-full ⇒ critical guard does not fire" lemma
(`¬ (CRITICAL_HP_DEN * maxHp < CRITICAL_HP_NUM * maxHp)`), which closes for any
`NUM < DEN`, so 75 < 100 keeps them all valid. -/
def CRITICAL_HP_NUM : Nat := 75
```

- [ ] **Step 5: Update the mutation anchor**

In `formal/diff/mutate.py:3136-3137`, change the original string to the new source line and pick a distinct mutant:

```python
        "CRITICAL_HP_FRACTION = 0.75",
        "CRITICAL_HP_FRACTION = 0.50",
```

- [ ] **Step 6: Run the goal test — expect PASS**

Run: `uv run pytest tests/test_ai/test_goals.py -q --no-cov`
Expected: PASS. If a pre-existing test asserted critical-value only below 25% and now fails because a 25–75% case flips to the ceiling, update that test's expectation (the new contract is "ceiling below 75%").

- [ ] **Step 7: Rebuild the liveness proofs**

Run: `cd formal && lake build Formal.Liveness.ProductionLadder Formal.Liveness.MeansFiring Formal.Liveness.BlockerQuieting Formal.Liveness.BlockerSettled Formal.Liveness.Leveling Formal.Liveness.PlanExists Formal.Liveness.FightReady Formal.Liveness.CycleStep Formal.Liveness.BlockerMonotone Formal.Liveness.CumulativeProgress`
Expected: build succeeds. If any `omega` step breaks, the goal state will show the new constants; re-close with `omega` (the lemmas are linear-arithmetic over the mirrored Nats).

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/thresholds.py formal/Formal/Liveness/ProductionLadder.lean formal/diff/mutate.py tests/test_ai/test_goals.py
git commit -m "$(cat <<'EOF'
fix(combat): raise CRITICAL_HP_FRACTION 0.25->0.75 (heal before fighting)

Fights were starting at single-digit HP (trace hp 4/16/28), causing the avoidable
losses that tripped the combat veto. RestoreHP now preempts below 75% so fights
start near-full. Lean mirror CRITICAL_HP_NUM 25->75 (proofs are NUM<DEN lemmas,
unaffected); mutation anchor updated.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `EquipAction` utility-slot quantity

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/equip.py`
- Test: `tests/test_ai/test_actions_equip.py` (create if absent; otherwise add to the existing equip test module — `grep -rl "EquipAction" tests/`)

**Interfaces:**
- Produces: `EquipAction(code: str, slot: str, quantity: int = 1)`. `is_applicable` additionally requires `state.inventory[code] >= quantity`. `apply` decrements inventory by `quantity`. `execute` passes `quantity=self.quantity` to `EquipSchema`.

- [ ] **Step 1: Write failing tests**

```python
def test_equip_action_quantity_requires_enough_inventory():
    state = make_state(inventory={"small_health_potion": 1})
    gd = _game_data_with_consumable("small_health_potion", level=1)
    action = EquipAction(code="small_health_potion", slot="utility1_slot", quantity=2)
    assert action.is_applicable(state, gd) is False  # only 1 held, want 2


def test_equip_action_quantity_decrements_by_quantity():
    state = make_state(inventory={"small_health_potion": 5}, level=1)
    gd = _game_data_with_consumable("small_health_potion", level=1)
    action = EquipAction(code="small_health_potion", slot="utility1_slot", quantity=2)
    result = action.apply(state, gd)
    assert result.inventory.get("small_health_potion", 0) == 3
    assert result.equipment["utility1_slot"] == "small_health_potion"
```

(Use the repo's existing equip-test fixtures; `grep -n "EquipAction" tests/test_ai/*.py` to find `make_state`/game-data helpers already used for equip.)

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_ai/ -k "equip_action_quantity" -q --no-cov`
Expected: FAIL — `EquipAction` has no `quantity` field.

- [ ] **Step 3: Add the field + wire it**

In `src/artifactsmmo_cli/ai/actions/equip.py`:

```python
    code: str
    slot: str
    quantity: int = 1
```

In `is_applicable`, replace the inventory gate at the top:

```python
        if state.inventory.get(self.code, 0) < self.quantity:
            return False
```

In `apply`, decrement by quantity:

```python
        new_inventory = dict(state.inventory)
        new_inventory[self.code] = new_inventory.get(self.code, 0) - self.quantity
        if new_inventory[self.code] <= 0:
            del new_inventory[self.code]
```

In `execute`, pass quantity:

```python
        body = EquipSchema(code=self.code, slot=ItemSlot(self.slot.replace("_slot", "")),
                           quantity=self.quantity)
```

Update `__repr__` to include quantity only when > 1 (keeps existing repr-based tests/anchors stable):

```python
    def __repr__(self) -> str:
        if self.quantity > 1:
            return f"Equip({self.code}x{self.quantity}->{self.slot})"
        return f"Equip({self.code}->{self.slot})"
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_ai/ -k "equip" -q --no-cov`
Expected: PASS (new tests + existing equip tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/equip.py tests/test_ai/
git commit -m "$(cat <<'EOF'
feat(equip): utility-slot quantity on EquipAction

API EquipSchema.quantity (utilities only, max 100) was never passed; the action
only ever loaded 1. Add a quantity field (default 1) gated on held inventory,
decrement by quantity on apply, pass to EquipSchema on execute. Enables stacking
health potions into a utility slot.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Pure core `marginal_potion_qty_pure`

Win-rate-scaled potion count, float-free integer math (proved over Nat in Task 5). Win-rate is an integer permille (`success_rate * 1000`); the float→permille conversion stays in unproven glue (Task 8), mirroring how `is_winnable` consumes `success_rate`.

**Files:**
- Create: `src/artifactsmmo_cli/ai/marginal_potion_qty.py`
- Create: `tests/test_ai/test_marginal_potion_qty.py`

**Interfaces:**
- Produces:
  ```python
  def marginal_potion_qty_pure(
      samples: int, win_permille: int, min_samples: int,
      threshold_permille: int, full_stack_permille: int,
      max_stack: int, utility_slot_filled: bool, held_heal_qty: int,
  ) -> int
  ```
  Returns equip quantity in `[0, max_stack]`, clamped to `held_heal_qty`. `0` when not marginal / cold / slot filled / no heal held.

- [ ] **Step 1: Write failing tests**

```python
from artifactsmmo_cli.ai.marginal_potion_qty import marginal_potion_qty_pure

# constants used throughout: min=5, threshold=950, full=500, max_stack=100
def _q(win_permille, samples=10, filled=False, held=100):
    return marginal_potion_qty_pure(samples, win_permille, 5, 950, 500, 100, filled, held)

def test_not_marginal_above_threshold_returns_zero():
    assert _q(950) == 0
    assert _q(980) == 0

def test_cold_start_returns_zero():
    assert _q(800, samples=4) == 0  # < min_samples

def test_just_below_threshold_returns_one():
    assert _q(949) == 1  # ceil of a near-zero fraction, floored at 1

def test_full_stack_at_or_below_full_winrate():
    assert _q(500) == 100
    assert _q(450) == 100  # clamped (still fought: veto floor 0.40)

def test_midband_interpolates():
    # r=725 permille -> fraction=(950-725)/450=0.5 -> ceil(0.5*100)=50
    assert _q(725) == 50

def test_monotone_non_increasing_in_winrate():
    qs = [_q(p) for p in range(500, 951, 25)]
    assert all(a >= b for a, b in zip(qs, qs[1:]))  # higher win -> not more potions

def test_clamped_to_held():
    assert _q(500, held=7) == 7  # wants full stack, holds 7

def test_slot_filled_returns_zero():
    assert _q(500, filled=True) == 0

def test_no_heal_held_returns_zero():
    assert _q(500, held=0) == 0
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_ai/test_marginal_potion_qty.py -q --no-cov`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the pure core**

```python
"""Win-rate-scaled potion quantity for marginal-fight provisioning.

The harder the fight, the more health potions to stack into a utility slot: 0 when
the monster is not marginal (observed win-rate at/above the threshold, or too few
samples), 1 just below the threshold, scaling up to a full stack at the full-stack
win-rate, then clamped to the full stack down to the combat veto floor. The
equipped count never exceeds what the bot holds.

Win-rate is an integer permille (success_rate * 1000) so the decision is float-free
and mirrors `formal/Formal/MarginalPotionQty.lean` bit-for-bit over Nat. The
float->permille conversion lives in the goal glue (strategy_driver), not here.
"""


def marginal_potion_qty_pure(
    samples: int,
    win_permille: int,
    min_samples: int,
    threshold_permille: int,
    full_stack_permille: int,
    max_stack: int,
    utility_slot_filled: bool,
    held_heal_qty: int,
) -> int:
    if utility_slot_filled or held_heal_qty <= 0:
        return 0
    if samples < min_samples or win_permille >= threshold_permille:
        return 0
    if win_permille <= full_stack_permille:
        desired = max_stack
    else:
        # fraction = (threshold - win) / (threshold - full), rises as win falls.
        # desired = ceil(fraction * max_stack), floored at 1. Integer ceil:
        # (a + b - 1) // b for a, b > 0.
        numerator = (threshold_permille - win_permille) * max_stack
        denominator = threshold_permille - full_stack_permille
        desired = max(1, (numerator + denominator - 1) // denominator)
    return min(desired, held_heal_qty)
```

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_ai/test_marginal_potion_qty.py -q --no-cov`
Expected: PASS (all 9).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/marginal_potion_qty.py tests/test_ai/test_marginal_potion_qty.py
git commit -m "$(cat <<'EOF'
feat(combat): marginal_potion_qty_pure win-rate-scaled provisioning core

Float-free integer core: 0 above 0.95 win / cold-start / slot-filled / no-heal;
1 just below 0.95; interpolates up to a full stack (100) at 0.50; clamped to held.
Lean proof + differential gate follow.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Lean proof + oracle dispatch + differential + mutation

Prove the core over Nat and lock Python↔Lean with a differential test and mutation anchors. Use the `superpowers`/`lean4` proving tools as needed; mirror the `consumable_selection` example end-to-end.

**Files:**
- Create: `formal/Formal/MarginalPotionQty.lean`
- Modify: the Lean oracle dispatcher (find it: `grep -rn '"consumable_selection"' formal/`) — add a `"marginal_potion_qty"` kind
- Create: `formal/diff/test_marginal_potion_qty_diff.py`
- Modify: `formal/diff/mutate.py` (new anchor list + register it in the runner)

**Interfaces:**
- Consumes: `marginal_potion_qty_pure` (Task 4).
- Produces: oracle kind `"marginal_potion_qty"` with args `[samples, win_permille, min_samples, threshold_permille, full_stack_permille, max_stack, slot_filled(0/1), held_heal_qty]` returning `{"qty": <int>}`.

- [ ] **Step 1: Write the Lean mirror**

`formal/Formal/MarginalPotionQty.lean`:

```lean
namespace Formal.MarginalPotionQty

/-- Integer ceil of `a / b` for `b > 0`: `(a + b - 1) / b`. -/
def ceilDiv (a b : Nat) : Nat := (a + b - 1) / b

def marginalPotionQty
    (samples winPermille minSamples thresholdPermille fullStackPermille
     maxStack : Nat) (slotFilled : Bool) (heldHealQty : Nat) : Nat :=
  if slotFilled || heldHealQty == 0 then 0
  else if samples < minSamples || thresholdPermille ≤ winPermille then 0
  else
    let desired :=
      if winPermille ≤ fullStackPermille then maxStack
      else max 1 (ceilDiv ((thresholdPermille - winPermille) * maxStack)
                          (thresholdPermille - fullStackPermille))
    min desired heldHealQty

/-- Bounded above by the full stack. -/
theorem qty_le_max (s w ms tp fp mx : Nat) (sf : Bool) (h : Nat) :
    marginalPotionQty s w ms tp fp mx sf h ≤ mx := by
  unfold marginalPotionQty; sorry

/-- Never more than held. -/
theorem qty_le_held (s w ms tp fp mx : Nat) (sf : Bool) (h : Nat) :
    marginalPotionQty s w ms tp fp mx sf h ≤ h := by
  unfold marginalPotionQty; sorry

/-- Zero at/above the threshold. -/
theorem qty_zero_above_threshold (s w ms tp fp mx : Nat) (sf : Bool) (h : Nat)
    (hge : tp ≤ w) : marginalPotionQty s w ms tp fp mx sf h = 0 := by
  unfold marginalPotionQty; sorry

end Formal.MarginalPotionQty
```

- [ ] **Step 2: Discharge the `sorry`s**

Use the lean4 proving workflow (`/lean4:prove` or the proof-repair agent). `qty_le_max`/`qty_le_held` follow from `min_le_left`/`min_le_right` and `max`/`ceilDiv` bounds; `qty_zero_above_threshold` from the second `if` guard (`tp ≤ w` makes `thresholdPermille ≤ winPermille` true). Verify: `cd formal && lake build Formal.MarginalPotionQty`. Expected: no `sorry`, no axioms beyond the allowed set.

- [ ] **Step 3: Register the oracle kind**

Find the dispatcher (`grep -rn '"consumable_selection"' formal/Formal/`). Add a branch decoding the 8 int args and emitting `{"qty": ...}`:

```lean
  | "marginal_potion_qty" =>
      match args with
      | [s, w, ms, tp, fp, mx, sf, h] =>
          let q := Formal.MarginalPotionQty.marginalPotionQty
                     s.toNat w.toNat ms.toNat tp.toNat fp.toNat mx.toNat (sf != 0) h.toNat
          Json.mkObj [("qty", Json.num q)]
      | _ => Json.mkObj [("error", Json.str "bad args")]
```

(Match the dispatcher's actual JSON helper names and arg type — copy the `consumable_selection` branch's exact style.)

Rebuild the oracle exe: `cd formal && lake build <oracle-exe-target>` (the target named in `formal/diff/oracle_client.py`'s `ORACLE` path).

- [ ] **Step 4: Write the differential test**

`formal/diff/test_marginal_potion_qty_diff.py`:

```python
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.marginal_potion_qty import marginal_potion_qty_pure
from formal.diff.oracle_client import run_oracle


@settings(max_examples=500, deadline=None)
@given(
    samples=st.integers(min_value=0, max_value=40),
    win_permille=st.integers(min_value=0, max_value=1000),
    slot_filled=st.integers(min_value=0, max_value=1),
    held=st.integers(min_value=0, max_value=100),
)
def test_marginal_potion_qty_matches_lean(samples, win_permille, slot_filled, held):
    args = [samples, win_permille, 5, 950, 500, 100, slot_filled, held]
    py = marginal_potion_qty_pure(samples, win_permille, 5, 950, 500, 100,
                                  bool(slot_filled), held)
    lean = run_oracle("marginal_potion_qty", [args])[0]
    assert lean["qty"] == py
```

- [ ] **Step 5: Run the differential test**

Run: `uv run pytest formal/diff/test_marginal_potion_qty_diff.py -q --no-cov`
Expected: PASS (Python == Lean over 500 random inputs).

- [ ] **Step 6: Add mutation anchors**

In `formal/diff/mutate.py`, add a list mirroring `CONSUMABLE_SELECTION_MUTATIONS` and register it where the runner aggregates mutation groups (follow how `CONSUMABLE_SELECTION_MUTATIONS` is referenced):

```python
MARGINAL_POTION_QTY_MUTATIONS = [
    ("marginal_potion_qty: threshold compare flip (>= -> >)",
     "    if samples < min_samples or win_permille >= threshold_permille:",
     "    if samples < min_samples or win_permille > threshold_permille:"),
    ("marginal_potion_qty: full-stack compare flip (<= -> <)",
     "    if win_permille <= full_stack_permille:",
     "    if win_permille < full_stack_permille:"),
    ("marginal_potion_qty: drop the floor-at-1",
     "        desired = max(1, (numerator + denominator - 1) // denominator)",
     "        desired = (numerator + denominator - 1) // denominator"),
    ("marginal_potion_qty: drop held clamp",
     "    return min(desired, held_heal_qty)",
     "    return desired"),
    ("marginal_potion_qty: ceil -> floor (drop the +den-1)",
     "        numerator = (threshold_permille - win_permille) * max_stack",
     "        numerator = (threshold_permille - win_permille) * max_stack - (denominator - 1)"),
]
```

- [ ] **Step 7: Run the mutation gate for this core**

Run the mutation runner scoped to the new group (use the same entrypoint the repo uses, e.g. `uv run python formal/diff/mutate.py --only marginal_potion_qty` — check `formal/diff/mutate.py --help` for the exact flag).
Expected: every mutant KILLED by the differential test.

- [ ] **Step 8: Commit**

```bash
git add formal/Formal/MarginalPotionQty.lean formal/diff/test_marginal_potion_qty_diff.py formal/diff/mutate.py formal/<oracle-dispatcher-file>
git commit -m "$(cat <<'EOF'
formal(combat): prove marginal_potion_qty + differential & mutation lock

Lean mirror over Nat (bounded, held-clamped, zero-above-threshold), oracle kind
marginal_potion_qty, hypothesis differential test (Python==Lean over win-permille),
and mutation anchors (every mutant killed).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `ProvisionMarginalFightGoal`

A single-purpose goal: when the combat target is marginal and a utility slot lacks a heal, equip the win-rate-scaled quantity of the strongest held heal into `utility1_slot`. Once the slot holds a heal it is satisfied, so the grind proceeds; after the stack is consumed (observed via state refresh) it re-fires.

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/provision_marginal_fight.py`
- Create: `tests/test_ai/test_provision_marginal_fight.py`

**Interfaces:**
- Consumes: `marginal_potion_qty_pure` (Task 4); `consumable_supply.best_held_heal` (strongest held heal code — if it does not exist, add a one-line helper there reusing the `hp_restore` scan); `EquipAction` (Task 3); thresholds constants (Task 7 adds `MARGINAL_WINRATE_THRESHOLD`, `FULL_STACK_WINRATE`, `UTILITY_SLOT_MAX_STACK`).
- Produces: `ProvisionMarginalFightGoal(target_monster: str)`.

- [ ] **Step 1: Write failing tests**

```python
from artifactsmmo_cli.ai.goals.provision_marginal_fight import ProvisionMarginalFightGoal

def test_satisfied_when_a_utility_slot_holds_a_heal():
    goal = ProvisionMarginalFightGoal(target_monster="green_slime")
    state = make_state(equipment={"utility1_slot": "small_health_potion"})
    assert goal.is_satisfied(state) is True

def test_unsatisfied_when_no_utility_heal():
    goal = ProvisionMarginalFightGoal(target_monster="green_slime")
    state = make_state(equipment={"utility1_slot": None, "utility2_slot": None})
    assert goal.is_satisfied(state) is False

def test_relevant_actions_keeps_only_equip_of_held_heal_to_utility():
    goal = ProvisionMarginalFightGoal(target_monster="green_slime")
    state = make_state(inventory={"small_health_potion": 100},
                       equipment={"utility1_slot": None})
    gd = _gd_with_consumable("small_health_potion", hp_restore=60)
    actions = [EquipAction("small_health_potion", "utility1_slot", quantity=50),
               EquipAction("copper_helmet", "helmet_slot")]
    kept = goal.relevant_actions(actions, state, gd)
    assert all(a.slot.startswith("utility") for a in kept)
    assert all(a.code == "small_health_potion" for a in kept)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_ai/test_provision_marginal_fight.py -q --no-cov`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the goal**

```python
"""ProvisionMarginalFightGoal: equip win-rate-scaled health potions before a
marginal fight. Satisfied once a utility slot holds a heal; re-fires after the
server consumes the stack (observed via per-cycle state refresh)."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Above the grind (GrindCharacterXP ceiling 45) so provisioning runs before the
# fight, below survival/RestoreHP (110) so healing still preempts.
PROVISION_MARGINAL_VALUE = 50.0

_UTILITY_SLOTS = ("utility1_slot", "utility2_slot")


class ProvisionMarginalFightGoal(Goal):
    """Equip potions into a utility slot for a marginal combat target."""

    def __init__(self, target_monster: str) -> None:
        self._target_monster = target_monster

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else PROVISION_MARGINAL_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return any(state.equipment.get(slot) is not None for slot in _UTILITY_SLOTS)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"utility_slot_filled": True}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        result: list[Action] = []
        for action in actions:
            if (isinstance(action, EquipAction)
                    and action.slot in _UTILITY_SLOTS
                    and game_data.item_stats(action.code) is not None
                    and game_data.item_stats(action.code).hp_restore > 0):
                result.append(action)
        return result

    def serialize(self) -> dict[str, object]:
        return {"type": "ProvisionMarginalFightGoal",
                "target_monster": self._target_monster}

    def __repr__(self) -> str:
        return f"ProvisionMarginalFight({self._target_monster})"
```

(If `desired_state` needs to satisfy the planner's projection, verify `EquipAction.apply` sets `equipment[utility1_slot]`; the planner reaches `is_satisfied` via that. If `WorldState` has no `utility_slot_filled` key, target the concrete slot instead — return `{}` and rely on `is_satisfied`; confirm the arbiter treats a satisfied-after-apply plan as valid, matching `RestoreHPGoal` which targets `{"hp": max_hp}`.)

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_ai/test_provision_marginal_fight.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/provision_marginal_fight.py tests/test_ai/test_provision_marginal_fight.py src/artifactsmmo_cli/ai/consumable_supply.py
git commit -m "$(cat <<'EOF'
feat(combat): ProvisionMarginalFightGoal equips potions before marginal fights

Single-purpose goal: equip the strongest held heal into a utility slot; satisfied
once a slot holds a heal, re-fires after mid-fight consumption. Value 50 (above the
grind, below RestoreHP).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Constants + scale the consumable supply target

**Files:**
- Modify: `src/artifactsmmo_cli/ai/thresholds.py` (add provisioning constants)
- Modify: `src/artifactsmmo_cli/ai/consumable_supply.py` (scale stock target)
- Test: `tests/test_ai/test_consumable_supply.py` (`grep -rl "heal_stock\|HEAL_STOCK_FLOOR" tests/`)

**Interfaces:**
- Produces: `MARGINAL_WINRATE_THRESHOLD = 0.95`, `FULL_STACK_WINRATE = 0.50`, `UTILITY_SLOT_MAX_STACK = 100` in `thresholds.py`. `consumable_supply.heal_stock_target(state, game_data, desired: int) -> int` returning `clamp(desired, HEAL_STOCK_FLOOR, UTILITY_SLOT_MAX_STACK)`; `maintain_consumables_fires` uses it.

- [ ] **Step 1: Add the constants**

In `src/artifactsmmo_cli/ai/thresholds.py`:

```python
# Marginal-fight potion provisioning (spec 2026-06-30).
MARGINAL_WINRATE_THRESHOLD = 0.95  # below this observed win-rate, bring potions
FULL_STACK_WINRATE = 0.50          # at/below this win-rate, bring a full stack
UTILITY_SLOT_MAX_STACK = 100       # openapi.json EquipSchema.quantity.maximum
```

- [ ] **Step 2: Write a failing supply test**

```python
def test_maintain_fires_until_desired_stack_when_marginal_target_demands_more():
    # holds 8 heals; a marginal target wants 50 -> still under-stocked -> fires
    state = make_state(inventory={"small_health_potion": 8})
    gd = _gd_with_craftable_heal("small_health_potion", hp_restore=60, craft_skill="alchemy")
    assert maintain_consumables_fires(state, gd, desired_stock=50) is True

def test_maintain_does_not_fire_when_held_meets_desired():
    state = make_state(inventory={"small_health_potion": 50})
    gd = _gd_with_craftable_heal("small_health_potion", hp_restore=60, craft_skill="alchemy")
    assert maintain_consumables_fires(state, gd, desired_stock=50) is False
```

- [ ] **Step 3: Run — expect FAIL**

Run: `uv run pytest tests/test_ai/test_consumable_supply.py -k "desired" -q --no-cov`
Expected: FAIL — `maintain_consumables_fires` takes no `desired_stock`.

- [ ] **Step 4: Scale the target**

In `consumable_supply.py`, add the clamp helper and thread an optional desired target (default `HEAL_STOCK_FLOOR` preserves current behavior for non-combat callers):

```python
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK


def heal_stock_target(desired: int) -> int:
    """Stock target: at least the floor, at most a full utility stack."""
    return max(HEAL_STOCK_FLOOR, min(desired, UTILITY_SLOT_MAX_STACK))


def maintain_consumables_fires(state: WorldState, game_data: GameData,
                               desired_stock: int = HEAL_STOCK_FLOOR) -> bool:
    """Under the (possibly scaled) stock target AND able to craft a good heal now."""
    if heal_stock(state, game_data) >= heal_stock_target(desired_stock):
        return False
    return best_craftable_heal(state, game_data) is not None
```

Update `MaintainConsumablesGoal` (and any other caller of `maintain_consumables_fires`) to pass the desired stock for the active marginal target when one exists (the goal can accept an optional `desired_stock` ctor arg defaulting to `HEAL_STOCK_FLOOR`; wiring the per-target value is Task 8).

- [ ] **Step 5: Run — expect PASS**

Run: `uv run pytest tests/test_ai/test_consumable_supply.py -q --no-cov`
Expected: PASS. Fix any caller now missing the new positional by relying on the default.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/thresholds.py src/artifactsmmo_cli/ai/consumable_supply.py tests/test_ai/test_consumable_supply.py src/artifactsmmo_cli/ai/goals/maintain_consumables.py
git commit -m "$(cat <<'EOF'
feat(combat): scale heal-stock target toward a full potion stack

Fixed floor=5 cannot feed a 100-potion stack for hard fights. heal_stock_target
clamps the desired count into [5, 100]; maintain_consumables_fires honors it.
Adds MARGINAL_WINRATE_THRESHOLD / FULL_STACK_WINRATE / UTILITY_SLOT_MAX_STACK.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Wire provisioning into `strategy_driver`

Route the `ReachCharLevel` step to `ProvisionMarginalFightGoal` (instead of `GrindCharacterXPGoal`) when the target is marginal and no utility slot holds a heal; otherwise grind as before. This is unproven glue — it computes the win-permille from history and calls `marginal_potion_qty_pure` to decide whether provisioning is wanted.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py:720-762` (the `ReachCharLevel` branch)
- Test: `tests/test_ai/test_strategy_driver.py` (`grep -rl "objective_step_goal\|GrindCharacterXPGoal" tests/`)

**Interfaces:**
- Consumes: `ctx.combat_monster`, `ctx.history` (confirm `SelectionContext` carries `history`; if not, the call site in `player.py` passes `self.history` — thread it into `ctx` or read it where `objective_step_goal` is called). `marginal_potion_qty_pure`, thresholds constants, `consumable_supply.best_held_heal`.
- Produces: provisioning routed before the grind for marginal targets.

- [ ] **Step 1: Write a failing routing test**

```python
def test_marginal_target_routes_to_provision_goal(tmp_path):
    state = make_state(level=3, equipment={"utility1_slot": None, "utility2_slot": None},
                       inventory={"small_health_potion": 100})
    gd = _gd_with_consumable("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    _record_mixed(history, "Fight(green_slime)", wins=8, losses=2)  # 80% < 0.95
    ctx = _ctx(combat_monster="green_slime", history=history)
    goal = objective_step_goal(ReachCharLevel(level=5), state, gd, ctx)
    assert isinstance(goal, ProvisionMarginalFightGoal)
    history.close()

def test_reliable_target_still_grinds(tmp_path):
    state = make_state(level=3, equipment={"utility1_slot": None})
    gd = _gd_with_consumable("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    _record_mixed(history, "Fight(green_slime)", wins=20, losses=0)  # 100% >= 0.95
    ctx = _ctx(combat_monster="green_slime", history=history)
    goal = objective_step_goal(ReachCharLevel(level=5), state, gd, ctx)
    assert isinstance(goal, GrindCharacterXPGoal)
    history.close()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -k "provision or reliable_target" -q --no-cov`
Expected: FAIL — routing not implemented (returns GrindCharacterXPGoal for both).

- [ ] **Step 3: Implement the routing**

In the `ReachCharLevel` branch, just before `return GrindCharacterXPGoal(...)`:

```python
        provision = _marginal_provision_goal(ctx, state, game_data)
        if provision is not None:
            return provision
        return GrindCharacterXPGoal(target_monster=ctx.combat_monster, initial_xp=state.xp)
```

Add the helper near the top of the module (after imports):

```python
def _marginal_provision_goal(ctx: SelectionContext, state: WorldState,
                             game_data: GameData) -> Goal | None:
    """ProvisionMarginalFightGoal when the combat target is observed-marginal and
    no utility slot holds a heal; else None (caller grinds)."""
    monster = ctx.combat_monster
    history = getattr(ctx, "history", None)
    if monster is None or history is None:
        return None
    if any(state.equipment.get(s) is not None for s in ("utility1_slot", "utility2_slot")):
        return None  # already provisioned (or carrying another utility) -> grind
    repr_ = f"Fight({monster})"
    samples = history.sample_count(repr_)
    win_permille = int(history.success_rate(repr_) * 1000)
    held = heal_stock(state, game_data)
    qty = marginal_potion_qty_pure(
        samples, win_permille, MIN_WIN_SAMPLES,
        int(MARGINAL_WINRATE_THRESHOLD * 1000), int(FULL_STACK_WINRATE * 1000),
        UTILITY_SLOT_MAX_STACK, utility_slot_filled=False, held_heal_qty=held)
    if qty <= 0:
        return None
    return ProvisionMarginalFightGoal(target_monster=monster)
```

Add imports at the top of `strategy_driver.py`:

```python
from artifactsmmo_cli.ai.combat import MIN_WIN_SAMPLES
from artifactsmmo_cli.ai.consumable_supply import heal_stock
from artifactsmmo_cli.ai.goals.provision_marginal_fight import ProvisionMarginalFightGoal
from artifactsmmo_cli.ai.marginal_potion_qty import marginal_potion_qty_pure
from artifactsmmo_cli.ai.thresholds import (
    FULL_STACK_WINRATE, MARGINAL_WINRATE_THRESHOLD, UTILITY_SLOT_MAX_STACK,
)
```

If `SelectionContext` has no `history`, add it (it is built in `guards.py`; thread `self.history` from `player.py`'s `_selection_context`). Confirm with `grep -n "history" src/artifactsmmo_cli/ai/tiers/guards.py src/artifactsmmo_cli/ai/player.py`.

- [ ] **Step 4: Run — expect PASS**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -q --no-cov`
Expected: PASS (both new cases + existing).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py src/artifactsmmo_cli/ai/tiers/guards.py src/artifactsmmo_cli/ai/player.py
git commit -m "$(cat <<'EOF'
feat(combat): route marginal char-level targets to potion provisioning

When the combat target's observed win-rate is < 0.95 and no utility slot holds a
heal, return ProvisionMarginalFightGoal before GrindCharacterXP. Win-permille is
computed from history (glue) and fed to the proven marginal_potion_qty core.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Full gate + verification

**Files:** none (verification only).

- [ ] **Step 1: Type + lint**

Run: `uv run mypy src/ && uv run ruff check src/ tests/`
Expected: clean.

- [ ] **Step 2: Full test suite + coverage**

Run: `uv run pytest`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage. Add targeted tests for any uncovered new line.

- [ ] **Step 3: Full formal gate**

Run: `cd formal && ./gate.sh` (serialize — do NOT run while the bot or any `src`-importing process is live; see memory `feedback_serialize_gate_runs`).
Expected: kernel green, all differential tests pass, every mutant killed (including the new `marginal_potion_qty` group and the updated `CRITICAL_HP` anchor), axiom lint clean.

- [ ] **Step 4: Offline plan sanity check**

Reproduce the original failure shape: a level-3 character with an empty head slot and `green_slime` at ~80% observed win-rate. Confirm via the `plan` CLI (memory `project_plan_cli`):

Run: `uv run artifactsmmo plan Robby` (or the offline harness the repo uses)
Expected: for a marginal `green_slime` target with empty utility slots, the selected goal is `ProvisionMarginalFight(green_slime)` (equip potions), and on the following projection the root is `ReachCharLevel` served by `GrindCharacterXP(green_slime)` — NOT `GatherMaterials(copper_helmet)`.

- [ ] **Step 5: Final branch state**

Run: `git log --oneline main..feat/combat-survivability`
Expected: 8 commits (Tasks 1–8). Report status; do not merge or push unless asked.

---

## Self-Review Notes

- **Spec coverage:** Part 1 → Task 2; Part 2 → Task 1; Part 3 trigger/qty curve → Tasks 4–5; EquipAction quantity → Task 3; goal → Task 6; supply scaling → Task 7; wiring → Task 8; full gate → Task 9. All spec sections mapped.
- **Open execution-time lookups (not placeholders — exact targets given):** the Lean oracle dispatcher file (grep command provided), `test_goals.py`/equip/supply/strategy fixture helper names (grep commands provided), and whether `SelectionContext` carries `history` (grep + fallback wiring provided). Each has a concrete resolution step.
- **Type consistency:** `marginal_potion_qty_pure` signature is identical in Tasks 4, 5, 8. `EquipAction(code, slot, quantity)` consistent in Tasks 3, 6, 8. Constant names (`MARGINAL_WINRATE_THRESHOLD`, `FULL_STACK_WINRATE`, `UTILITY_SLOT_MAX_STACK`, `MIN_WIN_SAMPLES`) consistent across Tasks 7, 8.
