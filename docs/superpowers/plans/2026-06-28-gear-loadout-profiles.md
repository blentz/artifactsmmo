# Gear Sub-project C — Loadout Profiles + Bank-Aware Dedup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `target_gear`-closure gear-protection economy with per-task loadout profiles + a proved bank-aware dedup, and wire the freed bank-space signal into expansion timing.

**Architecture:** A persisted `LearningStore` profiles table `(character, task_key)→loadout`; pure proved cores `gear_demand` (MAX-over-active-profiles) + `bank_space_cost`; active-set resolution from current+recent context; a consumer migration that reroutes every GEAR protection site from `target_gear`/`target_tools` to the active-profile gear set (non-gear protection unchanged); a `used`-floor into `should_expand_bank`.

**Tech Stack:** Python 3.13 (`uv` at `~/.local/bin/uv`), SQLModel/SQLite (LearningStore), Lean 4 (`formal/`), Hypothesis (differential), `formal/diff/mutate.py`, pytest (`--cov-fail-under=100`).

## Global Constraints

- `uv` at `~/.local/bin/uv`; ALWAYS `uv run`. `git checkout uv.lock` before commit if dirtied.
- No inline imports; no `if TYPE_CHECKING`; no `...` imports; NEVER catch `Exception` (LearningStore `record_*`/read methods catch `SQLAlchemyError` only, the existing pattern). ONE behavioral class per file; pure cores in `*_core.py`.
- Use only API data or fail. Tests: 0 errors/warnings/skipped (token-gated live tests excepted), 100% coverage; real fixtures; never mock the unit under test.
- Formal lockstep: computable Lean `def` + role theorems (∀ inputs) + `Contracts.lean` exact pins + `Manifest.lean` roster + `Audit.lean` `#print axioms` entry + differential (Python≡oracle on the HAND def) + mutation (every drop-term mutant killed). No `sorry`/`native_decide`/custom axioms; standard axioms only.
- NEVER run `gate.sh`/`mutate.py` while anything imports `src`. `git diff src` after mutation. Re-run `scripts/extract_lean.py` after any source move.
- Branch: `feat/gear-loadout-profiles` (off main `5eaec02b`). Spec: `docs/superpowers/specs/2026-06-28-gear-loadout-profiles-design.md`.

**Verbatim facts:**
- `task_key` = `"combat:<monster_code>"` / `"gather:<skill>"` (the keys `OptimizeLoadoutAction` uses).
- `gear_demand(active_profiles) -> dict[code,int]` = for each code, MAX over active profiles of its count (slots holding it) in that profile's loadout (rings can be 2 in one profile).
- `bank_space_cost(active_loadouts, equipped) -> int` = `|{distinct code in any active loadout} − equipped_codes|`.
- Bank-expansion: `used' = max(current_bank_used, bank_space_cost)`; `should_expand_bank(used', game_data.bank_capacity, state.gold, game_data.next_expansion_cost, reserve, trigger_num, trigger_den)` — cost/capacity LIVE (v8: 50 slots / 3500, never hardcoded).
- LearningStore template = `CraftYieldObservation` (models.py:191) + `record_craft_yield`/`observed_craft_yield` (store.py:564); catch `SQLAlchemyError` only.
- inventory_caps keep: `EQUIPPABLE_KEEP=1` (line 116) in `useful_quantity_cap_excl_equipped_pure`; dominance `_is_equippable_dominated` (line 268).

---

### Task 1: LearningStore loadout-profile persistence

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py` (new table), `src/artifactsmmo_cli/ai/learning/store.py` (record/accessor)
- Test: `tests/ai/learning/test_loadout_profile_store.py` (new; mirror the craft_yield store test)

**Interfaces:**
- Produces: `LearningStore.record_loadout_profile(task_key: str, loadout: dict[str, str]) -> None` (upsert, last-write-wins, best-effort); `LearningStore.loadout_profiles() -> dict[str, dict[str, str]]` ({task_key: {slot: code}}).

- [ ] **Step 1: Write the failing store test**

```python
# tests/ai/learning/test_loadout_profile_store.py
from artifactsmmo_cli.ai.learning.store import LearningStore


