# Harnesses Read The Learning Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every verification harness under `formal/diff/` re-runnable from the learning store, so no evidence the code cites depends on `play-trace-*.jsonl` files the user deletes at will.

**Architecture:** One shared adapter (`formal/diff/store_records.py`) reads `cycles` rows and yields per-cycle records in the shape the harnesses already consume, so each harness changes its loader and not its logic. `cycles` gains a nullable `skill_levels_json` column — the one datum the store lacks — written pre-action from `prev_state.skills`. `craft_xp_replay` moves to `craft_yield` instead, which already carries what it needs.

**Tech Stack:** Python 3.13, `uv`, pytest, SQLModel/SQLAlchemy over SQLite, Lean 4 (`formal/`).

**Spec:** `docs/superpowers/specs/2026-08-15-harnesses-read-the-learning-store-design.md`

## Global Constraints

- Every Python command runs through `uv run`. `unset VIRTUAL_ENV` first. `uv` is at `/home/blentz/.local/bin/uv` and may not be on PATH — use the full path.
- **Never** `git add -A` — `formal/.lake` is a symlink to a shared 9.3 GB cache. Stage named paths only.
- **Never** `git checkout <path>` or `git stash` to undo. Copy aside with `cp` and copy back.
- **Never** pipe `formal/gate.sh` into `tail` — the exit code would be `tail`'s. Redirect to a file and echo `$?` separately.
- **Never** run `formal/gate.sh` concurrently with the bot or anything importing `src/`.
- **Never** use `--no-verify`.
- Imports at the top of the file. No inline imports. No `if TYPE_CHECKING`. No `except Exception`.
- **Never read from `/home/blentz/git/artifactsmmo/.cache` or the live `learning.db` destructively.** Migration tests run against a `cp` copy, never the original.
- A subset test run reports a coverage failure; the 100% criterion is whole-suite only. Judge by passed/failed counts.
- **A harness must fail loudly on an empty corpus** — exit non-zero with a message. A harness that silently finds nothing is indistinguishable from one that checked and found nothing wrong.
- **Any figure that moves must move in its citations in the same commit.** Known sites: `src/artifactsmmo_cli/ai/skill_xp_positive.py`, `src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py`, `src/artifactsmmo_cli/ai/learning/projections.py`, `formal/Formal/XpPositive.lean`, `formal/Formal/SkillXpPositive.lean`, and each harness's committed `formal/diff/*_report.txt`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/artifactsmmo_cli/ai/learning/models.py` | `Cycle.skill_levels_json` field | 1 |
| `src/artifactsmmo_cli/ai/learning/store.py` | one-shot `ALTER` for the new column | 1 |
| `src/artifactsmmo_cli/ai/player.py` | writes `skill_levels_json` from `prev_state.skills` | 1 |
| `formal/diff/store_records.py` | **new** — the shared store reader every harness uses | 2 |
| `formal/diff/xp_formula_replay.py` | reads the store | 3 |
| `formal/diff/level_cost_replay.py` | reads the store | 3 |
| `formal/diff/trace_lockstep.py` | reads the store | 4 |
| `formal/diff/trace_characterize.py` | reads the store | 4 |
| `formal/diff/craft_xp_replay.py` | reads `craft_yield` | 5 |
| `formal/diff/gather_xp_replay.py` | reads the store; empty until the new column fills | 6 |

---

### Task 1: `cycles.skill_levels_json`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py` (the `Cycle` model)
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (migration block in `__init__`)
- Modify: `src/artifactsmmo_cli/ai/player.py:3274` area (the `Cycle(...)` construction)
- Test: `tests/test_ai/test_learning_store.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Cycle.skill_levels_json: str | None` — a JSON object mapping skill name to the character's level in that skill **before** the cycle's action, or `None` when unknown.

**Background.** This mirrors, exactly, the `craft_yield.skill_level` column added in commit `f08dd5aa` — read that commit first; the reasoning, the nullability argument and the migration shape all transfer. The store already performs two one-shot `ALTER`s in `LearningStore.__init__` (for `delta_skill_xp_json` and `consumables_expended_json`); add a third alongside them, following that pattern rather than inventing one.

