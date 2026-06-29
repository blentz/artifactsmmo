# Gear Sub-project D — Learned Combat-Loadout Diagnostics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture ground-truth combat-loadout outcomes (worn loadout, predict_win verdict, actual win/loss) per task and expose them in a read-only CLI report — with NO change to bot behavior.

**Architecture:** An append-per-fight `CombatLoadoutOutcome` LearningStore table; a recording hook in the player cycle loop firing on `FightAction` win/loss; a read-only `combat-loadout-report` CLI mirroring `macro-research` (pure aggregator + formatter + thin command). No Lean — D drives no bot decision.

**Tech Stack:** Python 3.13 (`uv` at `~/.local/bin/uv`), SQLModel/SQLite (LearningStore), typer (CLI), pytest (`--cov-fail-under=100`).

## Global Constraints

- `uv` at `~/.local/bin/uv`; ALWAYS `uv run`. `git checkout uv.lock` before commit if dirtied.
- No inline imports; no `if TYPE_CHECKING`; no `...` imports; NEVER catch `Exception` (LearningStore methods catch `SQLAlchemyError` only). ONE behavioral class per file.
- Use only API data or fail. Tests: 0 errors/warnings/skipped, 100% coverage; tests in `tests/`; real fixtures; never mock the unit under test. NO live-network test (test against crafted store rows).
- **No formal lockstep** — D drives no bot decision (pure recording + read-only aggregation); justified coverage-carve documented in `formal/README.md`. D adds no Lean and changes no proved core, so `formal/gate.sh` stays green.
- Branch: `feat/gear-learned-loadout` (off main `725b6836`). Spec: `docs/superpowers/specs/2026-06-29-gear-learned-loadout-design.md`.

**Verbatim facts:**
- Hook fires for `FightAction` ONLY when `outcome in {"ok", "error:fight_lost"}` (a real fight resolved; skip cooldown/other errors — no fight happened). `actual_win = (outcome == "ok")`.
- `task_key` = `combat:<monster_code>` (reuse `loadout_profiles.combat_key`).
- `loadout` = `prev_state.equipment` non-`None` slots, `json.dumps(sort_keys=True)`.
- `predicted_win` = `combat.predict_win(prev_state, game_data, monster_code)`.
- Store template = `CraftYieldObservation`/`LoadoutProfileObservation` (models.py) + `record_*`/accessor (store.py); catch `SQLAlchemyError` only.
- CLI template = `commands/macro_research.py` + `ai/macro/reader.py`/`report.py` (typer `--db`/`--out`; `_default_db_path()` → `~/.cache/artifactsmmo/learning.db`; load→pure-aggregate→markdown→print/write; registered in `main.py:60`).
- Player hook site: cycle loop, right after `if outcome == "ok": self._record_loadout_for_action(...)` (player.py ~668).

---

### Task 1: `CombatLoadoutOutcome` table + store record/accessor

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py`, `src/artifactsmmo_cli/ai/learning/store.py`
- Test: `tests/ai/learning/test_combat_loadout_outcome_store.py` (new)

**Interfaces:**
- Produces: `LearningStore.record_combat_outcome(task_key: str, loadout: dict[str, str], predicted_win: bool, actual_win: bool) -> None` (append, best-effort); `LearningStore.combat_loadout_outcomes() -> list[CombatLoadoutOutcomeRow]` where each row exposes `character, task_key, loadout: dict[str,str], predicted_win: bool, actual_win: bool` (best-effort, `[]` on error).

- [ ] **Step 1: Write the failing store test**

```python
# tests/ai/learning/test_combat_loadout_outcome_store.py
from artifactsmmo_cli.ai.learning.store import LearningStore


def test_record_and_read_combat_outcomes(tmp_path):
    store = LearningStore(db_path=tmp_path / "t.db", character="Robby")
    store.record_combat_outcome("combat:chicken", {"weapon_slot": "wooden_stick"}, True, True)
    store.record_combat_outcome("combat:chicken", {"weapon_slot": "iron_sword"}, True, False)
    rows = [r for r in store.combat_loadout_outcomes() if r.task_key == "combat:chicken"]
    assert len(rows) == 2  # APPEND (history), not last-write
    assert rows[0].loadout == {"weapon_slot": "wooden_stick"}
    assert rows[0].predicted_win is True and rows[0].actual_win is True
    assert rows[1].actual_win is False
    store.close()


