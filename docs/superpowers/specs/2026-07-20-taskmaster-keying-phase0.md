# Taskmaster Keying (Phase 0)

**Date:** 2026-07-20
**Status:** DESIGNED — not built
**Parent:** `2026-07-19-synergy-weighting-design.md` §6 Phase 0
**Blocks:** synergy Phase 4 (taskmaster choice)
**Independent of:** the requirement-model unification epic — these are plain bug fixes and
can land first, alone.

---

## 1. The bug

`ai/game_data.py:1398-1400`:

```python
elif ct == MapContentType.TASKS_MASTER:
    self._taskmaster_location = loc
```

**One slot, two tiles, `content.code` discarded.** The fixture
`tests/test_ai/scenarios/fixtures/gamedata_bundle.json` carries both
`(1,2) → 'monsters'` and `(4,13) → 'items'`. Whichever tile iteration reaches last wins; the
other taskmaster is invisible to the bot for its entire run.

This is the only `_build_maps` branch that does not key by `content.code` — `MONSTER`,
`RESOURCE`, `NPC` and `RAID` all do. It is also the third instance of one shape: a keyed
thing collapsed into a single unkeyed slot, making contention between siblings structurally
invisible (cf. the ring2 arbiter starvation and the currency-grind fall-off).

### 1.1 Why it matters beyond tidiness

Upstream docs (https://docs.artifactsmmo.com/concepts/tasks/):

> "The type of task you receive depends on the Tasks Master you visit."

So taskmaster choice is a **strategic lever** — binary, `TaskType.ITEMS` vs
`TaskType.MONSTERS`. Today the bot cannot pull it, and does not know it exists.

### 1.2 The compounding defect

`ai/actions/accept_task.py:33` — `AcceptTaskAction.apply` hardcodes `task_type="monsters"`
for the projected state regardless of which tile was walked to. The model asserts one type;
the server may return the other; nothing reconciles. Harmless while only one taskmaster is
reachable, actively wrong the moment 0.1 lands.

### 1.3 The discarded pool data

`_fetch_tasks` (`game_data.py:1642`) already pages the **entire** task pool with no filters.
`_build_tasks` (`:1656`) then keeps three reward projections and discards `type_`, `level`,
`skill`, `min_quantity`, `max_quantity`. The bot therefore cannot enumerate what a given
master can issue. The data is fetched and thrown away every run.

---

## 2. Changes

### 2.1 Key taskmasters by code

| Location | Change |
|---|---|
| `ai/location_catalog.py:26` | `taskmaster_tile: tuple[int,int] \| None` → `taskmaster_tiles: dict[str, tuple[int,int]]` |
| `ai/location_catalog.py:135` | `taskmaster_location()` → `taskmaster_location(code: str \| None = None)` |
| `ai/game_data.py:1398-1400` | key by `content.code` |
| `ai/game_data.py:189-194` | `_taskmaster_location` property/setter follow |
| `ai/game_data.py:655`, `:1187` | accessors follow |
| `tui/widgets/map_pane.py:138-140` | render one sprite per taskmaster tile, not one total |

**Compatibility.** `taskmaster_location()` with no argument keeps returning a single tile so
the ~5 existing call sites need no change in this phase. It resolves to the *nearest* master
rather than the last one parsed — an improvement that is also a behaviour change, so it
needs its own test. It still raises `RuntimeError` when no taskmaster exists at all,
preserving `location_catalog.py:135`'s contract.

### 2.2 Retain the task pool

In `_build_tasks` (`game_data.py:1656`), retain `type_`, `level`, `skill`, `min_quantity`,
`max_quantity` alongside the existing reward projections. Add:

```python
def tasks_for(self, task_type: str, max_level: int) -> list[TaskFullSchema]
```

**`CACHE_VERSION` must be bumped** (`ai/game_data_cache.py:11`, currently 4). The on-disk
bundle gains fields; a stale v4 bundle would hydrate a `GameData` whose `tasks_for` returns
empty, which fails *silently* as "no tasks at this level".

Retain the existing `GameDataCoverageError` on `tasks_coin < 1` (the C2 monotonicity proof
depends on it).

### 2.3 Accept-task carries its master

`AcceptTaskAction` gains `taskmaster_code: str`. `apply` (`accept_task.py:33`) projects
`task_type` from that code instead of the `"monsters"` literal. `ai/actions/factory.py:59-69`
constructs one `AcceptTaskAction` per discovered taskmaster rather than one against a single
tile.

`CompleteTaskAction`, `TaskExchangeAction`, `TaskCancelAction` and `TaskTradeAction` are
**left pointed at the nearest master pending R1** (§4). Changing their routing is not
required by anything in this phase and would depend on an unverified server rule.

---

## 3. Verification

| Test | Asserts |
|---|---|
| `test_both_taskmasters_discovered` | Against the real bundle fixture, both `(1,2)` and `(4,13)` are present and keyed `monsters` / `items`. **Fails today** |
| `test_taskmaster_location_returns_nearest` | The no-arg accessor picks by distance, not parse order |
| `test_taskmaster_location_raises_when_none` | Existing `RuntimeError` contract preserved |
| `test_accept_task_projects_master_type` | `apply` from the items master yields `task_type == "items"`. **Fails today** |
| `test_tasks_for_filters_type_and_level` | `tasks_for` returns only matching type at or below level |
| `test_stale_cache_version_rejected` | A v4 bundle is refused rather than hydrating an empty pool |
| Census gate | Four checks stay at zero |

Runtime activation: `plan <char>` must show the chosen master, since green tests do not prove
a live path fires.

---

## 4. Residual

**R1 — where a task may be completed or exchanged is ASSERTED, not probed.** The docs state
exchange works at "any Task Master"; **completion is unspecified**. This phase deliberately
does not act on either. Probe both live before synergy Phase 4 depends on the answer, and
record the result — if completion is master-specific, `CompleteTaskAction` must route to the
issuing master, and the travel cost of a mis-chosen master becomes part of Phase 4's
economics. Same trap as the duplicate-artifacts server rule: asserted once, never probed.

---

## 5. Out of scope

- Choosing between taskmasters — that is synergy Phase 4. This phase only makes the choice
  *representable*.
- Re-routing complete/exchange/cancel/trade (pending R1).
- Reward-value optimisation. The coin/gold tables (items 2/3/4, monsters 3/4/5 by level band)
  are noted in the synergy design but unused; selection there is on synergy alone.
