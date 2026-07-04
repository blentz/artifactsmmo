# Duplicate Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat `artifact` as a duplicate-allowed slot type exactly as `ring` is, so the bot may equip and acquire up to `min(3 slots, ownership)` copies of the same artifact across artifact1/2/3.

**Architecture:** Single-constant change — add `"artifact"` to `DUPLICATE_SLOT_TYPES` (equip.py), the one source of truth every dup-aware site already reads generically (equip cap, `loadout_picker` ownership cap, `empty_slot_rank_fills`, acquisition targeting, `OptimizeLoadout`). The Lean `RealizableLoadout` invariant is already parameterized over `dupAllowed`; `InventoryCaps.slotCount` already maps artifact→3. Work is unit tests, artifact witness theorems, differential-fixture + mutation updates, and confirming no acquisition stall for the unacquirable `novice_guide`.

**Tech Stack:** Python 3.13 (`uv run`), pytest + hypothesis, Lean 4 (`lake`), the `formal/` differential + mutation gate.

## Global Constraints

- ALWAYS prefix Python commands with `uv run`.
- Imports at top of file only — no inline imports, no `...`/relative imports, no `if TYPE_CHECKING`.
- ONE behavioral class per file. NEVER catch `Exception`. No multi-level error handling.
- Tests under `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- `formal/gate.sh` and `formal/mutate.py` run SERIALIZED — never concurrent with anything importing `src`.
- Use only API data or fail with an error — no defaulting.
- SERVER RULE (accepted risk): same-code artifact duplication is asserted, not live-probed. Acceptance is formal-gate green + a recorded probe trigger; do NOT claim runtime-proven (no character can hold 2 of a duplicable artifact yet). The dedicated repeated-action-failure StuckDetector is NOT merged, so there is no livelock safety net — the probe trigger is the mitigation.
- Ownership cap is load-bearing: a dup code may fill at most `min(slot_count, ownership(code))` slots — never over-equip beyond owned copies (this is what keeps the unique `novice_guide` at one slot).

---

### Task 1: Core constant + equip-side behavior + realizability

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/equip.py:26` (the constant)
- Test: `tests/ai/test_equip_owned_gear.py` or a new `tests/ai/test_duplicate_artifacts.py` (equip + pick_loadout dup behavior)
- Modify: `formal/Formal/RealizableLoadout.lean` (artifact witness theorems)
- Modify: `formal/diff/` fixtures that assume ring-only dup; `formal/diff/mutate.py` (artifact-dup mutant)

**Interfaces:**
- Consumes: `DUPLICATE_SLOT_TYPES` (equip.py); `EquipAction(code, slot)`; `pick_loadout` + `Rank`; `loadout_picker._dup_allowed`/`_forbidden` (cap = `ownership(code)`, already generic).
- Produces: `DUPLICATE_SLOT_TYPES = frozenset({"ring", "artifact"})`. No new symbols — every consumer already reads the set.

- [ ] **Step 1: Write the failing equip-side tests**

Create `tests/ai/test_duplicate_artifacts.py`. Use the `_make_state`/`_ALL_SLOTS`/GameData fixture pattern from `tests/ai/test_loadout_picker_purpose.py` (copy the helper — intentional test-support duplication). A dup artifact fixture: `ItemStats(code="perfect_pearl", level=1, type_="artifact", hp_bonus=10)` (level 1 to dodge the level gate in a level-1 state).

```python
from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, EquipAction
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Rank


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "perfect_pearl": ItemStats(code="perfect_pearl", level=1, type_="artifact", hp_bonus=10),
    }
    return gd


def test_artifact_is_duplicate_allowed() -> None:
    assert "artifact" in DUPLICATE_SLOT_TYPES


def test_pick_loadout_fills_three_artifact_slots_when_three_owned() -> None:
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 3},
                        equipment={"artifact1_slot": None, "artifact2_slot": None,
                                   "artifact3_slot": None})
    result = pick_loadout(Rank, state, gd)
    assert result["artifact1_slot"] == "perfect_pearl"
    assert result["artifact2_slot"] == "perfect_pearl"
    assert result["artifact3_slot"] == "perfect_pearl"


def test_pick_loadout_one_owned_fills_one_slot_only() -> None:
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 1},
                        equipment={"artifact1_slot": None, "artifact2_slot": None,
                                   "artifact3_slot": None})
    result = pick_loadout(Rank, state, gd)
    filled = [s for s in ("artifact1_slot", "artifact2_slot", "artifact3_slot")
              if result[s] == "perfect_pearl"]
    assert len(filled) == 1  # ownership cap: never over-equip


def test_equip_second_copy_into_sibling_slot_applicable() -> None:
    gd = _gd()
    state = _make_state(level=1, inventory={"perfect_pearl": 1},
                        equipment={"artifact1_slot": "perfect_pearl", "artifact2_slot": None})
    act = EquipAction(code="perfect_pearl", slot="artifact2_slot")
    assert act.is_applicable(state, gd) is True  # dup type: worn-elsewhere does not 485-block
```

