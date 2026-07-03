# Equip Owned Gear Into Empty Slots — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make owned gear with strictly-positive value actually equip into empty equipment slots at runtime, via a new `EquipOwnedGoal` selected by the arbiter above the grind tier — fixing the observed `novice_guide` case and activating the (currently runtime-inert) merged gather-artifact fix.

**Architecture:** A new value-banded goal `EquipOwnedGoal` whose fill target is `pick_loadout(Rank)` restricted to currently-empty slots (precomputed at construction, since `Goal.is_satisfied` gets no `game_data`). It is wired into `StrategyArbiter._build_candidates` in the COLLECT band (above STEP/grind, below GUARD/survival), so it owns the equip decision outside the re-arm cost economics that make `OptimizeLoadout` (cost `10·n`) never worth a flat `5.0` penalty. Because a live `pick_loadout(Rank)` caller is new, the deferred Rank picker differential binding is closed.

**Tech Stack:** Python 3.13 (`uv run`), pytest + hypothesis, Lean 4 (`lake`), the `formal/` differential + mutation + decide_key gate.

## Global Constraints

- ALWAYS prefix Python commands with `uv run`.
- Imports at top of file only — no inline imports, no `...`/relative imports, no `if TYPE_CHECKING`.
- ONE behavioral class per file. NEVER catch `Exception`. No multi-level error handling.
- Tests under `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- `formal/gate.sh` and `formal/mutate.py` run SERIALIZED — never concurrent with anything importing `src` (including a running bot).
- Use only API data or fail with an error — no defaulting.
- **RUNTIME ACTIVATION IS A HARD ACCEPTANCE CRITERION** (Task 4). Green tests + gate do NOT prove the behavior fires. The goal MUST be observed selected and equipping on a live/simulated plan before this work is "done." A change that is correct-but-inert is a failed task.
- Band values (arbiter_select.py:37-41): `BAND_GUARD=0 < BAND_COLLECT=1 < BAND_STEP=2 < BAND_FALLBACK_STEP=3 < BAND_DISCRETIONARY=4` (lower band = higher priority). Numeric goal values: grind/step `GrindCharacterXPGoal` ≤ 45.0 (PRIORITY_CEILING); survival guards = 70.0 (`CraftReliefGoal._GUARD_VALUE`). New goal value `EQUIP_GEAR_VALUE = 60.0` (between step and survival; band placement already guarantees ordering over step).

---

### Task 1: Close the Rank picker differential binding

Adding a live `pick_loadout(Rank)` caller (Task 3's fill computation) means the currently-deferred Rank picker binding must be closed so no unproven decision logic ships. The value-level `rank_value` ↔ `runRankValue` binding already exists (`formal/diff/test_gear_value_diff.py:41` `test_rank_value_matches_oracle`); the gap is only the PICKER purpose.

**Files:**
- Modify: `formal/Oracle.lean` (`runLoadoutPicker` ~306-334 — add `purposeKind == 2` rank branch; per-item rank inputs)
- Modify: `formal/diff/test_loadout_picker_diff.py` (add a Rank-purpose picker property test; update the deferral comment at ~23-32 to "closed")
- Modify: `formal/diff/mutate.py` (anchors)

**Interfaces:**
- Consumes: production `pick_loadout(Rank, state, gd)` (already functional — `_benefit` returns `gear_value(stats, Rank)` for non-Gather purposes); the proven `Formal.GearValue.rankValue` (GearValue.lean:36), `purposeBenefit (.rank rankOf)`, `pickSlot_purpose_rank_optimal` (GearValue.lean:221).
- Produces: an oracle `runLoadoutPicker` that accepts `purposeKind == 2` (rank) and a differential test asserting live per-slot `gear_value(stats, Rank)` ≡ oracle rank benefit, bit-exact.

> Lean/oracle proof deltas are authored via the compiler-guided workflow (lean4:prove). Acceptance is a clean `lake build` + green differential, not hand-copied proof terms.

- [ ] **Step 1: Add the failing Rank picker differential test**

In `test_loadout_picker_diff.py`, add `test_rank_pick_matches_lean`: generate a random owned pool of items across slot types with random `combat_raw`-contributing stats (attack/resistance/crit) AND utility stats (wisdom/prospecting/hp_bonus/inventory_space/haste), plus `subtype` tool/non-tool. Drive `pick_loadout(Rank, state, gd)`. For the chosen item in each slot, request the oracle with `purposeKind=2` and assert the pick's live `gear_value(chosen, Rank)` equals the oracle's returned rank benefit (bit-exact). The per-item oracle block must carry the `rankValue` inputs `[combat_raw, wisdom, prospecting, inventory_space, haste, is_tool]` (the same 6 `runRankValue` at Oracle.lean:232 consumes), computed on the Python side via the existing `combat_raw_of` / `ItemStats` fields.

- [ ] **Step 2: Run it — expect failure**

Run: `uv run pytest formal/diff/test_loadout_picker_diff.py -k rank -q`
Expected: FAIL — `runLoadoutPicker` currently handles only `purposeKind` 0/1; `purposeKind=2` is unhandled.

- [ ] **Step 3: Extend `runLoadoutPicker` for the rank purpose**

In `formal/Oracle.lean` `runLoadoutPicker`, add a `purposeKind == 2` branch constructing `Formal.GearValue.Purpose.rank rankOf`, where `rankOf : Item → Int` is built per item from the extended block's rank inputs via `Formal.GearValue.rankValue` (reuse the exact def `runRankValue` uses). Read the extra per-item rank ints alongside the existing block (extend the stride as Task-2 of the prior branch did for `isUtilityFill`). Keep `purposeKind` 0/1 byte-unchanged. Drive `cd formal && lake build` to a clean compile (no `sorry`, no new axiom).

- [ ] **Step 4: Run the differential — expect pass**

Run: `uv run pytest formal/diff/test_loadout_picker_diff.py -q`
Expected: PASS — rank picks bind bit-exact; the weapon/gather tests still pass. Update the deferral comment (~23-32) to record the binding is now closed by the live `EquipOwnedGoal` caller.

- [ ] **Step 5: Refresh mutation anchors**

Update `formal/diff/mutate.py` anchors shifted by the oracle edit. Run `cd formal && lake build` clean.

- [ ] **Step 6: Commit**

```bash
git add formal/Oracle.lean formal/diff/test_loadout_picker_diff.py formal/diff/mutate.py
git commit -m "formal(gear): close deferred Rank picker differential binding (purposeKind=2)"
```

---

### Task 2: `EquipOwnedGoal` production goal + unit tests

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/equip_owned_gear.py`
- Test: `tests/ai/test_equip_owned_gear.py`

