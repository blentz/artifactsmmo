# Fight log in the TUI — design

Date: 2026-07-27
Status: approved, ready for implementation planning

## Problem

The game API returns a full per-turn combat transcript on every fight, and the
bot throws it away. `FightAction.execute` (`src/artifactsmmo_cli/ai/actions/combat.py`)
reads `result.data.fight.result` to detect a loss and `.turns` to build an error
string, then discards the response. Nothing about a fight beyond win/lose ever
reaches the watcher, so a human watching the TUI cannot see what actually
happened in combat, and cannot compare real damage against what
`ai/combat.py:predict_win` expected.

## What the API provides

`POST /my/{name}/action/fight` returns `CharacterFightDataSchema`:

- `data.fight` — `CharacterFightSchema`, with **required** fields `result`,
  `turns`, `opponent`, `logs: list[str]`, and `characters:
  list[CharacterMultiFightResultSchema]`.
- `data.fight.characters[i]` — per participant: `character_name`, `xp`, `gold`,
  `drops`, `final_hp`.
- `data.cooldown.started_at` — server-side timestamp of the fight.

`logs` is the transcript, one entry per action, server-rendered English:

```
Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350
Turn 1: Robby used fire attack and dealt 12 damage. Mushmush HP: 338/350
Turn 13: Robby used fire attack and dealt 18 damage (Critical strike). Mushmush HP: 188/350
```

`GET /my/logs/{name}` returns `LogSchema` entries; those with `type == "fight"`
carry the **entire** `CharacterFightDataSchema` under `content`, including
`logs` and `content.cooldown.started_at`. Verified live: a 27-turn fight
produced 55 log lines, and the `started_at` value was byte-identical between
the fight response and the corresponding `/my/logs` entry.

`POST /simulation/fight` exists but is a paid feature and is out of scope.

## Constraints discovered

1. **Volume.** A 27-turn fight is ~55 lines. `WatchApp.LOG_BUFFER` is 500 lines
   and the main log pane is one line per cycle. Inlining transcripts would
   evict all decision history every ~9 fights.
2. **`WorldState` is formally modelled.** It appears across
   `formal/Formal/CycleInvariants.lean`, `Phase7Invariants.lean`,
   `GatherApply.lean`, `NpcBuyInventory.lean`, `OwnedCount.lean`. Adding a field
   pulls in differential-oracle and formal-gate work for a field the planner
   would then have to be proven to ignore.
3. **`execute()` has 37 implementations.** Changing its signature to thread a
   recorder through ripples across every action and its tests.
4. **The transcript is prose, not data.** Crit counts and damage totals exist
   only inside the English strings. Deriving them means regex over server
   wording, which conflicts with "Use only API data or fail with an error" and
   "Multiple levels of error handling is always a bug" (a parse-fallback path
   is exactly that second level).
5. **`WatchApp` has no API client.** It is constructed at
   `src/artifactsmmo_cli/commands/play.py:141` with `character` and `game_data`
   only.

## Decisions

| # | Decision | Rejected alternatives |
|---|---|---|
| D1 | Main log pane gets a **one-line structured summary**; the transcript lives only in a modal | Inline all turns (drowns the 500-line buffer); a fifth always-visible pane (reworks the 3x3 grid, shrinks map/inventory) |
| D2 | Modal is **session-first with on-demand API backfill** | Pure-API on every open (network on the hot path, empty when the API is down); session-only (drops restart history) |
| D3 | Modal is **two-pane master/detail** — fight list left, transcript right | Single concatenated scrolling log; list-only with drill-in |
| D4 | Transcript is **opaque prose**, rendered verbatim; the summary uses **only structured schema fields** | Regex-parse every line into columns (breaks on server rewording, no fallback permitted); best-effort parse showing `-` on failure (a silent-failure path) |
| D5 | The fight is captured **on the `FightAction` instance** | On `WorldState` (drags in the Lean surface); re-fetch from `/my/logs` after each fight (+1 request per fight, plus a log-write/read race) |

## Architecture

Data flows in one direction, and the two sources converge on one value object:

```
FightAction.execute ──► FightRecord ──► action.last_fight
                                             │
                    GamePlayer._notify_observer (isinstance gate)
                                             │
                                    CycleSnapshot.fight
                                             │
                          ┌──────────────────┴──────────────────┐
                     LogPane summary line            FightScreen (modal)
                                                              ▲
                              GET /my/logs/{name} ──► FightRecord
                                     (backfill, merged on started_at)
```

