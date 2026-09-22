# T2.0 Sibling-Route Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish, with evidence, whether `acquisition_cost._sibling_craft_option` changes any
pricing decision on live fleet data — so the season-9 fleet-capability track extends the route it
already has, or fixes the gate that suppresses it, rather than rebuilding either.

**Architecture:** One differential census. For each (character, item) pair where the character is
behind a crafting gate a live sibling already clears, price the item twice — once with the real
`SelectionContext.sibling_skills`, once with that map emptied — and report where the two answers
differ. A route that is priced but never lowers a price is inert; the differential distinguishes
that from a route that is absent, which counting eligible pairs alone cannot. Changes no ranking,
goal, plan or cost.

**Tech Stack:** Python 3.13, `uv`, SQLModel over SQLite, typer for the report command, pytest.

**Spec:** `docs/PLAN_season9_readiness.md` (track T2)

## Global Constraints

- Every Python command is prefixed `uv run`.
- All imports at the top of the file. No inline imports.
- Absolute imports only. Never `...`-relative.
- One *behavioural* class per file. Cohesive pure data/value objects may share a module.
- Never `except Exception`. Never `if TYPE_CHECKING`.
- No second implementation of anything — fix in place.
- Tests live in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- Use only API data, or fail with an error. No defaulting to cover missing game data.
- Durable claims rest on `~/.cache/artifactsmmo/learning.db` only.
- `scripts/pre_commit.sh:32` lints `src/artifactsmmo_cli/ai/` and `formal/` ONLY — never `tests/`.
  A lint or import-placement defect in a test file is invisible to every commit.
- `pyproject.toml` sets `branch = false`, so statement coverage can be 100% while a documented rule
  has no test behind it. Every rule this plan states gets its own test.

## Verified API surface

Read from the tree on 2026-09-22. Use these spellings.

| Name | Where | Shape |
|---|---|---|
| `_sibling_craft_option` | `ai/acquisition_cost.py:375` | `(item, state, game_data, ctx, store) -> RouteOption \| None` |
| `route_options` | `ai/acquisition_cost.py:527` | `(item, state, game_data, ctx, store=None, gated_drop=True) -> list[RouteOption]` |
| `acquisition_options` | `ai/acquisition_cost.py:580` | `(item, state, game_data, ctx, store=None, gated_drop=True) -> dict[str, list[RouteOption]]` |
| `acquisition_actions` | `ai/acquisition_cost.py:635` | `(item, qty, state, game_data, ctx, equip, store=None, gated_drop=True) -> int` |
| `RouteOption` | `ai/acquisition_cost_core.py:137` | frozen; fields include `kind`, `venue`, `actions_per_application`, `yield_per`, `capacity`, `inputs`, `unlock`, `unlock_actions` |
| `SelectionContext` | `ai/selection_context.py:33` | frozen dataclass; `sibling_skills: dict[str, int]`; `NO_PROFILE_CONTEXT` at `:240` |
| `CoordinationStore.sibling_skill_levels` | `ai/learning/coordination_store.py:660` | `(now) -> dict[str, int]` over the TTL'd `skill_ledger` |
| `LearningStore.fleet_supply_request_cycles` | `ai/learning/store.py:805` | `() -> float \| None`; prices the `sibling:` unlock |
| `GameDataCache` | `ai/game_data_cache.py:20` | reads `~/.cache/artifactsmmo/gamedata-<host>.json` |
| `default_learn_db_path` | `learning_db_path.py:13` | `() -> str` |

The sibling route's `unlock` is the literal `f"sibling:{item}"` (`acquisition_cost.py:421`). That
prefix is how the census identifies the route in a `RouteOption` list — match on
`unlock.startswith("sibling:")`, never on `kind`, because `kind` is `SourceKind.CRAFT.value` and
indistinguishable from an ordinary craft.

## What is already measured — do not re-establish

Measured on the live store and cached catalogue on 2026-09-22, before this plan was written:

- **The capability matrix is live.** `skill_ledger` holds 40 fresh rows — 5 characters × 8 skills,
  written 06:38 that morning.
- **The route's pricing gate is satisfied.** `fleet_supply_request_cycles()` reads 223
  (request, producer) `SupplyBank` pairs over 7,583 cycles, median 20. It is not None, so the
  "fleet has never served a request" early return does not fire.
- **The route has 104 eligible (character, item) pairs**: R2D2 32, Lor 31, C3P0 30, HAL 9, Robby 2.
  Examples: `hard_leather_armor/boots/helmet/pants` (gearcrafting 20) are gated for C3P0, Lor and
  R2D2 at 15 while HAL and Robby hold 20; `air/earth/fire/life_ring` (jewelrycrafting 15) likewise.
- **The fleet's own wall is NOT reachable this way.** T1 found C3P0's four binding monsters all
  need weaponcrafting 25; the fleet's best weaponcrafter is Robby at 18. No sibling clears it.

