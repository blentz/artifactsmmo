# Goal Tiers P3a.1 — Strategy Cost-Model Refinement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Refines the P3a engine; still shadow-only, no behavior change.

**Goal:** Replace the leaf=1 cost proxy with distance-in-steps and add an instrumental-skill tiebreak, so the shadow ranking stops collapsing to "biggest single gap / alphabetical skill".

**Architecture:** Add `root_cost` (levels-remaining for leaf goals; `unmet_closure_size` for gear) and `instrumental_skills` (crafting skills of target gear) to `tiers/strategy.py`; `decide` uses `root_cost` and an instrumental tiebreak; `RootScore` gains an `instrumental` flag for the trace.

**Tech Stack:** Python 3.13, uv, pytest.

---

## File Structure
- Modify `src/artifactsmmo_cli/ai/tiers/strategy.py` — `root_cost`, `instrumental_skills`, `RootScore.instrumental`, `decide` cost+sort.
- Modify `tests/test_ai/test_tiers_strategy.py`.

---

## Task 1: Distance cost + instrumental tiebreak

**Files:** Modify `src/artifactsmmo_cli/ai/tiers/strategy.py`; Test `tests/test_ai/test_tiers_strategy.py`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_tiers_strategy.py` (imports: add `root_cost`,
`instrumental_skills` to the existing `from ...strategy import (...)`):

```python
def test_root_cost_is_levels_remaining_for_leaf_goals():
    from artifactsmmo_cli.ai.tiers.strategy import root_cost
    gd = _gd()
    assert root_cost(ReachSkillLevel("mining", 50), make_state(skills={"mining": 3}), gd) == 47
    assert root_cost(ReachCharLevel(50), make_state(level=3), gd) == 47
    assert root_cost(ReachSkillLevel("mining", 5), make_state(skills={"mining": 5}), gd) == 1  # floor


def test_root_cost_for_gear_uses_closure_size():
    gd = _gd()
    # copper_dagger -> bar -> ore: 3 unmet nodes (same as unmet_closure_size)
    assert root_cost(ObtainItem("copper_dagger"), make_state(), gd) == 3


def test_instrumental_skills_are_target_gear_crafting_skills():
    from artifactsmmo_cli.ai.tiers.strategy import instrumental_skills
    gd = _gd()  # copper_dagger crafted by weaponcrafting is the only equippable
    obj = CharacterObjective.from_game_data(gd)
    assert instrumental_skills(obj, gd) == {"weaponcrafting"}
    assert instrumental_skills(CharacterObjective.from_game_data(GameData()), GameData()) == set()


def test_instrumental_skill_wins_tie():
    # Maxed char level + owned gear → only skill roots remain, all tied; the
    # skill that gates target gear (weaponcrafting) outranks the rest.
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(level=50, skills={s: 1 for s in obj.target_skill_levels},
                       equipment={"weapon_slot": "copper_dagger"})  # gear root satisfied
    d = StrategyEngine(obj, BalancedPersonality()).decide(state, gd)
    assert d.chosen_root == ReachSkillLevel("weaponcrafting", 50)
    chosen_rs = next(rs for rs in d.ranking if rs.root_repr == repr(d.chosen_root))
    assert chosen_rs.instrumental is True


def test_rootscore_instrumental_false_for_non_skill():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd)
    char = next((rs for rs in d.ranking if rs.category == "char_level"), None)
    assert char is not None and char.instrumental is False
```

Also update `test_unmet_closure_size_counts_unmet_nodes` — it stays valid
(`unmet_closure_size` is unchanged and still used for gear). No edit needed
unless it imported differently.

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k "root_cost or instrumental or rootscore" -q`
Expected: FAIL — `root_cost`/`instrumental_skills` missing; `RootScore` has no `instrumental`.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/tiers/strategy.py`:

Add `CharacterObjective` is already imported. Add `root_cost` after
`unmet_closure_size`:

```python
def root_cost(root: MetaGoal, state: WorldState, game_data: GameData) -> int:
    """Effort proxy in 'steps remaining': levels for leaf progression goals,
    craft/gather chain size for gear. Floored at 1."""
    if isinstance(root, ReachCharLevel):
        return max(1, root.level - state.level)
    if isinstance(root, ReachSkillLevel):
        return max(1, root.level - state.skills.get(root.skill, 1))
    return unmet_closure_size(root, state, game_data)


