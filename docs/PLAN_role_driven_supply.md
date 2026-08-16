# Role-Driven Supply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a character's role actually decide what it works on, by letting siblings fill each other's requests for things they cannot make themselves — at the quantity those requests are actually published in.

**Architecture:** One predicate changes. `SUPPLY_BANK` currently fires only on unmet demand ≥ 10, and every live request is quantity 1, so it never fires and roles buy nothing. The requester now publishes whether it could produce the item itself; a request it cannot self-serve is worth a sibling's cycle at any quantity, while bulk material requests keep the existing 10-unit bar. `SupplyBankGoal` is unchanged — it already gathers *or crafts* into the bank.

**Tech Stack:** Python 3.13, `uv`, SQLModel/SQLite (coordination DB in the shared learning DB), pytest, Lean 4 for the one mirrored predicate.

**Spec:** This document.

## Evidence this plan is built on

Measured live on 2026-08-16 against the running `play --all` fleet:

- Every published demand row is **quantity 1**, and `SUPPLY_DEMAND_MIN` is **10**, so zero rows clear the bar:
  ```
  HAL   lich_race_medal       1      Robby lich_race_trophy      1
  C3P0  lich_race_medal       1      Lor   greater_wooden_staff  1
  R2D2  lich_race_medal       1      rows at or above 10: 0
  ```
- `supply_target` was computed in 59 of 384 traced cycles, but the `collect` band fired in **1.3%** — the target exists and is never actioned.
- Four of five characters hold the role `miner` and **none of them mine**: C3P0 and HAL grind slimes, Lor crafts a staff. Roles are currently decorative.
- Lor (miner) spent 95 cycles and R2D2 (logger) 97 cycles pursuing **the same** `greater_wooden_staff`. Dividing that work is what the coordination layer exists for.

**Why the existing bar is not simply wrong:** its rationale — *"1-9 units of one material is a handful of gather actions, cheaper to self-serve than to route through the bank"* — is correct for a raw the requester can gather. It is false for an item the requester is skill-gated out of making. That asymmetry is the specialization case, and it is exactly what the bar rejects today.

## Global Constraints

- Python 3.13. Every command under `uv run`.
- **One behavioural class per file.** Pure-data/enum modules may share a file.
- No inline imports; no `if TYPE_CHECKING`; never `except Exception` (catching `SQLAlchemyError` is the established pattern in the coordination store).
- Use only API/game data or fail with an error.
- Tests in `tests/`. 0 errors, 0 warnings, 0 skipped, **100% statement coverage** — and verify WITH coverage using the narrow per-file form; a `--no-cov` run has shipped uncovered lines in this repo before. Never run the whole `tests/test_ai/` suite under coverage: it exceeds ten minutes.
- Full gate is one command: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo $?` — redirect and read `$?` directly; a pipeline reports the PIPE's status and has hidden a real GATE FAIL here.
- Mutation anchors refresh in the SAME commit as the code they point at; `uv run python formal/diff/mutate.py --check-anchors` must stay green.
- Pre-commit runs `pytest tests/test_ai/` only.
- Run everything in the FOREGROUND. Background monitors stalled four agents on the previous epic.

## Non-goals

- **Not** touching taskmaster tasks or combat-target selection.
- **Not** adding a production claim. Two siblings may serve the same request; the worst case is over-production into a shared bank, which is not lost. Noted, deliberately deferred.
- **Not** changing `SupplyBankGoal`, its priority band, or its position in `COLLECT_REWARD_ORDER`.

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/learning/models.py` (modify) | `MaterialDemand.self_servable` column. |
| `src/artifactsmmo_cli/ai/learning/coordination_store.py` (modify) | One-shot migration for existing DBs; `publish_demand` carries the flag; new `sibling_demand_asymmetric` read. |
| `src/artifactsmmo_cli/ai/player.py` (modify) | Compute this character's self-servable set; thread the asymmetric set onto the context; prefer asymmetric requests in `_pick_supply_target`. |
| `src/artifactsmmo_cli/ai/selection_context.py` (modify) | Carry `asymmetric_demand: frozenset[str]`. |
| `src/artifactsmmo_cli/ai/tiers/means.py` (modify) | `_fires(SUPPLY_BANK)` gains the asymmetric arm. |
| `formal/Formal/Liveness/ProductionLadder.lean` (modify) | Mirror the new predicate. |
| `formal/Formal/Liveness/LadderEval.lean` (modify) | Witnesses for the new arm. |

