# Iron Gear Acquisition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop pricing every skill-gated craft and every drop-sourced material at
`UNOBTAINABLE_PER_UNIT`, so `J` can rank iron-tier gear against the character-XP
trunk instead of never seeing it.

**Architecture:** Two independent pricing defects, each fixed at its own seam. (1)
`acquisition_cost._gated_craft_option` consults a grind rate averaged over the
last 100 cycles of *any* activity, which reads 0.0 for every character and every
crafting skill in the live database; it is replaced by a rate averaged over the
last 100 cycles the character actually spent grinding *that* skill. (2) Four
route-existence call sites ask `is_winnable` with the character's current,
possibly-damaged HP; they are moved onto a rested state, following the precedent
already set at `tiers/objective.py:224` and `tiers/guards.py:217`. No new
predicates, no new abstractions — one new store query and a state substitution at
four call sites.

**Tech Stack:** Python 3.13, `uv`, SQLModel/SQLAlchemy over SQLite, pytest with a
100%-coverage gate, Lean 4 differential + mutation gate under `formal/`.

**Spec:** `docs/PLAN_iron_gear_acquisition.md` — read it first. It carries the
probe evidence every task below argues from.

## Global Constraints

- Every Python command is prefixed `uv run` (`uv run pytest`, `uv run mypy`).
- Imports go at the top of the file. No inline imports. No `if TYPE_CHECKING`.
  No triple-dot relative imports.
- Never `except Exception`. Catch the specific error the call can raise.
- One behavioral class per file. These tasks add no classes.
- Tests live under `tests/`. No new "simple" test scripts.
- Success criteria for the suite: 0 errors, 0 warnings, 0 skipped, 100% coverage.
  `pyproject.toml` sets `--cov-fail-under=100`; `scripts/` is omitted from
  coverage, `src/` is not.
- Do not create a second implementation of anything. Fix in place.
- The full local gate is one command: `bash formal/gate.sh`, ~5 minutes warm.
  Redirect its output to a file — piping to `tail` reports the tail's exit code,
  not the gate's.
- Merge directly to `main` (`git push origin HEAD:main`), gate green before push.
  Do not open a PR.
- Mutation anchors must resolve to exactly one site. If a task edits a line an
  anchor quotes, refresh the anchor in the same commit and re-run
  `uv run python formal/diff/mutate.py --check-anchors`.
- The live learning database is
  `~/.cache/artifactsmmo/learning.db`. Durable claims rest on it, never on
  `play-trace-*.jsonl` — those are deleted periodically.

---

## File Structure

**Modified:**

- `src/artifactsmmo_cli/ai/learning/store.py` — add two query methods next to the
  existing `skill_xp_per_cycle` / `skill_xp_per_cycle_all` pair. This file already
  owns every learning query; the new ones belong beside their siblings so the
  three estimators can be read against each other.
- `src/artifactsmmo_cli/ai/acquisition_cost.py` — `_gated_craft_option` switches
  which estimator it consults. One call site, ~4 lines.
- `src/artifactsmmo_cli/ai/drop_obtainability.py` — `fightable_droppers` asks
  winnability at restorable HP.
- `src/artifactsmmo_cli/ai/obtain_sources.py` — `_drop_sources` likewise.
- `src/artifactsmmo_cli/ai/tiers/strategy.py` — two `drop_obtainable` calls
  likewise.
- `src/artifactsmmo_cli/ai/tiers/objective.py` — remove the now-redundant local
  `rested`, since the callee does it.
- `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py` — replace the "KNOWN GAP"
  docstring paragraph that Task 4 closes.

**Created:**

- `scripts/probe_acquisition_price.py` — the live probe from the investigation,
  committed so acceptance is re-runnable rather than a screenshot in a doc.
  `scripts/` is coverage-omitted by design (live I/O, needs a token).

**Tests modified:**

- `tests/test_ai/test_learning_store.py` — the new estimators.
- `tests/test_ai/test_acquisition_cost_wrapper.py` — `_store_with_rate` and two
  pinned tests whose seeded rows must now carry an `action_repr`.
- `tests/test_ai/test_drop_obtainability.py` — the HP-independence property.
- `tests/test_ai/test_obtain_sources.py` — same, at the `_drop_sources` seam.
- `tests/test_ai/test_skill_grind_target.py` — the memo key is sound once
  `obtainable` stops reading HP.

---

## Task 1: A grind rate that cannot decay to zero while the grind runs

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (add after
  `skill_xp_per_cycle_all`, which ends at line 661)
- Test: `tests/test_ai/test_learning_store.py`

**Interfaces:**
- Consumes: `Cycle.action_repr`, `Cycle.delta_skill_xp_json`,
  `_parse_skill_xp_value(raw, skill) -> int` (module-private, `store.py:61`),
  `LearningStore.WINDOW_RECENT = 100` (`store.py:116`).
- Produces:
  - `LearningStore.skill_grind_rate(skill: str, window: int = WINDOW_RECENT) -> float | None`
  - `LearningStore.fleet_skill_grind_rate(skill: str, window: int = WINDOW_RECENT) -> float | None`
  - `artifactsmmo_cli.ai.learning.store.grind_action_prefix(skill: str) -> str`

**Why this is the whole fix for D1.** The existing `skill_xp_per_cycle_all`
applies its `LIMIT 100` to *all* cycles and then measures one skill inside them.
The new estimator applies the limit to cycles that already matched
`action_repr LIKE 'LevelSkill(<skill>->%'`, so the sample is "the last 100 cycles
I spent grinding this skill". A character doing anything else does not dilute it,
and a grind in progress feeds the estimator that prices it.

