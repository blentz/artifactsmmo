# PLAN: Multi-Character Support

**Status:** DESIGN APPROVED — not yet implemented
**Date:** 2026-07-30

Run up to 5 characters at once, each an independent instance of the current AI
driving itself to level 50, all visible in one TUI.

## Goal

The account supports 5 characters. Today the bot plays exactly one. This work
runs all of them concurrently — each in its own subprocess, each running the
existing unmodified AI — and presents them in a single TUI where the map shows
every character at once and keys `1`–`5` choose which character the other panes
follow.

Collaboration between characters is explicitly **not** part of this work. Each
character pursues level 50 on its own, blind to the others. Collusive and
cooperative behaviours are future work that this architecture must not preclude.

## Non-goals

- No coordination of any kind: no bank leases, no shared planning, no division
  of labour, no cross-character messaging.
- No change to any planner, goal, action, or proven decision function.
- No change to the single-character `play <character>` path.

## Constraints discovered during design

These are measured facts, not estimates. They shape the design and any
implementation must respect them.

### Rate limits are per-IP, and the data bucket is the binding one

From <https://docs.artifactsmmo.com/api_guide/rate_limits/>:

| bucket | /second | /minute | /hour | /day |
|---|---|---|---|---|
| account | 10 | — | 300 | — |
| data | 10 | 200 | 2 000 | — |
| action | 10 | 100 | 5 000 | — |
| simulation | 1 | — | — | — |
| assistant | — | — | — | 25 |

Standard limits apply **per IP address**, so all five subprocesses draw from one
shared budget. Exceeding a limit returns HTTP 429; the documentation does not
promise a `Retry-After` header.

Measured from `play-trace-Robby.jsonl` — a real 7-day single-character run of
11 224 cycles:

- 1.09 cycles/min average
- 158 cycles in the busiest hour
- 11 cycles in the busiest minute

Each cycle costs **three** data-bucket reads: `get_character`,
`_fetch_active_events`, and `_fetch_raids` (all inside
`GamePlayer._fetch_world_state`). Five characters at peak is therefore
`5 × 158 × 3 ≈ 2 370` data requests/hour against a 2 000/hour ceiling — a
breach. The average hour (~980/hr) is comfortable, and the action bucket is
never close (790/hr peak against 5 000).

The overage is entirely redundant work: `active_events` and `raids` are
**global** — identical for every character — yet would be fetched five times
per cycle. Caching them removes the breach (see `GlobalReadsCache` below).

### The shared bank is a real race, and it is already survivable

Bank items and bank gold are account-scoped; character gold is per-character.
Five independent planners will race each other for banked materials.

This is accepted for v1. It is survivable because `GamePlayer._execute` already
catches `ApiActionError` (`ai/player.py:1176`) and downgrades a failed action to
an `error:*` cycle that re-plans, and a failed bank action additionally forces a
`_sync_bank` re-read. A lost race is therefore a replan, not a crash. Whether
the resulting thrash is acceptable in practice is a question for the traces
after this ships — it is the motivating data for future coordination work.

### The bot writes to stdout

`GamePlayer` prints human-readable progress to stdout throughout. Any protocol
that also uses stdout must move those prints out of the way first.

## Architecture

### Process model

`play --all` turns the main process into a supervisor. It holds no `GamePlayer`.

```
artifactsmmo play --all --tui
  ├─ asyncio.create_subprocess_exec("artifactsmmo","play","Robby","--emit-events")
  │    stdout ── {"kind":"snapshot","character":"Robby","payload":{...}}
  │    stderr ── human log + tracebacks
  ├─ … one child per remaining character
  └─ Textual WatchApp on the main thread
```

The supervisor:

1. Reads the roster from `APIWrapper.get_my_characters()` (`/my/characters`,
   already wired at `api_wrapper.py:90`).
2. Reads `/my/rates` once and divides each window across the children.
3. Spawns one child per character, each running the existing `play` command.
4. Reads each child's stdout as newline-delimited JSON, feeding the TUI.
5. Applies the restart policy when a child exits.

#### CLI surface

`--all` is a flag on the existing `play` command; the `character` positional
becomes optional.