- [ ] **Step 2: Run — verify failure.** `uv run pytest tests/ai/test_duplicate_artifacts.py -q --no-cov` → the dup tests FAIL (artifact not yet in the set → cap 1 → single slot; is_applicable False for the 2nd copy). `test_artifact_is_duplicate_allowed` FAILs.

- [ ] **Step 3: Add the constant.** In `src/artifactsmmo_cli/ai/actions/equip.py:26`:

```python
DUPLICATE_SLOT_TYPES: frozenset[str] = frozenset({"ring", "artifact"})
```

Update the adjacent comment (equip.py:19-25) to note artifacts join rings as server-dup-allowed (asserted; probe pending — see the spec's probe trigger).

- [ ] **Step 4: Run — verify pass.** `uv run pytest tests/ai/test_duplicate_artifacts.py -q --no-cov` → all pass.

- [ ] **Step 5: Add Lean artifact witnesses + update fixtures.** In `formal/Formal/RealizableLoadout.lean`, add artifact witness theorems mirroring the ring ones (`pickLoadout_dual_ring_fills_when_two_owned` → a triple-artifact-fills-when-three-owned; `pickLoadout_single_ring_no_dup_fill` → single-artifact-no-dup-fill). The core invariant is generic over `dupAllowed` so no invariant proof changes. Update any `formal/diff/` fixture that passes a ring-only `dupAllowed` so the oracle receives the production set (artifact included). Drive `cd formal && lake build` clean (no sorry/new axioms).

- [ ] **Step 6: Mutation.** In `formal/diff/mutate.py`, add a mutant that drops `"artifact"` from `DUPLICATE_SLOT_TYPES` — KILLED by `test_equip_second_copy_into_sibling_slot_applicable` / `test_pick_loadout_fills_three_artifact_slots_when_three_owned` (owned unit tests). Confirm the anchor string is unique. Run `uv run python formal/mutate.py` (serialized) → 0 survivors for the new mutant.

- [ ] **Step 7: Commit.**

```bash
git add src/artifactsmmo_cli/ai/actions/equip.py tests/ai/test_duplicate_artifacts.py \
        formal/Formal/RealizableLoadout.lean formal/diff/ formal/diff/mutate.py
git commit -m "feat(gear): allow duplicate artifacts (same code in multiple artifact slots), mirroring rings"
```

---

### Task 2: Acquisition side — multi-copy targeting + no unacquirable stall

Confirm the dup constant also correctly drives ACQUISITION (buy/craft extra copies of a duplicable *acquirable* artifact) and does NOT stall on the unacquirable `novice_guide`.

**Files:**
- Test: `tests/test_ai/test_progression.py` (or the progression goal's test module — locate via `grep -rln "UpgradeEquipment\|_worn_in_other_slot" tests/`)
- Modify (only if a test reveals a gap): `src/artifactsmmo_cli/ai/goals/progression.py`

**Interfaces:**
- Consumes: `progression.py:_worn_in_other_slot` (returns `False` for dup types — already generic), `_find_craftable_upgrade_target` (iterates craftable recipes only), `_find_inventory_upgrade` (owned copies only).

- [ ] **Step 1: Write the acquisition tests.**

Add two tests to the progression test module:

```python
def test_worn_dup_artifact_does_not_veto_sibling_target() -> None:
    """A duplicable artifact worn in artifact1 does NOT block targeting a 2nd
    copy for artifact2 (mirrors the dual-ring carve-out)."""
    # Build a GameData with a CRAFTABLE dup artifact (type_="artifact", a recipe),
    # state wearing one copy in artifact1_slot, artifact2_slot empty. Assert the
    # UpgradeEquipment target selection yields the artifact for artifact2_slot
    # (i.e. _worn_in_other_slot returns False for it).

def test_unacquirable_worn_artifact_not_targeted_no_stall() -> None:
    """novice_guide (no craft, no owned spare) worn in artifact1 is never a
    craftable/inventory upgrade target for artifact2/3 — no stall."""
    # GameData with novice_guide (no recipe), state wearing it in artifact1,
    # 0 spare in inventory. Assert neither _find_craftable_upgrade_target nor
    # _find_inventory_upgrade returns a novice_guide target.
```

Follow the exact fixture/construction shape used by the existing progression tests (read one first — do not invent GameData/WorldState fields).

- [ ] **Step 2: Run — observe.** `uv run pytest <progression test module> -k "dup_artifact or unacquirable" -q --no-cov`. The `no_stall` test should already PASS (craftable path skips no-recipe items; inventory path needs an owned copy). The `sibling_target` test should PASS if the generic `_worn_in_other_slot` already covers artifacts (it reads `DUPLICATE_SLOT_TYPES`) — confirming Task 1's constant flows through with no progression change.

- [ ] **Step 3: If `sibling_target` FAILS**, the acquisition path has a ring-specific assumption. Fix it in `progression.py` to read `DUPLICATE_SLOT_TYPES` generically (do not hardcode "ring"), re-run, and note the change. If it PASSES, no production change — the tests are regression locks proving the constant is sufficient.

- [ ] **Step 4: Commit.**

```bash
git add <progression test module> src/artifactsmmo_cli/ai/goals/progression.py
git commit -m "test(gear): dup-artifact acquisition targets sibling slot; unacquirable artifact no-stall"
```

---

### Task 3: Probe trigger, honest runtime note, full verification

**Files:** Memory + verification only (no production diff unless the gate finds a gap).

- [ ] **Step 1: Record the probe trigger in memory.** Create `/home/blentz/.claude/projects/-home-blentz-git-artifactsmmo/memory/project_duplicate_artifacts.md` documenting: merged state, the accepted-unverified server rule, and the LIVE PROBE TRIGGER — "the first time any character owns ≥2 of a tradeable artifact, confirm the 2nd-copy equip returns HTTP 200 (not 485); if 485, revert `\"artifact\"` from DUPLICATE_SLOT_TYPES." Add the one-line pointer to `MEMORY.md`. Link `[[project_dual_ring_carveout]]`, `[[project_equip_owned_gear]]`.

- [ ] **Step 2: Full suite + coverage.** `uv run pytest --cov=src --cov-report=term-missing -q` → 0 errors/warnings/skips, 100% coverage.

- [ ] **Step 3: Typecheck.** `uv run mypy src` → no errors.

- [ ] **Step 4: Formal gate (serialized).** `cd formal && ./gate.sh` → green (lake build, axiom lint, differentials incl. dup-artifact, mutation, coverage). Nothing importing `src` running concurrently.

- [ ] **Step 5: Honest runtime status.** In the final report, state plainly: the decision logic is proven green, but runtime activation is NOT demonstrable now (no character can hold 2 of a duplicable lvl20+ artifact). Do NOT claim runtime-proven. The probe trigger (Step 1) is the deferred live confirmation. Optionally run `uv run artifactsmmo plan Robby` to confirm the change did not perturb Robby's current behavior (he still equips the single `novice_guide`; no regression), and record the output.

---

## Self-Review

- **Spec coverage:** constant → Task 1; equip cap / ownership-bound / no-over-equip → Task 1 tests; realizability generic + artifact witnesses → Task 1 Step 5; acquisition dup-target + novice_guide no-stall → Task 2; demand economy — `InventoryCaps.slotCount` already maps artifact→3 (no change needed; Task 3 gate confirms); mutation → Task 1 Step 6; server-rule probe trigger + honest runtime deferral → Task 3 Steps 1/5; testing set → Tasks 1/2. All covered.
- **Placeholders:** Task 1 fully coded. Task 2 test bodies are described precisely (build a craftable dup artifact / a no-recipe artifact, assert target selection) rather than fully coded because they must mirror the existing progression-test fixture shape the implementer reads first — the assertions and the exact conditions are specified. Formal steps are contract-specified with file:line anchors + `lake build`/`gate.sh` acceptance (proof text compiler-authored by design).
- **Type consistency:** `DUPLICATE_SLOT_TYPES: frozenset[str]`, `EquipAction(code, slot)`, `pick_loadout(Rank, state, gd) -> dict[str, str|None]`, ownership cap `min(slot_count, ownership(code))` — consistent across tasks and matching the ring carve-out they mirror.

## Risk note

The only new runtime behavior that could misfire is a real server rejection of duplicate artifacts (premise wrong). With no merged repeated-action-failure detector, that would be an equip retry loop. The probe trigger (Task 3 Step 1) is the mitigation; escalate to revert the constant if a 485 is ever observed on a 2nd-copy artifact equip.