**The trap to avoid, restated because a fix here is one edit away from
reintroducing a shipped bug.** `skill_xp_per_cycle` — the *conditional* mean over
cycles with a positive delta — read 54.0 against a true 1.08 on R2D2 (a 50x
under-pricing) and captured the bot for 4.5 hours on 2026-08-08. The new
estimator is *not* that: it keeps every zero-XP gathering cycle inside the grind
in the denominator. Measured on the live DB, a grind cycle pays 53–131 XP roughly
once in 23, and the new estimator lands at 1.59–4.92 rather than ~60. Step 1's
test asserts both numbers on one fixture so the distinction cannot rot.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_learning_store.py`. Match the file's existing style:
real `LearningStore` on `:memory:`, real `record_cycle`, no mocks.

```python
class TestSkillGrindRate:
    """The rate that prices a skill-gated craft, measured over the grind's OWN
    cycles rather than over the last 100 cycles of whatever the character
    happened to be doing."""

    @staticmethod
    def _grind_cycle(i: int, char: str, skill: str, xp: int) -> Cycle:
        return Cycle(
            ts=f"2026-08-17T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character=char, outcome="ok",
            action_repr=f"LevelSkill({skill}->10)",
            delta_skill_xp_json=json.dumps({skill: xp}),
        )

    def test_a_window_of_other_work_does_not_dilute_the_rate(self, tmp_db_path):
        """THE LIVE BUG, pinned. Every character in the live DB reads 0.0 from
        `skill_xp_per_cycle_all` for every crafting skill, because the last 100
        cycles are all fights. The grind's own cycles still say 5.0."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(10):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting",
                                                     50 if i == 0 else 0))
            for i in range(10, 210):
                store.record_cycle(Cycle(
                    ts=f"2026-08-17T01:00:{i % 60:02d}+00:00", session_id="s",
                    cycle_index=i, character="c", outcome="ok",
                    action_repr="Fight(pig)",
                    delta_skill_xp_json=json.dumps({}),
                ))
            assert store.skill_xp_per_cycle_all("gearcrafting") == 0.0
            assert store.skill_grind_rate("gearcrafting") == 5.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_conditional_mean_and_the_grind_rate_must_differ(self, tmp_db_path):
        """THE 41x TRAP, pinned on one fixture. `skill_xp_per_cycle` drops the
        zero-xp gathering cycles a grind is mostly made of and reports the
        paying cycle's figure as the rate. The grind rate keeps them in the
        denominator. If these two ever agree, this fix has become the bug it
        was written next to."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(10):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting",
                                                     50 if i == 0 else 0))
            assert store.skill_xp_per_cycle("gearcrafting") == 50.0
            assert store.skill_grind_rate("gearcrafting") == 5.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_all_zero_grind_cycles_report_zero_not_none(self, tmp_db_path):
        """A grind that ran and gained nothing is EVIDENCE, and must be
        distinguishable from never having ground at all: 0.0, not None. The
        caller declines on the first and may fall back on the second."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(5):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting", 0))
            assert store.skill_grind_rate("gearcrafting") == 0.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_skill_never_ground_reports_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(5):
                store.record_cycle(self._grind_cycle(i, "c", "mining", 40))
            assert store.skill_grind_rate("gearcrafting") is None
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_different_skills_grind_is_not_counted(self, tmp_db_path):
        """`LevelSkill(mining->10)` cycles gain woodcutting xp as a side effect
        (measured live: 1,491 woodcutting xp inside the gearcrafting grind).
        Those cycles are not evidence about how fast a WOODCUTTING grind goes."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(5):
                store.record_cycle(Cycle(
                    ts=f"2026-08-17T00:00:{i:02d}+00:00", session_id="s",
                    cycle_index=i, character="c", outcome="ok",
                    action_repr="LevelSkill(mining->10)",
                    delta_skill_xp_json=json.dumps({"woodcutting": 60}),
                ))
            assert store.skill_grind_rate("woodcutting") is None
            assert store.skill_grind_rate("mining") == 0.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_window_applies_to_matching_rows_only(self, tmp_db_path):
        """The limit counts GRIND cycles, not all cycles — which is the entire
        difference from `skill_xp_per_cycle_all`. Twelve grind cycles with a
        window of 10 measure the ten most recent of them."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            for i in range(2):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting", 100))
            for i in range(2, 12):
                store.record_cycle(self._grind_cycle(i, "c", "gearcrafting", 10))
            assert store.skill_grind_rate("gearcrafting", window=10) == 10.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_rate_is_scoped_to_this_character(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="mine")
        store.start_session()
        try:
            for i in range(5):
                store.record_cycle(self._grind_cycle(i, "other", "gearcrafting", 80))
            assert store.skill_grind_rate("gearcrafting") is None
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_fleet_rate_pools_every_character(self, tmp_db_path):
        """A character that has never ground a skill can still be told what the
        grind costs, by the siblings who have. Same query, character predicate
        dropped."""
        store = LearningStore(db_path=tmp_db_path, character="mine")
        store.start_session()
        try:
            for i in range(5):
                store.record_cycle(self._grind_cycle(i, "other", "gearcrafting", 80))
            assert store.skill_grind_rate("gearcrafting") is None
            assert store.fleet_skill_grind_rate("gearcrafting") == 80.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_the_fleet_rate_is_none_when_nobody_has_ground_it(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="mine")
        store.start_session()
        try:
            assert store.fleet_skill_grind_rate("gearcrafting") is None
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_malformed_delta_row_counts_as_zero(self, tmp_db_path):
        """Same tolerance the sibling estimators have: one bad row must never
        crash the average, and it counts as a zero gain rather than vanishing
        from the denominator."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            store.record_cycle(Cycle(
                ts="2026-08-17T00:00:00+00:00", session_id="s", cycle_index=0,
                character="c", outcome="ok",
                action_repr="LevelSkill(gearcrafting->10)",
                delta_skill_xp_json="not json",
            ))
            store.record_cycle(self._grind_cycle(1, "c", "gearcrafting", 10))
            assert store.skill_grind_rate("gearcrafting") == 5.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()

    def test_a_negative_delta_does_not_credit_the_rate(self, tmp_db_path):
        """A level reset writes a negative delta (measured live: -2,185 mining
        xp inside the gearcrafting grind). Clamped to 0, matching
        `skill_xp_per_cycle_all`'s `max(0, ...)`."""
        store = LearningStore(db_path=tmp_db_path, character="c")
        store.start_session()
        try:
            store.record_cycle(self._grind_cycle(0, "c", "gearcrafting", -100))
            store.record_cycle(self._grind_cycle(1, "c", "gearcrafting", 10))
            assert store.skill_grind_rate("gearcrafting") == 5.0
        finally:
            store.end_session(exit_reason="normal")
            store.close()
```

Also add a test that the prefix helper escapes SQL wildcards, next to the class:

```python
def test_grind_action_prefix_is_escaped_for_LIKE():
    """`_` is a single-character wildcard in SQL LIKE. No skill in the live
    catalog contains one today, so this is a guard against a future skill code
    like `heavy_mining` silently matching `heavyXmining`. The query uses
    `startswith(..., autoescape=True)`; this pins the prefix it escapes."""
    assert grind_action_prefix("gearcrafting") == "LevelSkill(gearcrafting->"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestSkillGrindRate -v --no-cov
```

Expected: FAIL, `AttributeError: 'LearningStore' object has no attribute 'skill_grind_rate'`.

- [ ] **Step 3: Implement the two methods**

Add `grind_action_prefix` as a module-level function beside `_parse_skill_xp_value`
in `src/artifactsmmo_cli/ai/learning/store.py` (after line 79):

```python
def grind_action_prefix(skill: str) -> str:
    """The `action_repr` prefix every `LevelSkill` cycle for `skill` carries.

    `LevelSkill.__repr__` (`ai/actions/level_skill.py:95`) renders
    `LevelSkill({skill}->{target_level})`, so the target level is the only thing
    that varies. Matching on the prefix counts a
    `->5` grind and a `->10` grind as the same evidence about how fast this
    character gains xp in this skill, which is what they are.
    """
    return f"LevelSkill({skill}->"