So all three eligibility gates pass. The open question this plan answers is whether the priced
route ever changes an answer.

---

## File Structure

**Create:**
- `src/artifactsmmo_cli/audit/sibling_route_census.py` — the differential census.
- `src/artifactsmmo_cli/commands/sibling_route_report.py` — `artifactsmmo sibling-route-audit`,
  read-only.
- `tests/test_ai/test_sibling_route_census.py`
- `tests/test_ai/test_sibling_route_report.py`

**Modify:**
- `src/artifactsmmo_cli/main.py` — register the report command beside the others near line 60.

---

### Task 1: The differential census

**Files:**
- Create: `src/artifactsmmo_cli/audit/sibling_route_census.py`
- Test: `tests/test_ai/test_sibling_route_census.py`

**Interfaces:**
- Consumes: `route_options`, `acquisition_actions` from `artifactsmmo_cli.ai.acquisition_cost`;
  `SelectionContext` from `artifactsmmo_cli.ai.selection_context`; `GameData`, `WorldState`,
  `LearningStore`.
- Produces: `SiblingVerdict` (frozen dataclass: `item`, `skill`, `required_level`, `held_level`,
  `best_sibling_level`, `priced: bool`, `actions_with: int`, `actions_without: int`; property
  `saving`) and
  `sibling_route_verdicts(state, game_data, ctx, store, items) -> list[SiblingVerdict]`.

The census must answer three distinct questions per item, and keep them distinct:
1. **Eligible** — the character is behind the gate and a sibling clears it.
2. **Priced** — `route_options(...)` actually returns a route whose `unlock` starts with `sibling:`.
3. **Load-bearing** — pricing the item with the real `sibling_skills` yields FEWER actions than
   pricing it with `sibling_skills` emptied.

