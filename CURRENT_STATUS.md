# Current Status - ArtifactsMMO CLI

## Project Goal

Build a GOAP (Goal-Oriented Action Planning) AI player that plays ArtifactsMMO autonomously. The CLI tooling is for diagnostic and development purposes.

Design spec: `docs/superpowers/specs/2026-05-12-goap-ai-player-design.md`

---

## Infrastructure Status

### API Client
- Generated from live OpenAPI spec via `generate_openapi_client.sh`
- Two patches applied at generation time:
  1. Fight endpoint request body: `allOf+$ref+default` → plain `$ref` (ModelProperty default bug)
  2. `nullable:true` + `$ref` → `anyOf:[{$ref},{type:null}]` (null-safe from_dict generation)
- Custom template `openapi_templates/types.py.jinja` fixes ruff UP007 (`Union[X,Y]` → `X|Y`)

### Test Suite
- **991 passed, 1 skipped, 0 failed**

### CLI Commands (all working)
- `status` — API connectivity check
- `character` — list, create, delete, info, inventory, status, cooldown
- `action` — move, fight, gather, rest, equip, unequip, use, goto, path, batch
- `bank` — list, details, deposit/withdraw gold/items, expand, deposit-all, exchange
- `trade` — ge-buy, ge-sell, ge-orders, ge-cancel, prices, orders, history, analyze, trending, opportunities, spread
- `craft` — craft, recycle, preview, recipes
- `task` — new, complete, exchange, trade, cancel, status, list
- `info` — items, monsters, monster, resources, achievements, leaderboard, events, map, npcs, npc, nearest
- `account` — details, logs
- `play` — autonomous GOAP AI player (`--verbose`, `--dry-run`)

### Known Broken Commands
- `info items` — `CraftSchema.from_dict(None)` on items without crafting recipes (spec says nullable but API returns null; fix: nullable patch in generate script doesn't cover this path yet)
- `info nearest <resource>` — same underlying null issue via map content parsing
- `info map --x --y` — works now after rename fix

---

## GOAP AI Player — Implemented

### Architecture
```
src/artifactsmmo_cli/ai/
├── world_state.py       # Frozen dataclass — single source of truth
├── game_data.py         # Static cache: monster/resource locations, recipes, item stats
├── planner.py           # Forward A* search
├── player.py            # Main loop: sense → select goal → plan → act → update
├── actions/
│   ├── base.py          # Action ABC: is_applicable, apply, cost, execute
│   ├── combat.py        # FightAction(monster_code)
│   ├── gathering.py     # GatherAction(resource_code)
│   ├── rest.py          # RestAction
│   ├── bank.py          # DepositAllAction, WithdrawItemAction(code, qty)
│   ├── crafting.py      # CraftAction(code, qty)
│   ├── equipment.py     # EquipAction(code, slot)
│   ├── consumable.py    # UseConsumableAction
│   └── task.py          # AcceptTaskAction, CompleteTaskAction, TaskExchangeAction
└── goals/
    ├── base.py          # Goal ABC: value(), priority(), is_satisfied(), desired_state()
    ├── survival.py      # RestoreHPGoal, DepositInventoryGoal
    ├── combat.py        # FarmMonsterGoal, CompleteTaskGoal, AcceptTaskGoal
    ├── gathering.py     # GatherMaterialsGoal
    ├── progression.py   # UpgradeEquipmentGoal
    ├── farm_items.py    # FarmItemsGoal (item-type tasks)
    └── task_exchange.py # TaskExchangeGoal (task coin exchange)
```

### Goal Priority Hierarchy (approximate)
| Goal | Priority | Satisfied when |
|------|----------|----------------|
| `RestoreHPGoal` | `(1 - hp/max_hp) * 100` | `hp == max_hp` |
| `DepositInventoryGoal` | `(used/max) * 80` | ≥5 free slots |
| `UpgradeEquipmentGoal` (inventory) | `60` | upgrade equipped |
| `GatherMaterialsGoal` | `50` | all materials gathered |
| `CompleteTaskGoal` | `50 + (progress/total) * 40` | `progress >= total` |
| `TaskExchangeGoal` | `22` | no task coins anywhere |
| `AcceptTaskGoal` | `20` | task active |
| `FarmMonsterGoal` | `30 + (xp/max_xp) * 20` | never (continuous baseline) |
| `UpgradeEquipmentGoal` (craftable) | `35` if materials available | upgrade equipped |
| `FarmItemsGoal` | `28` | item task progress complete |

### Key Behaviors
- **Upgrade detection**: craftable item beats same-level non-craftable (starter) gear via `_is_upgrade_over` helper
- **Crafting progression**: lowest `crafting_level` item targeted first to level relevant skill linearly
- **Bank awareness**: upgrade search checks inventory + bank; withdraws when needed before equipping
- **Inventory priority**: item already in inventory → priority=60 (equip immediately, skip deposit)
- **Task coins**: withdrawn from bank and exchanged at taskmaster
- **Item tasks**: `FarmItemsGoal` activates when `task_type == "items"`
- **Verbose output**: `--verbose` shows goal priorities, selected plan, and applicable actions filtered by current goal

### CLI entry point
```
artifactsmmo play <character> [--verbose] [--dry-run]
```
`--dry-run` plans without executing (uses `action.apply()` instead of `action.execute()`).

---

## Known Remaining Issues / Next Up

- Multi-level crafting chains: `GatherMaterialsGoal` resolves one level of recipe ingredients but does not recursively expand sub-recipes (e.g., gathering `copper_ore` to smelt `copper_bar` to craft `copper_dagger` needs two gather phases). The planner handles it eventually via re-planning, but could be made explicit.
- Fight target selection: currently picks highest-level monster at or below character level with no combat simulation; could use fight simulation API for better targeting.
- No healing item crafting/buying — relies solely on RestAction for HP recovery.
