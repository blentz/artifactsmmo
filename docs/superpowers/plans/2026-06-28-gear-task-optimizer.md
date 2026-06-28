# Gear Sub-project B — Per-Task Loadout Optimizer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the proved per-monster loadout picker to a per-task `purpose`, route combat callers through it unchanged, and wire a new gather-loadout path so the bot equips the right tool for the skill it gathers.

**Architecture:** Relocate the picker out of `scoring.py` into a new `loadout_picker.py` ABOVE `gear_value` (resolving the sub-project-2 `gear_value → scoring` layering), generalize `pick_loadout(monster)` → `pick_loadout(purpose)` scoring via `gear_value(purpose)`, fold in the dead `pick_gather_loadout`, re-prove per-slot optimality ∀ purpose, generalize `OptimizeLoadoutAction` to carry a purpose key, and add a `GatherAction.cost` loadout penalty (the only new live behavior).

**Tech Stack:** Python 3.13 (`uv` at `~/.local/bin/uv`), Lean 4 (`formal/`), Hypothesis (differential), `formal/diff/mutate.py` (mutation), pytest (`--cov-fail-under=100`).

## Global Constraints

- `uv` at `~/.local/bin/uv`; ALWAYS prefix Python with `uv run`. `git checkout uv.lock` before commit if dirtied.
- DO NOT use inline imports; imports at top. DO NOT use `if TYPE_CHECKING`. DO NOT use `...` imports. NEVER catch `Exception`.
- ONE behavioral class per file (pure data/enum groups may share). Pure proved cores live in `*_core.py`.
- Use only API data or fail with an error — no invented defaults.
- Tests: 0 errors/warnings/skipped (token-gated live tests excepted), 100% coverage. Tests in `tests/`. Real fixtures; never mock the unit under test.
- Formal lockstep: computable Lean `def` + role theorems (∀ inputs) + `Contracts.lean` exact pins + `Manifest.lean` roster + `Audit.lean` axiom-lint entry + differential (Python≡oracle on the HAND def) + mutation (every drop-term mutant killed). No `sorry`/`native_decide`/custom axioms; standard axioms only.
- NEVER run `formal/gate.sh`/`mutate.py` concurrently with anything importing `src`. `git diff src` after every mutation run. Re-run `scripts/extract_lean.py` after ANY source move (the drift gate is strict — relocation shifts line numbers).
- Branch: `feat/gear-task-optimizer` (off main `51d8f0de` = sub-project 2 merged).
- Spec: `docs/superpowers/specs/2026-06-28-gear-task-optimizer-design.md`.