```

Add both methods immediately after `skill_xp_per_cycle_all` (which ends at line
661), so the three estimators sit together:

```python
    def skill_grind_rate(self, skill: str,
                         window: int = WINDOW_RECENT) -> float | None:
        """Mean per-cycle XP gain for `skill` over the most recent `window`
        cycles THIS CHARACTER SPENT GRINDING IT.

        The difference from `skill_xp_per_cycle_all` is where the LIMIT falls.
        That method limits to the last `window` cycles and then measures one
        skill inside them, so a character doing anything else reads 0.0 —
        measured 2026-08-17 on the live DB, all five characters read exactly
        0.0 for all four crafting skills, which made
        `acquisition_cost._gated_craft_option` decline every skill-gated craft
        and price every iron-tier item at `UNOBTAINABLE_PER_UNIT`. That is an
        absorbing state: the price forbids the grind, and the absent grind
        keeps the price. Here the LIMIT falls on rows that already matched the
        grind's `action_repr`, so the sample is the grind's own cycles and a
        grind in progress feeds the estimate that prices it.

        The zero-xp cycles INSIDE the grind stay in the denominator, and that
        is the safety property. A grind is mostly gathering: measured over
        3,658 live `LevelSkill(gearcrafting->10)` cycles, 136 were a craft
        paying 53-131 xp and 3,112 were 30-second gathers paying nothing.
        `skill_xp_per_cycle` above drops those gathers and so reported 54.0
        against a true 1.08 — the 50x under-pricing that committed R2D2 to 207
        `LevelSkill` actions over 4.5 hours for +270 skill xp and zero
        character xp (2026-08-08). This estimator reports 1.59-4.92 on the same
        live data. `TestSkillGrindRate.test_the_conditional_mean_and_the_grind_rate_must_differ`
        pins the two apart on one fixture.

        Returns None when this character has no recorded grind cycles for the
        skill — ignorance, on which the caller may fall back to
        `fleet_skill_grind_rate`. Returns 0.0 when the grind ran and gained
        nothing — evidence, on which the caller must decline. Those two are
        different answers and the caller must not conflate them.
        """
        return self._grind_rate(skill, window, character=self._character)

    def fleet_skill_grind_rate(self, skill: str,
                               window: int = WINDOW_RECENT) -> float | None:
        """`skill_grind_rate` pooled over EVERY character in the store.

        A character that has never ground a skill has no evidence of its own,
        but a sibling that has is evidence about the same server, the same
        recipes and the same workshops. The fallback is deliberately one-way:
        a character with its OWN observations always uses them, however
        unflattering, because its gear and level are baked into them.
        """
        return self._grind_rate(skill, window, character=None)

    def _grind_rate(self, skill: str, window: int,
                    character: str | None) -> float | None:
        """Shared body of the two grind-rate estimators — one query, so the
        per-character and fleet answers cannot drift into disagreeing about
        what a grind cycle is."""
        prefix = grind_action_prefix(skill)
        try:
            with SqlSession(self._engine) as s:
                stmt = select(Cycle.delta_skill_xp_json).where(
                    col(Cycle.action_repr).startswith(prefix, autoescape=True))
                if character is not None:
                    stmt = stmt.where(col(Cycle.character) == character)
                stmt = stmt.order_by(col(Cycle.id).desc()).limit(window)
                rows = list(s.exec(stmt))
            if not rows:
                return None
            total = sum(max(0, _parse_skill_xp_value(raw, skill)) for raw in rows)
            return float(total) / len(rows)
        except SQLAlchemyError:
            return None
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestSkillGrindRate -v --no-cov
uv run pytest tests/test_ai/test_learning_store.py -q --no-cov
```

Expected: PASS, no regressions in the rest of the file.

- [ ] **Step 5: Verify the estimator against the live database**

This is the step that proves the new query answers the question the spec measured.
Expected output is in `docs/PLAN_iron_gear_acquisition.md`'s increment-3 table:
own rates 3.58 / 1.59 / 4.92 / 2.28 and a fleet rate of 2.77.

```bash
uv run python -c "
from artifactsmmo_cli.ai.learning.store import LearningStore
DB='/home/blentz/.cache/artifactsmmo/learning.db'
for ch in ['C3P0','R2D2','Lor','HAL']:
    s=LearningStore(db_path=DB, character=ch)
    print(ch, 'own', s.skill_grind_rate('gearcrafting'),
              'fleet', s.fleet_skill_grind_rate('gearcrafting'),
              'old', s.skill_xp_per_cycle_all('gearcrafting'))
    s.close()
"
```

Expected: every `own` is a positive float near the table, every `old` is `0.0`.
If any `own` is `None` or `0.0`, stop — the `action_repr` prefix does not match
what `LevelSkill.__repr__` writes (`ai/actions/level_skill.py:95`), and the rest of this plan rests on it.

- [ ] **Step 6: Run lint and types**

```bash
uv run ruff check src/ tests/
uv run mypy src/
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(learning): a grind rate measured over the grind's own cycles

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Price the skill-gated craft from the grind rate

**Files:**
- Modify: `src/artifactsmmo_cli/ai/acquisition_cost.py:264-271` (inside
  `_gated_craft_option`)
- Modify: `tests/test_ai/test_acquisition_cost_wrapper.py:404-419`
  (`_store_with_rate`) and the two tests that seed rows without an `action_repr`
- Test: `tests/test_ai/test_acquisition_cost_wrapper.py`

**Interfaces:**
- Consumes: `LearningStore.skill_grind_rate`,
  `LearningStore.fleet_skill_grind_rate` (Task 1).
- Produces: no new names. `route_options` and `acquisition_actions` keep their
  signatures; only which rate reaches `skill_grind_cycles` changes.

**The existing tests are load-bearing and two of them must change.**
`_store_with_rate` records cycles with no `action_repr`, so under the new
estimator its store would report `None` and every test built on it would see the
route declined — a green-to-red cascade that says nothing about the fix. Stamping
the helper is not weakening a test, it is restoring the production invariant the
helper does not model: a real grind cycle always carries
`action_repr="LevelSkill(<skill>-><target>)"` because that is what
`GamePlayer` records for the action it executed.

