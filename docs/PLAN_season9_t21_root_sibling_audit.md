# T2.1 Root-Level Sibling Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer the half of the spec's T2 that T2.0 left open — for each character, how many
candidate **roots** are priced through `_sibling_craft_option`, and whether the **chosen** root is
one of them. T2.0 measured catalogue items; a lower price only matters if it moves the root walk's
answer.

**Architecture:** One new pure census that drives `decisions/root.resolve_root` and classifies the
roots it returns, reusing T2.0's `sibling_route_verdicts` for the per-item verdict. Exposed as a new
section on the existing `artifactsmmo sibling-route-audit` command, which already senses the
character and builds the context. Read-only; changes no ranking, goal, plan or cost.

**Tech Stack:** Python 3.13, `uv`, SQLModel over SQLite, typer, pytest.

**Spec:** `docs/PLAN_season9_readiness.md` (track T2), specifically `:200-202` — "for each
character, how many candidate roots are priced through `_sibling_craft_option`, and how many of
those become the chosen root."

## Global Constraints

- Every Python command is prefixed `uv run`.
- All imports at the top of the file. No inline imports. Absolute imports only; never `...`-relative.
- One *behavioural* class per file. Cohesive pure data/value objects may share a module.
- Never `except Exception`. Never `if TYPE_CHECKING`.
- No second implementation of anything — fix in place.
- Tests live in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- `pyproject.toml` sets `branch = false`: statement coverage can be 100% while a stated rule has no
  test. Every rule this plan states gets its own test.
- `scripts/pre_commit.sh:32` lints only `src/artifactsmmo_cli/ai/` and `formal/` — never `tests/`.
- Use only API data, or fail with an error.

## Verified API surface

Read from the tree on 2026-09-22.

| Name | Where | Shape |
|---|---|---|
| `resolve_root` | `ai/decisions/root.py:1009` | `(state, game_data, objective, ctx, history) -> RootResolution` |
| `RootResolution` | `ai/decisions/root.py:124` | fields `root`, `alternatives`, `trail`, `aged`, `blocked_target` |
| `CharacterObjective` | built at `ai/player.py:970` | `self._objective = CharacterObjective.from_game_data(self.game_data)` |
| `ObtainItem` | `ai/tiers/meta_goal.py:44` | frozen; fields `code`, `quantity=1`, `slot=None` |
| `ReachCharLevel` / `ReachSkillLevel` | `ai/tiers/meta_goal.py:36,81` | name no item |
| `sibling_route_verdicts` | `audit/sibling_route_census.py` | `(state, game_data, ctx, store, items) -> list[SiblingVerdict]` |
| `SiblingVerdict` | same | fields incl. `item`, `priced`, `actions_with`, `actions_without`; properties `saving`, `load_bearing` |
| existing command | `commands/sibling_route_report.py` | already senses, builds ctx from `player._last_ctx` + `sibling_skill_levels` |

**`alternatives` is the walk's OWN output — do not rebuild it.** `RootResolution.alternatives` is
"the ordered remainder of the ONE walk", not a ranking. The candidate set is `[root, *alternatives]`
read straight off the resolution. A previous session "confirmed" a fix by reconstructing that list
from the gate's inputs and was measuring its own output; drive `resolve_root` and read what it
returns.

---

## File Structure

**Create:**
- `src/artifactsmmo_cli/audit/root_sibling_census.py` — classify the walk's roots.
- `tests/test_ai/test_root_sibling_census.py`

**Modify:**
- `src/artifactsmmo_cli/commands/sibling_route_report.py` — add the roots section and `--all`.
- `tests/test_ai/test_sibling_route_report.py` — cover both.

A separate command was considered and rejected: `sibling-route-audit` already senses the character,
builds the real `SelectionContext` and opens the stores. A second command would duplicate all of it
for a different population of the same question.

---

### Task 1: The root census

**Files:**
- Create: `src/artifactsmmo_cli/audit/root_sibling_census.py`
- Test: `tests/test_ai/test_root_sibling_census.py`

**Interfaces:**
- Consumes: `resolve_root` and `RootResolution` from `artifactsmmo_cli.ai.decisions.root`;
  `ObtainItem` from `artifactsmmo_cli.ai.tiers.meta_goal`; `sibling_route_verdicts` and
  `SiblingVerdict` from `artifactsmmo_cli.audit.sibling_route_census`.
