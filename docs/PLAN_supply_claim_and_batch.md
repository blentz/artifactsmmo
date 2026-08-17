# Supply Claim and Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop two characters producing the same sibling request in parallel, and stop a supply commitment chasing a target that grows while it works.

**Architecture:** Two independent fixes to the existing `SUPPLY_BANK` path, neither touching how it fires. (1) An exclusive per-item production claim, mirroring the `TurnInClaim` shape already in the coordination store, so exactly one sibling serves a request. (2) A batched, non-receding target, mirroring `currency_grind_target_pure`'s milestone construction, so the goal's identity holds still while the character works through a batch.

**Tech Stack:** Python 3.13, `uv`, SQLModel/SQLite (coordination tables in the shared learning DB), pytest.

**Spec:** This document.

## Evidence this plan is built on

All measured from `~/.cache/artifactsmmo/learning.db` — the durable source. **Do not use `play-trace-*.jsonl` for anything here; the user deletes them periodically.**

One request, `SupplyBank(spruce_wood×60)`, served simultaneously by two characters:

```
R2D2   225 GatherAction + 14 DepositAllAction
Robby  231 GatherAction +  8 DepositAllAction
spruce_wood actually gathered under that goal: 456 units, against an ask of 60
```

**456 units for a 60-unit request — 7.6x over-production**, and ~456 cycles of fleet time, roughly nine hours at the measured 52 cycles/hour/character.

The target churned on the same item while they worked:

```
x50 → x10 → x60 → x61 → x40 → x37 → x59 → x41 → x81 → x116 → x100 → x97 → x129
```

`SupplyBank(spruce_wood×60)` alone ran 478 cycles across the two characters.

**Two distinct defects, compounding:**

1. **No production claim.** Nothing stops every eligible sibling serving the same request. `BankStockClaim` covers withdrawals and `TurnInClaim` covers the currency turn-in; production has no equivalent. The `SUPPLY_BANK` design has always listed this as a known limit — this is that limit, measured.
2. **A receding, churning target.** `_pick_supply_target` returns `(item, banked + demand, demand)` and `SupplyBankGoal.is_satisfied` targets an absolute banked count. Both are recomputed every cycle against a demand the asker keeps republishing, so the goal's identity moves (`x60` → `x81` → `x116` → `x129`) and the commitment never converges. The quantity is part of the goal's repr, so each move also churns sticky-commit keying — the same failure `currency_grind_target_pure` was written to fix for vendor currencies.

## Global Constraints

- Python 3.13. Every command under `uv run`.
- **One behavioural class per file.** Pure-data/enum modules may share a file.
- No inline imports; no `if TYPE_CHECKING`; never `except Exception` (catching `SQLAlchemyError` is the established pattern in the coordination store).
- Use only API/game data or fail with an error.
- Tests in `tests/`. 0 errors, 0 warnings, 0 skipped, **100% statement coverage** — verify WITH coverage using the narrow per-file form and check the missing-line list against the lines you ADD; do not eyeball it. Never run the whole `tests/test_ai/` suite under coverage: it exceeds ten minutes.
- Full gate: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo $?` — redirect and read `$?` directly; a pipeline reports the PIPE's status and has hidden a real GATE FAIL here.
- Mutation anchors refresh in the SAME commit as the code they point at; `--check-anchors` must stay green. Note a `--only` filter matches against the SOURCE PATH and the TEST PATH — check your substring actually selects the group you mean.
- **Never verify anything against trace files.** Query `learning.db`.
- Run everything in the FOREGROUND. Never two implementers at once.

## Non-goals

- **Not** changing when `SUPPLY_BANK` fires (`_fires` and its asymmetric arm are untouched).
- **Not** changing `SUPPLY_DEMAND_MIN`, the priority band, or the rung's position in `COLLECT_REWARD_ORDER`.
- **Not** changing what demand is published — the asker's own unmet closure stays as it is.

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/learning/models.py` (modify) | `SupplyClaim` table, unique on `item_code`. |
| `src/artifactsmmo_cli/ai/learning/coordination_store.py` (modify) | `claim_supply` / `supply_claim_holder` / `release_supply`. |
| `src/artifactsmmo_cli/ai/supply_batch_target.py` (new) | Pure: the next non-receding batch milestone. |
| `src/artifactsmmo_cli/ai/thresholds.py` (modify) | `SUPPLY_BATCH` constant with its derivation. |
| `src/artifactsmmo_cli/ai/player.py` (modify) | Skip sibling-claimed items, claim what is picked, renew and release; build the goal on the batch target. |

