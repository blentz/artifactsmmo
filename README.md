# ArtifactsMMO CLI + Autonomous AI Player

A Python CLI for [ArtifactsMMO](https://artifactsmmo.com) with two modes:
the standard CLI commands (move, gather, fight, bank, etc.) and an
autonomous GOAP-based AI player that plays a character end-to-end while
learning from observation.

## Install

```sh
uv sync
echo "<your API token>" > TOKEN
```

Python 3.13. Dependencies via `uv` (lockfile committed).

## Usage

### Standard CLI

```sh
uv run artifactsmmo character status <name>
uv run artifactsmmo character create <name> <skin>
uv run artifactsmmo move <name> <x> <y>
uv run artifactsmmo fight <name>
uv run artifactsmmo gather <name>
# ...etc — see `uv run artifactsmmo --help`
```

### Autonomous player

```sh
# Plain headless run
uv run artifactsmmo play <name>

# With learning store (persisted to ~/.cache/artifactsmmo/learning.db)
uv run artifactsmmo play <name> --learn

# Live TUI watcher (four-pane: status / map / inventory / log)
uv run artifactsmmo play <name> --learn --tui

# Trace decisions to JSONL for offline analysis
uv run artifactsmmo play <name> --learn --trace

# Plan-only (no API mutations)
uv run artifactsmmo play <name> --dry-run --verbose
```

## What the AI player does

The player runs a sense → plan → act loop using **GOAP** (Goal-Oriented
Action Planning) with forward A* search.

**Single root objective:** find the cheapest path to maximum character
level (50). Every decision is scored against expected character-XP per
cycle. Tasks/gold/skill-XP are means to that end, not first-class goals.

### Strategic decisions the player makes

- **Path projection** (`cheapest_path_to_level`): walks the monster
  ladder using documented per-kill XP and observed cycle costs to
  estimate cycles-remaining to L50. Trace shows
  `projected_cycles_to_max` and `path_next_action` every cycle.
- **Low-yield task cancel**: if a held task pays zero char-XP/cycle
  (e.g. items-tasks that only payout on CompleteTask), and any
  alternative pays positive, fire `TaskCancel` immediately.
- **Blocker registry**: persistent learning of progression gates
  (e.g. bank achievement requires defeating sea_marauder L45). Loaded
  on every session start; survives restarts.
- **Equipment optimizer**: per-fight loadout selection by element
  matching. Robby holding `fishing_net` will swap to `copper_dagger`
  vs `yellow_slime` (water-vs-earth resistance flip) automatically.
- **Overstock cap**: items held beyond their max recipe demand (plus
  task / equip / action-consumable floors) get sold or deleted in
  single batched actions.
- **HP critical floor**: `RestoreHP` priority jumps to 110 below 25%
  HP to preempt any combat goal.
- **Skill-up driver**: `LevelSkillGoal` interrupts gathering to craft
  for skill XP when a near-future upgrade is gated.
- **Survival recovery**: stuck-state detector with escalating recovery
  (state refresh → goal suppression → wildcard mode).

### TUI watcher

The four-pane Textual interface shows live state without changing the
bot's behavior:

```
┌────────────────┬─────────────────────────┐
│ Status         │ Map (NetHack-inspired)  │
│  L3 HP:[█▓ ]   │  ......T...M..          │
│  XP:[██ ]      │  ......@....            │
│  Gold: 335     │  ......$..>             │
│  Path → L50    │                         │
│  next: chicken │                         │
├────────────────┼─────────────────────────┤
│ Inventory      │ Log                     │
│  50 copper_ore │ 21:06 c1 RestoreHP   ok │
│  23 ash_wood   │ 21:08 c2 Fight       ok │
│  ...           │ ...                     │
└────────────────┴─────────────────────────┘
```

Map glyphs: `@` you, `M` monster, `T` tree, `*` ore, `~` fish, `%`
plant, `$` bank, `?` taskmaster, `!` NPC, `>` transition. Quit with
`q` or `Ctrl+C`.

## Design docs

Architecture, design rationale, and implementation plans live under
`docs/superpowers/`:

- `specs/2026-05-12-goap-ai-player-design.md` — initial GOAP design
- `specs/2026-05-15-goap-robustness-layer-design.md` — survival layer
- `specs/2026-05-17-autoregressive-planning-design.md` — learning store
- `specs/2026-05-18-strategic-reasoning-design.md` — Phase G (per-cycle scoring)
- `specs/2026-05-18-max-level-objective-design.md` — root objective
- `plans/...` — task-by-task implementation plans for each spec

## Project status

Active development. Single-character autonomous play works end-to-end:
gather → craft → fight → task → bank, with per-monster equipment
optimization, overstock control, blocker memory, and live TUI
observation. Multi-character coordination not in scope yet.

## License

GNU Affero General Public License v3 (AGPL-3.0) — see [LICENSE](LICENSE).

The AGPL ensures any modifications to this AI, including those used to
provide network services, remain open-source and available to the
community.
