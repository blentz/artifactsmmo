# GOAP AI Player — Design Spec
**Date:** 2026-05-12
**Status:** Approved

## Overview

The project's primary deliverable is a GOAP (Goal-Oriented Action Planning) AI player that plays ArtifactsMMO autonomously. The existing CLI commands serve as diagnostic and development tooling. The AI runs as a long-running CLI command (`artifactsmmo play <character>`), replanning every cycle using forward A* search over a bounded action graph.

## Architecture

The AI lives in a new `src/artifactsmmo_cli/ai/` package. The existing `commands/` package is unchanged.

```
src/artifactsmmo_cli/
├── ai/
│   ├── world_state.py      # WorldState frozen dataclass
│   ├── game_data.py        # Static game knowledge cache (map, items, recipes)
│   ├── planner.py          # Forward A* GOAP planner
│   ├── player.py           # GamePlayer: main sense→plan→act loop
│   ├── actions/
│   │   ├── base.py         # Action ABC
│   │   ├── movement.py     # MoveAction
│   │   ├── combat.py       # FightAction
│   │   ├── gathering.py    # GatherAction
│   │   ├── rest.py         # RestAction
│   │   ├── bank.py         # DepositAllAction, WithdrawItemAction
│   │   ├── crafting.py     # CraftAction
│   │   └── equipment.py    # EquipAction
│   └── goals/
│       ├── base.py         # Goal ABC
│       ├── survival.py     # RestoreHPGoal, DepositInventoryGoal
│       ├── combat.py       # FarmMonsterGoal, CompleteTaskGoal
│       └── progression.py  # UpgradeEquipmentGoal, CraftItemGoal
└── commands/
    └── play.py             # `artifactsmmo play <character>` CLI entry point
```

**Data flow:** `WorldState` is read by goals and the planner; written only by the player loop from API responses. `GameData` is loaded once at startup and never mutated. The planner never calls the API — only `action.execute()` does.

## World State

`WorldState` is a frozen dataclass so the planner can apply action effects to copies without mutating real state. The player loop builds a fresh `WorldState` from the API response after every action.

```python
@dataclass(frozen=True)
class WorldState:
    character: str
    level: int
    xp: int
    max_xp: int
    hp: int
    max_hp: int
    gold: int
    skills: dict[str, int]            # skill_name -> level
    x: int
    y: int
    inventory: dict[str, int]         # item_code -> quantity
    inventory_max: int
    equipment: dict[str, str | None]  # slot -> item_code | None
    cooldown_expires: datetime | None
    task_code: str | None
    task_type: str | None             # "monsters", "resources", "crafting"
    task_progress: int
    task_total: int
    bank_items: dict[str, int] | None  # None = unknown (not yet visited)
    bank_gold: int | None
```

Monster and resource locations are **not** stored in `WorldState` — they live in `GameData` (loaded at startup from the map/items APIs), keeping `WorldState` small and fast to copy during search.

`bank_items` is `None` until the AI visits the bank. The planner treats unknown bank state conservatively (assumes empty).

## Game Data Cache

`GameData` is loaded once at startup by querying the map, items, monsters, and resources APIs. It provides:

- `monster_locations(code) -> list[tuple[int,int]]` — tiles where a monster spawns
- `resource_locations(code) -> list[tuple[int,int]]` — tiles where a resource appears
- `workshop_location(skill) -> tuple[int,int]` — nearest workshop for a crafting skill
- `bank_location() -> tuple[int,int]`
- `item_stats(code) -> ItemStats` — level requirement, equipment slot, attack/defense values
- `crafting_recipe(code) -> dict[str, int] | None` — materials needed to craft an item

## Goals

Every goal implements three methods:

```python
class Goal(ABC):
    def value(self, state: WorldState, game_data: GameData) -> float:
        """Urgency score. Higher = more urgent. Called every cycle."""

    def is_satisfied(self, state: WorldState) -> bool:
        """True when this goal has been achieved."""

    def desired_state(self, state: WorldState, game_data: GameData) -> dict:
        """Partial world state the planner targets."""
```

### Goal inventory (v1)

| Goal | Value function | Satisfied when |
|------|---------------|----------------|
| `RestoreHPGoal` | `(1 - hp/max_hp) * 100` | `hp == max_hp` |
| `DepositInventoryGoal` | `(used/max) * 80` | inventory has ≥5 free slots |
| `CompleteTaskGoal` | `50 + (progress/total) * 40` | `task_progress >= task_total` |
| `FarmMonsterGoal` | `30 + (xp/max_xp) * 20` | never (continuous) |
| `UpgradeEquipmentGoal` | `35` if upgrade available, else `0` | better item equipped |

`RestoreHPGoal` and `DepositInventoryGoal` act as interrupts via their value functions — no special-case logic needed. When HP drops below ~30% the value exceeds 70, overriding all other goals automatically.

`CompleteTaskGoal` handles all task types (monster kills, gathering, and crafting) — its `desired_state` expresses the full sub-plan for the task type, including withdrawing materials and crafting when `task_type == "crafting"`. No separate `CraftItemGoal` is needed.

The player selects the goal with the highest `value()` each cycle. If planning fails for the top goal, it tries the next-highest.

