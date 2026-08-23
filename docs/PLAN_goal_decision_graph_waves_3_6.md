# Goal/Decision Graph Implementation Plan (waves 3-6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish collapsing the meta-decision layer — combat targets come from
the derived tier band, the two sequencing guards become Decisions, the flat
ranking is replaced by graph resolution, and the supporting mechanisms attach as
route options rather than rival roots.

**Architecture:** Waves 1-2 (merged) added the derived tier ladder, the
`Decision` node type, the transcription of six `objective_step_goal` branches,
and one behaviour change. These waves consume that groundwork.

**Tech Stack:** Python 3.13, `uv`, pytest, mypy strict, ruff, Lean 4 (wave 3
only).

**Spec:** `docs/superpowers/specs/2026-08-22-goal-decision-graph-design.md`

## Global Constraints

- Every Python command is prefixed `uv run` (CLAUDE.md). If `uv` is not on PATH,
  use `/home/blentz/.local/bin/uv`.
- One behavioural class per file. Pure data/schema/enum groups may share a module.
- No inline imports; no `if TYPE_CHECKING`; no triple-dot imports.
- Never catch `Exception`.
- No defaulting around missing API data — use API data or fail with an error.
- 0 errors, 0 warnings, 0 skipped, **100% coverage** (`--cov-fail-under=100`).
- Implementers end each task with `uv run ruff check src/ tests/`, then
  `uv run mypy --strict src/artifactsmmo_cli`, then `bash scripts/run_tests.sh`
  — ONE AT A TIME, nothing else running in the worktree. Two concurrent
  processes corrupt the shared `.coverage` file and report a bogus ~45% total.
  Never pass `--no-cov`. `formal/gate.sh` is the controller's job.
- The pre-commit hook is NOT sufficient evidence: it runs a 5-rule ruff subset
  and pytest with `--no-cov`.
- Do not create a second implementation of anything. Fix in place.
- A test that does not fail when its production line is mutated is decorative.
  Six such tests were caught during waves 1-2, every one in a test the plan
  author wrote. Mutate before reporting green.

---

## Ordering, and why it is not 3-4-5-6

**Wave 5 runs FIRST.** It is independent: it changes
`GamePlayer._winnable_farm_target`'s cascade and the three level-floor sites,
none of which touch the ranking. Waves 4 and 6 both fold things *into* the graph
that wave 3 creates, so they genuinely depend on it. Running 5 first ships a
self-contained improvement without waiting on the largest and riskiest wave.

Resulting order: **5 → 3 → 4 → 6**.

## Honest scope warning

Wave 3 is not comparable in size to the others. It replaces `decide_tree`'s
argmax (`ai/tiers/progression_tree.py`, 779 lines) and deletes `J`, the score
scale, the focus ledger, the d'Hondt arbiter and the sticky commitment. The
Lean liveness development binds to the current descent: `CumulativeProgress.lean`
carries a **fifteen-component lexicographic measure** (`ExtMeasure`, `toLex15`,
`extMeasureLt_wellFounded`) plus per-component descent lemmas. Those obligations
must be restated, not deleted.

Waves 3, 4 and 6 therefore each open with a DESIGN task whose deliverable is the
concrete code for the tasks that follow. That is not a placeholder — it is the
design pass the spec deferred, and it must be done against the real code before
anything can be written to no-placeholder fidelity.

---

# WAVE 5 — combat target from the tier band

## What is wrong today

`cheapest_path_to_level` (`ai/learning/projections.py`) filters candidates with
`1 <= lvl <= sim_level + 1`. The floor is literally `1`, dating to `ed676b81`
(2026-05-18). It is tier 2 of the `_winnable_farm_target` cascade and outranks
the windowed picker at tier 3, so `combat_picker`'s correct
`[char_level - 1, char_level + 2]` window never gets a vote.

Measured 2026-08-23: Robby level 30 fighting spider (20), Lor 19 fighting
flying_snake (12), C3P0 21 fighting highwayman (15), HAL 19 fighting highwayman
(15). Four of five characters grinding 4-10 levels below themselves.

**Expectation management:** for Robby specifically this may change nothing.
Spider is in `band(T20)`, T20 is his next uncleared tier, and it is the only
winnable monster in it. Under the tier model his current behaviour is correct
and his real constraint is gear. Wave 5 makes the RULE right; it does not
promise to move every character.