**Verbatim design facts:**
- Purpose value-objects (already exist, `ai/gear_value_core.py`): `Rank`, `Combat(monster_attack: Mapping, monster_resistance: Mapping)`, `Gather(skill: str)`.
- `gear_value(stats, purpose)` (already exists, `ai/gear_value.py`): Rank/Combat/Gather dispatch returning today's `equip_value`/`weapon_score`/`armor_score`/`gather_score` values.
- Picker benefit (higher = better, argmax per slot): Combat/Rank → `gear_value(stats, purpose)`; **Gather → `-gear_value(stats, Gather(skill))`** (negate the signed gather_score so bigger cooldown reduction = bigger benefit; equals today's `tool_value` magnitude on the tool domain — the proven `argmax(-gatherScore) = argmin(gatherScore)` duality).
- `GatheringSkill` enum (4 values mining/woodcutting/fishing/alchemy); `_GATHERING_SKILLS = frozenset(s.value for s in GatheringSkill)` at `item_catalog.py:10`.
- `game_data.resource_skill_level(code) -> (skill, level) | None`; `game_data.all_resource_locations`, `game_data.all_monster_locations`, `game_data.monster_attack(m)`, `game_data.monster_resistance(m)`.

---

### Task 1: Relocate the picker (mechanical, no behavior change)

Move the picker out of `scoring.py` into a new module so it can sit above `gear_value` (Task 2 makes it call `gear_value`). NO signature or behavior change.

**Files:**
- Create: `src/artifactsmmo_cli/ai/equipment/loadout_picker.py`
- Modify: `src/artifactsmmo_cli/ai/equipment/scoring.py` (remove the moved functions), `src/artifactsmmo_cli/ai/equipment/__init__.py` (re-export from new location), the 4 importers: `ai/combat.py:12`, `ai/actions/optimize_loadout.py:14`, `ai/actions/combat.py:19`, `ai/goals/grind_character_xp.py` (its `pick_loadout` import)
- Test: existing suite (no new test; this is a move)

**Interfaces:**
- Produces: `loadout_picker.pick_loadout(monster_code, state, game_data)`, `loadout_picker.pick_gather_loadout(skill, state, game_data)` (unchanged signatures this task).

- [ ] **Step 1: Create `loadout_picker.py`, move the functions**

Move VERBATIM from `scoring.py` into `loadout_picker.py`: `pick_loadout`, `pick_gather_loadout`, `_candidates_for_slot`, `_ordered_slots` (and their imports: `ITEM_TYPE_TO_SLOTS`/`DUPLICATE_SLOT_TYPES` from `actions.equip`, `ownership` from `equipment.realizable_loadout`, `weapon_score`/`armor_score`/`gather_score` from `equipment.scoring`, `ItemStats`/`GameData`/`WorldState`). `loadout_picker` imports `scoring` for the scorers — direction `loadout_picker → scoring`, no cycle.

- [ ] **Step 2: Trim `scoring.py`**

Remove the 4 moved functions from `scoring.py`; keep `weapon_score`/`weapon_score_raw`/`armor_score`/`gather_score`/`pick_gather_loadout`? — NO, `pick_gather_loadout` moves too. Keep only the score functions + their `*_pure` cores in `scoring.py`. Ensure `scoring.py` no longer references the moved helpers.

- [ ] **Step 3: Update `equipment/__init__.py` + the 4 importers**

`equipment/__init__.py`: import `pick_loadout` from `loadout_picker` (keep it in `__all__`). The 4 importer files change `from artifactsmmo_cli.ai.equipment.scoring import pick_loadout` → `from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout`.

- [ ] **Step 4: Verify no behavior change + no cycle**

Run: `~/.local/bin/uv run python -c "import artifactsmmo_cli.ai.equipment.loadout_picker, artifactsmmo_cli.ai.gear_value, artifactsmmo_cli.ai.equipment.scoring; print('NO CYCLE')"` then `~/.local/bin/uv run pytest --cov-fail-under=100 -q`.
Expected: NO CYCLE; full suite green (pure move). `~/.local/bin/uv run mypy --strict` on touched files. `git checkout uv.lock`.

- [ ] **Step 5: Re-extract (line shift) + commit**

Run `~/.local/bin/uv run python scripts/extract_lean.py` (the move shifts `scoring.py` line numbers referenced by `Extracted/EquipmentScoring.lean`). Confirm only sha/line-comment headers changed (no def body). `cd formal && lake build` clean.

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/equipment/loadout_picker.py src/artifactsmmo_cli/ai/equipment/scoring.py src/artifactsmmo_cli/ai/equipment/__init__.py src/artifactsmmo_cli/ai/combat.py src/artifactsmmo_cli/ai/actions/optimize_loadout.py src/artifactsmmo_cli/ai/actions/combat.py src/artifactsmmo_cli/ai/goals/grind_character_xp.py formal/Formal/Extracted/EquipmentScoring.lean
git commit -m "refactor(gear): relocate loadout picker to loadout_picker.py (above gear_value)"
```

---

### Task 2: Generalize `pick_loadout` to a purpose + migrate combat callers

Change the picker to score via `gear_value(purpose)`, fold in `pick_gather_loadout`, and route the 4 combat callers through `Combat(monster)`. Combat behavior is bit-identical (regression-locked).

**Files:**
- Modify: `src/artifactsmmo_cli/ai/equipment/loadout_picker.py` (signature + scoring), the 4 callers (build `Combat`), `src/artifactsmmo_cli/ai/equipment/__init__.py`
- Test: `tests/ai/test_loadout_picker_purpose.py` (new)

**Interfaces:**
- Consumes: `gear_value(stats, purpose)`, `Rank`/`Combat`/`Gather` (`ai/gear_value.py`, `ai/gear_value_core.py`).
- Produces: `pick_loadout(purpose, state, game_data) -> dict[str, str | None]` (purpose replaces monster_code); `pick_gather_loadout` REMOVED (folded).

- [ ] **Step 1: Write the regression + gather tests**

```python
# tests/ai/test_loadout_picker_purpose.py
"""pick_loadout(Combat(m)) reproduces the old per-monster pick exactly; Gather equips a tool."""

from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather
from artifactsmmo_cli.ai.item_catalog import ItemStats
# build a WorldState + GameData fixture mirroring the existing pick_loadout tests
# (open tests/ai/test_*loadout*/test_*scoring* for the fixture helper to reuse).


def test_combat_purpose_matches_legacy_per_monster_pick(loadout_fixture):
    state, game_data, monster = loadout_fixture  # monster has attack/resistance
    purpose = Combat(game_data.monster_attack(monster), game_data.monster_resistance(monster))
    # Legacy behavior is the per-slot argmax of weapon_score/armor_score — assert the
    # generalized picker reproduces the SAME loadout dict the old code produced for this
    # monster (capture the expected dict from the fixture's known-good loadout).
    result = pick_loadout(purpose, state, game_data)
    assert result == loadout_fixture.expected_combat_loadout


def test_gather_purpose_equips_best_tool(gather_fixture):
    state, game_data = gather_fixture  # owns axe (woodcutting -10) + a plain weapon
    result = pick_loadout(Gather("woodcutting"), state, game_data)
    assert result["weapon_slot"] == "iron_axe"  # the tool with the strongest woodcutting effect
```

> Reuse the existing loadout-test fixtures (search `tests/` for `pick_loadout` to find them). The combat assertion must compare against the ACTUAL old picks (capture them before changing the picker, or assert equality with a freshly-built `weapon_score`/`armor_score` argmax) — a real regression lock, not a tautology.

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_loadout_picker_purpose.py -v`
Expected: FAIL — `pick_loadout` still takes `monster_code`.

- [ ] **Step 3: Generalize the picker**

In `loadout_picker.py`: change `def pick_loadout(monster_code, state, game_data)` → `def pick_loadout(purpose, state, game_data)`. Replace the `monster_atk`/`monster_res` derivation + the per-slot `weapon = slot=="weapon_slot"` weapon_score/armor_score branch with a single benefit function:

```python
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Gather

def _benefit(stats: ItemStats, purpose: object) -> int:
    # Higher = better, argmax per slot. Combat/Rank score directly; Gather negates
    # the signed gather_score so a bigger cooldown reduction is a bigger benefit
    # (argmax(-gatherScore) == argmin(gatherScore) on the tool domain — the proven
    # PurposeRouting duality; armor candidates score 0 for Gather, so armor slots
    # keep their current item under the strict-improvement rule).
    value = gear_value(stats, purpose)
    return -value if isinstance(purpose, Gather) else value
```

Score every feasible candidate by `_benefit(cand, purpose)` (argmax); keep the empty-slot `best_score <= 0 → skip` gate, the strict-improvement vs current rule, the `_forbidden`/ownership/dual-ring cap, and `_ordered_slots` EXACTLY as they are. DELETE `pick_gather_loadout` (folded — `pick_loadout(Gather(skill))` replaces it). `gear_value` import makes `loadout_picker → gear_value → scoring` (no cycle; verified Task 1).

- [ ] **Step 4: Migrate the 4 combat callers**

Each currently calls `pick_loadout(monster_code, state, game_data)`. Change to `pick_loadout(Combat(game_data.monster_attack(m), game_data.monster_resistance(m)), state, game_data)` (import `Combat`):
- `ai/combat.py:90` (predict_win — `m = monster_code`)
- `ai/actions/combat.py:129` (FightAction.cost — `m = self.monster_code`)
- `ai/actions/optimize_loadout.py:46` (`m = self.target_monster_code`)
- `ai/goals/grind_character_xp.py:48` (`m = self._target_monster`)

- [ ] **Step 5: Run tests + full suite**

Run: `~/.local/bin/uv run pytest tests/ai/test_loadout_picker_purpose.py -v` then `~/.local/bin/uv run pytest --cov-fail-under=100 -q`. Any existing pick_loadout/pick_gather test updates to the purpose API (combat picks must be UNCHANGED; if a combat-loadout test now differs, STOP — that's a real regression, not an intended change). `~/.local/bin/uv run mypy --strict` on touched files. `git checkout uv.lock`.

- [ ] **Step 6: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/equipment/loadout_picker.py src/artifactsmmo_cli/ai/equipment/__init__.py src/artifactsmmo_cli/ai/combat.py src/artifactsmmo_cli/ai/actions/optimize_loadout.py src/artifactsmmo_cli/ai/actions/combat.py src/artifactsmmo_cli/ai/goals/grind_character_xp.py tests/ai/test_loadout_picker_purpose.py
git commit -m "feat(gear): generalize pick_loadout to purpose (Combat/Gather/Rank); fold gather picker"
```

---

### Task 3: Lean re-proof — unified `pickSlot` optimal ∀ purpose

Re-state the per-slot optimality through the purpose-parameterized picker; fold `pickGatherSlot` (argmin) into the unified `pickSlot` (argmax of negated benefit) via the proven duality.

**Files:**
- Modify: `formal/Formal/PurposeRouting.lean` and/or `formal/Formal/EquipmentScoring.lean` (unified `pickSlot` + theorem), `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`, `formal/Formal/Audit.lean`
- Test: (formal only; differential lands Task 5)

**Interfaces:**
- Consumes: existing `EquipmentScoring.pickSlot`/`pickslot_score_optimal`, `PurposeRouting.pickGatherSlot`/`pickGatherSlot_score_optimal`, the `tool_value = |gather_score|` / argmin-argmax duality already in these modules.

- [ ] **Step 1: State the unified theorem**

Read `EquipmentScoring.lean` + `PurposeRouting.lean` first. Add a purpose-parameterized `pickSlot` (or a `benefit : Item → Int` parameterization) and prove `pickSlot_score_optimal_purpose`: the slot's chosen item maximizes the purpose-benefit over feasible candidates, for any benefit function — then instantiate it for Combat (`gear_value Combat`), Rank (`gear_value Rank`), and Gather (`-gatherScore`, where the existing `pickGatherSlot_score_optimal` minimization is the same claim via `argmax(-f) = argmin f`). Keep the existing theorem names alive (the unified theorem should SUBSUME them, or keep them as instantiations).

- [ ] **Step 2: Prove + axiom-lint + pin**

`cd formal && lake build` (no sorry; standard axioms). Add the new theorem to `Manifest.lean` (#check), `Contracts.lean` (exact-statement pin), and `Audit.lean` (`#print axioms` line — the safety lint scans Audit.lean; do NOT skip this, per the sub-project-2 lesson). Verify `RealizableLoadout`/`LoadoutProjection`/`OwnedCount` contracts still elaborate (purpose-independent, unchanged).

- [ ] **Step 3: Commit**

```bash
git add formal/Formal/PurposeRouting.lean formal/Formal/EquipmentScoring.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean formal/Formal/Audit.lean
git commit -m "feat(gear): Lean — unified pickSlot optimality forall purpose (fold pickGatherSlot via duality)"
```

---

### Task 4: Gather wiring — OptimizeLoadout purpose + factory + GatherAction.cost penalty

The only new live behavior: the bot equips the best tool for the skill it gathers.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/optimize_loadout.py` (add `target_skill`, purpose dispatch in `_swap_plan`, `__repr__`), `src/artifactsmmo_cli/ai/actions/factory.py` (per-monster → `Combat` key unchanged; ADD per-`GatheringSkill` `OptimizeLoadoutAction(target_skill=...)`), `src/artifactsmmo_cli/ai/actions/gathering.py` (`GatherAction.cost` loadout penalty)
- Test: `tests/ai/test_gather_loadout.py` (new)

**Interfaces:**
- Consumes: `pick_loadout(Combat(...)/Gather(skill), …)` (Task 2), `resource_skill_level`, `GatheringSkill`.

- [ ] **Step 1: Write the gather-wiring tests**

```python
# tests/ai/test_gather_loadout.py
"""GatherAction.cost penalizes a sub-optimal gather tool; OptimizeLoadout(Gather) swaps it in."""

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.gear_value_core import Gather


def test_gather_cost_penalizes_suboptimal_tool(gather_cost_fixture):
    state, game_data = gather_cost_fixture  # owns iron_axe (woodcutting) but wears a sword;
    # resource is a woodcutting tree.
    worn_sword = GatherAction(resource_code="ash_tree", locations=frozenset({(0, 0)}))
    cost_suboptimal = worn_sword.cost(state, game_data)
    # with the axe already equipped the same gather has NO loadout penalty:
    state_axe = equip(state, "iron_axe", "weapon_slot")  # helper
    cost_optimal = worn_sword.cost(state_axe, game_data)
    assert cost_suboptimal > cost_optimal


def test_optimize_loadout_gather_swaps_in_tool(gather_cost_fixture):
    state, game_data = gather_cost_fixture
    act = OptimizeLoadoutAction(target_skill="woodcutting", game_data=game_data)
    assert act.is_applicable(state, game_data)
    new = act.apply(state, game_data)
    assert new.equipment["weapon_slot"] == "iron_axe"


def test_optimize_loadout_combat_unchanged(combat_loadout_fixture):
    state, game_data, monster = combat_loadout_fixture
    act = OptimizeLoadoutAction(target_monster_code=monster, game_data=game_data)
    # combat path still works via the monster key
    assert isinstance(act.apply(state, game_data).equipment, dict)
```

> Reuse existing gather/loadout fixtures (search `tests/` for `GatherAction` and `OptimizeLoadoutAction`). Add a `equip` helper or reuse one.

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_gather_loadout.py -v`
Expected: FAIL — `target_skill` unknown / no gather penalty.

- [ ] **Step 3: Generalize `OptimizeLoadoutAction`**

Add `target_skill: str = ""` beside `target_monster_code: str = ""`. In `_swap_plan`, build the purpose from whichever key is set:

```python
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout

def _swap_plan(self, state, game_data):
    if self.target_monster_code:
        purpose = Combat(game_data.monster_attack(self.target_monster_code),
                         game_data.monster_resistance(self.target_monster_code))
    elif self.target_skill:
        purpose = Gather(self.target_skill)
    else:
        return {}   # documented no-target sentinel
    optimal = pick_loadout(purpose, state, game_data)
    return {slot: new for slot, new in optimal.items() if state.equipment.get(slot) != new}
```

Update `__repr__` to show whichever key is set: `OptimizeLoadout({self.target_monster_code or 'gather:'+self.target_skill})`. The two-pass apply/execute/realizability assertions are unchanged (purpose-agnostic).

- [ ] **Step 4: Factory — create per gather skill**

In `actions/factory.py`, the per-monster loop keeps `OptimizeLoadoutAction(target_monster_code=monster_code, game_data=game_data)`. After the resource loop, add one Gather optimizer per gather skill:

```python
from artifactsmmo_cli.ai.item_catalog import _GATHERING_SKILLS
for skill in sorted(_GATHERING_SKILLS):
    actions.append(OptimizeLoadoutAction(target_skill=skill, game_data=game_data))
```

- [ ] **Step 5: `GatherAction.cost` loadout penalty (mirror FightAction.cost)**

In `GatherAction.cost`, after the base/banked-regather cost, add a gather-loadout penalty mirroring `FightAction.cost` (`actions/combat.py:124-132`):

```python
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.gear_value_core import Gather
# ... inside cost(), after computing `base`:
skill_req = game_data.resource_skill_level(self.resource_code)
if skill_req is not None:
    skill, _ = skill_req
    optimal = pick_loadout(Gather(skill), state, game_data)
    if any(state.equipment.get(slot) != code for slot, code in optimal.items()):
        base += GATHER_LOADOUT_PENALTY
return base
```

Define `GATHER_LOADOUT_PENALTY` at module top (mirror the magnitude/justification of `LOADOUT_PENALTY` in `actions/combat.py` — small enough not to dominate the banked-regather penalty, large enough to prompt a worthwhile swap; document the chosen value). The penalty fires ONLY on `GatherAction` (no other action carries it → never mid-combat).

- [ ] **Step 6: Run tests + full suite + mypy**

Run: `~/.local/bin/uv run pytest tests/ai/test_gather_loadout.py -v` then `~/.local/bin/uv run pytest --cov-fail-under=100 -q`, `~/.local/bin/uv run mypy --strict` on the 3 touched files. `git checkout uv.lock`.

- [ ] **Step 7: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/actions/optimize_loadout.py src/artifactsmmo_cli/ai/actions/factory.py src/artifactsmmo_cli/ai/actions/gathering.py tests/ai/test_gather_loadout.py
git commit -m "feat(gear): wire gather loadout — OptimizeLoadout(Gather) + GatherAction.cost penalty"
```

---

### Task 5: Differential + mutation + extraction + full gate

Bind the generalized picker to the proved Lean def, give it mutation teeth, re-sync extraction, certify the gate.

**Files:**
- Create/Modify: `formal/diff/test_loadout_picker_diff.py`, `formal/Oracle.lean` (handler for the unified `pickSlot`/benefit if not already covered), `formal/diff/mutate.py` (mutants for the generalized picker benefit + direction)
- Re-extract any drifted `Extracted/*.lean`

**Interfaces:**
- Consumes: the picker (Task 2), the unified Lean theorem (Task 3).

- [ ] **Step 1: Differential**

```python
# formal/diff/test_loadout_picker_diff.py
"""Generalized pick_loadout per-slot benefit ≡ Lean oracle over random purpose+pool."""

from hypothesis import given, strategies as st
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout  # or the _benefit core
from formal.diff.oracle_client import run_oracle  # match the sibling helper
# Feed random (purpose ∈ {Combat,Gather,Rank}, owned item pool, monster/skill) to BOTH
# the live picker's per-slot benefit ordering and the oracle's unified pickSlot; assert the
# chosen item per slot agrees. NO unique=True.
```

> Match how the existing EquipmentScoring/PurposeRouting differential is structured (open `formal/diff/` for the sibling). If the existing pick differential already exercises `pickSlot`, extend it for the purpose parameter rather than duplicating.

Run: `cd formal && ~/.local/bin/uv run pytest diff/test_loadout_picker_diff.py -v` → PASS.

- [ ] **Step 2: Mutation**

In `formal/diff/mutate.py`, add drop-term mutants for the generalized per-slot benefit: the `-value` negation for Gather (drop the negation → Gather picks the WORST tool → killed by the gather test/differential), the empty-slot `>0` gate, the strict-improvement comparison. Each must be killed. Run the mutation runner (match its flag); `git diff src` empty after.

- [ ] **Step 3: Re-extract + DecideKey/Realizable contracts**

Run `~/.local/bin/uv run python scripts/extract_lean.py` (Tasks 2/4 moved/changed sources). Confirm only headers/line-comments drift. `cd formal && lake build Formal.RealizableLoadout Formal.Contracts` — the realizability/dual-ring contracts must still elaborate (purpose-independent).

- [ ] **Step 4: Full suite + full gate**

Run: `~/.local/bin/uv run pytest --cov-fail-under=100`. Then, nothing else importing `src`: `cd formal && ./gate.sh` → green end-to-end (build, no-sorry, axiom-lint incl. the new pickSlot theorem in Audit, manifest, contracts, differential, mutation, extraction-drift). `git diff src` empty; `git checkout uv.lock`.

- [ ] **Step 5: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add formal/ tests/
git commit -m "test(gear): differential + mutation + full-gate lock for purpose-generalized picker"
```

---

## Final review (after all tasks)

Dispatch the whole-branch reviewer over `git merge-base main HEAD..HEAD`. Verify:
- Picker relocated to `loadout_picker.py`; `loadout_picker → gear_value → scoring` layering (no cycle); `pick_gather_loadout` GONE (folded), no surviving caller.
- `pick_loadout(Combat(m))` reproduces today's combat picks EXACTLY (regression-locked); the SOLE new behavior is the gather path.
- Gather wiring: `GatherAction.cost` penalizes a sub-optimal tool; `OptimizeLoadout(Gather(skill))` created per `GatheringSkill`; the penalty fires only on gather (never mid-combat).
- Soundness: differential calls the live picker; oracle runs the hand unified `pickSlot`; the theorem is pinned in `Contracts.lean` AND axiom-linted in `Audit.lean`; mutation kills the Gather negation + the gates; `RealizableLoadout` carried over unweakened.
- Then `superpowers:finishing-a-development-branch`.

## Self-review notes (plan author)

- **Spec coverage:** generalized picker → Task 2; relocation/cycle-fix → Task 1; combat-caller migration → Task 2; gather wiring (cost penalty + factory) → Task 4; Lean re-proof → Task 3; differential/mutation/gate/extraction → Task 5. All covered.
- **OptimizeLoadoutAction carries a purpose KEY** (`target_monster_code`/`target_skill`), not the dict-bearing `Combat` object — keeps `repr` stable (history keys on it) and `gear_value`'s `Combat` pure. Documented in Task 4 Step 3.
- **Gather benefit = `-gear_value(Gather)`** (negate the signed gather_score) is the single purpose-specific line; everything else in the picker is purpose-agnostic. Named identically in Task 2 (`_benefit`) and Task 5 (mutant target).
- **Honest open seams** (match-the-sibling, not placeholders): the loadout/gather test fixtures, `oracle_client` helper, `mutate.py` flag, the existing pick differential's structure, `GATHER_LOADOUT_PENALTY` magnitude (justify like `LOADOUT_PENALTY`) — each says "open the existing file and match," correct for in-file conventions.
- **Drift gate**: every task that moves/edits a source extracted to Lean re-runs `extract_lean.py` (Task 1 and Task 5 call it explicitly) — the sub-project-2 lesson (a line-shift reddens the gate).