def test_record_and_read_loadout_profile(tmp_path):
    store = LearningStore(db_path=tmp_path / "t.db", character="Robby")
    store.record_loadout_profile("combat:chicken", {"weapon_slot": "wooden_stick", "ring1_slot": "copper_ring"})
    store.record_loadout_profile("gather:woodcutting", {"weapon_slot": "iron_axe"})
    profiles = store.loadout_profiles()
    assert profiles["combat:chicken"] == {"weapon_slot": "wooden_stick", "ring1_slot": "copper_ring"}
    assert profiles["gather:woodcutting"] == {"weapon_slot": "iron_axe"}


def test_record_loadout_profile_upsert_last_write_wins(tmp_path):
    store = LearningStore(db_path=tmp_path / "t.db", character="Robby")
    store.record_loadout_profile("combat:chicken", {"weapon_slot": "wooden_stick"})
    store.record_loadout_profile("combat:chicken", {"weapon_slot": "iron_sword"})
    assert store.loadout_profiles()["combat:chicken"] == {"weapon_slot": "iron_sword"}
```

> Match `LearningStore.__init__`'s actual signature (open `store.py` — it's `(db_path, character)` per the investigator) and the craft_yield store test's fixture style.

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/learning/test_loadout_profile_store.py -v`
Expected: FAIL — `record_loadout_profile` missing.

- [ ] **Step 3: Add the table (models.py)**

Mirror `CraftYieldObservation`. Store the loadout as a JSON string column (a loadout is a small dict; one column keeps it one row per task_key, last-write-wins):

```python
class LoadoutProfileObservation(SQLModel, table=True):
    """The loadout the bot uses for a recurring task. One row per (character,
    task_key); last write wins. task_key is 'combat:<monster>' / 'gather:<skill>'.
    `loadout` is JSON {slot: code}. Source for sub-project C's keep economy + D's
    learned loadout."""

    __tablename__ = "loadout_profile"

    character: str = Field(primary_key=True)
    task_key: str = Field(primary_key=True)
    loadout: str  # JSON-encoded dict[slot, code]
```

- [ ] **Step 4: Add record/accessor (store.py)**

Mirror `record_craft_yield`/`observed_craft_yield` exactly (catch `SQLAlchemyError` only; `print("[learning] record_loadout_profile failed: ...")` on write error; return `{}` on read error). Use `json.dumps`/`json.loads` (import `json` at top of store.py if absent):

```python
def record_loadout_profile(self, task_key: str, loadout: dict[str, str]) -> None:
    """Upsert the loadout for (character, task_key). Last write wins. Best-effort."""
    try:
        with SqlSession(self._engine) as s:
            stmt = select(LoadoutProfileObservation).where(
                LoadoutProfileObservation.character == self._character,
                LoadoutProfileObservation.task_key == task_key,
            )
            existing = s.exec(stmt).first()
            encoded = json.dumps(loadout, sort_keys=True)
            if existing is not None:
                existing.loadout = encoded
                s.add(existing)
            else:
                s.add(LoadoutProfileObservation(
                    character=self._character, task_key=task_key, loadout=encoded))
            s.commit()
    except SQLAlchemyError as e:
        print(f"[learning] record_loadout_profile failed: {e}")

def loadout_profiles(self) -> dict[str, dict[str, str]]:
    """All stored {task_key: {slot: code}} for this character. Best-effort ({} on error)."""
    try:
        with SqlSession(self._engine) as s:
            rows = s.exec(select(LoadoutProfileObservation).where(
                LoadoutProfileObservation.character == self._character)).all()
        return {r.task_key: json.loads(r.loadout) for r in rows}
    except SQLAlchemyError:
        return {}
```

- [ ] **Step 5: Run + commit**

Run: `~/.local/bin/uv run pytest tests/ai/learning/test_loadout_profile_store.py -v` (pass); `~/.local/bin/uv run pytest --cov-fail-under=100 -q`; `~/.local/bin/uv run mypy --strict src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py`. `git checkout uv.lock`.

```bash
git add src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py tests/ai/learning/test_loadout_profile_store.py
git commit -m "feat(gear): LearningStore loadout-profile table + record/accessor"
```

