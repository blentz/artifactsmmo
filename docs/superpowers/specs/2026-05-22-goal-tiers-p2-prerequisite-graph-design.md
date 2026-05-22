# Goal Tiers — P2: Tier-2 Meta-Goal Prerequisite Graph

Date: 2026-05-22
Status: Approved (design)

Part of the multi-phase goal-architecture redesign:
- P1 (done) — Tier-1 objective + gap + personality seam.
- **P2 (this spec)** — Tier-2 meta-goal **prerequisite graph**: the concrete,
  data-derived search space P3 will walk. Pure, **no behavior change**.
- P3 — Tier-3 frontier search over this graph; behavior switches there.
- P4 — Tier-4 tactical. P5 — personalities.

## Goal

Provide the search substrate for the tiered architecture: a set of concrete
**meta-goal nodes** (reach a char level, reach a skill level, obtain an item)
and a pure `prerequisites(node, state, game_data)` edge function derived
entirely from game data (recipes, resource→skill, monster levels). The graph
encodes the level↔gear↔skill dependencies (and the cycles they can form);
**gathering is the acyclic base case** that lets a chain terminate. P2 ships a
pure, fully-tested module consumed by **nothing yet** — no behavior change. P3
adds the frontier search (find the nearest node whose whole prerequisite
closure is satisfiable) and wires it into the loop.

## Current state

P1 delivered `ai/tiers/`: `equip_value`, `CharacterObjective` (target char
level 50, each skill 50, best-value item per slot) + `ObjectiveGap`,
`Personality`/`weighted_remaining`. `GameData` exposes `crafting_recipe(code)`
(`{material: qty}` or None), `item_stats(code)` (with `crafting_skill`,
`crafting_level`), `_resource_drops` (resource→drop item), `resource_skill(code)`
(`(skill, level)`), and `monster_level(code)` / `_monster_level`.
`FightAction.is_applicable` gates combat on `char_level >= monster_level - 1`.
Decisions still run through the flat `priorities.py` goal list (untouched here).

## Design

### Module layout (extends `src/artifactsmmo_cli/ai/tiers/`)
- `meta_goal.py` — the `MetaGoal` protocol + three frozen node types
  (`ReachCharLevel`, `ReachSkillLevel`, `ObtainItem`). Tightly-coupled models in
  one file (objective.py precedent).
- `prerequisite_graph.py` — pure free functions: `prerequisites`,
  `objective_roots`, `combat_capable`, `best_attainable_weapon`.
- Extend `tiers/__init__.py` exports.

### Nodes — `meta_goal.py`
All frozen + hashable (used in visited-sets during P3 traversal). Each carries
its own satisfaction test against a `WorldState`/`GameData`.

```python
class MetaGoal(Protocol):
    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool: ...
```

- `ReachCharLevel(level: int)` — satisfied when `state.level >= level`.
- `ReachSkillLevel(skill: str, level: int)` — satisfied when
  `state.skills.get(skill, 1) >= level`.
- `ObtainItem(code: str, quantity: int = 1)` — satisfied when the owned count
  (inventory + bank + 1 if equipped) `>= quantity`.

Owned count helper (module-level in `meta_goal.py`): inventory `get(code,0)` +
`(state.bank_items or {}).get(code,0)` + `(1 if code in
state.equipment.values() else 0)`.

### Edges — `prerequisites(node, state, game_data) -> list[MetaGoal]`
Pure free function in `prerequisite_graph.py`, dispatching on node type. Returns
the **direct** prerequisites (callers filter for unmet / traverse). Edges are
derived only from game data:

- **`ObtainItem(code, qty)`**
  - If already satisfied → `[]`.
  - Craftable (`crafting_recipe(code)` is not None):
    `[ReachSkillLevel(craft_skill, craft_level)]` (when the item's
    `crafting_skill`/`crafting_level` are known) **+** `[ObtainItem(mat, mat_qty)
    for mat, mat_qty in recipe.items()]`. (Per-craft material quantities; P3
    scales for batch.)
  - Else gatherable — some resource `r` has `_resource_drops[r] == code` with a
    `resource_skill(r) = (skill, level)`: `[ReachSkillLevel(skill, level)]`
    (once the gather skill is met, gathering yields the item; the gather action
    itself is a planner concern).
  - Else (buyable / monster-drop / unknown production) → `[]` (leaf). Economy
    and drop-sourcing are P3/economy concerns; P2 treats these as terminal.