## Actions

Every action implements four methods:

```python
class Action(ABC):
    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        """Can this action be taken from this state?"""

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        """Pure function: return new WorldState after applying this action's effects."""

    def cost(self, state: WorldState, game_data: GameData) -> float:
        """Estimated seconds. A* minimises total cost = total time."""

    def execute(self, state: WorldState, client) -> WorldState:
        """Call the API. Return updated WorldState built from the API response."""
```

### Action inventory (v1)

| Action | Key precondition | Key effect | Cost |
|--------|-----------------|------------|------|
| `MoveAction(x, y)` | not in cooldown | position = (x, y) | distance × 5s |
| `FightAction(monster)` | at monster tile, hp > 30% | xp++, drops to inventory | ~10s + cooldown |
| `GatherAction(resource)` | at resource tile, skill met | resource to inventory | ~6s + cooldown |
| `RestAction` | hp < max_hp | hp = max_hp | ~2s |
| `DepositAllAction` | at bank | inventory → bank | ~2s per item type |
| `WithdrawItemAction(code, qty)` | at bank, item in bank | item to inventory | ~2s |
| `CraftAction(code, qty)` | at correct workshop, materials in inventory | item created | ~5s |
| `EquipAction(code, slot)` | item in inventory | equipment[slot] = code | ~1s |

`MoveAction` is a composable primitive inserted dynamically during planning: when an action's `is_applicable` fails due to wrong location, the planner prepends a `MoveAction` to the required tile. This avoids enumerating "MoveToBank", "MoveToMonster", etc. as separate actions.

## Planner

```python
class GOAPPlanner:
    def plan(
        self,
        state: WorldState,
        goal: Goal,
        actions: list[Action],
        game_data: GameData,
        max_depth: int = 8,
    ) -> list[Action]:
```

**Algorithm:** Forward A* search.

- **Node:** `(f_score, depth, state, plan_so_far)`
- **g(n):** cumulative cost (sum of `action.cost()` along the path)
- **h(n):** `max_goal_value - goal.value(state)` — lower value = further from goal = higher heuristic cost
- **Expansion:** for each `Action` where `is_applicable(state)` is true, compute successor via `action.apply(state)`, add to priority queue
- **Termination:** first node where `goal.is_satisfied(state)` returns true
- **Depth limit:** 8 actions. If no plan found, return `[]`

The planner is pure — no API calls, no side effects. Planning completes in milliseconds for depth ≤ 8 with ~10 action types.

## Play Loop

```python
class GamePlayer:
    def run(self, character: str) -> None:
        self.state = self._fetch_world_state(character)   # full API query on startup
        self.game_data = GameData.load(self.client)       # cache map, items, recipes

        while True:
            self._wait_for_cooldown()                     # sleep until cooldown_expires
            self.state = self._refresh_if_uncertain()     # re-query on error/staleness

            goal = self._select_goal()
            plan = self.planner.plan(self.state, goal, self.actions, self.game_data)

            if not plan:
                goal = self._select_goal(exclude={goal})
                plan = self.planner.plan(self.state, goal, self.actions, self.game_data)

            if not plan:
                time.sleep(10)
                continue

            action = plan[0]                              # execute one action per cycle
            self._log(action, goal, plan)
            self.state = action.execute(self.state, self.client)
```

State refreshes (`_refresh_if_uncertain`) happen on: startup, after any API error, after 60 seconds without a successful action, and whenever the character visits the bank (to sync bank contents).

## CLI Command

```python
@app.command("play")
def play(
    character: str = typer.Argument(..., help="Character name to play"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full plan each cycle"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only, do not execute actions"),
) -> None:
    """Run the GOAP AI player for a character."""
```

**Output format** (one line per action):
```
[12:04:01] Goal: CompleteTask(87.3)  Plan: Move→Fight→Fight→Fight
[12:04:01] → Move(0,1)  5s
[12:04:07] → Fight(chicken)  XP+15  HP:94→72  drops:feather×2
[12:04:19] Goal: RestoreHP(62.0)  Plan: Rest
[12:04:19] → Rest  HP:72→150
```

`--dry-run` runs the full sense→select→plan loop but calls `action.apply()` instead of `action.execute()`, printing what the AI would do without spending cooldowns. Used for debugging goal selection and plan quality.

## Testing Strategy

- **Unit tests** for each `Action.apply()` — pure functions, no mocking needed
- **Unit tests** for each `Goal.value()` and `Goal.is_satisfied()` — pure functions
- **Unit tests** for `GOAPPlanner.plan()` — constructed `WorldState` inputs, assert plan sequence
- **Integration tests** for `action.execute()` — mock the API client, verify correct endpoint called with correct parameters
- **No end-to-end tests** against the live API in the test suite — the `--dry-run` flag serves that purpose

## Build Order

1. `world_state.py` + `game_data.py` — data model foundation
2. `actions/base.py` + `actions/movement.py` — simplest action first
3. Remaining actions (combat, gathering, rest, bank, crafting, equipment)
4. `goals/base.py` + all goal implementations
5. `planner.py` — A* search
6. `player.py` — main loop
7. `commands/play.py` — CLI wiring
8. Tests throughout, following the order above