---

### Task 2: Pure dedup + bank-space cores + Lean lockstep

**Files:**
- Create: `src/artifactsmmo_cli/ai/loadout_profiles_core.py`, `formal/Formal/LoadoutProfiles.lean`
- Modify: `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`, `formal/Formal/Audit.lean`
- Test: `tests/ai/test_loadout_profiles_core.py`

**Interfaces:**
- Produces (Python): `gear_demand(active_loadouts: Sequence[Mapping[str, str]]) -> dict[str, int]`; `bank_space_cost(active_loadouts: Sequence[Mapping[str, str]], equipped: Set[str]) -> int`.
- Produces (Lean `Formal.LoadoutProfiles`): `gearDemand`, `bankSpaceCost`, theorems `gearDemand_eq_max`, `gearDemand_dedup_bound`, `gearDemand_mono`, `bankSpaceCost_nonneg`, `bankSpaceCost_mono`, and `shouldExpandBank_floor_preserves`.

- [ ] **Step 1: Write the failing core tests**

```python
# tests/ai/test_loadout_profiles_core.py
from artifactsmmo_cli.ai.loadout_profiles_core import bank_space_cost, gear_demand


def test_shared_gear_held_once():
    p1 = {"weapon_slot": "copper_dagger", "ring1_slot": "copper_ring"}
    p2 = {"weapon_slot": "copper_dagger", "helmet_slot": "iron_helmet"}
    d = gear_demand([p1, p2])
    assert d["copper_dagger"] == 1          # shared -> held once
    assert d["copper_ring"] == 1
    assert d["iron_helmet"] == 1


def test_ring_counts_two_within_one_profile():
    p = {"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"}
    assert gear_demand([p])["copper_ring"] == 2


def test_demand_is_max_not_sum():
    p1 = {"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"}  # 2
    p2 = {"ring1_slot": "copper_ring"}                                # 1
    assert gear_demand([p1, p2])["copper_ring"] == 2                  # max, not 3


def test_bank_space_cost_excludes_equipped():
    p1 = {"weapon_slot": "copper_dagger", "helmet_slot": "iron_helmet"}
    p2 = {"weapon_slot": "copper_dagger", "boots_slot": "leather_boots"}
    # distinct gear = {copper_dagger, iron_helmet, leather_boots}; equipped copper_dagger
    assert bank_space_cost([p1, p2], {"copper_dagger"}) == 2
```

- [ ] **Step 2: Run to verify failure** — `~/.local/bin/uv run pytest tests/ai/test_loadout_profiles_core.py -v` → FAIL (module missing).

- [ ] **Step 3: Write the pure core**

```python
# src/artifactsmmo_cli/ai/loadout_profiles_core.py
"""PURE proved cores for loadout-profile dedup + bank-space cost (extracted;
mirrors Formal/LoadoutProfiles.lean). No GameData/IO. See
docs/superpowers/specs/2026-06-28-gear-loadout-profiles-design.md."""

from collections.abc import Mapping, Sequence, Set


def _counts(loadout: Mapping[str, str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for code in loadout.values():
        out[code] = out.get(code, 0) + 1
    return out


def gear_demand(active_loadouts: Sequence[Mapping[str, str]]) -> dict[str, int]:
    """For each gear code, the MAX over active loadouts of its count in that
    loadout (one loadout worn at a time -> shared gear held once; rings can be 2
    in one loadout). Mirrors Formal.LoadoutProfiles.gearDemand."""
    demand: dict[str, int] = {}
    for loadout in active_loadouts:
        for code, n in _counts(loadout).items():
            if n > demand.get(code, 0):
                demand[code] = n
    return demand


def bank_space_cost(active_loadouts: Sequence[Mapping[str, str]],
                    equipped: Set[str]) -> int:
    """Distinct gear across active loadouts that is NOT currently equipped — the
    bank room the active profiles demand. Mirrors Formal.LoadoutProfiles.bankSpaceCost."""
    distinct = {code for loadout in active_loadouts for code in loadout.values()}
    return len(distinct - set(equipped))
```

- [ ] **Step 4: Run core tests** — pass (4/4).

- [ ] **Step 5: Lean cores + theorems**