### 1. `src/artifactsmmo_cli/ai/fight_record.py` (new)

Two frozen pydantic value objects in one module. This is the CLAUDE.md
one-class-per-file exemption for "tightly-coupled value objects" — neither is
behavioral.

```python
class FightDrop(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    quantity: int

class FightRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    started_at: str                 # server time, from cooldown.started_at
    result: str                     # "win" | "loss"
    turns: int
    opponent: str
    logs: tuple[str, ...]           # verbatim server prose
    hp_before: int | None           # None when backfilled (see below)
    hp_after: int                   # CharacterMultiFightResultSchema.final_hp
    xp: int
    gold: int
    drops: tuple[FightDrop, ...]
```

Two constructors:

- `from_fight_response(data, character, hp_before)` — live path.
- `from_log_entry(entry, character)` — backfill path, `hp_before=None`.

Both select this character's row from `fight.characters` **by matching
`character_name`**, never by index. The schema permits up to 3 participants
(`FightRequestSchema.participants`, `maxItems: 2` additional), so `[0]` is not
reliably this character.

`started_at` is the record's identity and sort key. It comes from the server on
both paths and is identical across them, which makes merging exact — no clock
skew, no content hashing.

**`hp_before` is `int | None` by necessity.** On the live path it is the
player's own pre-fight `state.hp`. The `/my/logs` entry has no structured
starting-HP field — it exists only inside the `Fight start:` prose line, which
D4 forbids parsing. Backfilled rows therefore render `hp ?->275`. This is
representable absence surfaced honestly to the user, not a defaulted value
standing in for missing API data.

### 2. Capture — `ai/actions/combat.py`, `ai/player.py`

`FightAction` gains one field:

```python
last_fight: FightRecord | None = field(default=None, compare=False, repr=False)
```

- `compare=False` keeps `__eq__` over the existing four fields. Without it, a
  fought action would stop comparing equal to its freshly-generated twin and
  the planner would see its cached plan as invalidated after every fight.
- `repr=False` keeps `repr(action)` unchanged; it feeds the file tracer and
  `CycleSnapshot.action`.

`FightAction` is a plain `@dataclass`, already mutable and already unhashable
(`__hash__` is `None`), so nothing else is disturbed. The field is declared last,
after the existing defaulted fields.

In `execute`, ordered so losses are captured:

```python
self.last_fight = None
result = action_fight(client=client, name=state.character, body=FightRequestSchema())
result = Action._raise_for_error(result, f"Fight {self.monster_code}")
self.last_fight = FightRecord.from_fight_response(
    result.data, character=state.character, hp_before=state.hp)
new_state = WorldState.from_character_schema(...)
if result.data.fight.result == FightResult.LOSS:
    raise RuntimeError(...)          # existing behaviour, unchanged
return new_state
```

The record is built **before** the existing LOSS raise. `GamePlayer` catches
that `RuntimeError`, records `outcome="error:fight_lost"`, and still reaches
`_notify_observer` with the same action object — the notify call at
`player.py:1032` passes `action=action` and sits outside the try/except. Losses,
the most interesting transcripts, come through with no extra machinery.

`_notify_observer` gains one line beside the existing grind gate:

```python
fight_record = action.last_fight if isinstance(action, FightAction) else None
```

`CycleSnapshot` gains `fight: FightRecord | None = None`.

### 3. Live summary — `tui/fight_format.py` (new), `tui/widgets/log_pane.py`

Pure functions, no class:

- `fight_summary_line(rec) -> str` — the dim line appended by `build_log_lines`
  when `snap.fight` is set.
- `fight_row_label(rec) -> str` — one row in the modal's list.
- `fight_detail_lines(rec) -> list[str]` — the transcript block.

Summary format, every field structural:

```
   fight: win 27t  hp 485->275  xp 45  gold 12  drops mushmush_hat x1
```

`win` renders green, `loss` red. Loss cycles get the line too — the outcome is
`error:fight_lost` but the record is present. Backfilled records are never shown
here (this path is live-only), so `hp ?->` cannot appear in the main pane.

### 4. Modal — `tui/screens/fight_screen.py` (new), `tui/app.py`

`FightScreen(Screen[None])`, widget id `fight-modal`, bound to `f` (free; current
binds are q/c/l/p/e) and `escape`. `ListView` of fights on the left, `RichLog`
on the right; moving the selection re-renders the detail pane.

