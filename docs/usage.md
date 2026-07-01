# Usage

## Standard CLI

```sh
uv run artifactsmmo character status <name>
uv run artifactsmmo character create <name> <skin>
uv run artifactsmmo move <name> <x> <y>
uv run artifactsmmo fight <name>
uv run artifactsmmo gather <name>
# ...etc — see `uv run artifactsmmo --help`
```

## Autonomous player

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

See [tui.md](tui.md) for the live watcher and [ai-player.md](ai-player.md)
for how the player decides.

## Session stats

The `stats` subcommand reads from the same SQLite store `play --learn` writes
to (`~/.cache/artifactsmmo/learning.db`) and renders every metric that
matters for debugging a session — no inline scripts.

```sh
# List recent sessions
uv run artifactsmmo stats sessions

# Summarise the most recent session for a character
uv run artifactsmmo stats summary --character Robby

# Whole DB, with a time window
uv run artifactsmmo stats summary --session all --since 2026-06-05T00:00

# Focused views
uv run artifactsmmo stats summary --planner-only --top 20
uv run artifactsmmo stats summary --goals-only --top 30
```

Sections rendered: overview (cycles, duration, goal-change rate), outcomes +
per-action errors, top selected goals, top actions, planner load per goal
(max/avg nodes + plan_len + timeouts), fight attempts + losses with HP
context, inventory events (crafts/equips/deletes/deposits/withdraws) +
per-item breakdowns, task completions with duration + s/unit, stuck windows
(8+ cycles with no progress).