## Task 5.1: Combat target comes from the next uncleared tier's band

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/band_target.py`
- Test: `tests/test_ai/test_band_target.py`

**Interfaces:**
- Consumes: `next_uncleared_tier(state, game_data, history) -> int | None` and
  `normal_band(game_data, tier) -> tuple[str, ...]` (waves 1-2, merged);
  `is_winnable(state, game_data, monster_code, history) -> bool` from
  `artifactsmmo_cli.ai.combat`; `GameData.xp_per_kill(code, char_level) -> int`.
- Produces: `band_combat_target(state, game_data, history) -> str | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_band_target.py`:

```python
"""The combat target is the next uncleared tier's band, not an unbounded argmax.

`cheapest_path_to_level` filters `1 <= lvl <= sim_level + 1` — a floor of 1 —
and outranks the windowed picker, so four of five live characters were grinding
4 to 10 levels below themselves on 2026-08-23.
"""
import artifactsmmo_cli.ai.tiers.band_target as mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.band_target import band_combat_target
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "king_slime": 15,
                         "spider": 20, "ogre": 20}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "king_slime": "boss", "spider": "normal",
                        "ogre": "normal"}
    gd._monster_hp = {"chicken": 60, "mushmush": 350, "king_slime": 1000,
                      "spider": 550, "ogre": 650}
    return gd


def test_the_target_comes_from_the_next_uncleared_band(monkeypatch):
    """Only ogre is unwinnable, so T20 is uncleared and the target is drawn
    from band(T20) — not from the whole catalogue."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "ogre")
    assert band_combat_target(make_state(level=30), _gd(), None) == "spider"


def test_a_boss_in_the_band_is_never_the_target(monkeypatch):
    """king_slime sits in band(10) and is type=boss. It must not be picked even
    when it is the only unwinnable thing keeping the rung open."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "king_slime")
    target = band_combat_target(make_state(level=30), _gd(), None)
    assert target != "king_slime"


def test_the_target_is_winnable(monkeypatch):
    """An unwinnable monster is what keeps the rung open; it is never the thing
    to go and fight."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c == "spider")
    assert band_combat_target(make_state(level=30), _gd(), None) == "spider"


def test_no_winnable_monster_in_the_band_yields_none(monkeypatch):
    """Nothing in the band is beatable: that is a GEAR wall, and the honest
    answer is no combat target rather than a monster from a lower tier."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: False)
    assert band_combat_target(make_state(level=30), _gd(), None) is None


def test_a_finished_ladder_yields_none(monkeypatch):
    """Every rung cleared: there is no next uncleared tier to draw from."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    assert band_combat_target(make_state(level=30), _gd(), None) is None


def test_the_highest_xp_winnable_in_the_band_wins(monkeypatch):
    """Within the band the choice is the best XP per kill, so the grind is not
    arbitrary among equals."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    gd = _gd()
    gd._monster_level = {"spider": 20, "ogre": 22}
    gd._monster_type = {"spider": "normal", "ogre": "normal"}
    gd._monster_hp = {"spider": 550, "ogre": 650}
    state = make_state(level=20)
    best = max(("spider", "ogre"), key=lambda c: gd.xp_per_kill(c, state.level))
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    monkeypatch.setattr(mod, "next_uncleared_tier", lambda s, g, h: 20)
    monkeypatch.setattr(mod, "normal_band", lambda g, t: ("spider", "ogre"))
    assert band_combat_target(state, gd, None) == best
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_band_target.py -q --no-cov
```

Expected: `ModuleNotFoundError: No module named
'artifactsmmo_cli.ai.tiers.band_target'`.

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/ai/tiers/band_target.py`:

```python
"""The monster to farm: the best winnable NORMAL monster in the next uncleared
tier's band.

Replaces an unbounded argmax. `cheapest_path_to_level` filtered candidates with
`1 <= lvl <= sim_level + 1` — a floor of literally 1, dating to ed676b81
(2026-05-18) — and it is tier 2 of `GamePlayer._winnable_farm_target`, ranking
above the windowed picker at tier 3. So `combat_picker`'s correct
`[char_level - 1, char_level + 2]` window never got a vote and four of five live
characters were grinding 4 to 10 levels below themselves (2026-08-23).

No explicit level floor appears here, and none is wanted. The band IS the floor:
a tier's monsters sit between that rung and the next, so a target far below the
character cannot be drawn in the first place. A character whose LEVEL has
outrun its TIER — Robby at 30 with T20 uncleared — correctly keeps fighting the
tier it is stuck on; its constraint is gear, not target selection.

None means the band holds nothing winnable, which is a GEAR wall and must be
reported as such rather than papered over with a monster from a lower tier.
"""

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.tier_ladder import normal_band
from artifactsmmo_cli.ai.tiers.tier_progress import next_uncleared_tier
from artifactsmmo_cli.ai.world_state import WorldState


def band_combat_target(state: WorldState, game_data: GameData,
                       history: LearningStore | None) -> str | None:
    """Best winnable normal monster in the next uncleared tier's band, by XP."""
    tier = next_uncleared_tier(state, game_data, history)
    if tier is None:
        return None
    winnable = [code for code in normal_band(game_data, tier)
                if is_winnable(state, game_data, code, history)]
    if not winnable:
        return None
    return max(winnable, key=lambda code: (game_data.xp_per_kill(code, state.level),
                                           code))
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_ai/test_band_target.py -q --no-cov
```

Expected: 6 passed.

- [ ] **Step 5: Prove the band bound is load-bearing**

Temporarily replace `normal_band(game_data, tier)` with
`tuple(game_data.monster_levels)` — the unbounded catalogue the old code used.
Run the tests and confirm `test_the_target_comes_from_the_next_uncleared_band`
FAILS (it will pick `mushmush` or `chicken`). Restore exactly, confirm green,
and quote the failure in your report. Do NOT use `git checkout` to restore an
untracked file — it silently does nothing. Copy the file aside first.

- [ ] **Step 6: Lint, types, and the coverage-enforcing suite**

```bash
uv run ruff check src/ tests/
uv run mypy --strict src/artifactsmmo_cli
bash scripts/run_tests.sh
```

ONE AT A TIME. Expected: "All checks passed!", "Success: no issues found",
"Required test coverage of 100% reached".

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/band_target.py tests/test_ai/test_band_target.py
git commit -m "feat(tiers): combat target from the next uncleared tier's band

Replaces an unbounded argmax whose floor was literally 1. The band is the
floor: a tier's monsters sit between its rung and the next, so a target far
below the character cannot be drawn. None means the band holds nothing
winnable — a gear wall, reported rather than papered over.

Nothing consumes this yet."
```

## Task 5.2: Wire the cascade to the band target

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_winnable_farm_target`,
  `_path_aligned_monster`)
- Test: `tests/test_ai/test_band_target_wiring.py` (create)

**Interfaces:**
- Consumes: `band_combat_target(state, game_data, history) -> str | None`
  from Task 5.1.
- Produces: no new names. `_winnable_farm_target` keeps its signature.

**This is the behaviour change of wave 5.**

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_band_target_wiring.py`:

```python
"""The cascade's tier-2 source is the band target, not the unbounded projection."""
import artifactsmmo_cli.ai.player as player_mod
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _make_planner_gd


def test_the_cascade_asks_the_band_not_the_unbounded_projection(monkeypatch):
    """`_path_aligned_monster` used `cheapest_path_to_level`, whose candidate
    floor is 1. The cascade must consult `band_combat_target` instead."""
    player = GamePlayer(character="Robby")
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()

    monkeypatch.setattr(player_mod, "band_combat_target",
                        lambda state, game_data, history: "spider")
    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: None)
    monkeypatch.setattr(GamePlayer, "_is_winnable", lambda self, code: True)

    assert player._winnable_farm_target() == "spider"


def test_no_band_target_yields_no_combat_target(monkeypatch):
    """A gear wall must surface as None, not fall through to a lower tier."""
    player = GamePlayer(character="Robby")
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()

    monkeypatch.setattr(player_mod, "band_combat_target",
                        lambda state, game_data, history: None)
    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: None)

    assert player._winnable_farm_target() is None


def test_a_winnable_task_monster_still_wins(monkeypatch):
    """Tier 1 is unchanged: the held task's monster outranks the band when it
    is winnable, because the task is what the character is blocked on."""
    player = GamePlayer(character="Robby")
    player.state = make_state(level=30)
    player.game_data = _make_planner_gd()

    monkeypatch.setattr(GamePlayer, "_task_aligned_monster", lambda self: "pig")
    monkeypatch.setattr(player_mod, "band_combat_target",
                        lambda state, game_data, history: "spider")

    assert player._winnable_farm_target() == "pig"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_ai/test_band_target_wiring.py -q --no-cov