---

### Task 1: The column and its migration

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py`
- Modify: `src/artifactsmmo_cli/ai/learning/coordination_store.py`
- Test: `tests/test_ai/test_coordination_store.py`

**Interfaces:**
- Produces: `MaterialDemand.self_servable: bool` (default `True`), and a module-level `_migrate_material_demand_self_servable(conn)` run from the same place `_migrate_role_lease_unique_index` is run.

**Why the migration is mandatory, not defensive:** `SQLModel.metadata.create_all` only creates tables that do not exist; it never alters an existing table. Every `learning.db` in use predates this column, so without a migration the first `publish_demand` raises `OperationalError: table material_demand has no column named self_servable`, the surrounding `except SQLAlchemyError` swallows it, and the demand board silently stops updating — the exact "old cache, dead feature" failure `_migrate_role_lease_unique_index` exists to prevent. Read that function before writing this one; follow its shape (detect with `PRAGMA`, alter in place, preserve rows).

`self_servable` defaults to `True` so an un-migrated or legacy row reads as "the requester can handle this itself", which reproduces today's behaviour rather than flooding the fleet with work.

- [ ] **Step 1: Write the failing tests**

```python
def test_self_servable_defaults_true_so_legacy_rows_keep_todays_behaviour(tmp_path):
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="HAL")
    store.publish_demand({"copper_ore": 12}, frozenset({"copper_ore"}), now)
    with SqlSession(store._engine) as s:
        row = s.exec(select(MaterialDemand)).one()
    assert row.self_servable is True


def test_a_request_the_requester_cannot_make_is_stored_as_not_self_servable(tmp_path):
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Lor")
    store.publish_demand({"greater_wooden_staff": 1}, frozenset(), now)
    with SqlSession(store._engine) as s:
        row = s.exec(select(MaterialDemand)).one()
    assert row.self_servable is False


def test_a_pre_existing_database_without_the_column_is_migrated_in_place(tmp_path):
    """The failure this guards is silent: without the migration the first
    publish raises OperationalError, `except SQLAlchemyError` swallows it, and
    the demand board stops updating with no error anywhere."""
    db = str(tmp_path / "legacy.db")
    raw = sqlite3.connect(db)
    raw.execute(
        "CREATE TABLE material_demand (id INTEGER PRIMARY KEY, character TEXT, "
        "item_code TEXT, quantity INTEGER, expires_at TEXT)")
    raw.execute("INSERT INTO material_demand (character, item_code, quantity, expires_at) "
                "VALUES ('Robby', 'copper_ore', 5, '2099-01-01T00:00:00+00:00')")
    raw.commit()
    raw.close()

    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    store = CoordinationStore(db_path=db, character="HAL")
    store.publish_demand({"iron_ore": 4}, frozenset({"iron_ore"}), now)

    with SqlSession(store._engine) as s:
        rows = {r.item_code: r for r in s.exec(select(MaterialDemand)).all()}
    assert set(rows) == {"copper_ore", "iron_ore"}      # the legacy row survived
    assert rows["copper_ore"].self_servable is True     # back-filled with the safe default
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -k self_servable -v --no-cov`
Expected: FAIL — `publish_demand()` takes 3 positional arguments.

- [ ] **Step 3: Implement the column, the signature and the migration**

`publish_demand(self, demand: Mapping[str, int], self_servable: frozenset[str], now: datetime) -> None` — the second argument is the set of codes the REQUESTER can produce itself. A frozenset rather than a parallel mapping because the flag is a property of the requester, not of the quantity, and a set cannot fall out of step with the demand keys the way a second dict can.

Every existing `publish_demand` call site must be updated in this task; leaving one behind is a silent behaviour change.

- [ ] **Step 4: Run the tests and the file**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v --no-cov`
Expected: PASS, including every pre-existing test in the file.