def test_combat_outcomes_per_character_isolated(tmp_path):
    db = tmp_path / "t.db"
    a = LearningStore(db_path=db, character="A")
    a.record_combat_outcome("combat:chicken", {"weapon_slot": "stick"}, True, True)
    a.close()
    b = LearningStore(db_path=db, character="B")
    assert b.combat_loadout_outcomes() == []
    b.close()
```

> Match `LearningStore.__init__` (`db_path, character`) + the craft_yield/loadout_profile store-test fixture style. Decide the row type returned by `combat_loadout_outcomes()` — a small frozen dataclass/NamedTuple (`CombatLoadoutOutcomeRow`) decoupling callers from the SQLModel row (so the JSON is already parsed to `dict`). Define it where the accessor lives.

- [ ] **Step 2: Run to verify failure** — `~/.local/bin/uv run pytest tests/ai/learning/test_combat_loadout_outcome_store.py -v` → FAIL (method missing).

- [ ] **Step 3: Add the append table (models.py)**

```python
class CombatLoadoutOutcome(SQLModel, table=True):
    """One row per resolved fight: the worn loadout, predict_win's verdict, and the
    actual result. APPEND (calibration history; NOT last-write). task_key is
    'combat:<monster>'. `loadout` is JSON {slot: code}. Read-only diagnostics
    (sub-project D); drives no bot behavior."""

    __tablename__ = "combat_loadout_outcome"

    id: int | None = Field(default=None, primary_key=True)  # autoincrement
    character: str = Field(index=True)
    task_key: str
    loadout: str  # JSON {slot: code}
    predicted_win: bool
    actual_win: bool
```

- [ ] **Step 4: Add record/accessor (store.py)**

Mirror `record_loadout_profile`/`loadout_profiles` (catch `SQLAlchemyError` only; write prints `[learning] record_combat_outcome failed: ...`; read returns `[]`). `record_combat_outcome` is an INSERT (append, no upsert). The accessor returns the decoupled row type:

```python
@dataclass(frozen=True)
class CombatLoadoutOutcomeRow:
    character: str
    task_key: str
    loadout: dict[str, str]
    predicted_win: bool
    actual_win: bool


def record_combat_outcome(self, task_key, loadout, predicted_win, actual_win):
    try:
        with SqlSession(self._engine) as s:
            s.add(CombatLoadoutOutcome(
                character=self._character, task_key=task_key,
                loadout=json.dumps(loadout, sort_keys=True),
                predicted_win=predicted_win, actual_win=actual_win))
            s.commit()
    except SQLAlchemyError as e:
        print(f"[learning] record_combat_outcome failed: {e}")

def combat_loadout_outcomes(self):
    try:
        with SqlSession(self._engine) as s:
            rows = s.exec(select(CombatLoadoutOutcome).where(
                CombatLoadoutOutcome.character == self._character)).all()
        return [CombatLoadoutOutcomeRow(r.character, r.task_key, json.loads(r.loadout),
                                        r.predicted_win, r.actual_win) for r in rows]
    except SQLAlchemyError:
        return []
```

Place `CombatLoadoutOutcomeRow` in its own module or beside the accessor (ONE behavioral class per file — this is a pure data dataclass, exempt). `import json` already present (Task-1 of C added it).

- [ ] **Step 5: Run + commit**

`~/.local/bin/uv run pytest tests/ai/learning/test_combat_loadout_outcome_store.py -v` (pass); full suite; `~/.local/bin/uv run mypy --strict` on the 2 files. `git checkout uv.lock`.

```bash
git add src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py tests/ai/learning/test_combat_loadout_outcome_store.py
git commit -m "feat(gear-d): CombatLoadoutOutcome append table + record/accessor"
```

---

### Task 2: Player recording hook (win + loss)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_player_learning.py` (extend)

