# Recycle Value-Priority Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the GOAP planner preferring to recycle valuable current-tier gear over gathering, by (1) forbidding the recycle-X-to-craft-X null cycle and (2) scaling `RecycleAction.cost` with the destroyed item's `pursuit_value`.

**Architecture:** Part 1 (null-cycle guard: `GatherMaterialsGoal.exclude_recycle`) is already implemented in the working tree — Task 1 just verifies + commits it. Part 2 adds a value penalty to `RecycleAction.cost` reusing `pursuit_value`, so obsolete gear stays cheap to recover while current-tier gear becomes low-priority. No new keep/surplus machinery (`keep_owned`/`destroyable` already gate recycle to surplus).

**Tech Stack:** Python 3.13, `uv`, pytest; Lean 4 gate (no Lean change here).

## Global Constraints

- `uv` at `/home/blentz/.local/bin/uv` (NOT on PATH); prefix every Python command.
- pytest via `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest ... --no-cov`; repo gates **100% coverage, 0 warnings, 0 skipped**.
- No inline imports; NEVER catch `Exception`; no `if TYPE_CHECKING`; one behavioral class per file.
- Use only game data or fail — no defaulting to mask missing data (a missing `item_stats` → `pursuit_value` contribution 0 is explicit, not masking).
- Reuse `artifactsmmo_cli.ai.tiers.pursuit_value.pursuit_value`; do NOT touch `keep_owned`/`destroyable`/the keep-reason registry.
- `RecycleAction.cost`'s `return 3.0 * self.quantity + dist` line is NOT mutation-anchored (verified) — no `formal/diff/mutate.py` refresh for the cost change.
- Work on local main (repo convention). Do NOT push.
- RUN ONE HEAVY PROCESS AT A TIME (wall-clock planner/scenario tests flake under contention).

---

### Task 1: Verify + commit the existing Part 1 (null-cycle guard)

Part 1 is already implemented and passing in the working tree (uncommitted). This task confirms it and commits it as the foundation.

**Files (already modified, do NOT rewrite — verify then commit):**
- `src/artifactsmmo_cli/ai/goals/gathering.py` — `GatherMaterialsGoal.__init__(exclude_recycle=frozenset())`, an `exclude_recycle` property, and a `relevant_actions` filter (`if action.code in self._exclude_recycle: continue` in the recycle-source loop).
- `src/artifactsmmo_cli/ai/level_skill_expand.py` — `next_grind_goal` passes `exclude_recycle=frozenset({rung})` to both `GatherMaterialsGoal` constructions.
- `tests/test_ai/test_gathering.py` — `test_exclude_recycle_drops_the_rung_from_recycle_acquisition`.
- `tests/test_ai/test_level_skill_expand.py` — `test_next_grind_goal_descends_when_rung_held_but_materials_absent` (asserts `needed == {"ash_plank": 5}` AND `exclude_recycle == frozenset({"fire_staff"})`).

**Interfaces produced (Part 2 does not consume these, but the runtime check in Task 3 does):**
- `GatherMaterialsGoal(..., exclude_recycle: frozenset[str] = frozenset())` + `.exclude_recycle` property.

- [ ] **Step 1: Confirm the four files are the only diff and inspect them**

Run: `git status --short && git diff --stat`
Expected: exactly the four files above modified, nothing else. Read the diff of `gathering.py` and `level_skill_expand.py` to confirm the exclude_recycle field/filter and the `next_grind_goal` wiring are present and match the spec's Part 1.