- [ ] **Step 5: Coverage**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -q --cov=src/artifactsmmo_cli/ai/learning/coordination_store --cov=src/artifactsmmo_cli/ai/learning/models --cov-report=term-missing --cov-fail-under=0`
Expected: no missing lines in what you added, migration branch included.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py \
        src/artifactsmmo_cli/ai/learning/coordination_store.py \
        tests/test_ai/test_coordination_store.py
git commit -m "feat(coordination): a demand row says whether its asker can serve it"
```

---

### Task 2: Read the asymmetry back

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/coordination_store.py`
- Test: `tests/test_ai/test_coordination_store.py`

**Interfaces:**
- Consumes: the column from Task 1.
- Produces: `CoordinationStore.sibling_demand_asymmetric(now: datetime) -> frozenset[str]` — codes for which at least one live row from ANOTHER character is `self_servable=False`.

**The aggregation rule is OR, and it is deliberate.** If any requester cannot make the item, the item is worth a sibling's cycle; a second requester who happens to be able to make it does not cancel the first one's need. Reducing with AND would silently drop the only case this feature exists for.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_code_is_asymmetric_when_any_asker_cannot_make_it(tmp_path):
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="Lor").publish_demand(
        {"greater_wooden_staff": 1}, frozenset(), now)             # cannot make it
    CoordinationStore(db_path=db, character="C3P0").publish_demand(
        {"greater_wooden_staff": 1}, frozenset({"greater_wooden_staff"}), now)  # can

    assert CoordinationStore(db_path=db, character="R2D2").sibling_demand_asymmetric(now) == \
        frozenset({"greater_wooden_staff"})


def test_a_code_every_asker_can_make_is_not_asymmetric(tmp_path):
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="Lor").publish_demand(
        {"copper_ore": 30}, frozenset({"copper_ore"}), now)

    assert CoordinationStore(db_path=db, character="R2D2").sibling_demand_asymmetric(now) == frozenset()


def test_my_own_row_never_makes_a_code_asymmetric_for_me(tmp_path):
    """Otherwise a character serves itself through the bank, forever."""
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    lor = CoordinationStore(db_path=db, character="Lor")
    lor.publish_demand({"greater_wooden_staff": 1}, frozenset(), now)

    assert lor.sibling_demand_asymmetric(now) == frozenset()


def test_an_expired_row_stops_making_a_code_asymmetric(tmp_path):
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db, character="Lor").publish_demand(
        {"greater_wooden_staff": 1}, frozenset(), now)
    later = now + timedelta(seconds=DEMAND_TTL_SECONDS + 1)

    assert CoordinationStore(db_path=db, character="R2D2").sibling_demand_asymmetric(later) == frozenset()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -k asymmetric -v --no-cov`
Expected: FAIL — `'CoordinationStore' object has no attribute 'sibling_demand_asymmetric'`

- [ ] **Step 3: Implement**

Mirror `sibling_demand`'s shape exactly: same "other characters only" filter, same unexpired predicate, same single query.

- [ ] **Step 4: Run and cover**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v --no-cov` then the narrow coverage form from Task 1 Step 5.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/coordination_store.py tests/test_ai/test_coordination_store.py
git commit -m "feat(coordination): surface which requests only a sibling can fill"
```

---

### Task 3: Publish the flag, thread the set

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Modify: `src/artifactsmmo_cli/ai/selection_context.py`
- Test: `tests/test_ai/test_player_coordination.py`

**Interfaces:**
- Consumes: `publish_demand(demand, self_servable, now)` and `sibling_demand_asymmetric(now)`.
- Produces: `SelectionContext.asymmetric_demand: frozenset[str]` (default `frozenset()`), and `GamePlayer._asymmetric_demand` set once per cycle in `_update_coordination`.

**How the requester computes its own flag.** `_update_coordination` already builds exactly what is needed, a few lines below the publish call:

```python
producing = {code: game_data.producing_requirement(code) for code in item_demand}
skill_of_item = {code: req[0] if req is not None else None for code, req in producing.items()}
level_of_item = {code: req[1] for code, req in producing.items() if req is not None}
```

Build the same two maps over THIS character's own unmet demand, and mark a code self-servable when `serves_item(code, skill, level_of_item, state.skills)` is True. `serves_item` is already the one level gate with two readers (`demand_by_role` and `_pick_supply_target`); this makes three, and they must not disagree — do not re-type its logic.