An item can be eligible and unpriced (a gate suppresses it), or priced and not load-bearing (it is
outpriced by the character's own routes). Those are different findings with different fixes, and
collapsing them is how this audit would produce a confident wrong answer.

- [ ] **Step 1: Write the failing test**

```python
"""The sibling-route differential: eligible, priced, and load-bearing are three questions."""

from artifactsmmo_cli.audit.sibling_route_census import SiblingVerdict


def test_saving_is_the_action_difference() -> None:
    v = SiblingVerdict(item="air_ring", skill="jewelrycrafting", required_level=15,
                       held_level=13, best_sibling_level=20, priced=True,
                       actions_with=8, actions_without=40)
    assert v.saving == 32


def test_a_priced_route_that_saves_nothing_is_not_load_bearing() -> None:
    v = SiblingVerdict(item="air_ring", skill="jewelrycrafting", required_level=15,
                       held_level=13, best_sibling_level=20, priced=True,
                       actions_with=40, actions_without=40)
    assert v.saving == 0
    assert v.load_bearing is False


def test_a_load_bearing_route_saves_actions() -> None:
    v = SiblingVerdict(item="air_ring", skill="jewelrycrafting", required_level=15,
                       held_level=13, best_sibling_level=20, priced=True,
                       actions_with=8, actions_without=40)
    assert v.load_bearing is True


def test_an_unpriced_route_is_never_load_bearing_even_if_the_costs_differ() -> None:
    # Defensive: if the two prices differ while no sibling route was returned, the
    # difference came from somewhere else and must not be credited to this route.
    v = SiblingVerdict(item="air_ring", skill="jewelrycrafting", required_level=15,
                       held_level=13, best_sibling_level=20, priced=False,
                       actions_with=8, actions_without=40)
    assert v.load_bearing is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_sibling_route_census.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.audit.sibling_route_census'`

- [ ] **Step 3: Write the value object and the census**

Write `SiblingVerdict` with the fields above and:

```python
    @property
    def load_bearing(self) -> bool:
        """The route was priced AND pricing the item without it costs more.

        `priced` is a conjunct, not a formality. Emptying `sibling_skills` changes
        one input to a walk that reads many; if the two prices differ while no
        sibling route was returned, the difference came from somewhere else and
        crediting it here would manufacture evidence for the thing being audited.
        """
        return self.priced and self.saving > 0
```

`sibling_route_verdicts` must, per item:
- read `route_options(item, state, game_data, ctx, store)` and set `priced` from whether any
  returned option has `unlock.startswith("sibling:")`;
- compute `actions_with = acquisition_actions(item, 1, state, game_data, ctx, equip=False, store=store)`;
- compute `actions_without` the same way against `dataclasses.replace(ctx, sibling_skills={})`;
- record `held_level` from `state.skills` and `best_sibling_level` from `ctx.sibling_skills`.

Read the real field names on `SelectionContext` before writing the `replace` call.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_sibling_route_census.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Add a census-level test over a declared world**

Add a test that drives `sibling_route_verdicts` over a fixture world where exactly one item is
eligible and a sibling clears its gate. **Declare that world in this test module's own fixtures** —
do not reuse a shared `GameData` fixture. One shared world across scenarios has already produced
three vacuous measurements and a shipped false retraction in this codebase.

Prove the test is load-bearing before accepting it: temporarily empty `ctx.sibling_skills` in the
fixture, confirm the verdict flips to `priced=False`, then restore by copying the file aside and
back — never `git checkout <path>`. Record the observed failure in your report.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/audit/sibling_route_census.py tests/test_ai/test_sibling_route_census.py
git commit -m "feat(audit): differential census for the sibling-craft route"
```

---

### Task 2: The report command

**Files:**
- Create: `src/artifactsmmo_cli/commands/sibling_route_report.py`
- Modify: `src/artifactsmmo_cli/main.py`
- Test: `tests/test_ai/test_sibling_route_report.py`

**Interfaces:**
- Consumes: `SiblingVerdict`, `sibling_route_verdicts` from Task 1; `CoordinationStore`,
  `LearningStore`, `default_learn_db_path`.
- Produces: `sibling_route_audit_command`.

Before writing it, read `src/artifactsmmo_cli/commands/objective_audit_report.py` — it is this
repo's working precedent for a read-only diagnostic that senses live state without writing session
rows into the fleet's database, and it already solved the config/client/player construction. Mirror
its real sequence; if this plan's description disagrees with that file, follow the file.

The command takes a character, senses its live state, builds the context from
`CoordinationStore.sibling_skill_levels`, enumerates the candidate items (every craftable item
where the character is behind the gate and a sibling clears it), and prints three counts —
**eligible**, **priced**, **load-bearing** — followed by the load-bearing rows with their savings,
largest first.

Print all three counts even when the lower two are zero. "Eligible 30, priced 0" is the finding
that says a gate suppresses the route; a report that showed only load-bearing rows would print
nothing and read as "no candidates", which is a different and wrong conclusion.

- [ ] **Step 1: Write the failing test**

Cover the command with the sense seam and the store substituted, asserting: the three count lines
print; a run whose verdicts are all `priced=False` still prints the eligible count and an explicit
"0 priced" line; and a load-bearing row prints its saving. No real API call may be reachable.

- [ ] **Step 2: Run it and confirm it fails for the stated reason.**

- [ ] **Step 3: Write the command, mirroring `objective_audit_report.py`'s construction.**

- [ ] **Step 4: Register it in `main.py`** beside the other `app.command(...)` registrations:

```python
app.command("sibling-route-audit",
            help="Read-only: whether a sibling's crafting skill changes any price")(
    sibling_route_audit_command)
```

- [ ] **Step 5: Run it live and record the REAL output**

Run: `uv run artifactsmmo sibling-route-audit C3P0`

C3P0 has 30 eligible items, so the eligible count must be non-zero. If it prints 0 eligible, the
candidate enumeration disagrees with the measurement in this plan's "already measured" section and
that disagreement is the finding — report it rather than adjusting the number.

The live fleet is running and the API is rate-limited; a 429 is contention, not a defect.

- [ ] **Step 6: Run the full gate**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo "exit=$?"`
Do NOT pipe into `tail` — a pipeline reports the tail's exit code, not the gate's. Two live-API
audit tests fail HTTP 429 whenever the fleet runs and pass standalone; that is pre-existing.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/commands/sibling_route_report.py src/artifactsmmo_cli/main.py \
        tests/test_ai/test_sibling_route_report.py
git commit -m "feat(audit): sibling-route-audit report over eligible, priced and load-bearing"
```

---

## What this plan deliberately does not do

- It changes no ranking, goal, plan or cost, and does not touch `_sibling_craft_option` itself.
- It does not extend the route to gathering skills or multi-hop. The spec makes both conditional on
  what this census finds, and neither is justified before it reports.
- It does not decide T2's remedy. That decision is made against this output.

## Findings to record when the audit runs

Record all of them, including the runs that find nothing.

1. Eligible / priced / load-bearing counts per character. The gap between the first two names a
   suppressing gate; the gap between the second and third names an outpricing.
2. If priced is 0 against 104 eligible pairs, find the gate that suppresses it BEFORE changing
   anything — the three known early returns in `_sibling_craft_option` are the character's own skill
   already clearing the gate, no sibling clearing it, and an unpriceable `fleet_supply_request_cycles`.
   The third is already measured non-None, so it is not the answer.
3. The largest savings, with the item and the sibling that supplies it. A route that saves 30+
   actions on `hard_leather_*` is the argument for the whole track.
4. Whether any load-bearing item is gear the character actually wants, or only an intermediate. A
   saving on something nothing needs is not a reason to extend anything.