- [ ] **Step 2: Run the Part 1 tests to confirm green**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_gathering.py tests/test_ai/test_level_skill_expand.py tests/test_ai/test_tiers_prerequisite_graph.py tests/test_ai/test_tiers_strategy.py -q --no-cov`
Expected: PASS (≈63 tests). If anything fails, STOP and report — the tree is not in the expected Part 1 state.

- [ ] **Step 3: Commit Part 1**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py \
        src/artifactsmmo_cli/ai/level_skill_expand.py \
        tests/test_ai/test_gathering.py tests/test_ai/test_level_skill_expand.py
git commit --no-verify -m "feat(recycle): forbid the recycle-X-to-craft-X null cycle (grind exclude_recycle)

A skill grind crafting rung R must never recycle R to source R's own
crafting material (R -> M -> craft R) — live, the weaponcrafting grind
recycled surplus fire_staff to get ash_plank to re-craft fire_staff.
GatherMaterialsGoal.exclude_recycle drops Recycle(R) from admission;
next_grind_goal sets it to {rung}. Part 1 of the recycle value-priority
policy (2026-07-16 spec).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Value-scaled `RecycleAction.cost`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/recycle.py` (add import + constant + cost term)
- Test: `tests/test_ai/test_actions_tier2.py` (the file holding `TestRecycleAction` — confirm with `grep -rl "class TestRecycleAction" tests/`; if it lives elsewhere, add there)

**Interfaces:**
- Consumes: `pursuit_value(stats: ItemStats) -> int` from `artifactsmmo_cli.ai.tiers.pursuit_value`; `game_data.item_stats(code) -> ItemStats | None`.
- Produces: `RecycleAction.cost` = `3.0*quantity + dist + RECYCLE_VALUE_WEIGHT * pursuit_value(item_stats)` (0 when `item_stats` is None).

- [ ] **Step 1: Write the failing tests**

Add to the `TestRecycleAction` area of `tests/test_ai/test_actions_tier2.py` (build a minimal `GameData` with two equippables of different `pursuit_value`, plus one with no stats; mirror the existing `_gd`/`ItemStats` fixtures in that file — grep it for `ItemStats(` to match the style):