- **`ReachCharLevel(level)`**
  - If `combat_capable(state, game_data)` → `[]` (a beatable monster exists;
    grinding it is the action — a leaf).
  - Else (under-equipped: no beatable monster) →
    `[ObtainItem(best_attainable_weapon(game_data))]` when a weapon exists. This
    is the **level ← gear** edge: become combat-capable by getting a weapon,
    which pulls in the craft chain (gear ← craft-skill ← materials ← gather).

- **`ReachSkillLevel(skill, level)`** → `[]` (leaf). A skill is raised by
  repeated skill actions; the materials/recipes those actions consume are pulled
  in through the `ObtainItem` chains that *require* the skill, not through the
  skill node itself. This keeps the graph finite with gathering as the base case.

### Capability + weapon helpers — `prerequisite_graph.py`
- `combat_capable(state, game_data) -> bool` = any monster with
  `monster_level <= state.level + 1` (mirrors the `FightAction` level gate).
  *Win-rate / gear-strength refinement (learning store) is deferred to P3's
  search; P2 uses the documented level gate as the floor.*
- `best_attainable_weapon(game_data) -> str | None` = highest `equip_value`
  item of `type_ == "weapon"` (ties broken by code); `None` if none. (Shares
  `equip_value`; consistent with the objective's weapon target.)

### Roots — `objective_roots(objective) -> list[MetaGoal]`
Bridges P1 → P2: from a `CharacterObjective`,
`[ReachCharLevel(target_char_level)]` + `[ReachSkillLevel(s, lvl) for s, lvl in
target_skill_levels.items()]` + `[ObtainItem(code) for code in
target_gear.values()]`. These are the roots P3's frontier search starts from.

### Cycles
Edges can form cycles (e.g. a level-N resource needs a high gather skill whose
only practical leveling path loops back through gear). P2 does **not** resolve
cycles — `prerequisites` returns direct edges only; the gathering/`[]`-leaf base
cases mean most chains terminate, and P3's traversal carries a visited-set for
the rest. P2 adds no traversal/search itself.

### Data flow (P2)
`CharacterObjective → objective_roots → MetaGoal nodes`; per node,
`prerequisites(node, state, game_data)` yields direct prerequisite nodes;
`node.is_satisfied(state, game_data)` tests completion. No caller wired — the
player loop is untouched.

## Error handling
- Pure, no API calls. Missing recipe/skill/stats → the relevant branch yields
  `[]` (treated as a leaf), never raises.
- `best_attainable_weapon` returns `None` on an empty item table →
  `ReachCharLevel` under-equipped branch yields `[]` (nothing to obtain).
- Unknown craft skill on a craftable item → omit the `ReachSkillLevel`
  prerequisite, keep the material prerequisites.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on new code.

- **Node satisfaction:** `ReachCharLevel`/`ReachSkillLevel` thresholds;
  `ObtainItem` counts inventory + bank + equipped against quantity.
- **`ObtainItem` edges:** craftable → skill + material prereqs (with the right
  craft skill/level and per-material quantities); gatherable → gather
  `ReachSkillLevel`; buyable/unknown → leaf; already-owned → `[]`.
- **`ReachCharLevel` edges:** combat-capable (a low-level monster exists) →
  leaf; under-equipped (all monsters above `level+1`) → `[ObtainItem(best
  weapon)]`; no weapons in data → leaf.
- **`ReachSkillLevel`** → always leaf.
- **`combat_capable`** boundary: monster at exactly `level+1` capable; at
  `level+2` not.
- **`best_attainable_weapon`:** highest-value weapon; code tiebreak; None when
  no weapons.
- **`objective_roots`:** one `ReachCharLevel`, one `ReachSkillLevel` per skill,
  one `ObtainItem` per targeted gear slot.
- **Cycle safety:** a hand-built cyclic recipe fixture — assert `prerequisites`
  returns finite direct edges and a BFS with a visited-set terminates (the test
  drives traversal; P2 itself adds none).

## Files
- Create `src/artifactsmmo_cli/ai/tiers/meta_goal.py`,
  `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`.
- Modify `src/artifactsmmo_cli/ai/tiers/__init__.py` — exports.
- Tests: `tests/test_ai/test_tiers_meta_goal.py`,
  `tests/test_ai/test_tiers_prerequisite_graph.py`.

## Out of scope (later phases)
- The frontier search / "nearest fully-satisfiable subgoal" selection (P3).
- Wiring into the player loop / retiring `priorities.py` (P3).
- Win-rate / gear-strength combat capability (P3 search refinement).
- Economy sourcing (buy/sell/bank) and monster-drop items as prerequisite
  branches (P3).
- HP safety interrupt, battle-prep, tactical policies (P3/P4).