**No migration is required.** `SupplyClaim` is a NEW table, and `SQLModel.metadata.create_all` creates missing tables — the hazard that needed a migration last time was ADDING A COLUMN to an existing one. Confirm this holds rather than assuming it.

---

### Task 1: The production claim

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py`
- Modify: `src/artifactsmmo_cli/ai/learning/coordination_store.py`
- Test: `tests/test_ai/test_coordination_store.py`

**Interfaces:**
- Produces:
  - `SupplyClaim` table — `id`, `character` (indexed), `item_code` (indexed), `claimed_at`, `expires_at`, with `UniqueConstraint("item_code", name="uq_supply_claim_item")`.
  - `CoordinationStore.claim_supply(item_code: str, now: datetime) -> bool` — True iff this character now holds it. Renews in place for the current holder.
  - `CoordinationStore.supply_claim_holder(item_code: str, now: datetime) -> str | None`
  - `CoordinationStore.release_supply(item_code: str) -> None`

**THE UNIQUENESS IS ON THE ITEM, NOT ON (character, item_code).** That is what makes the claim exclusive across characters and is the entire point. `(character, item_code)` would let all five characters "win" their own claim and the fix would be a no-op that still passes a naive test. `TurnInClaim` (models.py) is the correct precedent — read it and `CoordinationStore.claim_turn_in` before writing; `RoleLease` is deliberately the OPPOSITE (non-exclusive) and is the wrong model here.

Renewal matters: a production run spans hundreds of cycles, so the holder re-claiming each cycle must succeed and extend the expiry rather than lock itself out. TTL is `DEMAND_TTL_SECONDS` (600) — the coordination system's one liveness clock; do not add a second.

- [ ] **Step 1: Write the failing tests**

```python
def test_only_one_character_can_hold_a_supply_claim(tmp_path):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    r2d2 = CoordinationStore(db_path=db, character="R2D2")
    robby = CoordinationStore(db_path=db, character="Robby")

    assert r2d2.claim_supply("spruce_wood", now) is True
    assert robby.claim_supply("spruce_wood", now) is False
    assert robby.supply_claim_holder("spruce_wood", now) == "R2D2"


def test_the_holder_can_renew_without_locking_itself_out(tmp_path):
    """A production run spans hundreds of cycles; the holder re-claims every one."""
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    r2d2 = CoordinationStore(db_path=db, character="R2D2")

    assert r2d2.claim_supply("spruce_wood", now) is True
    later = now + timedelta(seconds=120)
    assert r2d2.claim_supply("spruce_wood", later) is True
    with SqlSession(r2d2._engine) as s:
        rows = s.exec(select(SupplyClaim)).all()
    assert len(rows) == 1
    assert rows[0].expires_at > _iso(now)


def test_an_expired_claim_frees_the_item_for_a_sibling(tmp_path):
    """A character that dies mid-run must not hold the request hostage."""
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="R2D2").claim_supply("spruce_wood", now)
    later = now + timedelta(seconds=DEMAND_TTL_SECONDS + 1)

    assert CoordinationStore(db_path=db, character="Robby").claim_supply(
        "spruce_wood", later) is True


def test_releasing_frees_the_item_immediately(tmp_path):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    r2d2 = CoordinationStore(db_path=db, character="R2D2")
    r2d2.claim_supply("spruce_wood", now)
    r2d2.release_supply("spruce_wood")

    assert CoordinationStore(db_path=db, character="Robby").claim_supply(
        "spruce_wood", now) is True


