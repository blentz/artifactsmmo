# Mining Tool Relevance — Implementation Plan

> **For agentic workers:** inline TDD (superpowers:executing-plans). The change threads one new signal through frozen WorldState → game_data → 6 consumers; tightly coupled, do not parallelize.

**Goal:** The bot crafts a pickaxe (mining tool) when it is mining for its own crafted gear, the same way it already crafts an axe/fishing-net for task-driven woodcutting/fishing.

**Root cause:** `GameData.active_gathering_skills(task_code)` derives "active" gather skills only from the current taskmaster task's recipe tree. Self-directed mining (gathering copper ore to craft copper equipment) is driven by the UpgradeEquipment target, not `task_code`, so mining never becomes "active" → the pickaxe is never flagged a relevant tool upgrade. Axe/net got built because a task's recipe tree happened to need wood/fish.

**Approach (chosen):** Union the active-skill set with the recipe tree of the bot's current committed crafting/upgrade target. Carry that target on `WorldState.crafting_target` (set each cycle via `dataclasses.replace`) so every consumer — tool relevance, gating-XP, scalarizer — reads it uniformly.

**Tech Stack:** Python 3.13, uv, pytest.

---

## Task 1: WorldState carries the crafting target
**Files:** `src/artifactsmmo_cli/ai/world_state.py`; test `tests/test_ai/test_world_state.py` (or existing).
- Add frozen field `crafting_target: str | None = None` (the item the bot is currently working to craft/upgrade toward).
- Test: default is None; `dataclasses.replace(state, crafting_target="copper_pickaxe").crafting_target == "copper_pickaxe"`.

## Task 2: active_gathering_skills unions task + crafting target
**Files:** `src/artifactsmmo_cli/ai/game_data.py`; test `tests/test_ai/test_game_data*.py`.
- Signature: `active_gathering_skills(self, task_code: str | None, crafting_target: str | None = None) -> set[str]`.
- Walk the recipe tree for BOTH roots (task_code and crafting_target), union the skills. Remove the `if not task_code: return set()` early-out; instead walk whichever roots are non-None.
- Test: task_code=None + crafting_target whose recipe chain reaches a mined resource → returns {"mining"}; both roots → union; both None → empty set.

## Task 3: player sets state.crafting_target each cycle
**Files:** `src/artifactsmmo_cli/ai/player.py`.
- After `self._committed_upgrade_target = committed` (line ~953), set
  `self.state = replace(self.state, crafting_target=committed[0] if committed else None)`.
  (Import `dataclasses.replace`.) This runs before goals are built and before planning/scalarizer, so all consumers see it.

## Task 4: route the target through all consumers
**Files:** `player.py` (996, 1162), `goals/progression.py` (62, 203, 226, 257), `learning/scalarizer.py` (137).
- Change each `active_gathering_skills(state.task_code)` → `active_gathering_skills(state.task_code, state.crafting_target)` (and `self.state` variants).

## Task 5: behavioral test — pickaxe becomes relevant when crafting needs mining
**Files:** `tests/test_ai/test_goals.py`.
- Build GameData where a copper-gear craft target's recipe chain reaches a mining resource, current weapon boosts a non-mining skill, pickaxe craftable. Assert the craftable-upgrade picker / `_upgrade_is_relevant_tool` selects the pickaxe when `state.crafting_target` is the copper gear (mining active), and does NOT when crafting_target is None and task_code is unrelated.

## Task 6: verify
- `uv run pytest -q` → 0 fail/skip. Coverage 100% on changed files. `uv run ruff check` + `uv run mypy` clean on changed files.

---
## Self-review
- Frozen-state safe (replace, not mutate). Ordering verified: target computed before goals/planner.
- Single signal change keeps tool relevance, gating XP, and scalarizer consistent (the chosen approach's intent).
- All 7 call sites enumerated; each has `state`.