A code with no producing skill at all (`skill_of_item[code] is None`) is **not** self-servable: nothing this character can do produces it, which is precisely a request only someone else — or a vendor — can fill.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_character_publishes_its_own_inability_to_make_what_it_wants(tmp_path):
    """Lor is a miner at woodcutting 1; a greater_wooden_staff gates far above
    that, so its request must go out marked for a sibling."""
    player, store = _player_with_coordination(tmp_path, "Lor")
    player.state = make_state(skills={"woodcutting": 1, "mining": 8})
    player._last_decide_crafting_target = "greater_wooden_staff"

    player._update_coordination(player.state, player.game_data)

    with SqlSession(store._engine) as s:
        rows = {r.item_code: r.self_servable for r in s.exec(select(MaterialDemand)).all()}
    assert rows["greater_wooden_staff"] is False


def test_a_character_that_can_make_its_own_material_says_so(tmp_path):
    player, store = _player_with_coordination(tmp_path, "Lor")
    player.state = make_state(skills={"mining": 20})
    player._last_decide_crafting_target = "copper_ore"

    player._update_coordination(player.state, player.game_data)

    with SqlSession(store._engine) as s:
        rows = {r.item_code: r.self_servable for r in s.exec(select(MaterialDemand)).all()}
    assert rows["copper_ore"] is True


def test_the_asymmetric_set_reaches_the_selection_context(tmp_path):
    player, _ = _player_with_coordination(tmp_path, "R2D2")
    _publish_sibling_request(tmp_path, "Lor", {"greater_wooden_staff": 1}, self_servable=frozenset())

    player._update_coordination(player.state, player.game_data)
    ctx = player._selection_context(combat_monster=None)

    assert "greater_wooden_staff" in ctx.asymmetric_demand


def test_no_coordination_store_leaves_the_asymmetric_set_empty():
    player = GamePlayer(character="solo")
    player.state = make_state()
    player._update_coordination(player.state, player.game_data)
    assert player._asymmetric_demand == frozenset()
```

Build `_player_with_coordination` and `_publish_sibling_request` as local helpers in the test module, following how the existing tests in `test_player_coordination.py` construct a player with a store — read that file first and reuse its fixtures rather than inventing a second style.

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_ai/test_player_coordination.py -k "self_servable or asymmetric or inability" -v --no-cov`
Expected: FAIL on the missing `asymmetric_demand` / the unchanged publish signature.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run, then cover**

Run: `uv run pytest tests/test_ai/test_player_coordination.py -v --no-cov`, then
`uv run pytest tests/test_ai/test_player_coordination.py -q --cov=src/artifactsmmo_cli/ai/player --cov=src/artifactsmmo_cli/ai/selection_context --cov-report=term-missing --cov-fail-under=0`

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/selection_context.py \
        tests/test_ai/test_player_coordination.py
git commit -m "feat(ai): publish what this character cannot make for itself"
```

---

### Task 4: Fire on asymmetry

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/means.py`
- Test: `tests/test_ai/test_means_supply_bank.py` (new file if none exists for this means; otherwise extend the existing one)

**Interfaces:**
- Consumes: `ctx.supply_target` (existing, `(item_code, banked_target, unmet_demand)`) and `ctx.asymmetric_demand` (Task 3).
- Produces: the amended `_fires(MeansKind.SUPPLY_BANK, ...)`.

**The predicate becomes:** fires when a supply target exists AND either its unmet demand is at least `SUPPLY_DEMAND_MIN`, or its item code is in `ctx.asymmetric_demand`. Keep `SUPPLY_DEMAND_MIN` at 10 and keep its comment block — the bulk-material rationale it records is still correct and still load-bearing for the first arm. Add to it, explaining the second arm: a request its asker is skill-gated out of filling is worth a sibling's cycle at any size, and that asymmetry is the whole point of holding a role.

- [ ] **Step 1: Write the failing tests**

