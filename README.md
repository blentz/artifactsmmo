# ArtifactsMMO CLI + Autonomous AI Player

A Python CLI for [ArtifactsMMO](https://artifactsmmo.com) with two modes: the
standard CLI commands (move, gather, fight, bank, …) and an autonomous
GOAP-based AI player that plays a character end-to-end while learning from
observation.

![Live TUI: the autonomous player grinding combat XP, with status, inventory, sprite map, and decision log](docs/demo.gif)

## Install

```sh
uv sync
echo "<your API token>" > TOKEN
```

Python 3.13, dependencies via [`uv`](https://docs.astral.sh/uv/) (lockfile
committed).

## Quickstart

```sh
# Run a single CLI command
uv run artifactsmmo fight <name>

# Turn the AI player loose, and watch it live
uv run artifactsmmo play <name> --learn --tui
```

Full command reference and session-stats tooling: [docs/usage.md](docs/usage.md).

## What the AI player does

It runs a sense → plan → act loop with a single goal: reach max character
level (50) by the cheapest path. Everything else is a means to that end.

| Feature | What it does |
| --- | --- |
| **Plays end-to-end** | Gathers, crafts, fights, runs tasks, and banks on its own to level a character to 50. |
| **Plans the fastest route** | Estimates how far each path to max level is and follows the shortest one. |
| **Fights smart** | Picks the best weapon and armor for each monster's elemental weakness before engaging. |
| **Stays alive** | Heals before it can die, and when it gets stuck it escalates recovery until it breaks free. |
| **Manages its bag** | Sells or discards surplus while protecting materials, tools, and task items — and crafts overflow into progress instead of dumping it. |
| **Levels skills just in time** | Trains crafting skills only when needed to unlock the next upgrade. |
| **Reuses the bank** | Withdraws stored materials instead of re-gathering them. |
| **Remembers what blocks it** | Learns progression gates across runs so it doesn't retry the impossible. |
| **Learns as it plays** | Records observed costs and outcomes to a store that sharpens later decisions. |
| **Shows its work** | A four-pane live terminal UI renders status, map, inventory, and every decision. |
| **Provably correct core** | Its decision logic is proven in Lean 4 and gated so the code can't drift from the proofs. |

How each decision is made: [docs/ai-player.md](docs/ai-player.md). The live
watcher: [docs/tui.md](docs/tui.md).

## Documentation

- [docs/usage.md](docs/usage.md) — CLI reference + session stats
- [docs/ai-player.md](docs/ai-player.md) — how the player decides
- [docs/tui.md](docs/tui.md) — live TUI watcher and sprite map
- [docs/development.md](docs/development.md) — dev setup, testing, formal verification, design specs

## Project status

Active development. Single-character autonomous play works end-to-end:
gather → craft → fight → task → bank, with per-monster equipment
optimization, overstock control, blocker memory, and live TUI observation.
Multi-character coordination is not in scope yet.

## License

GNU Affero General Public License v3 (AGPL-3.0) — see [LICENSE](LICENSE). The
AGPL ensures any modifications to this AI, including those used to provide
network services, remain open-source and available to the community.