**Interfaces:**
- Consumes: `record_combat_outcome` (Task 1), `combat.predict_win`, `loadout_profiles.combat_key`, `FightAction`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_ai/test_player_learning.py
def test_records_combat_outcome_on_win(player_fixture): ...
def test_records_combat_outcome_on_loss(player_fixture): ...   # outcome="error:fight_lost" → actual_win False, still recorded
def test_no_combat_outcome_on_cooldown_or_nonfight(player_fixture): ...  # error:cooldown / non-Fight → no row
```

> Reuse the existing player-learning fixture (the one `test_record_loadout_*` uses). Assert via `history.combat_loadout_outcomes()`: a win → one row predicted=<predict_win at that state>, actual_win True, loadout=worn; a loss → actual_win False; a cooldown/non-fight → no row.

- [ ] **Step 2: Run to verify failure** — FAIL (no `_record_combat_outcome`).

- [ ] **Step 3: Add the hook**

Add a method + call it in the cycle loop right after the existing `if outcome == "ok": self._record_loadout_for_action(...)` (player.py ~668), NOT gated on `ok`:

```python
def _record_combat_outcome(self, action: Action, state: WorldState, outcome: str) -> None:
    """Record a resolved fight's worn loadout + predict_win verdict + result for
    diagnostics (sub-project D). Fires on win ('ok') and loss ('error:fight_lost')
    only — other outcomes mean no fight resolved. Best-effort; drives no behavior."""
    if self.history is None or self.game_data is None:
        return
    if not isinstance(action, FightAction):
        return
    if outcome not in ("ok", "error:fight_lost"):
        return
    loadout = {slot: code for slot, code in state.equipment.items() if code is not None}
    predicted = predict_win(state, self.game_data, action.monster_code)
    self.history.record_combat_outcome(
        combat_key(action.monster_code), loadout, predicted, outcome == "ok")
```

Call site (after the C hook block):

```python
                if outcome == "ok":
                    self._record_loadout_for_action(action, prev_state_for_learning)
                self._record_combat_outcome(action, prev_state_for_learning, outcome)
```

Add top-level imports if absent: `from artifactsmmo_cli.ai.combat import predict_win` (check — player may already import it), `combat_key` is from `loadout_profiles` (already imported for the C hook).

- [ ] **Step 4: Run + commit**

Run the new tests + full suite + mypy on player.py. `git checkout uv.lock`.

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_learning.py
git commit -m "feat(gear-d): record combat-loadout outcome on fight win/loss"
```

---

### Task 3: Read-only `combat-loadout-report` CLI

**Files:**
- Create: `src/artifactsmmo_cli/ai/macro/loadout_calibration.py` (pure aggregator + markdown formatter), `src/artifactsmmo_cli/commands/combat_loadout_report.py` (thin command)
- Modify: `src/artifactsmmo_cli/main.py` (register), `src/artifactsmmo_cli/ai/macro/reader.py` if a shared reader fits — else a small loader in the command
- Test: `tests/ai/macro/test_loadout_calibration.py`, `tests/commands/test_combat_loadout_report.py`

**Interfaces:**
- Consumes: `LearningStore.combat_loadout_outcomes()` / `CombatLoadoutOutcomeRow` (Task 1).
- Produces: pure `loadout_calibration_report(rows: list[CombatLoadoutOutcomeRow]) -> str` (markdown); `combat_loadout_report(db, out)` typer command.

- [ ] **Step 1: Write the failing aggregator tests**

```python
# tests/ai/macro/test_loadout_calibration.py
from artifactsmmo_cli.ai.learning.store import CombatLoadoutOutcomeRow
from artifactsmmo_cli.ai.macro.loadout_calibration import loadout_calibration_report


def _row(task, loadout, pred, act):
    return CombatLoadoutOutcomeRow("Robby", task, loadout, pred, act)


def test_report_calibration_buckets():
    rows = [
        _row("combat:chicken", {"weapon_slot": "stick"}, True, True),
        _row("combat:chicken", {"weapon_slot": "stick"}, True, False),   # predicted-win but lost
        _row("combat:wolf", {"weapon_slot": "sword"}, False, True),      # predicted-loss but won
    ]
    report = loadout_calibration_report(rows)
    assert "combat:chicken" in report
    assert "predicted-win but lost" in report.lower() or "over-estimate" in report.lower()
    # chicken: 2 fights, predicted-win 100%, actual-win 50%, 1 over-estimate
    assert "combat:wolf" in report


def test_report_per_loadout_tally():
    rows = [
        _row("combat:chicken", {"weapon_slot": "stick"}, True, True),
        _row("combat:chicken", {"weapon_slot": "stick"}, True, True),
        _row("combat:chicken", {"weapon_slot": "axe"}, True, False),
    ]
    report = loadout_calibration_report(rows)
    assert "stick" in report and "axe" in report   # both worn loadouts surfaced with tallies


def test_report_empty_rows():
    assert isinstance(loadout_calibration_report([]), str)   # no crash, empty-state message
```

- [ ] **Step 2: Run to verify failure** — module missing.

- [ ] **Step 3: Implement the pure aggregator + formatter**