`test_a_NON_POSITIVE_observed_rate_declines_the_route` needs the same stamp for a
sharper reason. Its name says *non-positive rate*, and after Task 1 an unstamped
row produces *no rate at all* — a different code path with a different meaning.
Left unstamped it would still pass, while silently testing absence instead of
evidence, and `test_no_observed_rate_declines_the_route` right below it already
covers absence. Two tests asserting the same branch under different names is how
a real branch goes uncovered.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_acquisition_cost_wrapper.py`:

```python
def test_a_window_of_fighting_no_longer_hides_the_grind(
        gated_state, game_data) -> None:
    """THE LIVE DEFECT, pinned at the pricing seam.

    Measured 2026-08-17: all five live characters read 0.0 from
    `skill_xp_per_cycle_all` for every crafting skill, because their recent
    cycles are fights, so `_gated_craft_option` declined every skill-gated
    craft and `iron_sword` priced at UNOBTAINABLE. The grind cycles that
    answer the question were sitting in the same table the whole time."""
    store = LearningStore(db_path=":memory:", character="fought_recently")
    store.start_session()
    try:
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-08-17T00:00:{i:02d}+00:00", session_id="s",
                cycle_index=i, character="fought_recently", outcome="ok",
                action_repr="LevelSkill(weaponcrafting->10)",
                delta_skill_xp_json=json.dumps({"weaponcrafting": 40}),
            ))
        for i in range(5, 205):
            store.record_cycle(Cycle(
                ts=f"2026-08-17T01:00:{i % 60:02d}+00:00", session_id="s",
                cycle_index=i, character="fought_recently", outcome="ok",
                action_repr="Fight(pig)",
                delta_skill_xp_json=json.dumps({}),
            ))
        assert store.skill_xp_per_cycle_all("weaponcrafting") == 0.0
        routes = route_options("iron_sword", gated_state, game_data,
                               NO_PROFILE_CONTEXT, store)
        assert [r.kind for r in routes] == ["craft"]
        assert routes[0].unlock == "skill:weaponcrafting:10"
        assert routes[0].unlock_actions > 0
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_a_sibling_that_has_ground_the_skill_prices_it_for_one_that_has_not(
        gated_state, game_data) -> None:
    """The fallback. A fresh character has no evidence of its own about how
    fast weaponcrafting goes; a sibling on the same server does. Own
    observations are never overridden by the fleet's — only absence is."""
    store = LearningStore(db_path=":memory:", character="fresh")
    store.start_session()
    try:
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-08-17T00:00:{i:02d}+00:00", session_id="s",
                cycle_index=i, character="veteran", outcome="ok",
                action_repr="LevelSkill(weaponcrafting->10)",
                delta_skill_xp_json=json.dumps({"weaponcrafting": 40}),
            ))
        assert store.skill_grind_rate("weaponcrafting") is None
        assert store.fleet_skill_grind_rate("weaponcrafting") == 40.0
        routes = route_options("iron_sword", gated_state, game_data,
                               NO_PROFILE_CONTEXT, store)
        assert [r.kind for r in routes] == ["craft"]
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_own_zero_evidence_beats_a_positive_fleet_rate(
        gated_state, game_data) -> None:
    """The fallback is ONE-WAY, and this is why. A character whose own grind
    ran and gained nothing has told us something about ITS gear and level that
    a sibling's number cannot override. `0.0` is evidence; `None` is
    ignorance; only ignorance falls back."""
    store = LearningStore(db_path=":memory:", character="stuck")
    store.start_session()
    try:
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-08-17T00:00:{i:02d}+00:00", session_id="s",
                cycle_index=i, character="stuck", outcome="ok",
                action_repr="LevelSkill(weaponcrafting->10)",
                delta_skill_xp_json=json.dumps({"weaponcrafting": 0}),
            ))
        for i in range(5, 10):
            store.record_cycle(Cycle(
                ts=f"2026-08-17T00:01:{i:02d}+00:00", session_id="s",
                cycle_index=i, character="veteran", outcome="ok",
                action_repr="LevelSkill(weaponcrafting->10)",
                delta_skill_xp_json=json.dumps({"weaponcrafting": 40}),
            ))
        assert store.skill_grind_rate("weaponcrafting") == 0.0
        assert store.fleet_skill_grind_rate("weaponcrafting") == 20.0
        assert not route_options("iron_sword", gated_state, game_data,
                                 NO_PROFILE_CONTEXT, store)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_acquisition_cost_wrapper.py -k "window_of_fighting or sibling_that_has_ground or own_zero_evidence" -v --no-cov
```

Expected: FAIL. The first two fail because `route_options` returns `[]`.

- [ ] **Step 3: Switch the call site**

In `src/artifactsmmo_cli/ai/acquisition_cost.py`, replace lines 264-268:

```python
    rate = store.skill_xp_per_cycle_all(skill)
    max_xp = state.skill_max_xp.get(skill, 0)
    if not rate or rate <= 0 or max_xp <= 0:
        return None
```

with:

```python
    # OWN evidence first, the fleet's only in its ABSENCE. `None` means this
    # character has never ground this skill; `0.0` means it ground it and
    # gained nothing, which is a fact about ITS gear and level that a
    # sibling's number must not paper over. The `is None` test is therefore
    # load-bearing and must not become a falsy test — `0.0 or fleet` would
    # silently make a stuck character borrow a healthy one's rate.
    rate = store.skill_grind_rate(skill)
    if rate is None:
        rate = store.fleet_skill_grind_rate(skill)
    max_xp = state.skill_max_xp.get(skill, 0)
    if not rate or rate <= 0 or max_xp <= 0:
        return None
```

Then update the docstring paragraph at `acquisition_cost.py:250-256`, which names
the retired estimator. Replace:

```
    So: no observations, a non-positive observed rate, or no `<skill>_max_xp`
    from the API all decline the route. A non-positive rate is EVIDENCE the grind
    is not progressing, which is a stronger reason to decline than ignorance is.
    Declining costs the character that one route, not its progress — every other
    root still competes."""
```

with:

```
    So: no observations anywhere in the fleet, a non-positive observed rate, or
    no `<skill>_max_xp` from the API all decline the route. A non-positive rate
    is EVIDENCE the grind is not progressing, which is a stronger reason to
    decline than ignorance is. Declining costs the character that one route, not
    its progress — every other root still competes.

    THE RATE COMES FROM THE GRIND'S OWN CYCLES (2026-08-17). It used to come
    from `skill_xp_per_cycle_all`, which averages over the last 100 cycles of
    ANY activity — so a character spending its recent cycles fighting read 0.0
    and this route was declined for every skill-gated craft it could ever want.
    Measured live: all five characters, all four crafting skills, 0.0, and every
    iron-tier item consequently priced at UNOBTAINABLE_PER_UNIT while the
    gearcrafting grind that would open it was itself unrankable. The two are the
    same fact: the price forbade the grind and the absent grind kept the price.
    `skill_grind_rate` limits to cycles whose `action_repr` is this skill's
    `LevelSkill`, so a grind in progress feeds the estimate that prices it."""