```python
def test_bulk_demand_still_fires_the_supply_rung():
    ctx = _ctx(supply_target=("copper_ore", 40, 12), asymmetric_demand=frozenset())
    assert _fires(MeansKind.SUPPLY_BANK, make_state(), _gd(), ctx) is True


def test_a_single_unit_request_the_asker_cannot_make_now_fires():
    """The live case: every published row is quantity 1, so before this the
    rung never fired at all."""
    ctx = _ctx(supply_target=("greater_wooden_staff", 1, 1),
               asymmetric_demand=frozenset({"greater_wooden_staff"}))
    assert _fires(MeansKind.SUPPLY_BANK, make_state(), _gd(), ctx) is True


def test_a_small_request_the_asker_can_make_itself_still_does_not_fire():
    """The bar's original rationale, preserved: a few units of an ore you can
    gather yourself is cheaper to self-serve than to route through the bank."""
    ctx = _ctx(supply_target=("copper_ore", 3, 3), asymmetric_demand=frozenset())
    assert _fires(MeansKind.SUPPLY_BANK, make_state(), _gd(), ctx) is False


def test_no_supply_target_never_fires():
    ctx = _ctx(supply_target=None, asymmetric_demand=frozenset({"greater_wooden_staff"}))
    assert _fires(MeansKind.SUPPLY_BANK, make_state(), _gd(), ctx) is False
```

- [ ] **Step 2: Run them and watch the middle one fail**

Run: `uv run pytest tests/test_ai/test_means_supply_bank.py -v --no-cov`
Expected: the single-unit test FAILS; the other three pass, proving the change is additive.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run, then cover `means.py`**

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/means.py tests/test_ai/test_means_supply_bank.py
git commit -m "feat(tiers): serve a sibling's request it cannot fill itself"
```

---

### Task 5: Prefer the requests only you can fill

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_pick_supply_target`)
- Test: `tests/test_ai/test_player_coordination.py`

**Interfaces:**
- Consumes: `_asymmetric_demand` (Task 3).
- Produces: unchanged signature and return shape — only the choice among candidates changes.

Today `_pick_supply_target` takes the highest-demand item this character's role can produce. With the new arm, a 30-unit ore request would always outrank the single staff only this character can craft. Rank asymmetric requests ahead of symmetric ones, then by demand within each group. Keep the existing `serves_item` gate exactly as it is — it is what makes the role decide the answer.

**Do not order by item code as a tiebreak.** This repo forbids repr/name ordering as a decision tiebreak; ties on (asymmetric, demand) keep whatever order the existing code produces.

- [ ] **Step 1: Write the failing test**

```python
def test_a_request_only_i_can_fill_outranks_a_bigger_one_anyone_could(tmp_path):
    player, _ = _player_with_coordination(tmp_path, "R2D2")   # logger
    player._asymmetric_demand = frozenset({"greater_wooden_staff"})
    item_demand = {"copper_ore": 30, "greater_wooden_staff": 1}

    target = player._pick_supply_target(
        item_demand, {"copper_ore": "mining", "greater_wooden_staff": "woodcutting"},
        make_state(skills={"woodcutting": 20, "mining": 20}),
        {"copper_ore": 1, "greater_wooden_staff": 10})

    assert target is not None and target[0] == "greater_wooden_staff"


def test_among_equals_the_bigger_request_still_wins(tmp_path):
    player, _ = _player_with_coordination(tmp_path, "R2D2")
    player._asymmetric_demand = frozenset()
    item_demand = {"copper_ore": 30, "ash_wood": 5}

    target = player._pick_supply_target(
        item_demand, {"copper_ore": "mining", "ash_wood": "woodcutting"},
        make_state(skills={"woodcutting": 20, "mining": 20}),
        {"copper_ore": 1, "ash_wood": 1})

    assert target is not None and target[0] == "copper_ore"
```