**Why pre-action.** The server's `level_penalty` applies at the level held when the XP is paid. A replay that reads the level *after* the action misattributes every action that levels the skill. The craft-XP work found the general form of this error the hard way: a replay taking the following snapshot credited each action with its neighbour's result, and it survived three review rounds before anyone checked it against `fight.xp`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_learning_store.py`, near the existing `TestGAMigration` class:

```python
class TestSkillLevelsColumn:
    def test_a_cycle_records_the_skill_levels_held_before_its_action(self, tmp_db_path):
        """The gap that forced the craft-xp measurement onto play-traces:
        `cycles` recorded skill DELTAS and never skill LEVELS, so a replay
        could not compute `skill_level - content_level` from the store at all.
        """
        import json
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        store.record_cycle(Cycle(
            ts="2026-08-15T00:00:00+00:00", cycle_index=0, outcome="ok",
            skill_levels_json=json.dumps({"mining": 11, "woodcutting": 4}),
        ))
        rows = store.recent_cycles(limit=1)
        assert json.loads(rows[0].skill_levels_json) == {"mining": 11, "woodcutting": 4}
        store.close()

    def test_a_cycle_written_without_levels_reads_back_as_none(self, tmp_db_path):
        """Nullable on purpose: the 49,263 rows already in the wild were
        written before this column existed and cannot acquire levels. A
        consumer must exclude them, not read them as level 0."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        store.record_cycle(Cycle(ts="2026-08-15T00:00:00+00:00",
                                 cycle_index=0, outcome="ok"))
        assert store.recent_cycles(limit=1)[0].skill_levels_json is None
        store.close()

    def test_an_old_cycles_table_gains_the_column_on_open(self, tmp_path):
        """The `consumables_expended_json` incident is what this mirrors: a
        column that shipped in the model without a matching one-shot ALTER made
        every record_cycle INSERT fail on pre-existing DBs, and learning went
        silently dead on old caches."""
        import sqlite3
        db_path = str(tmp_path / "old_cycles.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE cycles (
                id INTEGER PRIMARY KEY, ts TEXT NOT NULL, session_id TEXT NOT NULL,
                cycle_index INTEGER NOT NULL, character TEXT NOT NULL,
                selected_goal TEXT, action_repr TEXT, action_class TEXT, outcome TEXT,
                delta_skill_xp_json TEXT NOT NULL DEFAULT '{}',
                consumables_expended_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY, character TEXT, started_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        store = LearningStore(db_path=db_path, character="hero")
        check = sqlite3.connect(db_path)
        try:
            cols = {r[1] for r in check.execute("PRAGMA table_info(cycles)")}
        finally:
            check.close()   # unclosed connections surface as an unraisable
                            # warning blamed on a LATER test; close explicitly
        assert "skill_levels_json" in cols
        store.close()
```

If `recent_cycles` is not the accessor this store exposes, use whichever read method the neighbouring tests use — do not add a new one for the test's convenience.

- [ ] **Step 2: Run them and confirm they fail**

```bash
cd /home/blentz/git/artifactsmmo && unset VIRTUAL_ENV && \
  /home/blentz/.local/bin/uv run pytest tests/test_ai/test_learning_store.py \
  -q -k "SkillLevelsColumn" -p no:cacheprovider --no-cov
```

Expected: failures naming `skill_levels_json`.

- [ ] **Step 3: Add the model field**

In `models.py`'s `Cycle`, beside `delta_skill_xp_json`:

```python
    skill_levels_json: str | None = Field(default=None)
    """The character's skill levels BEFORE this cycle's action, as a JSON
    object, or None for a row written before this column existed (2026-08-15).

    PRE-ACTION, and that is load-bearing: the server's `level_penalty` applies
    at the level held when the xp is paid, so a replay reading the level after
    the action misattributes every action that levels the skill.

    `cycles` has always carried skill DELTAS (`delta_skill_xp_json`) and never
    LEVELS, which is why measurements needing `skill_level - content_level` had
    to read play-trace files instead — a dependency this column removes. See
    `docs/superpowers/specs/2026-08-15-harnesses-read-the-learning-store-design.md`.

    NULLABLE, NOT BACK-FILLED. The rows already in the wild were written
    without levels and cannot acquire them; inventing one would hand a
    measurement a fabricated observation."""
```

- [ ] **Step 4: Add the migration**

In `store.py`'s `__init__`, immediately after the `consumables_expended_json` block:

```python
            # Harness-migration column (2026-08-15): cycles gains the skill
            # levels held BEFORE the action. NULLABLE with no DEFAULT — the
            # rows already in the wild were written without levels, and
            # back-filling 0 or today's level would hand a replay a fabricated
            # observation. A consumer excludes NULL rather than defaulting it.
            if cols and "skill_levels_json" not in cols:
                conn.exec_driver_sql("ALTER TABLE cycles ADD COLUMN skill_levels_json TEXT")
```

- [ ] **Step 5: Write it at the cycle write site**

In `player.py`, in the `Cycle(...)` construction that begins at line 3240, immediately after the `delta_skill_xp_json=` line:

```python
            # PRE-action levels: `prev_state` is the state the action ran
            # against, so this is the level `level_penalty` applied at when the
            # server paid this cycle's xp.
            skill_levels_json=json.dumps(prev_state.skills, ensure_ascii=False,
                                         sort_keys=True),
```

- [ ] **Step 6: Run the tests**

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run pytest \
  tests/test_ai/test_learning_store.py tests/test_ai/test_player.py \
  -q -p no:cacheprovider --no-cov
```

Expected: all pass.

- [ ] **Step 7: Verify the migration against a COPY of the live cache**

```bash
cp /home/blentz/.cache/artifactsmmo/learning.db /tmp/lv_migrate_check.db
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python -c "
from artifactsmmo_cli.ai.learning.store import LearningStore
import sqlite3
s = LearningStore(db_path='/tmp/lv_migrate_check.db', character='Robby')
c = sqlite3.connect('/tmp/lv_migrate_check.db')
print('cols:', 'skill_levels_json' in {r[1] for r in c.execute('PRAGMA table_info(cycles)')})
print('rows preserved:', c.execute('select count(*) from cycles').fetchone()[0])
print('old rows null:', c.execute('select count(*) from cycles where skill_levels_json is null').fetchone()[0])
c.close(); s.close()
"
```

Expected: `True`, ~49263 rows preserved, and all of them null. **Never run this against the original DB.**

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py \
        src/artifactsmmo_cli/ai/player.py tests/test_ai/test_learning_store.py
git commit -m "feat(learning): record the skill levels held before each cycle's action

cycles carried skill DELTAS and never LEVELS, so any measurement needing
skill_level - content_level had to read play-trace files. That is the
dependency this column removes.

PRE-action, from prev_state.skills: level_penalty applies at the level held
when the xp is paid. Nullable, one-shot ALTER, no back-fill -- the rows already
in the wild cannot acquire levels and inventing them would feed a replay a
fabricated observation."
```

---

### Task 2: The shared store reader

**Files:**
- Create: `formal/diff/store_records.py`
- Test: `tests/test_formal/test_store_records.py` (create if the directory does not exist; otherwise put it beside the nearest existing `formal/diff` test)

**Interfaces:**
- Consumes: `Cycle.skill_levels_json` from Task 1.
- Produces:
  - `load_cycles(db_path: str, character: str | None = None) -> list[CycleRecord]`
  - `CycleRecord` — a frozen dataclass with fields: `character: str`, `cycle_index: int`, `action_repr: str | None`, `action_class: str | None`, `outcome: str | None`, `level: int | None`, `xp: int | None`, `hp: int | None`, `delta_xp: int | None`, `delta_hp: int | None`, `delta_skill_xp: dict[str, int]`, `skill_levels: dict[str, int] | None`
  - `EmptyCorpusError` — raised by `load_cycles` when the query returns no rows

**Background.** Each harness currently hand-rolls a loader over `play-trace-*.jsonl`, producing dicts shaped `{"cycle": n, "state": {...}, "action": ...}` and then *differencing consecutive states* to recover deltas. The store already stores those deltas per row, attributed to that row's own action.

**That difference is the point, not an implementation detail.** Differencing consecutive snapshots is what produced the off-by-one that made a craft replay credit every craft with the following cycle's XP. Reading `delta_xp` from the row removes the opportunity to make that mistake, because the row's delta belongs to the row's action by construction.

- [ ] **Step 1: Write the failing tests**

```python
import json
import pytest
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from formal.diff.store_records import EmptyCorpusError, load_cycles


def _seed(db_path, character="hero"):
    store = LearningStore(db_path=db_path, character=character)
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-08-15T00:00:00+00:00", cycle_index=0, outcome="ok",
        action_repr="Gather(copper_rocks)", action_class="GatherAction",
        level=12, xp=340, hp=90, delta_xp=0, delta_hp=-5,
        delta_skill_xp_json=json.dumps({"mining": 17}),
        skill_levels_json=json.dumps({"mining": 11}),
    ))
    store.close()


def test_load_cycles_reads_rows_as_records(tmp_db_path):
    _seed(tmp_db_path)
    [rec] = load_cycles(tmp_db_path)
    assert rec.action_repr == "Gather(copper_rocks)"
    assert rec.level == 12
    assert rec.delta_skill_xp == {"mining": 17}
    assert rec.skill_levels == {"mining": 11}


def test_a_row_without_skill_levels_reads_as_none_not_empty(tmp_db_path):
    """None means "this row cannot answer a level question"; {} would mean
    "the character had no skills", and a consumer must be able to tell those
    apart to exclude the row rather than treat it as level 0."""
    store = LearningStore(db_path=tmp_db_path, character="hero")
    store.start_session()
    store.record_cycle(Cycle(ts="2026-08-15T00:00:00+00:00",
                             cycle_index=0, outcome="ok"))
    store.close()
    [rec] = load_cycles(tmp_db_path)
    assert rec.skill_levels is None


def test_an_empty_corpus_raises_rather_than_returning_nothing(tmp_db_path):
    """A harness that silently finds nothing to check is indistinguishable
    from one that checked and found nothing wrong. Every consumer of this
    loader must fail loudly instead."""
    LearningStore(db_path=tmp_db_path, character="hero").close()
    with pytest.raises(EmptyCorpusError):
        load_cycles(tmp_db_path)
```

- [ ] **Step 2: Run them and confirm they fail**

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run pytest \
  tests/test_formal/test_store_records.py -q -p no:cacheprovider --no-cov
```

Expected: `ModuleNotFoundError: formal.diff.store_records`.

- [ ] **Step 3: Write the module**

`formal/diff/store_records.py`, with a module docstring stating why it exists (harnesses read the store, traces are a debugging artifact the user deletes) and why deltas are read rather than differenced (the off-by-one above). Implement `CycleRecord` as a frozen dataclass, `EmptyCorpusError` as a `RuntimeError` subclass, and `load_cycles` reading via `LearningStore`'s engine ordered by `(character, cycle_index)`. Parse `delta_skill_xp_json` defensively the way `learning/projections._parse_skill_xp` does — malformed JSON yields `{}` rather than raising — and parse `skill_levels_json` to `None` when absent.

- [ ] **Step 4: Run the tests**

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add formal/diff/store_records.py tests/test_formal/test_store_records.py
git commit -m "feat(diff): one store reader for every verification harness

Harnesses hand-rolled loaders over play-trace files and DIFFERENCED
consecutive state snapshots to recover deltas -- which is exactly how a craft
replay came to credit every craft with the following cycle's xp. The store
attributes each delta to its own row, so reading it removes the opportunity to
make that error.

Raises EmptyCorpusError rather than returning [] : a harness that silently
finds nothing looks identical to one that checked and found nothing wrong."
```

---

### Task 3: Migrate `xp_formula_replay` and `level_cost_replay`

**Files:**
- Modify: `formal/diff/xp_formula_replay.py`
- Modify: `formal/diff/level_cost_replay.py`
- Modify: `formal/diff/xp_formula_replay_report.txt`, `formal/diff/level_cost_replay_report.txt` (regenerate)

**Interfaces:**
- Consumes: `load_cycles`, `CycleRecord`, `EmptyCorpusError` from Task 2.
- Produces: nothing later tasks depend on.

**Background.** Both read only fields the store already has — `level`, `xp`, `action_repr`, `outcome`. `xp_formula_replay` anchors the combat XP gate (399/399 corroboration in its current report); `level_cost_replay` anchors `cheapest_path_to_level`.

Both currently take a trace path as `argv[1]` and a game-data snapshot as `argv[2]`. Keep the snapshot argument; replace the trace argument with a DB path defaulting to `~/.cache/artifactsmmo/learning.db`.

- [ ] **Step 1: Replace `xp_formula_replay`'s loader**

Delete its inline `trace.open()` loop and read `load_cycles(db_path)` instead. Its `for prev, cur in zip(records, records[1:])` pairing exists to recover a per-cycle XP delta by differencing; replace it with a single pass reading `rec.delta_xp` directly. Keep every counter and every printed line it already produces.

- [ ] **Step 2: Run it and capture the new numbers**

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python formal/diff/xp_formula_replay.py \
  > /tmp/xpf.txt 2>&1; echo "rc=$?"; cat /tmp/xpf.txt
```

Expected: rc=0 and a table. **The figures will differ from the committed report** — the corpus changed from 169 trace files to 49,263 rows. That is expected; what matters is that the conclusion holds. If the conclusion inverts, stop and report it rather than updating the report file.

- [ ] **Step 3: Regenerate its report and update citations**

Write the new output to `formal/diff/xp_formula_replay_report.txt`. Then grep for every citation of the old figures and update each one in this same commit:

```bash
grep -rn "xp_formula_replay" --include=*.py --include=*.lean --include=*.md src/ formal/ docs/
```

- [ ] **Step 4: Repeat Steps 1-3 for `level_cost_replay`**

Same shape: replace the `trace_dir.glob("play-trace-*.jsonl")` loop at line 80 with `load_cycles`, run it, regenerate `level_cost_replay_report.txt`, update every citation found by:

```bash
grep -rn "level_cost_replay" --include=*.py --include=*.lean --include=*.md src/ formal/ docs/
```

- [ ] **Step 5: Verify both fail loudly on an empty corpus**

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python -c "
from artifactsmmo_cli.ai.learning.store import LearningStore
LearningStore(db_path='/tmp/empty_corpus.db', character='x').close()"
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python formal/diff/xp_formula_replay.py /tmp/empty_corpus.db; echo "rc=$? (expect non-zero)"
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python formal/diff/level_cost_replay.py /tmp/empty_corpus.db; echo "rc=$? (expect non-zero)"
```

- [ ] **Step 6: Commit**

```bash
git add formal/diff/xp_formula_replay.py formal/diff/level_cost_replay.py \
        formal/diff/xp_formula_replay_report.txt formal/diff/level_cost_replay_report.txt
# plus every citation file the greps found
git commit -m "refactor(diff): xp_formula_replay and level_cost_replay read the store

Both needed only level, xp and action_repr, all of which cycles already has.
Corpus moves from 169 trace files to 49,263 rows, so the reported figures move
with it; every citation of a moved figure is updated in this commit."
```

---

### Task 4: Migrate `trace_lockstep` and `trace_characterize`

**Files:**
- Modify: `formal/diff/trace_lockstep.py`, `formal/diff/trace_characterize.py`
- Modify: their two committed `_report.txt` files (regenerate)

**Interfaces:**
- Consumes: `load_cycles`, `CycleRecord`, `EmptyCorpusError` from Task 2.
- Produces: nothing later tasks depend on.

**Background.** Both are diagnostic characterisations reading `level`, `xp` and `hp` — all present in `cycles`. Neither anchors a production constant, so their figures moving is lower-risk than Task 3's; the citation discipline still applies.

Note both are named `trace_*`. **Do not rename them in this task.** A rename changes every citation and every gate reference at the same time as the behaviour changes, which makes a regression impossible to bisect. If a rename is wanted, it is a separate commit after this one is green.

- [ ] **Step 1: Replace `trace_lockstep`'s loader with `load_cycles`, preserving every assertion and printed line.**

- [ ] **Step 2: Run it, confirm rc=0, regenerate `trace_lockstep_report.txt`.**

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python formal/diff/trace_lockstep.py \
  > formal/diff/trace_lockstep_report.txt 2>&1; echo "rc=$?"
```

- [ ] **Step 3: Repeat for `trace_characterize`.**

- [ ] **Step 4: Verify both exit non-zero against `/tmp/empty_corpus.db`.**

- [ ] **Step 5: Update any citations.**

```bash
grep -rn "trace_lockstep\|trace_characterize" --include=*.py --include=*.lean --include=*.md src/ formal/ docs/
```

- [ ] **Step 6: Commit**

```bash
git add formal/diff/trace_lockstep.py formal/diff/trace_characterize.py \
        formal/diff/trace_lockstep_report.txt formal/diff/trace_characterize_report.txt
git commit -m "refactor(diff): trace_lockstep and trace_characterize read the store

Names kept for now: renaming at the same time as the behaviour changes would
make a regression impossible to bisect."
```

---

### Task 5: `craft_xp_replay` reads `craft_yield`

**Files:**
- Modify: `formal/diff/craft_xp_replay.py`
- Modify: `formal/diff/craft_xp_replay_report.txt` (regenerate)
- Modify: `src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py` (`_beats`'s craft-XP paragraph, if its figures move)

**Interfaces:**
- Consumes: `craft_yield.skill_level` (added in commit `f08dd5aa`) and `LearningStore.observed_craft_xp(item_code) -> tuple[int, int, int | None] | None`.
- Produces: nothing later tasks depend on.

**Background.** This harness does **not** need Task 1's column: `craft_yield` already carries `(xp, quantity, skill_level)` per `(character, item_code)`. Rows whose `skill_level` is null — every row written before `f08dd5aa` — are **excluded, not defaulted**.

Its current trace path is removed entirely rather than kept as a fallback. A measurement that can be re-run one way and not the other invites someone to re-run the wrong one.

**Its numbers WILL move sharply.** The trace corpus gave 450 craft cycles across 13 items; `craft_yield` currently holds 73 rows over 27 items, of which the ones with a skill level are only those written since `f08dd5aa` — likely very few. Expect the verdict to become inconclusive for lack of data.

**That is an acceptable and correct outcome, and it must be reported as such.** Do not preserve the old REFUTED verdict by keeping the trace path, and do not manufacture coverage. `_beats`'s docstring currently states the REFUTED finding with figures from the trace corpus; if the store cannot reproduce it, the docstring must say the finding is historical, cite when it was measured, and state that the corpus behind it was deleted — not imply a reader can reproduce it today.

- [ ] **Step 1: Replace the trace loader with a `craft_yield` read**, excluding null-`skill_level` rows and reporting how many rows were excluded for that reason.

- [ ] **Step 2: Run it and read the coverage honestly.**

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python formal/diff/craft_xp_replay.py \
  > /tmp/craftxp.txt 2>&1; echo "rc=$?"; cat /tmp/craftxp.txt
```

- [ ] **Step 3: Regenerate `craft_xp_replay_report.txt` from that run.**

- [ ] **Step 4: Update `_beats`'s craft-XP paragraph** to match what the harness can now show, marking the trace-corpus finding as historical with its date and the fact that its corpus is gone.

- [ ] **Step 5: Regenerate the Lean extraction** — `_beats`'s docstring changed, which shifts the line numbers the generated Lean records:

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python scripts/extract_lean.py
bash formal/gate/check_extraction.sh > /tmp/xc.txt 2>&1; echo "rc=$?"; tail -2 /tmp/xc.txt
```

Expected: rc=0.

- [ ] **Step 6: Commit**

```bash
git add formal/diff/craft_xp_replay.py formal/diff/craft_xp_replay_report.txt \
        src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py \
        formal/Formal/Extracted/SkillGrindSelection.lean
git commit -m "refactor(diff): craft_xp_replay reads craft_yield, not play-traces

craft_yield already carries (xp, quantity, skill_level) since f08dd5aa. Rows
without a level are excluded, not defaulted.

Coverage drops sharply -- the trace corpus gave 450 cycles over 13 items and
craft_yield's levelled rows are only those written since f08dd5aa. The REFUTED
verdict is therefore recorded as HISTORICAL, with its date and the fact that
its corpus was deleted, rather than preserved by keeping a trace path nobody
can re-run."
```

---

### Task 6: `gather_xp_replay` reads the store

**Files:**
- Modify: `formal/diff/gather_xp_replay.py`
- Modify: `formal/diff/gather_xp_replay_report.txt` (regenerate)
- Modify: `src/artifactsmmo_cli/ai/skill_xp_positive.py` (the gap table and `GREY_SKILL_GAP`'s docstring)
- Check: `formal/Formal/SkillXpPositive.lean`, `formal/Formal/XpPositive.lean` for citations

**Interfaces:**
- Consumes: `load_cycles` from Task 2 and `CycleRecord.skill_levels` from Task 1.
- Produces: nothing later tasks depend on.

**Background.** This is the harness the whole plan exists for, and the one whose evidence is most load-bearing: it anchors `GREY_SKILL_GAP = 11`, which gates every gather and craft the grind considers. Its current report rests on 3231 gathers with zero exceptions at the band boundary — measured on the trace corpus the user deleted.

It computes `gap = skill_levels[skill] - resource_level` and so needs Task 1's column. **Rows without `skill_levels` are excluded.** Since no historical row has them, the harness will initially find few or no usable observations.

**It must exit non-zero and say so.** A green run over zero observations would assert that the band holds while having checked nothing, which is precisely the vacuity this project has a standing rule against.

- [ ] **Step 1: Replace the loader with `load_cycles`, filtering to gather actions and excluding rows whose `skill_levels` is `None`.**

- [ ] **Step 2: Add the empty-corpus guard.**

```python
    if not usable:
        print("NO USABLE OBSERVATIONS: no cycle rows carry skill_levels_json.\n"
              "The column landed 2026-08-15; rows written before it are excluded\n"
              "rather than defaulted. Run the bot to accumulate observations.",
              file=sys.stderr)
        return 1
```

- [ ] **Step 3: Run it.**

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python formal/diff/gather_xp_replay.py; echo "rc=$?"
```

Expected today: rc=1 with that message. **That is the correct result, not a failure of the task.**

- [ ] **Step 4: Rewrite `skill_xp_positive.py`'s evidence paragraph.**

The docstring currently presents the gap table as something a reader can reproduce. Rewrite it to state: the boundary was measured on 2026-08-14 over 3231 gathers with no exception at gap 10 versus gap 11; that measurement's corpus (`play-trace-*.jsonl`) was deleted on 2026-08-15; and the harness now reads the learning store and will re-derive it once `skill_levels_json` accumulates. Keep the table — it is the evidence — but stop implying it is re-runnable today.

Do **not** change `GREY_SKILL_GAP`'s value. It is corroborated by the published docs, by `Formal.SkillXpPositive`, and by a mutation group; only its reproducibility changed.

- [ ] **Step 5: Regenerate the extraction if `skill_xp_positive.py`'s line numbers moved.**

```bash
unset VIRTUAL_ENV && /home/blentz/.local/bin/uv run python scripts/extract_lean.py
bash formal/gate/check_extraction.sh > /tmp/xc2.txt 2>&1; echo "rc=$?"; tail -2 /tmp/xc2.txt
```

- [ ] **Step 6: Regenerate `gather_xp_replay_report.txt`** with the no-observations output, so the committed report reflects what the harness now reports rather than a stale table.

- [ ] **Step 7: Run the full gate** (bot must be stopped).

```bash
unset VIRTUAL_ENV && bash formal/gate.sh > /tmp/gate_harness.log 2>&1; echo "rc=$?"
grep -nE "ALL GATE PARTS PASSED|GATE FAIL|Total coverage|planner_bug" /tmp/gate_harness.log | tail -5
```

Expected: rc=0. If the gate runs any of the migrated harnesses and one now exits non-zero, that is a real integration finding — report it rather than weakening the guard.

- [ ] **Step 8: Commit**

```bash
git add formal/diff/gather_xp_replay.py formal/diff/gather_xp_replay_report.txt \
        src/artifactsmmo_cli/ai/skill_xp_positive.py \
        formal/Formal/Extracted/SkillXpPositive.lean
git commit -m "refactor(diff): gather_xp_replay reads the store, and says when it cannot

This harness anchors GREY_SKILL_GAP = 11. Its evidence -- 3231 gathers, zero
exceptions at the boundary -- was measured on the play-trace corpus the user
deleted on 2026-08-15.

It now reads cycles.skill_levels_json and excludes rows without levels, which
today means every historical row. It therefore exits NON-ZERO reporting that it
has no usable observations, rather than passing green over an empty set.

GREY_SKILL_GAP is unchanged and not in doubt -- the published docs,
Formal.SkillXpPositive and a mutation group all corroborate it. What changed is
that its docstring no longer implies a reader can reproduce the table today."
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Increment 1 — `cycles.skill_levels_json`, pre-action, nullable, one-shot ALTER | 1 |
| Increment 2 — the four unblocked harnesses | 3, 4 |
| Increment 3 — `craft_xp_replay` reads `craft_yield` | 5 |
| Increment 4 — `gather_xp_replay`, exits non-zero on an empty corpus | 6 |
| "A harness must fail loudly on an empty corpus" | 2 (`EmptyCorpusError`), 3 Step 5, 4 Step 4, 6 Step 2 |
| "Citations move in the same commit as the figures" | 3 Steps 3-4, 4 Step 5, 5 Step 4, 6 Step 4 |
| The `GREY_SKILL_GAP` reproducibility cost, stated honestly | 6 Step 4 |
| Off-by-one guard (deltas read, not differenced) | 2 (background + `CycleRecord.delta_*`), 3 Step 1 |
| Migration verified against a copy of the live cache | 1 Step 7 |
| Full gate green with the bot stopped | 6 Step 7 |

No spec requirement is without a task. The spec's two residuals — the
shadow-decision gap, and fit-and-check sharing one source — are explicitly
out of scope there and have no task here, correctly.

**Type consistency:** `load_cycles(db_path, character=None) -> list[CycleRecord]` and `EmptyCorpusError` are defined in Task 2 and used under those names in Tasks 3, 4 and 6. `CycleRecord.skill_levels` is `dict[str, int] | None` throughout; `delta_skill_xp` is `dict[str, int]` (never None — malformed JSON yields `{}`). Task 5 uses `observed_craft_xp`, which already exists at `store.py` since `f08dd5aa` and returns `(xp, quantity, skill_level)`.

**Known risk, named rather than hidden:** Task 3 and Task 4 assume each harness's logic survives swapping a differenced delta for a stored one. If a harness turns out to need a field `cycles` does not carry — as `gather_xp_replay` did — that is a Task-1-shaped finding, not something to work around by reaching back to a trace file.