Create `formal/Formal/LoadoutProfiles.lean`. Model a loadout as `List (String × String)` (slot, code) or `List String` (codes). Statements (prove with `lean4:prove`; read `Formal/BankExpansionTiming.lean` for `shouldExpandBank` to state the floor lemma):

```lean
namespace Formal.LoadoutProfiles
-- gearDemand: for code c, max over loadouts of (count c in loadout)
def gearDemand (loadouts : List (List String)) (c : String) : Nat := ...
theorem gearDemand_eq_max (loadouts) (c) :
    gearDemand loadouts c = (loadouts.map (fun l => l.count c)).foldl max 0 := ...
theorem gearDemand_dedup_bound (loadouts) (c) :
    gearDemand loadouts c ≤ (loadouts.map (fun l => l.count c)).foldl max 0 := ...   -- = bound; the "held once" fact: ≤ max single-profile count
theorem gearDemand_mono (loadouts l) (c) :
    gearDemand loadouts c ≤ gearDemand (l :: loadouts) c := ...
def bankSpaceCost (loadouts : List (List String)) (equipped : List String) : Nat := ...
theorem bankSpaceCost_mono ... ; theorem bankSpaceCost_le_distinct ...
-- floor preserves shouldExpandBank guarantees (rides expand_stable_under_more_fill)
theorem shouldExpandBank_floor_preserves
    (used cost capacity gold k r tn td : Int) (h : used ≤ max used cost) :
    Formal.BankExpansionTiming.shouldExpandBank used capacity gold k r tn td = true →
    Formal.BankExpansionTiming.shouldExpandBank (max used cost) capacity gold k r tn td = true := ...
```

> Pin exact field names / encoding by reading the sibling modules. Do NOT weaken any statement. Keep the defs computable.

- [ ] **Step 6: Prove + pin + build**