- `play --all --tui` — supervise all account characters with the TUI.
- `play --all` — supervise headless, streaming each child's stderr prefixed
  with the character name.
- `play --all <character>` — error. The two are mutually exclusive.
- `play --all --trace-file X` — error. Per-character traces keep the existing
  `play-trace-{character}-{timestamp}.jsonl` default, which is already unique
  per child.
- `play <character> [--tui]` — **unchanged**. In-process worker thread, no
  subprocess. This remains the debuggable unit and the target of existing tests.

#### `--emit-events`

A new flag on `play`. When set, the child:

- wraps `player.run()` in `contextlib.redirect_stdout(sys.stderr)`, so the
  bot's own prints and any traceback go to stderr and **stdout carries only the
  event stream**;
- installs an emitter as the cycle observer and planning observer that writes
  one JSON line per event to stdout, flushing each line.

Without the redirect the bot's chatty stdout would interleave with and corrupt
the protocol. With it, stderr becomes the human log the DEAD panel quotes.

### Event protocol

`ChildEvent` is a pydantic discriminated union on `kind`. One JSON object per
line on the child's stdout.

| kind | payload |
|---|---|
| `snapshot` | the full `CycleSnapshot` |
| `planning` | `active: bool` — drives the existing `set_planning` overlay |
| `exit` | `reason: str` — see below |

The exit `reason` is the `exit_reason` `play()` already computes for the
learning store (`normal`, `server_unavailable`, `stuck_exit`,
`keyboard_interrupt`, `crash`), with one refinement: when the uncaught
exception is an `httpx` transport error the child emits `crash:network`
instead of bare `crash`. Only the child can make that distinction — it holds
the exception — and the restart policy needs it. What the learning store
records is unaffected.

`CycleSnapshot` is already a pydantic `BaseModel`, so the wire format is
`model_dump_json()` on the child and `model_validate_json()` on the parent with
no hand-written serializer to drift.

Parse failures are not silent. An incomplete trailing line at EOF is normal
(the child died mid-write) and is discarded. A **complete** line that fails to
parse is surfaced as a visible error on that character's pane — it means the
protocol has drifted and must be fixed, not tolerated.

### Rate limiting

Two cooperating pieces:

**`RateBudget`** — pure. Takes the `/my/rates` response and a child count,
returns each child's share of every bucket/window. The parent reads the live
limits rather than hardcoding the table above, per the project's
"use only API data or fail with an error" rule.

**`RateGovernor`** — a multi-window token bucket (second, minute, hour) per
bucket type, enforced inside each child. A plain token bucket is inherently
cooldown-aware: while the character sits on cooldown the bucket refills, so a
cooldown-bound bot never sees latency added by the governor. It blocks only
when a genuine burst has drained a window.

Plus honest 429 handling in the API layer: honor `Retry-After` when the server
sends one, exponential backoff when it does not. There is no 429 path today —
`utils/helpers.py:21` only maps the code to a message string.

### `GlobalReadsCache`

A 60-second TTL over `_fetch_active_events` and `_fetch_raids`. Events and raids
change on a minutes-to-hours timescale, so a 60s TTL loses nothing semantically.

This takes a cycle from three data reads to one, which is what brings five
characters back under the hourly ceiling. It applies to the single-character
path too, which gets the same reduction for free.

### TUI

`WatchApp` takes `characters: list[str]` instead of `character: str`.

- **`MultiSnapshotStore`** — per-character `last_snapshot`, `recent_snapshots`
  deque, and `fights` deque, replacing `WatchApp`'s three single-character
  fields. Buffer caps stay per-character, so a busy character cannot evict
  another's history.
- **Focus** — a `focused` character plus bindings `1`–`5` calling
  `action_focus(n)`. The status pane, inventory pane, log pane, and all four
  modals read the focused character.
- **`MapPane.update_snapshots(snapshots, focused)`** — centers on the focused
  character and draws every character whose tile falls in the viewport. Same
  silhouette for all, distinguished by colour:
  `recolor(PLAYER_SPRITE, {..., "b": <colour>})` repaints the tunic key. Five
  colours already exist in `tui/palette.py`: `TUNIC`, `BLOOD`, `LEAF`, `BREW`,
  `AMBER`, assigned by roster index.