```

- [ ] **Step 4: Stamp the test helper and the mis-named pinned test**

In `tests/test_ai/test_acquisition_cost_wrapper.py`, change `_store_with_rate`
(lines 404-419) to stamp the action and say why:

```python
def _store_with_rate(skill: str, xp_per_cycle: int, cycles: int = 5) -> LearningStore:
    """A real `LearningStore` carrying observed skill-xp gains — not a stub.

    `skill_grind_rate` measures cycles whose `action_repr` is this skill's
    `LevelSkill`, so the rows carry one. That is not a concession to the query:
    a real grind cycle always carries it, because `GamePlayer` records the
    action it executed, and a row without one is a fixture that could not
    happen. Recording rows means asserting against the number the production
    query computes, rather than one this test invented."""
    store = LearningStore(db_path=":memory:", character="grind_probe")
    store.start_session()
    for i in range(cycles):
        store.record_cycle(Cycle(
            ts=f"2026-08-08T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="grind_probe", outcome="ok",
            action_repr=f"LevelSkill({skill}->10)",
            delta_skill_xp_json=json.dumps({skill: xp_per_cycle}),
        ))
    return store
```

In `test_a_NON_POSITIVE_observed_rate_declines_the_route`, add the same stamp to
the seeded rows and re-point the assertion, so the test keeps testing the branch
its name claims:

```python
        store.record_cycle(Cycle(
            ts=f"2026-08-08T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="no_progress", outcome="ok",
            action_repr="LevelSkill(weaponcrafting->10)",
            delta_skill_xp_json=json.dumps({"weaponcrafting": 0}),
        ))
    try:
        assert store.skill_grind_rate("weaponcrafting") == 0.0
```

Leave `test_no_observed_rate_declines_the_route` exactly as it is — it seeds no
rows at all, which is now precisely the `None` branch, and the two tests finally
cover two different branches.

In `test_the_UNCONDITIONAL_rate_is_what_prices_a_grind`, add the stamp to its ten
rows and extend the assertion pair so it pins all three estimators against each
other on the one fixture that distinguishes them:

```python
        assert store.skill_xp_per_cycle("weaponcrafting") == 50.0
        assert store.skill_xp_per_cycle_all("weaponcrafting") == 5.0
        assert store.skill_grind_rate("weaponcrafting") == 5.0
```

- [ ] **Step 5: Run the whole wrapper suite**

```bash
uv run pytest tests/test_ai/test_acquisition_cost_wrapper.py -q --no-cov
```

Expected: PASS, including the three new tests and the two edited ones.

- [ ] **Step 6: Verify the price against the live database**

Create `scripts/probe_acquisition_price.py` with the probe used to find the
defect, so acceptance is a command rather than a memory:

```python
"""Live probe: what does `J`'s pricer actually charge for an item, and why.

Senses the real character through the API, then asks `acquisition_cost` the
same question `J` asks — with the store, without it, and at full HP — and
prints the routes `obtain_sources` named. Read-only: no action is executed and
no server state changes.

    uv run python scripts/probe_acquisition_price.py C3P0 iron_boots iron_shield

Lives in scripts/ because it needs a TOKEN and a live API; `pyproject.toml`
omits scripts/ from coverage for exactly that reason.
"""

import sys
from dataclasses import replace

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions, route_options
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

DEFAULT_DB = "~/.cache/artifactsmmo/learning.db"
DEFAULT_ITEMS = ["iron_boots", "iron_shield", "iron_helm", "iron_armor",
                 "iron_legs_armor", "iron_ring", "iron_sword", "iron_bar",
                 "wool", "cowhide", "feather"]


def main(character: str, items: list[str]) -> None:
    from pathlib import Path
    config = Config.from_token_file()
    ClientManager().initialize(config)
    store = LearningStore(db_path=str(Path(DEFAULT_DB).expanduser()),
                          character=character)
    store.start_session()
    try:
        player = GamePlayer(character=character, history=store,
                            game_data_ttl_minutes=config.game_data_ttl_minutes)
        player._initialize(ClientManager().client)
        state, game_data = player.state, player.game_data
        assert state is not None and game_data is not None
        ctx = player._selection_context()
        rested = replace(state, hp=state.max_hp)
        print(f"=== {character} level={state.level} hp={state.hp}/{state.max_hp}")
        print("skills      ", dict(sorted(state.skills.items())))
        for skill in sorted(set(state.skills)):
            own = store.skill_grind_rate(skill)
            fleet = store.fleet_skill_grind_rate(skill)
            if own is not None or fleet is not None:
                print(f"  grind rate {skill:16s} own={own} fleet={fleet}")
        print()
        for item in items:
            now = acquisition_actions(item, 1, state, game_data, ctx,
                                      equip=False, store=store)
            full = acquisition_actions(item, 1, rested, game_data, ctx,
                                       equip=False, store=store)
            kinds = [(r.kind, r.unlock, r.unlock_actions)
                     for r in route_options(item, state, game_data, ctx, store)]
            print(f"{item:16s} at_current_hp={now:>9d}  at_full_hp={full:>9d}"
                  f"  routes={kinds}")
    finally:
        store.end_session(exit_reason="normal")
        store.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: probe_acquisition_price.py CHARACTER [ITEM ...]")
    main(sys.argv[1], sys.argv[2:] or DEFAULT_ITEMS)
```

Run it:

```bash
uv run python scripts/probe_acquisition_price.py C3P0
uv run python scripts/probe_acquisition_price.py R2D2
```

Expected after this task: `iron_boots` reports a finite `at_current_hp` in the
low hundreds (the spec's table predicts 413 for C3P0, 424 for R2D2) instead of
1,000,000, and its `routes` list is non-empty with `unlock` reading
`skill:gearcrafting:10`. Items whose inputs are `wool` or `cowhide` may still
report ~3,000,xxx — that is D2, fixed in Task 3, and `at_full_hp` should already
show the difference.

- [ ] **Step 7: Lint, types, commit**

```bash
uv run ruff check src/ tests/
uv run mypy src/
git add src/artifactsmmo_cli/ai/acquisition_cost.py \
        tests/test_ai/test_acquisition_cost_wrapper.py \
        scripts/probe_acquisition_price.py
git commit -m "fix(pricing): a skill-gated craft is priced from the grind's own cycles

Every character read a 0.0 grind rate because the estimator averaged over the
last 100 cycles of any activity, so every iron-tier item priced at
UNOBTAINABLE and the grind that would open it was itself unrankable.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Route existence asks at restorable HP

**Files:**
- Modify: `src/artifactsmmo_cli/ai/drop_obtainability.py:107-130`
  (`fightable_droppers`)