`cd formal && lake build`; axioms standard. Add all theorem names to `Manifest.lean` (#check), `Contracts.lean` (exact pins), `Audit.lean` (#print axioms — do NOT skip; the sub-project-2 lesson). `cd formal && lake build` full green.

- [ ] **Step 7: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/loadout_profiles_core.py tests/ai/test_loadout_profiles_core.py formal/Formal/LoadoutProfiles.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean formal/Formal/Audit.lean
git commit -m "feat(gear): proved gear_demand + bank_space_cost cores + Lean lockstep"
```

---

### Task 3: Active-set resolution + auto-creation hook

**Files:**
- Create: `src/artifactsmmo_cli/ai/loadout_profiles.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (record profile on a task cycle)
- Test: `tests/ai/test_loadout_profiles.py`, extend a player test

**Interfaces:**
- Consumes: `loadout_profiles_core.gear_demand/bank_space_cost`, `LearningStore.loadout_profiles`, `pick_loadout`, `recent_goal_cycles`.
- Produces: `active_loadouts(state, game_data, history, combat_monster, gather_skills) -> list[dict[str,str]]`; `active_profile_gear(...) -> dict[str,int]` (the gear-demand keep set: `gear_demand(active_loadouts)`); `task_key_for(...)` helper; `profile_for_combat`/`profile_for_gather` recording helpers.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ai/test_loadout_profiles.py
from artifactsmmo_cli.ai.loadout_profiles import active_loadouts, active_profile_gear


def test_active_includes_current_objective_and_recent(profiles_fixture):
    # store has combat:chicken (current) + gather:mining (recent) + combat:wolf (neither)
    state, game_data, history = profiles_fixture
    loadouts = active_loadouts(state, game_data, history,
                               combat_monster="chicken", gather_skills=frozenset())
    keys = {tuple(sorted(l.items())) for l in loadouts}
    # chicken (current) + mining (recent) active; wolf (neither) excluded
    assert any("wooden_stick" in l.values() for l in loadouts)   # chicken
    assert all("wolf_only_gear" not in l.values() for l in loadouts)


def test_active_profile_gear_dedups(profiles_fixture):
    state, game_data, history = profiles_fixture
    gear = active_profile_gear(state, game_data, history,
                               combat_monster="chicken", gather_skills=frozenset({"mining"}))
    assert gear.get("copper_dagger", 0) == 1   # shared across profiles -> 1
```

> Build `profiles_fixture` with a `LearningStore(tmp)` seeded via `record_loadout_profile`, a `WorldState`, and a recent-cycle log (use `record_cycle` with `selected_goal` strings the resolver parses). Mirror existing learning-test fixtures.

- [ ] **Step 2: Run to verify failure** — module missing.

- [ ] **Step 3: Implement `loadout_profiles.py`**

```python
# src/artifactsmmo_cli/ai/loadout_profiles.py
"""Resolve the ACTIVE loadout profiles (current objective + recent window) and
the deduped gear set the keep economy protects."""

from collections.abc import Mapping
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loadout_profiles_core import bank_space_cost, gear_demand
from artifactsmmo_cli.ai.world_state import WorldState

RECENT_PROFILE_WINDOW = 50  # cycles; mirror the learning windows


def combat_key(monster_code: str) -> str:
    return f"combat:{monster_code}"

def gather_key(skill: str) -> str:
    return f"gather:{skill}"


def active_task_keys(history: LearningStore, combat_monster: str | None,
                     gather_skills: frozenset[str]) -> set[str]:
    """current-objective tasks UNION recent-window tasks (from the cycle log)."""
    keys: set[str] = set()
    if combat_monster:
        keys.add(combat_key(combat_monster))
    for skill in gather_skills:
        keys.add(gather_key(skill))
    # recent: parse task_keys out of recent goal cycles (selected_goal carries the
    # monster/skill). Reuse the store's recent-goal accessor; match its API.
    keys |= _recent_task_keys(history, RECENT_PROFILE_WINDOW)
    return keys


def active_loadouts(state, game_data, history, combat_monster, gather_skills):
    stored = history.loadout_profiles()
    active = active_task_keys(history, combat_monster, gather_skills)
    return [stored[k] for k in active if k in stored]


def active_profile_gear(state, game_data, history, combat_monster, gather_skills):
    """The deduped gear-demand keep set {code: demand} for active profiles."""
    return gear_demand(active_loadouts(state, game_data, history, combat_monster, gather_skills))


def active_bank_space_cost(state, game_data, history, combat_monster, gather_skills):
    loadouts = active_loadouts(state, game_data, history, combat_monster, gather_skills)
    equipped = {c for c in state.equipment.values() if c is not None}
    return bank_space_cost(loadouts, equipped)
```

Implement `_recent_task_keys` by reading recent `Cycle.selected_goal` (reuse the store's recent-goal API — open `store.py` for `recent_goal_cycles`/the cycle query) and extracting the monster/skill into `combat:`/`gather:` keys. If parsing a goal repr is brittle, prefer a structured field; document the parse.

- [ ] **Step 4: Auto-creation hook (player.py)**

Where a task action executes successfully (after `action.execute`, near the existing `record_*` calls), upsert the profile for the performed task: if the action is a combat/gather task, build `task_key` + `pick_loadout(purpose)` and call `history.record_loadout_profile`. Best-effort (the `record_*` already swallows `SQLAlchemyError`). Add a focused unit test that performing a fight records `combat:<monster>` with the current pick_loadout.

- [ ] **Step 5: Run + commit**

Run the new tests + full suite + mypy on the 2 files. `git checkout uv.lock`.

```bash
git add src/artifactsmmo_cli/ai/loadout_profiles.py src/artifactsmmo_cli/ai/player.py tests/ai/test_loadout_profiles.py
git commit -m "feat(gear): active loadout-profile resolution + auto-record hook"
```

---

### Task 4: Bank-expansion wiring (used-floor)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/expand_bank.py` (feed the floor)
- Test: `tests/ai/test_expand_bank_profile_floor.py`

**Interfaces:**
- Consumes: `loadout_profiles.active_bank_space_cost`, `should_expand_bank` (unchanged), the proven `shouldExpandBank_floor_preserves`.

- [ ] **Step 1: Write the test**

```python
# tests/ai/test_expand_bank_profile_floor.py
"""Bank expands when active-profile gear would overflow the bank (used-floor)."""

def test_expansion_fires_on_profile_overflow(expand_fixture):
    # current bank_used below trigger, but active-profile bank_space_cost above it
    state, game_data, history = expand_fixture
    goal = ExpandBankGoal(...)  # match the constructor
    assert not goal.is_satisfied(state)  # i.e. it WANTS to expand (loadout floor pushed used over trigger)
```

> Open `expand_bank.py` for the exact `ExpandBankGoal` constructor + `is_satisfied` shape; build the fixture so current `len(bank_items)` is below the trigger but `active_bank_space_cost` is above it, with gold ≥ cost + reserve.

- [ ] **Step 2: Run to verify failure** (current code ignores profiles → no expansion).

- [ ] **Step 3: Feed the floor in `expand_bank.py`**

Where `should_expand_bank(used, game_data.bank_capacity, ...)` is called (line ~46), compute `used' = max(used, active_bank_space_cost(state, game_data, history, combat_monster, gather_skills))` and pass `used'`. The goal must receive the `history` + current-task context (combat_monster / gather_skills) — thread them via the constructor the way other goals get `ctx` fields (match `strategy_driver`'s `ExpandBankGoal(...)` construction at line 383; add the needed fields). Cost/capacity stay `game_data.next_expansion_cost`/`bank_capacity` (live v8).

- [ ] **Step 4: Run + commit**

New test + full suite + mypy. `git checkout uv.lock`.

```bash
git add src/artifactsmmo_cli/ai/goals/expand_bank.py src/artifactsmmo_cli/ai/strategy_driver.py tests/ai/test_expand_bank_profile_floor.py
git commit -m "feat(gear): bank expansion fires on active-profile overflow (used-floor)"
```

---

### Task 5: Keep-economy consumer migration (the replace)

Reroute the GEAR portion of every protection site from `target_gear`/`target_tools` to the active-profile gear set. NON-gear protection unchanged. This is the behavior change.

**Files (per-site):**
- `src/artifactsmmo_cli/ai/tiers/guards.py` (SelectionContext: carry the active-profile gear set), `src/artifactsmmo_cli/ai/strategy_driver.py` (build it once; feed protected_codes from it), `src/artifactsmmo_cli/ai/inventory_caps.py` (equippable keep up to `gear_demand`), `src/artifactsmmo_cli/ai/inventory_profile.py` (gear roots = active-profile gear), `src/artifactsmmo_cli/ai/recycle_surplus.py` / `src/artifactsmmo_cli/ai/bank_selection.py` (consume the new protected set), `src/artifactsmmo_cli/ai/actions/factory.py` (recycle-exclusion).
- Test: `tests/ai/test_keep_economy_profiles.py` (new) + updates to existing keep/recycle/deposit tests.

**Migration rule (apply per site):** the PROTECTION uses of `ctx.target_gear | ctx.target_tools` (recycle protected_codes 311/352/355, deposit profile_codes, bank keep gear part, factory recycle-exclusion 191) → the active-profile gear set ∪ {in-flight upgrade}. The PURSUIT uses (craft_relief source_codes 679/691 — the gear the bot crafts next) STAY on `target_gear` (pursuit ≠ protection). For each migrated site, the protected gear codes = `set(active_profile_gear(...).keys()) | in_flight_upgrade_codes`; inventory_caps keeps each up to `gear_demand(code)` (not blanket 1).

- [ ] **Step 1: Write the behavior tests**

```python
# tests/ai/test_keep_economy_profiles.py
def test_unprofiled_gear_becomes_reclaimable(keep_fixture): ...   # gear in NO active profile + not in-flight -> recyclable
def test_profiled_gear_protected(keep_fixture): ...               # gear in an active profile -> kept up to demand, not recycled/banked/sold
def test_inflight_upgrade_not_recycled(keep_fixture): ...         # target_gear pursuit item mid-craft -> +1 spare protected
def test_shared_gear_kept_once(keep_fixture): ...                 # 2 profiles share copper_dagger -> keep 1
def test_nongear_protection_unchanged(keep_fixture): ...          # tasks_coin/task_code/consumables/recipe-materials still protected exactly as before
```

> The last test is the critical regression lock — assert the non-gear keep-set is byte-identical to pre-migration for a fixture exercising task/consumable/material protection.

- [ ] **Step 2-4: Migrate each site** (one sub-commit acceptable, or a single commit). For each: replace the gear protected-set source, keep non-gear logic, run that site's existing tests, update any that asserted old target_gear-closure gear protection (cite the spec's intentional replace). If a non-gear test changes, STOP — only GEAR protection should change.

- [ ] **Step 5: Full suite + mypy + commit**

`~/.local/bin/uv run pytest --cov-fail-under=100 -q`; mypy on all touched files. Document each intentional behavior change in its test. `git checkout uv.lock`.

```bash
git add -A && git commit -m "feat(gear): keep economy uses active-profile gear set (replaces target_gear protection)"
```

---

### Task 6: Differential + mutation + extraction + full gate

**Files:**
- Create: `formal/diff/test_loadout_profiles_diff.py`; Modify `formal/Oracle.lean` (gearDemand/bankSpaceCost handlers), `formal/diff/mutate.py`
- Re-extract drifted `Extracted/*.lean`

- [ ] **Step 1: Oracle handlers** for `gearDemand`/`bankSpaceCost` (hand defs), per the `g NN` idiom; build + smoke-test.
- [ ] **Step 2: Differential** `test_loadout_profiles_diff.py` — live `gear_demand`/`bank_space_cost` ≡ oracle over random loadout sets + equipped (NO `unique=True`).
- [ ] **Step 3: Mutation** — drop the `max` in `gear_demand`, the `- equipped` in `bank_space_cost`, the `max(used,cost)` floor (Task 4) → each killed. Run runner; `git diff src` empty.
- [ ] **Step 4: Re-extract** (`scripts/extract_lean.py`); confirm only header/line drift; `lake build` the InventoryCaps/RealizableLoadout contracts still elaborate.
- [ ] **Step 5: Full suite + full gate.** `~/.local/bin/uv run pytest --cov-fail-under=100`; `cd formal && ./gate.sh` green end-to-end. `git diff src` empty; `git checkout uv.lock`.
- [ ] **Step 6: Commit** — `test(gear): differential + mutation + full-gate lock for loadout profiles`.

---

## Final review (after all tasks)

Whole-branch review over `git merge-base main HEAD..HEAD`. Verify:
- ONE protected-gear definition (active-profile gear set + in-flight spare); `target_gear` retained ONLY for pursuit; no protection site still reads `target_gear`/`target_tools` for the GEAR keep.
- Non-gear protection (tasks_coin/task_code/consumables/recipe materials) byte-identical to before (regression-locked).
- Dedup: shared gear kept once; rings 2; demand = MAX not sum. Un-profiled gear reclaimable; in-flight upgrade safe.
- Bank expansion fires on profile overflow using LIVE v8 cost/capacity; reserve gate intact; rides proven monotonicity.
- Soundness: differential calls live cores; oracle runs hand defs; theorems pinned in Contracts + Audit; mutation kills MAX / equipped-subtraction / floor.
- `record_loadout_profile` best-effort (SQLAlchemyError only). Then `superpowers:finishing-a-development-branch`.

## Self-review notes (plan author)

- **Spec coverage:** persistence→T1; cores+Lean→T2; active resolution+auto-create→T3; bank wiring→T4; keep-economy replace→T5; differential/mutation/gate→T6. All covered.
- **Protection vs pursuit split** is the delicate part of T5 — the migration rule lists which `target_gear` uses migrate (protection) vs stay (pursuit). The non-gear-unchanged regression lock is the safety net.
- **Naming consistency:** `gear_demand`/`bank_space_cost`/`active_loadouts`/`active_profile_gear`/`active_bank_space_cost`/`combat_key`/`gather_key`/`record_loadout_profile`/`loadout_profiles` — used identically across tasks.
- **Honest open seams** (match-the-sibling): `LearningStore.__init__` signature, `recent_goal_cycles` API for `_recent_task_keys`, `ExpandBankGoal` constructor, the keep/recycle test fixtures, Oracle/mutate idioms — each says "open the sibling and match."
- **Live v8** cost/capacity verified (8.0.0 client == server); T4 keeps them live-sourced.