```

Expected: `AttributeError: module 'artifactsmmo_cli.ai.player' has no attribute
'band_combat_target'`.

- [ ] **Step 3: Rewire tier 2**

In `player.py`, import `band_combat_target` at the top of the file (alongside
the other `artifactsmmo_cli.ai.tiers` imports) and replace
`_path_aligned_monster`'s body so it returns
`band_combat_target(self.state, self.game_data, self.history)`, keeping its
`None` guards for `self.state`/`self.game_data`/`self.history`.

Keep `self._last_path_plan` populated for the trace: call
`cheapest_path_to_level` as before and assign it, but do NOT read
`plan.next_action_monster` for the target. The projection stays a diagnostic;
it stops being a decision input. Say so in a comment.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_ai/test_band_target_wiring.py -q --no-cov
```

Expected: 3 passed.

- [ ] **Step 5: Expect other suites to move, and justify each**

A different combat target changes scenario outcomes. For every golden or
scenario expectation you change, state in your report why the new value is
correct. Do NOT weaken an assertion to make it pass — if a test's intent
conflicts with this change, report it instead of editing it into agreement.

- [ ] **Step 6: Lint, types, suite**

```bash
uv run ruff check src/ tests/
uv run mypy --strict src/artifactsmmo_cli
bash scripts/run_tests.sh
```

- [ ] **Step 7: Verify at runtime, not just in tests**

```bash
uv run artifactsmmo plan Robby --learn 2>&1 | sed -n '/^state:/,/^goals_tried/p'
uv run artifactsmmo plan Lor --learn 2>&1 | sed -n '/^state:/,/^goals_tried/p'
```

Record the actual selected goal and first action for each. Green tests are not
runtime activation. If Robby still targets spider, that is the EXPECTED result
described under "Expectation management" — report it as such, do not treat it
as a failure and do not change the code to force a different answer.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "fix(combat): target the next uncleared tier's band