- Modify: `src/artifactsmmo_cli/ai/obtain_sources.py:298-315` (`_drop_sources`)
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py:192` and `:204`
- Modify: `src/artifactsmmo_cli/ai/tiers/objective.py:224,233`
- Test: `tests/test_ai/test_drop_obtainability.py`,
  `tests/test_ai/test_obtain_sources.py`

**Interfaces:**
- Consumes: `dataclasses.replace`, `WorldState.hp`, `WorldState.max_hp`,
  `combat.is_winnable`.
- Produces: no signature changes anywhere. `fightable_droppers`,
  `drop_obtainable`, `_drop_sources` and `obtain_sources` keep their exact
  parameter lists; only the state they hand to `is_winnable` changes.

**Why the change goes inside `fightable_droppers`, not at its callers.**
`drop_obtainability`'s module docstring pins an equivalence:
`drop_obtainable(...) is False` ⇒ `select_drop_fight(...) is None`, for the same
`item`, `state` and `allow_grey`. `select_drop_fight` is the EMISSION face — it
turns the same oracle's verdict into the `FightAction` a goal plans with. Moving
the boolean face to rested HP while leaving the emission face on current HP would
break that contract in the worst direction: a plan step nothing approved. One
edit inside the shared oracle moves both faces together.

**Why planning a fight the character cannot currently win is safe.** Two gates
downstream are untouched and still read current HP:
`FightAction._structurally_applicable` refuses below
`_MIN_FIGHT_HP_FRACTION = 0.3` (`actions/combat.py:82`), and
`GuardKind.RESTORE_HP` (`tiers/guards.py:211-217`) fires exactly when the fight
is unwinnable now and winnable rested — it is already written in terms of
`predict_win(replace(state, hp=state.max_hp), ...)`. The planner is allowed to
plan through a rest. The executor is not allowed to walk into a losing fight.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_drop_obtainability.py`:

```python
def test_a_damaged_character_has_the_same_routes_as_a_healthy_one(
        game_data, state) -> None:
    """THE LIVE DEFECT, pinned. `predict_win` reads CURRENT hp by design, so
    asking it a route-EXISTENCE question made the answer swing on how beaten up
    the character happened to be when `J` ran. Measured 2026-08-17: C3P0 at
    63/315 hp reported sheep, cow and blue_slime all unwinnable and therefore
    `wool` unobtainable, which priced `iron_shield` at 3,000,926; the same
    character at 315/315 reported all three winnable. A 7,000x swing in a
    RANKING key, driven by combat noise.

    Rest is an action the planner has, and the fight's own gates still read
    current hp at execution time."""
    healthy = replace(state, hp=state.max_hp)
    hurt = replace(state, hp=max(1, state.max_hp // 5))
    for item in ("wool", "cowhide", "feather"):
        assert (drop_obtainable(item, hurt, game_data, allow_grey=True)
                == drop_obtainable(item, healthy, game_data, allow_grey=True)), item
        assert (fightable_droppers(item, hurt, game_data, allow_grey=True)
                == fightable_droppers(item, healthy, game_data, allow_grey=True)), item


def test_an_unwinnable_dropper_is_still_refused_when_rested(
        game_data, state) -> None:
    """The gate is MOVED, not removed. A monster the character loses to even at
    full hp is still not a route — otherwise this change would hand the planner
    a fight it can never take, which is the livelock the winnability gate
    exists to prevent."""
    weak = replace(state, hp=state.max_hp, level=1, equipment={})
    hopeless = [item for item in ("cowhide", "wool")
                if not drop_obtainable(item, weak, game_data, allow_grey=True)]
    assert hopeless, (
        "fixture no longer has an unwinnable dropper; this test cannot "
        "distinguish 'gate moved' from 'gate deleted' and must be re-seeded")
```

Append to `tests/test_ai/test_obtain_sources.py`:

```python
def test_the_DROP_source_does_not_depend_on_current_hp(game_data, state) -> None:
    """Same property one layer down, at the seam `acquisition_cost` reads.
    `obtain_sources` answers "how may I obtain this RIGHT NOW", and a bank that
    is closed or an event that is asleep are honest reasons for a route to be
    absent. Being at 20% hp is not one — it is a reason to rest."""
    healthy = replace(state, hp=state.max_hp)
    hurt = replace(state, hp=max(1, state.max_hp // 5))
    for item in ("wool", "cowhide", "feather"):
        assert (obtain_sources(item, hurt, game_data, NO_PROFILE_CONTEXT)
                == obtain_sources(item, healthy, game_data, NO_PROFILE_CONTEXT)), item
```

Add whatever of `replace`, `drop_obtainable`, `fightable_droppers`,
`obtain_sources`, `NO_PROFILE_CONTEXT` the two files do not already import.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_drop_obtainability.py tests/test_ai/test_obtain_sources.py -k "hp" -v --no-cov
```

Expected: FAIL on the equality assertions, with the hurt state returning fewer
droppers than the healthy one.

- [ ] **Step 3: Move the four route-existence sites onto a rested state**

In `src/artifactsmmo_cli/ai/drop_obtainability.py`, change the `COMBAT` bullet in
`fightable_droppers`' docstring and the comprehension:

```python
    * COMBAT — `is_winnable` AT RESTORABLE HP: never offer a fight the
      character loses when healthy. Evaluated at `max_hp`, not at current hp,
      because this answers "is there a route" and Rest is an action the planner
      has. `combat.predict_win` reads CURRENT hp by design (see its docstring —
      a damaged character really does lose fights a healthy one wins), and that
      is the right basis for the runtime question "take this fight now", which
      is still asked at `player.py:1047`, `player.py:3742`,
      `combat_targets.py:88` and `guards.py:215`. Asking it here made route
      EXISTENCE swing on combat noise: measured 2026-08-17, C3P0 at 63/315 hp
      priced `iron_shield` at 3,000,926 and at 315/315 hp priced it at 926.
      The downstream gates are untouched: `FightAction` still refuses below
      `_MIN_FIGHT_HP_FRACTION`, and `GuardKind.RESTORE_HP` exists precisely to
      rest for a fight that is winnable rested and not winnable now.
```

```python
    rested = replace(state, hp=state.max_hp)
    return [
        (monster_code, rate, mn, mx)
        for monster_code, rate, mn, mx in game_data.monsters_dropping(item)
        if game_data.monster_spawn_known(monster_code)
        and is_winnable(rested, game_data, monster_code)
        and (allow_grey or game_data.xp_per_kill(monster_code, state.level) > 0)
    ]
```

Note `xp_per_kill` keeps the ORIGINAL `state` — it reads `state.level`, which
resting does not change, and threading the rested copy there would be a
gratuitous difference between two lines that must stay readable as one gate.
Add `from dataclasses import replace` to the imports at the top of the file if it
is not already there.

In `src/artifactsmmo_cli/ai/obtain_sources.py`, `_drop_sources`:

```python
    rested = replace(state, hp=state.max_hp)
    out: list[Source] = []
    for monster_code, _rate, _min_q, _max_q in game_data.monsters_dropping(item):
        if not game_data.all_monster_locations.get(monster_code):
            continue  # no live tiles (e.g. event monster, event inactive)
        # AT RESTORABLE HP, matching `drop_obtainability.fightable_droppers`.
        # This is a route-EXISTENCE question; see that function's COMBAT bullet
        # for the measurement and for which call sites still read current hp.
        if is_winnable(rested, game_data, monster_code):
            out.append(Source(SourceKind.DROP, monster_code, 1, UNBOUNDED_CAPACITY))
    return out