def test_releasing_an_item_another_character_holds_is_a_no_op(tmp_path):
    """Release must be scoped to this character's own row, or a loser could
    evict the winner and both would produce again — the bug this fixes."""
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="R2D2").claim_supply("spruce_wood", now)
    CoordinationStore(db_path=db, character="Robby").release_supply("spruce_wood")

    assert CoordinationStore(db_path=db, character="Robby").supply_claim_holder(
        "spruce_wood", now) == "R2D2"
```

Write `_iso` however the file's existing tests format an expiry for comparison; reuse their helper if one exists rather than adding a second.

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -k supply_claim -v --no-cov`
Expected: FAIL — `'CoordinationStore' object has no attribute 'claim_supply'`.

- [ ] **Step 3: Implement the table and the three methods**

Model `claim_supply` on `claim_turn_in`. Confirm while you are there that `create_all` really does create the new table on an EXISTING database — add a test that opens a store against a DB file created before the table existed and claims successfully, if the file's existing tests give you a pattern for that.

- [ ] **Step 4: Run the file, then coverage**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v --no-cov`, then
`uv run pytest tests/test_ai/test_coordination_store.py -q --cov=src/artifactsmmo_cli/ai/learning/coordination_store --cov=src/artifactsmmo_cli/ai/learning/models --cov-report=term-missing --cov-fail-under=0`

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py \
        src/artifactsmmo_cli/ai/learning/coordination_store.py \
        tests/test_ai/test_coordination_store.py
git commit -m "feat(coordination): one producer per sibling request"
```

---

### Task 2: The non-receding batch target

**Files:**
- Create: `src/artifactsmmo_cli/ai/supply_batch_target.py`
- Modify: `src/artifactsmmo_cli/ai/thresholds.py`
- Test: `tests/test_ai/test_supply_batch_target.py`

**Interfaces:**
- Produces:
  - `thresholds.SUPPLY_BATCH = 10`
  - `supply_batch_target_pure(banked: int, demand: int) -> int` — the absolute banked count this commitment targets.

**The property that matters is that the target does not move while the character works.** `currency_grind_target_pure` (`ai/currency_grind_target.py`) exists for exactly this reason and its docstring explains the failure it fixed: a target recomputed on every acquisition churns the goal's repr, which is part of its identity, resetting sticky-commit keying each cycle. Read it first; this is the same construction applied to a sibling's demand instead of a vendor price.

Rules:
- Return the next multiple of `SUPPLY_BATCH` strictly above `banked`, clamped so it never exceeds `banked + demand` (never produce more than was asked).
- `demand <= 0` returns `banked` — nothing to do.
- Always strictly greater than `banked` while `demand > 0`, so the goal can never be trivially satisfied and spin.

`SUPPLY_BATCH = 10` is deliberately the same number as `SUPPLY_DEMAND_MIN`: the bulk arm only admits requests of at least ten units, so a ten-unit batch is one arm's-worth of work and never splits a qualifying request into a stutter of tiny commitments. Say that in the constant's comment.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from artifactsmmo_cli.ai.supply_batch_target import supply_batch_target_pure
from artifactsmmo_cli.ai.thresholds import SUPPLY_BATCH


def test_nothing_demanded_targets_what_is_already_banked():
    assert supply_batch_target_pure(banked=17, demand=0) == 17


def test_a_small_demand_is_capped_at_what_was_asked():
    # Never produce more than the ask, even though the batch would reach 20.
    assert supply_batch_target_pure(banked=17, demand=1) == 18


def test_a_large_demand_advances_one_batch_at_a_time():
    assert supply_batch_target_pure(banked=0, demand=60) == SUPPLY_BATCH
    assert supply_batch_target_pure(banked=7, demand=60) == SUPPLY_BATCH


def test_the_target_does_not_move_while_working_through_a_batch():
    """The defect this exists to prevent: a target recomputed each cycle churns
    the goal's repr, which is part of its identity."""
    targets = {supply_batch_target_pure(banked=b, demand=60 - b) for b in range(0, SUPPLY_BATCH)}
    assert targets == {SUPPLY_BATCH}


def test_crossing_a_batch_boundary_advances_exactly_one_batch():
    assert supply_batch_target_pure(banked=SUPPLY_BATCH, demand=60) == 2 * SUPPLY_BATCH