_path_aligned_monster used cheapest_path_to_level, whose candidate floor is
literally 1, and it outranks the windowed picker — so four of five characters
ground 4 to 10 levels below themselves. The projection stays as a trace
diagnostic; it is no longer a decision input."
```

## Task 5.3: Delete the now-dead level floors

**Files:**
- Modify: `src/artifactsmmo_cli/ai/combat_picker.py`
- Modify: `src/artifactsmmo_cli/ai/actions/combat.py`
- Modify: `src/artifactsmmo_cli/ai/learning/projections.py`
- Test: existing suites plus `tests/test_ai/test_band_target_wiring.py`

**Interfaces:** no new names.

**Do this ONLY after 5.2 is green.** Deleting a floor before its replacement is
live would widen targeting, not narrow it.

- [ ] **Step 1: Establish what still depends on each site**

For each of `combat_picker.pick_winnable_monster_pure`, `FightAction`'s
`xp_per_kill > 0` lower gate, and `cheapest_path_to_level`'s `1 <= lvl` filter,
grep for callers and record them in your report BEFORE changing anything. A
Lean differential binds `pick_winnable_monster_pure`
(`formal/Formal/CombatTargetExistence.lean`, `pickWinnableWindowed`, diff-locked
by `formal/diff/test_combat_picker_diff.py`) — if you change that function's
behaviour the Lean model must change with it, and that is a STOP-and-report, not
something to work around.

- [ ] **Step 2: Report before editing**

Write what you found to the report and stop for the controller if any site is
still load-bearing. Only proceed to delete sites that your grep shows are dead
once 5.2 is live.

- [ ] **Step 3: Verify and commit**

```bash
uv run ruff check src/ tests/
uv run mypy --strict src/artifactsmmo_cli
bash scripts/run_tests.sh
uv run python formal/diff/mutate.py --check-anchors
```

---

# WAVE 3 — graph resolution replaces the ranking

## Task 3.1: DESIGN — how resolution replaces the argmax

**Files:**
- Create: `docs/superpowers/specs/2026-08-23-wave3-resolution-design.md`

**Deliverable:** the concrete code for tasks 3.2 onward. This task writes no
production code.

- [ ] **Step 1: Map what `decide_tree` actually produces**

Read `src/artifactsmmo_cli/ai/tiers/progression_tree.py` (779 lines) in full.
Record: every field of `StrategyDecision`, every consumer of `.ranking`, and
which of them read `score`, `contribution`, `cost`, `j` or `reachable_level`.
`ai/plan_tree.rank_detail` and the TUI plan pane are two known consumers.

- [ ] **Step 2: Establish the Lean obligation precisely**

Read `formal/Formal/Liveness/CumulativeProgress.lean`. Record which of the
fifteen `ExtMeasure` components are functions of the ranking, and which are
functions of state alone. Only the former need restating. Name the theorems that
would break.

- [ ] **Step 3: Decide the resolution contract**

Specify `resolve_root(state, game_data, ctx, history) -> MetaGoal | None` and
how it replaces the argmax without changing `StrategyDecision`'s shape for
consumers that only read `chosen_root`/`chosen_step`.

- [ ] **Step 4: Write the design document and STOP**

Include: the replacement measure (the spec proposes
`(tier, character level, skill level, materials outstanding)`), the deletion
list with a consumer count for each item, and a wave-3 task breakdown with real
code. Report to the controller for approval before any implementation.

---

# WAVE 4 — sequencing guards become Decisions

## Task 4.1: DESIGN — GEAR_REVIEW and CRAFT_POTIONS as graph nodes

**Files:**
- Create: `docs/superpowers/specs/2026-08-23-wave4-guards-design.md`

**Blocked on wave 3.** A guard can only "become a Decision" once the resolution
walk exists to host it.

- [ ] **Step 1: Record what each guard currently does**

`GuardKind.GEAR_REVIEW` fires on `ctx.gear_review_active` (the `GearLatch`) and
maps to `UpgradeEquipmentGoal`/`GatherMaterialsGoal` via `map_guard`.
`GuardKind.CRAFT_POTIONS` fires on `craft_potions_fires`. Record every input
each reads.

- [ ] **Step 2: Specify their Decision equivalents and the deletion**

`GearLatch` and `combat_deficit.deficit_upgrade_target` are absorbed into
`MaxGearForLevel`. The eleven interrupt guards stay untouched — name them
explicitly so a later implementer cannot mistake the scope.

- [ ] **Step 3: Write the design document and STOP for approval.**

---

# WAVE 6 — supporting mechanisms as route options

## Task 6.1: DESIGN — potions, cooking, tasks and GE as route options

**Files:**
- Create: `docs/superpowers/specs/2026-08-23-wave6-routes-design.md`

**Blocked on wave 3.**

- [ ] **Step 1: Record how each mechanism currently enters the decision**

Potion crafting, cooking, task synergy and GE trading. For each: is it a root,
a guard, or a discretionary goal today?

- [ ] **Step 2: Specify the route-option contract**

How a `Decision` asks "cheapest way to satisfy my child" and how a task becomes
a funding route for the active link rather than a rival objective.

- [ ] **Step 3: Write the design document and STOP for approval.**

---

## Verification (every wave)

The existing net carries this: planner-completeness census, obtain-parity
census, the mutation gate, and `bash formal/gate.sh`. Every task leaves the gate
green.

Live acceptance, read from `~/.cache/artifactsmmo/learning.db` only — never from
trace files, which are deleted periodically:

- **Wave 5:** no character fights a monster more than one tier below its next
  uncleared tier. Baseline 2026-08-23: Robby 30 vs spider 20, Lor 19 vs
  flying_snake 12, C3P0 21 vs highwayman 15, HAL 19 vs highwayman 15.
- **Wave 3:** planner nodes per cycle do not regress; `chosen_root` remains
  stable across cycles without the sticky-commitment machinery.

## Self-review

**Spec coverage.** Spec wave 5 → tasks 5.1-5.3 (full fidelity). Spec waves 3, 4,
6 → design tasks 3.1, 4.1, 6.1, each producing the code for its own
implementation tasks.

**Why 3/4/6 are design-first rather than fully specified here:** writing
no-placeholder implementation steps for them requires reading 779 lines of
`progression_tree.py` and the fifteen-component Lean measure, and deciding a
replacement measure. Guessing that code would produce exactly the plan defects
waves 1-2 suffered — two of which I authored and which cost fix rounds. The
design task IS the work; it is scheduled, not deferred.

**Type consistency.** `band_combat_target(state, game_data, history)` has the
same signature in 5.1 and 5.2. `next_uncleared_tier(state, game_data, history)`
and `normal_band(game_data, tier)` match waves 1-2 as merged.

**Known soft spot.** Task 5.1's last test monkeypatches `next_uncleared_tier`
and `normal_band` to isolate the XP tiebreak. That is deliberate — the other
five tests exercise the real ones — but an implementer should confirm the
tiebreak also holds unmonkeypatched before reporting green.