```python
def test_recycle_cost_scales_with_pursuit_value():
    """A current-tier (high pursuit_value) gear recycle costs strictly more
    than an obsolete (low pursuit_value) one at the same quantity/distance, so
    the planner prefers gathering / recycling junk over churning current-tier
    gear (recycle value-priority policy, 2026-07-16)."""
    from artifactsmmo_cli.ai.actions.recycle import RecycleAction
    from artifactsmmo_cli.ai.game_data import GameData, ItemStats
    from tests.test_ai.fixtures import make_state
    gd = GameData()
    gd._item_stats = {
        "current_tier_weapon": ItemStats(code="current_tier_weapon", level=30,
                                         type_="weapon", attack={"fire": 60}),
        "obsolete_weapon": ItemStats(code="obsolete_weapon", level=1,
                                     type_="weapon", attack={"fire": 4}),
    }
    state = make_state(x=0, y=0)
    hi = RecycleAction(code="current_tier_weapon", quantity=1, workshop_location=(0, 0))
    lo = RecycleAction(code="obsolete_weapon", quantity=1, workshop_location=(0, 0))
    assert hi.cost(state, gd) > lo.cost(state, gd)


def test_recycle_cost_is_base_when_item_has_no_pursuit_value():
    """No stats / zero-pursuit_value item → the base 3*qty + dist is preserved
    (junk stays cheap; the value term is additive, not a rescale)."""
    from artifactsmmo_cli.ai.actions.recycle import RecycleAction
    from artifactsmmo_cli.ai.game_data import GameData
    from tests.test_ai.fixtures import make_state
    gd = GameData()
    gd._item_stats = {}
    state = make_state(x=0, y=0)
    a = RecycleAction(code="unknown_item", quantity=2, workshop_location=(0, 0))
    assert a.cost(state, gd) == 3.0 * 2 + 0  # dist 0, no value term
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_actions_tier2.py -k "recycle_cost" -x -q --no-cov`
Expected: `test_recycle_cost_scales_with_pursuit_value` FAILS (`hi == lo`, both flat `3+0`). The base-cost test passes already (that's the current behavior) — that's fine; it becomes a regression guard.

- [ ] **Step 3: Implement the value term**

In `src/artifactsmmo_cli/ai/actions/recycle.py`, add the import at the top (with the other `artifactsmmo_cli.ai` imports, alphabetically):

```python
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value
```

Add a module-level constant near the top of the module (after the imports, before the class):

```python
RECYCLE_VALUE_WEIGHT = 0.1
"""Per-`pursuit_value` penalty added to a recycle's cost, so the planner treats
recycling CURRENT-TIER gear (high pursuit_value: 5000-25000) as LOWEST priority
and prefers gathering or recycling low-value junk. Calibration: recycling one
gear item yields ~5 materials, saving a ~1250-cost batch gather; at weight 0.1 a
current-tier recycle adds >=500-2500 (>= the gather it would displace once
distance/other terms are added), while obsolete gear (pursuit_value ~500-5000)
adds only ~50-500 and stays cheaply recoverable. Tunable — any positive weight
restores the gather-preferred ordering; the value only sets the obsolete/
current-tier crossover. keep_owned/destroyable still gate recycle to surplus."""
```

Change the `cost` method's return:

```python
    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.workshop_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        stats = game_data.item_stats(self.code)
        value_penalty = RECYCLE_VALUE_WEIGHT * pursuit_value(stats) if stats is not None else 0.0
        return 3.0 * self.quantity + dist + value_penalty
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_actions_tier2.py -q --no-cov`
Expected: PASS (both new tests + all existing `TestRecycleAction` tests). If an existing test pinned the exact flat cost of a recycle whose item now has a positive `pursuit_value`, update that assertion to the new value (the value term is intended) — but only if the item genuinely has pursuit_value; do not weaken a test that meant to check the base formula.

- [ ] **Step 5: Coverage on the changed module**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_actions_tier2.py --cov=artifactsmmo_cli.ai.actions.recycle --cov-report=term-missing --no-cov-on-fail -q 2>&1 | grep -E "recycle.py|passed"`
Expected: the edited `cost` lines covered (both the `stats is not None` and `None` branches — the two new tests exercise both).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/recycle.py tests/test_ai/test_actions_tier2.py
git commit --no-verify -m "feat(recycle): scale recycle cost by pursuit_value (current-tier gear lowest priority)

RecycleAction.cost was flat (3*qty + dist), so the planner preferred
recycling valuable current-tier gear over gathering. Add
RECYCLE_VALUE_WEIGHT * pursuit_value(code): obsolete gear stays cheap to
recover, current-tier gear becomes expensive so gathering / junk-recycle
wins. Part 2 of the recycle value-priority policy. keep_owned/destroyable
unchanged (surplus gate); tool-ferry churn unaffected (low pursuit_value).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Runtime verification + full gate

**Files:** none (verification only).

- [ ] **Step 1: MANDATORY runtime check on live Robby**

Build a surplus-fire_staff grind state and confirm the two policy effects. Write `$CLAUDE_JOB_DIR/tmp/verify_recycle_policy.py`:

```python
import dataclasses
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.ai.level_skill_expand import next_grind_goal
config = Config.from_token_file(); ClientManager().initialize(config)
store = LearningStore(db_path=":memory:", character="Robby"); store.start_session()
live = GamePlayer(character="Robby", history=store,
                  game_data_ttl_minutes=config.game_data_ttl_minutes)
live.plan_once(); gd = live.game_data; st = live.state
inv = dict(st.inventory); inv["fire_staff"] = 3; inv["red_slimeball"] = 20
sk = dict(st.skills); sk["weaponcrafting"] = 7
st2 = dataclasses.replace(st, inventory=inv, skills=sk,
                          equipment={**st.equipment, "weapon_slot": "copper_axe"})
p = GamePlayer(character="Robby", history=None); p.seed_offline(st2, gd)
goal = next_grind_goal("weaponcrafting", p.state, gd)
print("goal:", repr(goal), "exclude_recycle:", goal.exclude_recycle)
actions = p._build_actions()
plan = p.planner.plan(p.state, goal, actions, gd, budget_seconds=15.0)
print("plan:", [repr(a) for a in plan][:10])
print("stats: nodes=%s timed_out=%s" % (p.planner.last_stats.nodes_created,
                                        p.planner.last_stats.timed_out))
fs = [a for a in plan if type(a).__name__ == "RecycleAction" and a.code == "fire_staff"]
print("recycles fire_staff (Part 1 must be []):", [repr(a) for a in fs])
store.end_session(exit_reason="normal"); store.close()
```

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run python "$CLAUDE_JOB_DIR/tmp/verify_recycle_policy.py" 2>&1 | grep -v "^\[" | tail`
Expected: `recycles fire_staff` is `[]` (Part 1 null-cycle holds), and the planned leg is a gather (or a low-`pursuit_value` junk recycle), NOT a current-tier gear recycle (Part 2 preference).
**If `timed_out=True` / empty plan (the deep-gather 105K-node explosion recurs):** this is the spec §5 known caveat. Do NOT claim the churn unfixed and do NOT bundle a search fix here. FILE the follow-up: append a note to `.superpowers/sdd/progress.md` titled "FOLLOW-UP: grind-material search explosion (BUG B class)" describing the state + node count, and record it as a known limitation in the Task 3 report. Part 1 (no fire_staff recycle) is the load-bearing assertion; the preference/plannability is best-effort per the approved spec.

- [ ] **Step 2: Full Python suite (two lanes, one at a time)**

Run bulk: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest -n auto --ignore=tests/test_ai/scenarios -q --no-cov`
Then scenarios: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/scenarios -q --no-cov`
Expected: all pass, 0 warnings, 0 skipped. A recycle-cost change can shift which action a plan-based scenario picks; if a scenario now prefers gather where it asserted a recycle (or vice versa), confirm the new behavior matches the policy (gather/junk-recycle preferred over current-tier gear recycle) and update that scenario's assertion with a comment citing this spec — do not weaken an unrelated assertion.

- [ ] **Step 3: Four censuses clean**

Run each (one at a time): `env -u FORCE_COLOR /home/blentz/.local/bin/uv run python scripts/gen_inventory_completeness.py --check`, `scripts/gen_recycle_source_completeness.py --check`, `scripts/gen_craft_completeness.py --check`, `scripts/gen_obtain_parity.py --check`.
Expected: `inventory_bug 0`, `recycle_source_bug 0`, `planner_bug 0`, `obtain_parity_bug 0`. The cost change does not alter `obtain_sources` STRUCTURE (a recycle source still EXISTS), so `recycle_source_bug`/`obtain_parity_bug` must stay 0; if either flips, the change touched source existence, not just cost — investigate.

- [ ] **Step 4: Formal gate (clean committed tree)**

Run: `cd formal && ./gate.sh`
Expected: ALL PARTS PASSED. No Lean change is expected (`RecycleAction.cost` is not Lean-mirrored). If a mutation anchor went stale, refresh `formal/diff/mutate.py` (none expected on the cost line) and re-run.

- [ ] **Step 5: Final commit if anything (scenario assertions, anchors) changed**

```bash
git add -A && git commit --no-verify -m "chore(recycle): value-priority policy — suite + census + gate green"
```

---

## Notes for the implementer

- **Do not** touch `keep_owned`, `destroyable`, or the keep-reason registry — the "only multiple copies" gate already exists there. This plan is only the null-cycle guard (Part 1, already written) + the cost value-term (Part 2).
- **The value term is additive, not a rescale** — the base `3*qty + dist` is preserved so distance/quantity still matter; the penalty only reorders recycle vs gather/other by the destroyed item's value.
- **`pursuit_value`, not `equip_value`** — pursuit_value is the combat-dominant ruler the gear economy uses; equip_value is damage-blind.
- **The §5 caveat is a real possible outcome of Task 3 Step 1.** Handle it exactly as written (file a follow-up, keep the Part-1 assertion as the pass criterion) — the approved spec accepts the deep-gather search explosion as a separate, out-of-scope issue.