```

In `src/artifactsmmo_cli/ai/tiers/strategy.py`, both `drop_obtainable` calls now
get the rested basis from the callee, so they need no change — but the comment at
line 203-204 claims the call is "state-aware (preserves the winnability and spawn
gates this docstring calls load-bearing)", which is now imprecise. Replace it:

```python
    # Fightable drop: the shared oracle, state-aware (spawn gate plus
    # winnability AT RESTORABLE HP — see `fightable_droppers`, which decides
    # the hp basis for every caller so they cannot disagree).
```

In `src/artifactsmmo_cli/ai/tiers/objective.py`, the local `rested` at line 224 is
now redundant with the callee's. Delete the binding and pass `state`, so exactly
one place decides the hp basis:

```python
    bank = state.bank_items or {}
```

and at line 233:

```python
        if drop_obtainable(leaf, state, game_data,
                           allow_grey=ATTAINABILITY_ALLOWS_GREY):
```

Then remove the now-unused `replace` import from `objective.py` if nothing else
in the file uses it — `ruff` will say.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_ai/test_drop_obtainability.py tests/test_ai/test_obtain_sources.py -q --no-cov
uv run pytest tests/test_ai/ -q --no-cov -x
```

Expected: PASS. If a `tiers/` test fails, read it before changing it — a real
behavior change in reachability is the point of this task, but a test that pinned
the OLD hp-dependence deliberately needs its rationale re-read, not its assertion
flipped.

- [ ] **Step 5: Verify the swing is gone against the live database**

```bash
uv run python scripts/probe_acquisition_price.py C3P0
uv run python scripts/probe_acquisition_price.py R2D2
uv run python scripts/probe_acquisition_price.py Lor
```

Expected: `at_current_hp` equals `at_full_hp` on every row, and no iron row
reports a 3,000,xxx figure. If a character happens to be at full HP when the
probe runs, the two columns agree trivially — check one that is damaged, or
re-run after the fleet has been fighting.

- [ ] **Step 6: Run the obtain-parity census**

This is the gate that exists to catch the two plan producers disagreeing about
what is obtainable, which is exactly what this task changes.

```bash
uv run python scripts/gen_obtain_parity.py --check
```

Expected: exit 0, no cell classified `obtain_parity_bug`.

- [ ] **Step 7: Lint, types, commit**

```bash
uv run ruff check src/ tests/
uv run mypy src/
git add src/artifactsmmo_cli/ai/drop_obtainability.py \
        src/artifactsmmo_cli/ai/obtain_sources.py \
        src/artifactsmmo_cli/ai/tiers/strategy.py \
        src/artifactsmmo_cli/ai/tiers/objective.py \
        tests/test_ai/test_drop_obtainability.py \
        tests/test_ai/test_obtain_sources.py
git commit -m "fix(obtain): route existence asks winnability at restorable hp

A route-existence question answered at current hp made wool and cowhide price
at UNOBTAINABLE whenever the character was damaged, swinging iron gear between
~400 and ~3,000,400. Runtime target selection still reads current hp.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Close the memo-key gap Task 3 made closable

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py:167-176`
  (the `KNOWN GAP` paragraph in the memo-key docstring)
- Test: `tests/test_ai/test_skill_grind_target.py`

**Interfaces:**
- Consumes: `drop_obtainable` at restorable HP (Task 3).
- Produces: no new names. The memo key tuple is unchanged — the point is that it
  is now correct as written.

**Why this is its own task and not a comment tweak.** The docstring currently
records a live defect:

> KNOWN GAP, PRE-EXISTING AND UNFIXED (noticed while profiling, 2026-08-13).
> `state.hp` is NOT in this key, but the `obtainable` field it guards reads it:
> `_obtainable` → `drop_obtainable` → `fightable_droppers` → `is_winnable` →
> `combat.predict_win` […] two states differing ONLY in HP share a candidate list
> whose `obtainable` verdicts can differ, which is exactly the too-coarse-key
> failure `test_the_memo_key_notices_a_changed_inventory` calls "worse than no
> memo".