- [ ] **Step 2: Run and watch the first fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run, cover, commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_coordination.py
git commit -m "feat(ai): prefer the sibling request nobody else can fill"
```

---

### Task 6: Mirror the predicate in Lean

**Files:**
- Modify: `formal/Formal/Liveness/ProductionLadder.lean`
- Modify: `formal/Formal/Liveness/LadderEval.lean`
- Verify: `bash formal/gate.sh`

`ProductionLadder.lean:355` currently reads:

```lean
def supplyBankFires (s : State) : Bool := decide (s.supplyDemand ≥ SUPPLY_DEMAND_MIN)
```

That mirrors the Python predicate exactly, and `LadderEval.lean` carries witnesses including the threshold boundary. Add a `supplyAsymmetric : Bool` field to the ladder `State` and extend the predicate to `decide (s.supplyDemand ≥ SUPPLY_DEMAND_MIN) || s.supplyAsymmetric`.

**Witnesses are mandatory and must prove both directions** — this repo treats a vacuous liveness lemma as worse than none. Keep the existing threshold-boundary witnesses (the first arm is unchanged) and add:
- fires at `supplyDemand = 1` when `supplyAsymmetric = true`;
- does NOT fire at `supplyDemand = 1` when `supplyAsymmetric = false`.

Model the additions on the `currencyTurnIn` witnesses added in the previous epic, which are the closest precedent for a Bool-valued arm.

- [ ] **Step 1: Run the gate and read the failure**

Run: `bash formal/gate.sh > /tmp/gate6.log 2>&1; echo $?`
Expected: non-zero once Task 4 has landed, or a clean run that the differential later contradicts — either way, read the Lean error before editing.

- [ ] **Step 2: Extend the state and predicate**

- [ ] **Step 3: Add the witnesses**

- [ ] **Step 4: Full gate**

Run: `bash formal/gate.sh > /tmp/gate6.log 2>&1; echo $?`
Expected: 0, `ALL GATE PARTS PASSED`, 100.00% coverage.

- [ ] **Step 5: Commit**

```bash
git add formal/
git commit -m "feat(formal): the supply rung fires on asymmetry too"
```

---

### Task 7: Mutation coverage and the live check

**Files:**
- Modify: `formal/diff/mutate.py`
- Verify: live `play --all`

- [ ] **Step 1: Add three mutants, each in its own run group, each killed by a NAMED test**

- the asymmetric arm deleted from `_fires` (killed by `test_a_single_unit_request_the_asker_cannot_make_now_fires`)
- `sibling_demand_asymmetric`'s own-character filter dropped (killed by `test_my_own_row_never_makes_a_code_asymmetric_for_me`)
- the asymmetric-first ordering in `_pick_supply_target` inverted (killed by `test_a_request_only_i_can_fill_outranks_a_bigger_one_anyone_could`)

- [ ] **Step 2: Anchors and sweep**

Run: `uv run python formal/diff/mutate.py --check-anchors`, then
`uv run python formal/diff/mutate.py --only supply,coordination_store`
Expected: anchors unique; every new mutant killed, 0 survivors.

- [ ] **Step 3: Full gate**

Run: `bash formal/gate.sh > /tmp/gate7.log 2>&1; echo $?` — expect 0.

- [ ] **Step 4: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "test(mutation): guard the asymmetric supply arm"
```

- [ ] **Step 5: The live check — this is the acceptance test, not the suite**

Green tests have repeatedly not meant a runtime-active feature in this repo. After committing, confirm on the running fleet:

```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('file:/home/blentz/.cache/artifactsmmo/learning.db?mode=ro', uri=True)
for r in c.execute('select character,item_code,quantity,self_servable from material_demand'):
    print(r)
"
```

Expect rows carrying `self_servable = 0` for items their asker is gated out of making. Then watch a trace for a `SupplyBank(...)` goal actually being selected — that is the outcome this whole plan exists for, and its absence means the feature is inert however green the suite is.

## Verification before calling this done

- [ ] `bash formal/gate.sh` exits 0 with `ALL GATE PARTS PASSED` and 100.00% coverage.
- [ ] `uv run pytest tests/test_multi tests/test_utils -q` passes (pre-commit does not cover these).
- [ ] `material_demand` on the live DB shows at least one `self_servable = 0` row.
- [ ] A live trace shows `SupplyBank(...)` selected at least once.

## Known limits this plan does NOT remove

1. **No production claim.** Two siblings can serve the same request and both produce it. The bank keeps the surplus, so nothing is lost, but the actions are.
2. **Roles remain non-exclusive.** Four characters can still all hold `miner`; this plan makes the role decide what they *do* for each other, not how many hold it.
3. **Demand is still published as the requester's own unmet closure.** If a character holds all the materials and only lacks the finished item, the board shows the finished item — which is exactly the case this plan serves, but it means a sibling never sees the sub-materials as separate requests.