@pytest.mark.parametrize("banked", [0, 3, 10, 57])
def test_the_target_always_exceeds_what_is_banked_while_demand_remains(banked):
    assert supply_batch_target_pure(banked, demand=5) > banked
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_ai/test_supply_batch_target.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run and cover**

Run: `uv run pytest tests/test_ai/test_supply_batch_target.py -v --no-cov`, then the narrow coverage form on the new module — it must be 100% with no missing lines.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/supply_batch_target.py \
        src/artifactsmmo_cli/ai/thresholds.py \
        tests/test_ai/test_supply_batch_target.py
git commit -m "feat(ai): a supply commitment that does not chase a moving target"
```

---

### Task 3: Wire both into the player

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_pick_supply_target`, `_update_coordination`)
- Test: `tests/test_ai/test_player_coordination.py`

**Interfaces:**
- Consumes: `claim_supply` / `supply_claim_holder` / `release_supply` (Task 1), `supply_batch_target_pure` (Task 2).
- Produces: no signature change. `_pick_supply_target` still returns `(item_code, target_banked_quantity, unmet_demand)` — but the second element is now the BATCH target, and the choice skips items a sibling has claimed.

Behaviour, in order:
1. While ranking candidates, **skip any item whose `supply_claim_holder` is another character**. Its own claim does not exclude it — that is how a multi-cycle run continues.
2. Having chosen, **claim it** (`claim_supply`). If the claim is LOST — a sibling won the same cycle — treat that item as unavailable and take the next candidate rather than producing into a race. A lost claim is normal contention, not an error.
3. **Renew every cycle** the same item stays chosen. `claim_supply` renews in place for the holder, so step 2 covers this; do not add a second path.
4. **Release when this character stops serving that item** — a different item is chosen, or no target is picked at all. A claim left behind blocks the fleet for up to `DEMAND_TTL_SECONDS`.
5. Build the returned quantity with `supply_batch_target_pure(banked, unmet_demand)` instead of `banked + demand`.

Keep the `serves_item` gate and the asymmetric-first ordering exactly as they are — they decide WHICH request, and this task only decides whether it is available and how much of it to commit to.

- [ ] **Step 1: Write the failing tests**

```python
def test_an_item_a_sibling_is_already_producing_is_skipped(tmp_path):
    """The measured bug: R2D2 and Robby each spent ~230 gathers on the same
    60-unit spruce_wood request."""
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="R2D2").claim_supply("spruce_wood", NOW)
    player, _ = _player_with_coordination(tmp_path, "Robby", db=db)

    target = player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}), {"spruce_wood": 1})

    assert target is None


def test_my_own_claim_does_not_block_me_from_continuing(tmp_path):
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "R2D2", db=db)
    store.claim_supply("spruce_wood", NOW)

    target = player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}), {"spruce_wood": 1})

    assert target is not None and target[0] == "spruce_wood"


def test_choosing_an_item_claims_it_for_this_character(tmp_path):
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)

    player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}), {"spruce_wood": 1})

    assert store.supply_claim_holder("spruce_wood", NOW) == "Robby"


def test_the_target_is_one_batch_not_the_whole_demand(tmp_path):
    """456 units were produced against a 60-unit ask because the commitment was
    the whole demand against a moving bank count."""
    db = str(tmp_path / "coord.db")
    player, _ = _player_with_coordination(tmp_path, "Robby", db=db)

    target = player._pick_supply_target(
        {"spruce_wood": 60}, {"spruce_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20}, bank_items={"spruce_wood": 0}),
        {"spruce_wood": 1})

    assert target is not None
    assert target[1] == SUPPLY_BATCH      # not 60
    assert target[2] == 60                # the unmet demand is reported unchanged


def test_switching_items_releases_the_previous_claim(tmp_path):
    db = str(tmp_path / "coord.db")
    player, store = _player_with_coordination(tmp_path, "Robby", db=db)
    store.claim_supply("spruce_wood", NOW)

    player._pick_supply_target(
        {"iron_ore": 80}, {"iron_ore": "mining"},
        make_state(skills={"mining": 20}), {"iron_ore": 1})

    assert store.supply_claim_holder("spruce_wood", NOW) is None
```