**Interfaces:**
- Consumes: `Goal` (goals/base.py: abstract `value(self, state, game_data, history=None)`, `is_satisfied(self, state)`, `desired_state(self, state, game_data)`; overridable `relevant_actions`, `max_depth`); `EquipAction(code: str, slot: str, quantity: int = 1)` (actions/equip.py); `WorldState.equipment: dict[str, str | None]`; `pick_loadout` + `Rank` (used by Task 3's mapper, not the goal itself).
- Produces: `class EquipOwnedGoal(Goal)` with dataclass field `fills: dict[str, str]` (slot→code, precomputed empty-slot Rank picks); module const `EQUIP_GEAR_VALUE = 60.0`. Task 3 constructs `EquipOwnedGoal(fills=...)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/ai/test_equip_owned_gear.py`. Reuse the `_make_state` / `_ALL_SLOTS` pattern from `tests/ai/test_loadout_picker_purpose.py` (copy the helper — a test-support duplication is acceptable; do not import test internals across modules).

```python
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.goals.equip_owned_gear import EQUIP_GEAR_VALUE, EquipOwnedGoal
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}

def _make_state(inventory=None, equipment=None) -> WorldState:
    eq = dict(_ALL_SLOTS)
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="c", level=10, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={}, x=0, y=0, inventory=inventory or {}, inventory_max=20,
        equipment=eq, cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )

def test_unsatisfied_and_valued_when_fill_pending() -> None:
    goal = EquipOwnedGoal(fills={"artifact1_slot": "novice_guide"})
    state = _make_state(inventory={"novice_guide": 1}, equipment={"artifact1_slot": None})
    assert goal.is_satisfied(state) is False
    assert goal.value(state, GameData()) == EQUIP_GEAR_VALUE

def test_satisfied_when_target_slot_filled() -> None:
    goal = EquipOwnedGoal(fills={"artifact1_slot": "novice_guide"})
    state = _make_state(equipment={"artifact1_slot": "novice_guide"})
    assert goal.is_satisfied(state) is True
    assert goal.value(state, GameData()) == 0.0

def test_desired_state_targets_fill_slots() -> None:
    goal = EquipOwnedGoal(fills={"artifact1_slot": "novice_guide"})
    state = _make_state(inventory={"novice_guide": 1})
    assert goal.desired_state(state, GameData()) == {"equipment": {"artifact1_slot": "novice_guide"}}

def test_relevant_actions_emit_equip_per_fill() -> None:
    goal = EquipOwnedGoal(fills={"artifact1_slot": "novice_guide", "weapon_slot": "wooden_staff"})
    state = _make_state(inventory={"novice_guide": 1, "wooden_staff": 1})
    acts = goal.relevant_actions([], state, GameData())
    assert {(a.code, a.slot) for a in acts} == {("novice_guide", "artifact1_slot"), ("wooden_staff", "weapon_slot")}
    assert all(isinstance(a, EquipAction) for a in acts)

def test_empty_fills_is_satisfied_zero_value() -> None:
    goal = EquipOwnedGoal(fills={})
    state = _make_state()
    assert goal.is_satisfied(state) is True
    assert goal.value(state, GameData()) == 0.0
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/ai/test_equip_owned_gear.py -q --no-cov`
Expected: FAIL — `equip_owned_gear` module does not exist.

- [ ] **Step 3: Implement the goal**

Create `src/artifactsmmo_cli/ai/goals/equip_owned_gear.py`:

```python
"""EquipOwnedGoal: equip owned positive-value gear into empty equipment slots.

The fill target is computed by the arbiter mapper (pick_loadout(Rank) restricted
to empty slots) and passed in, because Goal.is_satisfied receives no game_data —
mirroring the precomputed-target pattern in goals/progression.py. The goal owns
the equip decision as a first-class objective, so it fires independent of the
FightAction/GatherAction re-arm cost economics (LOADOUT_PENALTY < OptimizeLoadout
cost) that otherwise leave owned gear unequipped.
"""

from dataclasses import dataclass, field

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

EQUIP_GEAR_VALUE = 60.0
"""Priority between the grind/step ceiling (45) and the survival guard floor (70).
Placed in the COLLECT band by the arbiter, so it outranks the step/grind goal and
free gear equips before more grinding, without preempting survival/combat guards."""


@dataclass
class EquipOwnedGoal(Goal):
    """Equip each owned item in `fills` into its (currently empty) slot."""

    fills: dict[str, str] = field(default_factory=dict)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else EQUIP_GEAR_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return all(state.equipment.get(slot) == code for slot, code in self.fills.items())

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"equipment": dict(self.fills)}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return [EquipAction(code=code, slot=slot) for slot, code in self.fills.items()]

    def __repr__(self) -> str:
        return f"EquipOwnedGear({sorted(self.fills.items())})"
```

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/ai/test_equip_owned_gear.py -q --no-cov`
Expected: PASS (5/5).

- [ ] **Step 5: Typecheck + commit**

```bash
uv run mypy src/artifactsmmo_cli/ai/goals/equip_owned_gear.py
git add src/artifactsmmo_cli/ai/goals/equip_owned_gear.py tests/ai/test_equip_owned_gear.py
git commit -m "feat(gear): EquipOwnedGoal — equip owned gear into empty slots"
```

---

### Task 3: Arbiter wiring (COLLECT band) + fill computation + formal lockstep

Wire `EquipOwnedGoal` into `StrategyArbiter._build_candidates` so it is selected above the grind tier. The fill computation (`pick_loadout(Rank)` ∩ empty slots, minus reserved items) is new decision logic and gets extract + differential + mutation; adding a `MeansKind` requires the decide_key lockstep (`Formal/DecideKey.lean` + Oracle + `decide_key`).

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/means.py` (~56 — add a `MeansKind` member to the COLLECT tuple)
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (~1171-1230 `_build_candidates`; the `map_means` path — compute fills, construct `EquipOwnedGoal`, append in the COLLECT band)
- Modify: `src/artifactsmmo_cli/ai/` fill-computation core (new pure function `empty_slot_rank_fills_pure` in a focused module, e.g. `equipment/empty_slot_fills.py`) — the decision logic to extract
- Modify: `formal/Formal/DecideKey.lean`, `formal/Oracle.lean`, `formal/diff/` (decide_key differential), `formal/diff/mutate.py`

**Interfaces:**
- Consumes: `EquipOwnedGoal(fills)` (Task 2); `pick_loadout(Rank, state, gd)` bound by Task 1; the existing reservation view used by the crafting path (locate via `grep -n "reserv" src/artifactsmmo_cli/ai/strategy_driver.py` and reuse it).
- Produces: `empty_slot_rank_fills(state, game_data, reserved) -> dict[str, str]` = `{slot: code for slot, code in pick_loadout(Rank, state, gd).items() if state.equipment.get(slot) is None and code is not None and code not in reserved}`; the arbiter appends `EquipOwnedGoal(fills)` as a COLLECT candidate when `fills` is non-empty.

- [ ] **Step 1: Write the failing fill-computation unit test**

Create `tests/ai/test_empty_slot_fills.py` asserting `empty_slot_rank_fills`:
- empty artifact slot + owned `novice_guide` (hp_bonus/wisdom/prospecting > 0) → `{"artifact1_slot": "novice_guide"}`;
- all slots full → `{}`;
- filled slot with a better owned item → NOT included (empty-only);
- item present in `reserved` → excluded;
- two empty ring slots + one owned ring → ring assigned to exactly one slot (realizability, from pick_loadout's cap).
Use a `GameData` fixture assigning `gd._item_stats` directly (established pattern).

- [ ] **Step 2: Run — verify failure.** `uv run pytest tests/ai/test_empty_slot_fills.py -q --no-cov` → FAIL (module missing).

- [ ] **Step 3: Implement `empty_slot_rank_fills`** in `src/artifactsmmo_cli/ai/equipment/empty_slot_fills.py`:

```python
"""Empty-slot Rank fills: the best owned item per currently-empty slot."""

from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.world_state import WorldState


def empty_slot_rank_fills(state: WorldState, game_data: GameData,
                          reserved: frozenset[str]) -> dict[str, str]:
    """{slot: code} for each currently-empty slot the owned pool can fill with a
    strictly-positive-Rank item, excluding reserved item codes. Reuses
    pick_loadout(Rank)'s proven realizability / one-slot-per-code, then keeps only
    empty slots (never displaces an incumbent)."""
    picked = pick_loadout(Rank, state, game_data)
    return {
        slot: code
        for slot, code in picked.items()
        if state.equipment.get(slot) is None and code is not None and code not in reserved
    }
```

- [ ] **Step 4: Run — verify pass.** `uv run pytest tests/ai/test_empty_slot_fills.py -q --no-cov` → PASS.

- [ ] **Step 5: Wire into the arbiter.** In `strategy_driver.py:_build_candidates`, in the `map_means` COLLECT path, compute `fills = empty_slot_rank_fills(state, game_data, reserved)` and, when non-empty, append `Candidate(EquipOwnedGoal(fills), band=BAND_COLLECT, ...)` matching the existing collect-candidate construction shape. Add the `MeansKind.EQUIP_OWNED_GEAR` member to the COLLECT tuple in `means.py` and its `map_means` case. Follow the existing collect wiring verbatim for the `Candidate` fields.

- [ ] **Step 6: Decide_key + differential lockstep.** A new `MeansKind` changes the arbiter's decision key. Update `Formal/DecideKey.lean` (the means/decide-key model), `Oracle.lean`, and the decide_key differential in lockstep so production `decide_key` ≡ model over the new candidate — per the recycle-surplus / strategy-arbiter lesson. Extract the `empty_slot_rank_fills` decision core if the gate requires it in the proven subset. Author via the compiler-guided Lean workflow; `lake build` clean, no new axioms.

- [ ] **Step 7: Mutation.** Add mutants: (a) drop the empty-only filter (`state.equipment.get(slot) is None`) — killed by the "does not displace filled slot" unit test; (b) drop the `reserved` exclusion — killed by the reserved-item test; (c) flip the band placement — killed by Task 4's activation assertion or an arbiter-ordering unit test. Each mutant bound to an OWNED unit test group.

- [ ] **Step 8: Commit.**

```bash
git add src/artifactsmmo_cli/ai/equipment/empty_slot_fills.py tests/ai/test_empty_slot_fills.py \
        src/artifactsmmo_cli/ai/tiers/means.py src/artifactsmmo_cli/ai/strategy_driver.py \
        formal/Formal/DecideKey.lean formal/Oracle.lean formal/diff/ formal/diff/mutate.py
git commit -m "feat(gear): select EquipOwnedGoal in COLLECT band; empty-slot Rank fills + decide_key lockstep"
```

---

### Task 4: RUNTIME ACTIVATION GATE (hard acceptance criterion)

Prove the goal actually fires and equips — not just that unit tests pass. This is the criterion the previous gather fix failed.

**Files:** Test: `tests/ai/test_equip_owned_gear_activation.py` (simulated-plan assertion); plus a live observation.

- [ ] **Step 1: Simulated-plan activation test.** Write `test_equip_owned_goal_selected_over_grind`: build a `WorldState` mirroring Robby (level 10, `novice_guide` in inventory, all artifact slots empty, otherwise combat-capable so a grind step exists), run the real arbiter (`StrategyArbiter.select` or `plan_once` against a `GameData` seeded from the snapshot fixture — see `reference_snapshot_regen` / existing arbiter tests for how to build one), and assert: (a) the selected goal is `EquipOwnedGoal`, (b) `plan[0]` is `EquipAction(code="novice_guide", slot="artifact1_slot")`. This test is the regression lock that the goal is reachable and out-ranks grind.

- [ ] **Step 2: Run it.** `uv run pytest tests/ai/test_equip_owned_gear_activation.py -q --no-cov` → PASS. If it FAILS because grind still out-ranks (band/value wrong) or the goal isn't built (mapper wiring), fix Task 3 — do not weaken this test.

- [ ] **Step 3: Live plan observation.** Run `uv run artifactsmmo plan Robby` and confirm the printed `selected_goal` is `EquipOwnedGear(...)` and the plan's first action is `Equip(novice_guide → artifact1_slot)`. Capture the output in the report. (If Robby's slots were filled by a prior run, pick any character with an owned unequipped artifact + empty slot, or note the state that would trigger it.)

- [ ] **Step 4: Live execution observation (the definitive check).** With user awareness that this mutates the live character, run one execution cycle (`uv run artifactsmmo play Robby` for a single cycle, or the project's single-step run) and confirm via `uv run artifactsmmo character status Robby` that `Artifact 1` changed from `None` to `novice_guide`. Record before/after equipment. This is the concrete proof the fix is NOT inert.

- [ ] **Step 5: Commit the activation test.**

```bash
git add tests/ai/test_equip_owned_gear_activation.py
git commit -m "test(gear): runtime-activation gate — EquipOwnedGoal selected + equips novice_guide"
```

---

### Task 5: Full-suite + formal gate verification

**Files:** none (verification only).

- [ ] **Step 1: Full suite + coverage.** `uv run pytest --cov=src --cov-report=term-missing -q` → 0 errors/warnings/skips, 100% coverage.
- [ ] **Step 2: Typecheck.** `uv run mypy src` → no errors.
- [ ] **Step 3: Formal gate (serialized).** `cd formal && ./gate.sh` → green (lake build, axiom lint, differentials incl. the new Rank picker + decide_key, mutation, coverage). Nothing importing `src` may run concurrently.
- [ ] **Step 4: Confirm the merged gather fix is now live.** Re-state in the report: with `EquipOwnedGoal` firing, an owned artifact equips during any plan (combat/gather/craft), which is exactly what `project_gather_artifact_fill` needed to stop being inert.

---

## Self-Review

- **Spec coverage:** goal → Task 2; Rank ruler + empty-only + reservations → Task 3 (`empty_slot_rank_fills`); value band → `EQUIP_GEAR_VALUE`/Task 3 wiring; independence from penalty economics → arbiter selection (Task 3); Rank differential closure → Task 1; runtime activation (the spec's whole point) → Task 4 hard gate; formal (structural scorer-generic, new decision logic extract+diff+mutation, non-vacuous) → Tasks 1/3/5; testing set → Tasks 2/3/4. Fallback (artifact-only) is documented in the spec as an escape hatch if Task 1's Rank binding blocks — surface as a BLOCKED escalation, do not silently narrow.
- **Placeholders:** Python (Tasks 2/3) fully coded. Formal tasks (1/3/6-step) are contract-specified with exact file:line anchors and `lake build`/`gate.sh` acceptance — proof text is compiler-authored by design, not omitted detail. `Candidate`/`map_means` field shapes say "match the existing collect construction verbatim" because the implementer reads the live shape at that line — the arbiter internals are not reproduced here to avoid drift.
- **Type consistency:** `EquipOwnedGoal(fills: dict[str, str])`, `EQUIP_GEAR_VALUE=60.0`, `empty_slot_rank_fills(state, game_data, reserved: frozenset[str]) -> dict[str, str]`, `EquipAction(code, slot)`, `desired_state -> {"equipment": {slot: code}}` — consistent across tasks and matching progression.py's equipment-predicate convention.

## Risk note (read before executing)

Task 3's decide_key/`MeansKind` lockstep is the highest-risk step (a known minefield — a new `MeansKind` perturbs the proven decision ladder). Task 4 is placed immediately after so inertness/mis-ranking is caught at once. If Task 3's lockstep proves intractable, escalate BLOCKED rather than shipping a goal that never selects — and consider the spec's documented artifact-only fallback (reuses the proven `armor_score({})` binding, no Rank picker work) as a reduced-scope first cut that still rescues the inert merged fix.