def instrumental_skills(objective: CharacterObjective, game_data: GameData) -> set[str]:
    """Crafting skills that gate target gear — leveling these unlocks gear the
    objective wants, so they win skill ties."""
    skills: set[str] = set()
    for code in objective.target_gear.values():
        stats = game_data.item_stats(code)
        if stats is not None and stats.crafting_skill:
            skills.add(stats.crafting_skill)
    return skills
```

Add `instrumental: bool` to `RootScore`:

```python
@dataclass(frozen=True)
class RootScore:
    root_repr: str
    category: str
    contribution: float
    cost: int
    score: float
    step_repr: str
    instrumental: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
```

Rewrite `decide`'s cost + ranking (replace the cost line, sort, and RootScore
construction):

```python
    def decide(self, state: WorldState, game_data: GameData) -> StrategyDecision:
        interrupt = "restore_hp" if state.hp_percent < CRITICAL_HP_FRACTION else None
        gap = self.objective.gap(state)
        instrumental = instrumental_skills(self.objective, game_data)

        def is_instrumental(root: MetaGoal) -> bool:
            return isinstance(root, ReachSkillLevel) and root.skill in instrumental

        candidates: list[tuple[MetaGoal, MetaGoal, float, int, float]] = []
        for root in objective_roots(self.objective):
            if root.is_satisfied(state, game_data):
                continue
            step = actionable_step(root, state, game_data)
            if step is None:
                continue
            contribution = self._contribution(root, gap, game_data)
            cost = root_cost(root, state, game_data)
            score = contribution / max(cost, 1)
            candidates.append((root, step, contribution, cost, score))
        candidates.sort(key=lambda c: (-c[4], 0 if is_instrumental(c[0]) else 1, repr(c[0])))
        ranking = [
            RootScore(repr(r), root_category(r), contribution, cost, score, repr(s),
                      is_instrumental(r))
            for (r, s, contribution, cost, score) in candidates
        ]
        if candidates:
            chosen_root: MetaGoal | None = candidates[0][0]
            chosen_step: MetaGoal | None = candidates[0][1]
        else:
            chosen_root = chosen_step = None
        return StrategyDecision(
            interrupt=interrupt,
            chosen_root=chosen_root,
            chosen_step=chosen_step,
            desired_state=desired_state_of(chosen_step),
            ranking=ranking,
        )
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q`
Expected: PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(ai): distance cost + instrumental tiebreak in strategy ranking"
```

---

## Task 2: Full verification

- [ ] **Step 1: Full suite + lint + coverage**

Run: `uv run pytest -q` → all pass, 0 skipped.
Run: `uv run pytest tests/test_ai -q --cov=artifactsmmo_cli.ai.tiers.strategy --cov-report=term-missing`
→ `strategy.py` 100% (add a test for any missed branch — e.g. `root_cost` gear
delegation, the non-instrumental path).
Run: `uv run ruff check src/artifactsmmo_cli/ai/tiers tests/test_ai/test_tiers_strategy.py` → clean.
Run: `uv run mypy src/artifactsmmo_cli/ai/tiers` → no errors.

- [ ] **Step 2: Commit any fixups**

```bash
git add -A && git commit -m "test(ai): close coverage/lint gaps for P3a.1 cost model"
```

---

## Self-review notes
- **Spec coverage:** `root_cost` levels-remaining + gear delegation + floor (T1);
  `instrumental_skills` from target gear (T1); instrumental tiebreak picks the
  gating skill (T1); `RootScore.instrumental` in trace + False for non-skill (T1).
  All mapped.
- **No behavior change:** still shadow-only; `decide` is consumed only by
  `_emit_trace`. `actionable_step`, contribution, HP flag, wiring unchanged.
- **`unmet_closure_size` retained** (gear branch of `root_cost`) — its existing
  test still passes.
- **Type consistency:** `root_cost(MetaGoal, WorldState, GameData) -> int`;
  `instrumental_skills(CharacterObjective, GameData) -> set[str]`; `RootScore`
  default `instrumental=False` keeps existing construction valid.