- Produces: `RootSiblingVerdict` (frozen dataclass: `root_repr`, `item`, `chosen`, `verdict:
  SiblingVerdict | None`) and
  `root_sibling_verdicts(state, game_data, objective, ctx, store) -> list[RootSiblingVerdict]`.

Rules this census states, each of which gets a test:

1. The candidate set is `[resolution.root, *resolution.alternatives]`, with `None` roots filtered
   (the wall case — `resolve_root` can return `root=None`). Order is preserved; the chosen root is
   the one flagged `chosen=True`, and exactly one row carries it when a root resolved.
2. A root that names no item — `ReachCharLevel`, `ReachSkillLevel` — yields `item=None` and
   `verdict=None`. It is still reported, because "the chosen root names no item" is the answer in
   the case where the route cannot possibly apply, and dropping it would make the denominator lie.
3. A root naming an item is priced by `sibling_route_verdicts` over exactly that item. Do not
   re-derive the verdict; call the existing census.
4. `chosen` is set from identity against `resolution.root`, not from position, so a reordering in
   `alternatives` cannot silently move the flag.

- [ ] **Step 1: Write the failing test** covering rules 1-4 over a fixture world this module
  declares itself. Do not reuse a shared `GameData` fixture — one shared world across scenarios has
  produced three vacuous measurements and a shipped false retraction in this codebase.

- [ ] **Step 2: Run it, confirm it fails for the stated reason.**

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Confirm it passes.**

- [ ] **Step 5: Prove the `chosen` flag is load-bearing.** Mutate the implementation to set `chosen`
  by position (`index == 0`) instead of identity, and confirm a test fails — the two agree whenever
  the chosen root leads the list, so a test that only ever sees that case pins nothing. Restore by
  copying the file aside and back, never `git checkout`. Record the observed failure.

- [ ] **Step 6: Commit.**

---

### Task 2: The roots section and `--all`

**Files:**
- Modify: `src/artifactsmmo_cli/commands/sibling_route_report.py`
- Test: `tests/test_ai/test_sibling_route_report.py`

Add a section printing, for the character: how many candidate roots the walk returned, how many name
an item, how many of those are sibling-priced, how many are load-bearing, and — stated plainly —
whether the CHOSEN root is sibling-priced and load-bearing. Print the chosen root's repr either way.

Add `--all` iterating every character in the fleet, since the spec asks "for each character". Read
the roster the same way the existing code learns about siblings; if no roster source exists short of
the API, take a repeated `--character` option instead and say so in your report rather than inventing
one.

**The output must not repeat T2.0's vacuity.** A root-level count of 0 sibling-priced roots is a
real and likely answer — the walk may never name an item behind a sibling-clearable gate. Print the
counts even when they are 0, and state in the section header that a chosen root naming no item
(`ReachCharLevel`, `ReachSkillLevel`) means the route could not apply this cycle, which is different
from the route being outpriced.

- [ ] **Step 1: Write the failing test** for the section, including the all-zeros case and the
  names-no-item case, with the sense seam substituted so no real API call is reachable.
- [ ] **Step 2: Run it, confirm it fails for the stated reason.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Confirm it passes.**
- [ ] **Step 5: Run live** for every character and record the REAL verbatim output. The fleet is
  running and rate-limited; a 429 is contention, not a defect.
- [ ] **Step 6: Full gate**, `bash formal/gate.sh > /tmp/gate.log 2>&1; echo "exit=$?"` — never pipe
  into `tail`, which reports the tail's exit code.
- [ ] **Step 7: Commit.**

---

## What this plan deliberately does not do

- It does not change the route, the walk, or any cost. Measurement only.
- It does not touch `audit/sibling_route_census.py` or `ai/acquisition_cost.py`.
- It does not address the finding that the `sibling:` unlock has zero production consumers. That is
  a separate question — whether anything ACTS on a chosen sibling-priced root — and this plan only
  establishes whether one is ever chosen.
- It does not do the durable history census. That needs `cycles.root_repr` populated, which needs
  the fleet restarted onto current `main`; the user is doing that on their own schedule.

## Findings to record

1. Per character: candidate roots, how many name items, how many sibling-priced, how many
   load-bearing, and whether the chosen root is among them.
2. If ZERO chosen roots are sibling-priced across all five characters, that is the headline: the
   route lowers prices for catalogue items the walk never names, and T2's remedy is about what the
   walk considers, not about the route.
3. Whether the chosen root names an item at all. If most characters' chosen roots are
   `ReachSkillLevel` or `ReachCharLevel`, the sibling route is structurally unreachable from the
   root walk regardless of pricing.