`loadout_calibration.py`: group rows by `task_key`; per task compute predicted-win rate, actual-win rate, the two mis-prediction bucket counts (predicted-win&¬actual = over-estimate; ¬predicted-win&actual = under-estimate); per distinct `loadout` (use `json.dumps(sort_keys=True)` of the dict, or a frozenset of items, as the group key) compute win/loss tally; render a markdown report ranked by worst calibration (largest over-estimate rate first). Pure function `(rows) -> str`; mirror `report.format_report`'s markdown-table style. Handle empty input with an empty-state message.

- [ ] **Step 4: Implement the command + register**

`commands/combat_loadout_report.py` mirroring `macro_research.py`: typer `--db`/`--out` options + `_default_db_path()` → `~/.cache/artifactsmmo/learning.db`; `BadParameter` if db missing; load rows (open a `LearningStore` read-only on the db path OR a small loader that selects `CombatLoadoutOutcome` rows across characters — match how `reader.load_cycle_rows` reads cross-character); call `loadout_calibration_report(rows)`; print or write to `--out`. Register in `main.py` beside `macro-research`:

```python
app.command("combat-loadout-report",
            help="Per-task predict_win calibration + which loadouts won (read-only)")(
    combat_loadout_report_command)
```

> If the report should span ALL characters (like macro-research), add a cross-character loader (select `CombatLoadoutOutcome` with no character filter) returning `CombatLoadoutOutcomeRow`s — don't reuse the per-character store accessor for the CLI. Match `macro-research`'s cross-character behavior. Decide + document.

- [ ] **Step 5: Write the command test**

```python
# tests/commands/test_combat_loadout_report.py
# Use typer's CliRunner (match existing command tests); seed a temp db with
# CombatLoadoutOutcome rows; invoke `combat-loadout-report --db <tmp>`; assert exit 0
# + the report text appears; assert BadParameter on a missing db.
```

- [ ] **Step 6: Run + commit**

Run both new test files + full suite + mypy on the 3 src files. `git checkout uv.lock`.

```bash
git add src/artifactsmmo_cli/ai/macro/loadout_calibration.py src/artifactsmmo_cli/commands/combat_loadout_report.py src/artifactsmmo_cli/main.py tests/ai/macro/test_loadout_calibration.py tests/commands/test_combat_loadout_report.py
git commit -m "feat(gear-d): read-only combat-loadout-report CLI (predict_win calibration)"
```

---

### Final verification (after all tasks)

- Full suite: `~/.local/bin/uv run pytest --cov-fail-under=100` (100%; D's new modules fully covered).
- Gate sanity (D adds no Lean / touches no proved core, so the formal gate is unaffected, but confirm): `cd formal && lake build` clean; optionally a full `cd formal && ./gate.sh` to certify nothing regressed.
- Add D to the `formal/README.md` coverage-carve-out list with the justification "read-only diagnostics, no bot decision logic."
- Dispatch the whole-branch reviewer over `git merge-base main HEAD..HEAD`. Verify: NO behavior change (no bot loadout-choice / predict_win / is_winnable edit); hook fires on win AND loss, only for resolved fights; records the WORN loadout (not pick_loadout); best-effort (`SQLAlchemyError` only); aggregator buckets correct; no live-network test; carve-out documented. Then `superpowers:finishing-a-development-branch`.

## Self-review notes (plan author)

- **Spec coverage:** table+store→T1; recording hook (win+loss, resolved-fights-only)→T2; pure aggregator+formatter+CLI+registration→T3; carve-out + gate sanity→final verification. All covered.
- **No behavior change** is the invariant — the final review explicitly checks no bot decision path changed (no predict_win/is_winnable/loadout-choice edit). T2 only ADDS a recording call.
- **No Lean** — D has no decision logic; the carve-out is documented (final verification). The aggregator is pure + unit-tested but drives no bot behavior, so no differential/mutation.
- **Naming consistency:** `CombatLoadoutOutcome`(table)/`CombatLoadoutOutcomeRow`(dataclass)/`record_combat_outcome`/`combat_loadout_outcomes`/`_record_combat_outcome`(hook)/`loadout_calibration_report`/`combat-loadout-report`(CLI) — used identically across tasks.
- **Honest open seams** (match-the-sibling): the store-test/player/command fixtures, the cross-character CLI loader decision, `CliRunner` usage — each says "match the existing sibling."
- **No live-network test** — explicitly required (dodges the flaky class that bit C).