Changes in `app.py`:

- add `("f", "toggle_fight", "Fights")` to `BINDINGS` and an
  `action_toggle_fight` following the existing `_open_modal` pattern;
- add `FightScreen` to `_MODAL_SCREENS` (otherwise the single-modal toggle
  cannot close it and a second press collides on `DuplicateIds`);
- add `#fight-modal` to the `layout: vertical` CSS reset alongside the other
  modal ids;
- add `FightScreen` to the isinstance tuple in `update_snapshot` so a fight that
  lands while the modal is open appears immediately.

Transcript lines pass through `rich.markup.escape` before being written.
`RichLog(markup=True)` treats a literal `[` in server text as markup; the
current sample has none, but escaping is required for the general case.
`Critical strike` and `Blocked` are then emphasised by plain substring search,
which silently no-ops if the server rewords — no parse, no failure mode.

### 5. Backfill — `api_wrapper.py`, `commands/play.py`, `tui/app.py`

`ApiWrapper.get_character_logs(name, page, size)` wraps the already-generated
`artifactsmmo_api_client.api.my_characters.get_character_logs_my_logs_name_get`.

`WatchApp.__init__` gains the client, which already exists at
`play.py:138` as `ClientManager().client`.

`WatchApp` owns a **dedicated fight list**, not a filter over
`_recent_snapshots`. That deque is capped at `LOG_BUFFER = 500` *cycles*; a
fight-shaped view of it would silently drop older fights as unrelated cycles
pushed them out. `_store_snapshot` appends `snap.fight` to a separate
`deque(maxlen=200)` of `FightRecord` when it is not `None`, and `FightScreen` is
constructed from that list plus whatever has been backfilled.

Pressing `m` in the modal fetches the next page (size 100), keeps entries with
`type == "fight"`, converts each via `FightRecord.from_log_entry`, merges into
the list deduped on `started_at`, and re-sorts descending. The list shows a
`--- session start ---` separator between session-captured and backfilled
records, and a footer hint for `m`.

The fetch runs under Textual's `@work(thread=True)`. The generated client call
is synchronous and would otherwise block the event loop and freeze the UI for
the duration of the request.

## Error handling

- **No new fallback layers.** The fight response is already validated by
  `Action._raise_for_error`; `FightRecord` construction reads required schema
  fields and raises on a missing character row rather than substituting a
  default.
- **No `except Exception`** anywhere in the new code, per CLAUDE.md.
- A failed backfill request surfaces its error in the modal footer. It does not
  retry and does not silently show an empty list — an empty result and a failed
  request must be visually distinguishable.
- `hp_before=None` on backfilled records is rendered as `?`, never as `0` or as
  the current HP.

## Testing

New files:

- `tests/test_ai/test_fight_record.py` — both constructors; participant
  selection by name with a 3-character fight; `hp_before=None` on the backfill
  path; `started_at` identical across the two constructors given the two shapes
  of the same fight.
- `tests/test_tui/test_fight_format.py` — summary line for win and loss, drops
  rendering, `hp ?->` for a backfilled record.
- `tests/test_tui/test_fight_screen.py` — list/detail rendering, selection
  change, markup escaping of a transcript line containing `[`, merge-and-dedup
  on `started_at`, session separator placement.

Extended:

- existing `FightAction` tests — capture on win; capture on loss recorded
  **before** the raise; `last_fight` cleared at the start of `execute`;
  `FightAction.__eq__` and `repr` unchanged by the new field.
- `tests/test_tui/test_log_pane.py` — summary line appended when `snap.fight`
  is set, absent when it is `None`.
- `tests/test_tui/test_app.py` — `f` toggle, `_MODAL_SCREENS` membership,
  live update reaching an open `FightScreen`.

Fixtures are built from the real payload shape captured from the live API, not
hand-invented.

Success criteria per CLAUDE.md: 0 errors, 0 warnings, 0 skipped, 100% coverage.

## Out of scope

- `POST /simulation/fight` — paid feature.
- Deriving crit counts, damage totals, or per-element breakdowns (D4).
- Feeding fight outcomes back into `ai/combat.py:predict_win` calibration. The
  transcript makes that comparison possible for a human reading the modal; doing
  it automatically is separate work.

## Formal-gate impact

None. No planner state, action cost, applicability, or goal ranking changes.
`WorldState` is deliberately untouched — that is the entire reason the capture
seam sits on the action instance. No new mutation anchors: this is display code,
not decision logic.