Read `tests/test_ai/test_player_coordination.py` first and extend its existing fixture helper to accept a shared `db` path rather than inventing a second construction style. Define `NOW` once at module scope as a UTC datetime — the store rejects naive ones.

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run, then coverage on `player.py`**

Check the reported missing-line list against the exact lines you ADD.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_coordination.py
git commit -m "fix(ai): one producer, one batch, per sibling request"
```

---

### Task 4: Mutation coverage, the gate, and the live check

**Files:**
- Modify: `formal/diff/mutate.py`
- Verify: `bash formal/gate.sh`, then `learning.db`

- [ ] **Step 1: Three mutants, each in its own run group, each killed by a NAMED test**

- the sibling-claim skip removed from `_pick_supply_target` (kill: `test_an_item_a_sibling_is_already_producing_is_skipped`)
- `SupplyClaim`'s exclusivity widened to `(character, item_code)` — if this cannot be expressed as a source mutation, mutate `claim_supply` to always return True instead (kill: `test_only_one_character_can_hold_a_supply_claim`)
- `supply_batch_target_pure` returning `banked + demand` — the old receding behaviour (kill: `test_the_target_is_one_batch_not_the_whole_demand`)

- [ ] **Step 2: Anchors and the sweep**

Run `uv run python formal/diff/mutate.py --check-anchors`, then a targeted sweep. **Check your `--only` substrings actually select all three groups** — the filter matches source and test paths, and a substring that matches neither silently skips the group. Verify the selected count matches what you expect before believing a clean result.

- [ ] **Step 3: Full gate, alone**

Run: `bash formal/gate.sh > /tmp/gate4.log 2>&1; echo $?` — expect 0. Do not run other pytest processes concurrently; CPU contention produces spurious GOAP search-budget flakes.

- [ ] **Step 4: Consider whether the Lean ladder is affected**

`supplyBankFires` mirrors `_fires`, which this plan does NOT change — the claim and the batch affect WHICH target is picked and HOW MUCH is committed, not whether the rung fires. Confirm that by reading `ProductionLadder.lean`'s predicate and the ladder differential, and say so in your report. If the differential feeds `supply_target` into the oracle in a way the batch changes, the Lean side needs updating and that is part of this task.

- [ ] **Step 5: The live check — against the learning DB, never trace files**

The running fleet predates these commits, so a restart is required before anything is observable. Report what you can see now, and be explicit that it is pre-restart:

```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('file:/home/blentz/.cache/artifactsmmo/learning.db?mode=ro', uri=True)
print('supply claims:', c.execute('select count(*) from supply_claims').fetchone())
print('recent SupplyBank goals:')
for r in c.execute(\"select selected_goal, character, count(*) from cycles where selected_goal like 'SupplyBank%' group by 1,2 order by 3 desc limit 5\"):
    print('  ', r)
"
```

Do NOT claim the fix works live without a row that shows it. Do not restart the fleet.

- [ ] **Step 6: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "test(mutation): guard the supply claim and the batch target"
```

## Verification before calling this done

- [ ] `bash formal/gate.sh` exits 0 with `ALL GATE PARTS PASSED` and 100.00% coverage.
- [ ] `uv run pytest tests/test_multi tests/test_utils -q` passes (pre-commit does not cover these).
- [ ] After a fleet restart: `supply_claims` holds at most ONE row per item code, and no two characters show `SupplyBank(<same item>...)` in overlapping cycles.

## Known limits this plan does NOT remove

1. **A request larger than one batch takes several commitments.** That is the point — the character re-evaluates between batches instead of committing to hundreds of cycles — but it means a 60-unit ask is six arm-and-satisfy rounds, each paying the arbiter's selection cost.
2. **The claim is advisory, like every other claim here.** Nothing blocks on it; a lost race degrades to today's behaviour for one cycle.
3. **The asker can still out-demand the fleet.** If its unmet demand keeps growing, a supplier keeps re-arming batch after batch. Bounding total effort per requester is a separate question.