- **Tile collision** — when two characters occupy one tile, the focused
  character draws on top; otherwise the lowest roster index wins. Roster order
  comes from the account, never from sorting names or reprs.
- **Animation stays focused-only.** Swing frames and glide interpolation are
  keyed to a single action timeline. Non-focused characters render as static
  sprites at their last known tile.
- **Roster line** in `StatusPane`:
  `[1]●Robby L19 (0,2)  [2]●Alice L7 (5,-1)  [3]✗Bob` — colour chip, level,
  coordinates, alive/dead marker, and restart count when non-zero. This is how
  characters currently outside the viewport stay visible; there are no
  off-screen edge arrows.

### Lifecycle

`RestartPolicy` is a pure function from exit reason to decision:

| exit_reason | decision | why |
|---|---|---|
| `server_unavailable` | restart with backoff | transient; the server came back |
| `crash:network` | restart with backoff | transient transport failure |
| `stuck_exit` | stay dead | the AI needs intervention; a restart re-sticks |
| `crash` | stay dead | a restart loop masks a real bug behind apparent health |
| `keyboard_interrupt` | stay dead | the operator stopped it deliberately |
| `normal` | stay dead | the character finished |

Backoff doubles from 5s to a 5-minute ceiling, and a character that has been
restarted 5 times stays dead until restarted by hand — an endlessly flapping
child is a bug report, not a working system. A dead slot shows the child's last
stderr line and offers a restart key, which resets the counter. The restart
count is visible in the roster so a flapping child cannot look healthy.

## New modules

One behavioral class per file, per `AGENTS.md`.

| file | contents |
|---|---|
| `multi/character_supervisor.py` | one child: spawn, read stdout/stderr, reap |
| `multi/supervisor_pool.py` | owns N supervisors, applies the restart policy |
| `multi/restart_policy.py` | pure exit-reason → decision |
| `multi/child_event.py` | the `ChildEvent` union (schema module, exempt from one-class-per-file) |
| `utils/rate_governor.py` | multi-window token bucket |
| `utils/rate_budget.py` | pure split of `/my/rates` across children |
| `ai/global_reads_cache.py` | TTL over events/raids |
| `tui/multi_snapshot_store.py` | per-character buffers |
| `tui/character_roster.py` | pure colour and order assignment |

## Testing

Per the project's success criteria: 0 errors, 0 warnings, 0 skipped, 100%
coverage, everything under `tests/`.

- **Pure units** — budget split arithmetic, governor window boundaries and
  refill, restart classification for every exit reason, roster colour
  assignment, snapshot-store eviction.
- **Protocol** — `CycleSnapshot` round-trip through JSONL; an incomplete
  trailing line is discarded; a complete-but-unparseable line raises a visible
  error rather than being skipped.
- **Supervisor** — driven against a **real** subprocess (`python -c` emitting
  canned lines and exiting with a chosen reason), not a mocked one. The unit
  under test is never mocked.
- **TUI** — focus switching, multi-character map rendering, tile-collision
  ordering, and the roster line, following the existing Textual test patterns.
- **Rate limits** — a regression guard for the constraint that motivated
  `GlobalReadsCache`. The measured peak of 158 cycles/hour/character is a named
  constant; the test multiplies it by the per-cycle data-read count with the
  cache active, times five characters, and asserts the result stays under the
  hourly `data` ceiling parsed from a `/my/rates` fixture. If a future change
  adds a per-cycle data read, this test fails and says why.

## Formal surface

Untouched. No new `MeansKind` or `GuardKind`, no change to any proven decision
function, no new liveness obligation. This work is process supervision and
presentation infrastructure sitting outside the modelled game logic, and the
Lean gate should stay green without new proof obligations.

## Open items for implementation

- Five children running with `--learn` share one SQLite file. Rows are already
  keyed by character, but the store needs WAL mode and a `busy_timeout` to
  survive concurrent writers. Verify and fix in `ai/learning/store.py`.
- Confirm how a 429 currently surfaces through the generated client — as an
  `ApiActionError`, an `httpx` error, or a non-standard status — before writing
  the backoff path, so the handling attaches at the right layer.