Task 3 severs that chain's dependence on `state.hp`. Leaving the paragraph in
place would leave a closed defect reading as an open one, and the next engineer
would either re-fix it or widen the key and pay the hit rate the paragraph warns
about. A test is what makes the claim checkable rather than asserted.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_skill_grind_target.py`:

```python
def test_the_memo_key_may_omit_hp_because_obtainable_no_longer_reads_it(
        game_data, state) -> None:
    """The memo key's documented KNOWN GAP, closed and pinned.

    Two states differing ONLY in hp must produce identical candidate lists,
    which is what makes omitting `state.hp` from the key sound rather than
    too-coarse. Before the route-existence hp fix they could differ, because
    `obtainable` reached `predict_win` at current hp."""
    healthy = replace(state, hp=state.max_hp)
    hurt = replace(state, hp=max(1, state.max_hp // 5))
    for skill in ("gearcrafting", "weaponcrafting"):
        assert (build_selectable_grind_candidates(skill, hurt, game_data)
                == build_selectable_grind_candidates(skill, healthy, game_data)), skill
```

`build_selectable_grind_candidates(skill, state, game_data, ctx=NO_PROFILE_CONTEXT)
-> list[GrindCandidate]` is the module's producer (`skill_grind_target.py:217`);
the memo this task is about is the one `_cache_key` keys. Add the import if the
test file lacks it. Do not add a wrapper to make the test convenient.

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/test_ai/test_skill_grind_target.py -k memo_key_may_omit_hp -v --no-cov
```

Expected: PASS, because Task 3 already made it true. If it FAILS, there is a
fifth route-existence site Task 3 missed — find it with
`grep -rn "is_winnable(\|predict_win(" src/` and check each hit against the
current-HP-vs-route-existence question before touching this test.

- [ ] **Step 3: Replace the stale paragraph**

In `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py`, replace lines 167-176
with:

```python
    HP IS DELIBERATELY ABSENT, AND THAT IS NOW SOUND. It was a recorded gap
    (noticed while profiling 2026-08-13): the `obtainable` field this key
    guards reached `combat.predict_win` through `_obtainable` ->
    `drop_obtainable` -> `fightable_droppers` -> `is_winnable`, and that
    predicate reads CURRENT hp, so two states differing only in hp could share
    a candidate list whose verdicts differed — the too-coarse-key failure
    `test_the_memo_key_notices_a_changed_inventory` calls "worse than no memo".
    `fightable_droppers` now evaluates winnability at RESTORABLE hp (2026-08-17,
    the route-existence hp fix), so the chain no longer reads `state.hp` at all
    and the key is complete as written. Pinned by
    `test_the_memo_key_may_omit_hp_because_obtainable_no_longer_reads_it`.
```

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest tests/test_ai/test_skill_grind_target.py -q --no-cov
uv run ruff check src/ tests/
uv run mypy src/
git add src/artifactsmmo_cli/ai/tiers/skill_grind_target.py \
        tests/test_ai/test_skill_grind_target.py
git commit -m "docs(grind): the memo key's hp gap is closed, not open

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Full gate, mutation anchors, and push

**Files:**
- Possibly modify: `formal/diff/mutate.py` (anchor strings, only if a previous
  task edited a line an anchor quotes)

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces: a green `formal/gate.sh` on a branch fast-forwardable to `main`.

- [ ] **Step 1: Check mutation anchors**

```bash
uv run python formal/diff/mutate.py --check-anchors
```

Expected: every anchor resolves to exactly one site. Tasks 1-4 touch
`combat.py` not at all, so the `predict_win` / `combat_margin` anchor blocks
(`mutate.py:655-760`) should be unaffected — but `drop_obtainability.py`,
`obtain_sources.py` and `acquisition_cost.py` edits can still collide. If an
anchor fails to resolve, update its quoted substring to the new text in THIS
commit; a stale anchor discovered by the nightly sweep is 14 hours of lost
signal.

- [ ] **Step 2: Targeted mutation sweep on the changed files**

A full sweep is ~36 minutes and peaks around 22GB; `--only` is a ~1-minute
subset.

```bash
uv run python formal/diff/mutate.py --only src/artifactsmmo_cli/ai/acquisition_cost.py 2>&1 | tee /tmp/mut_acq.txt
uv run python formal/diff/mutate.py --only src/artifactsmmo_cli/ai/obtain_sources.py 2>&1 | tee /tmp/mut_obtain.txt
```

Expected: no new survivors. A survivor is a diagnosis job before it is a
test-writing job — the last three survivors in this repo were a wrong `run_group`
binding, an equivalent mutant, and a vacuous test, not missing coverage.

- [ ] **Step 3: Run the full local gate**

Redirect to a file. Piping to `tail` reports the tail's exit code and has already
turned a visible `GATE FAIL` into `rc=0` once in this project.

```bash
bash formal/gate.sh > /tmp/gate.log 2>&1; echo "rc=$?"; tail -30 /tmp/gate.log
```

Expected: `rc=0` and `ALL GATE PARTS PASSED`.

- [ ] **Step 4: Confirm the fix is live, not merely green**

Green tests are not runtime activation. Run the planner against a real character
and confirm an iron root actually appears with a finite price.

```bash
uv run python scripts/probe_acquisition_price.py R2D2
uv run artifactsmmo plan R2D2 --learn
```

Expected from the probe: every iron row finite, `iron_boots` in the low hundreds,
`at_current_hp == at_full_hp`. Expected from `plan`: the printed ranking shows an
`ObtainItem(code='iron_...')` root with a real `acquire_cost` rather than
1,000,001. It need not be the CHOSEN root — the character-XP trunk may still win
on merit, and that is a legitimate outcome. What must change is that the root is
now comparable instead of walled.

- [ ] **Step 5: Push**

```bash
git push origin HEAD:main
```

---

## Task 6: Live measurement, and the increment-3 decision

**Files:** none. This task produces a finding, not a diff.

**Interfaces:**
- Consumes: `~/.cache/artifactsmmo/learning.db` after a live run with Tasks 1-4
  merged.
- Produces: either a one-line close of the spec's increment 3, or the evidence a
  follow-up plan is written against.

The spec's increment 3 asks whether the grind, once priceable, actually runs to
completion — and deliberately does not specify a latch, because the mechanism
named in the first draft was wrong. `plan_commitment` is restart-resume
persistence, not policy, and the focus ledger is an *anti*-starvation fall-off
built by the ring2-arbiter work to decay a root pursued too long. Adding
stickiness there would fight a mechanism installed on purpose.

- [ ] **Step 1: Run the fleet**

Restart the bot so the merged code is live. Let it run long enough for the
predicted grind to complete: the spec's table says 413-991 cycles for
gearcrafting 10, roughly 3.5-8 hours per character at a ~30s modal cooldown.

- [ ] **Step 2: Query whether gearcrafting moved**

```bash
uv run python -c "
import sqlite3, json
c = sqlite3.connect('/home/blentz/.cache/artifactsmmo/learning.db')
for ch in ['C3P0','HAL','Lor','R2D2']:
    seen = {}
    for ts, sj in c.execute(
        'select ts, skill_levels_json from cycles where character=? '
        'and skill_levels_json is not null order by ts', (ch,)):
        g = json.loads(sj).get('gearcrafting')
        if g is not None and g not in seen:
            seen[g] = ts[:16]
    print(ch, dict(sorted(seen.items())))
"
```

Expected on success: a new, higher gearcrafting level with a timestamp after the
merge. Before this work every character showed exactly one value, frozen since
2026-08-16.

- [ ] **Step 3: Query whether an iron craft finally happened**

```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('/home/blentz/.cache/artifactsmmo/learning.db')
for r in c.execute(
    'select character, action_repr, level, count(*) from cycles '
    \"where action_repr like 'Craft(iron%' group by 1,2,3 order by 4 desc\"):
    print(r)
"
```

Expected on success: at least one `Craft(iron_boots×1)` / `Craft(iron_shield×1)`
row — the first iron gear this account has ever produced.

- [ ] **Step 4: Decide**

- If gearcrafting reached 10 and an iron piece was crafted: close the spec's
  increment 3 with no code. Record the result in
  `docs/PLAN_iron_gear_acquisition.md`.
- If the grind started and was abandoned: capture what displaced it before
  specifying anything.

```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('/home/blentz/.cache/artifactsmmo/learning.db')
for r in c.execute(
    'select substr(ts,1,13), character, selected_goal, count(*) from cycles '
    \"where ts > '2026-08-18' group by 1,2,3 order by 1 desc limit 40\"):
    print(r)
"
```

Write the follow-up against that output, not against a guess about which
mechanism dropped the goal.

---

## Self-Review

**Spec coverage.** Increment 1 → Tasks 1 and 2. Increment 2 → Task 3, plus Task 4
for the documented side effect it closes. Increment 3 → Task 6, reshaped into the
measurement the spec now asks for. Increments 4 and 5 are explicitly out of scope
for this plan and stay in the spec as future work; they are design changes
(a seventh `SourceKind` for cross-character supply, and an adequacy-verdict
change) that deserve their own brainstorm.

**Type consistency.** `skill_grind_rate` and `fleet_skill_grind_rate` both return
`float | None`, are defined in Task 1, and are consumed in Task 2 under those
exact names. `grind_action_prefix` is defined in Task 1 and used in Task 1's test
and Task 1's `_grind_rate`. No signature changes anywhere in Task 3, so no
cross-task interface exists to drift.

**Known soft spot, stated rather than hidden.** Task 4's test calls a candidate
function in `skill_grind_target.py` by a name this plan did not verify against the
module. That step says so and instructs the implementer to read the module and its
existing tests, and to call what they call rather than add a wrapper. Every other
code block quotes text read from the file it modifies.
