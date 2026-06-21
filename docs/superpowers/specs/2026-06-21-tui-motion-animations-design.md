# TUI Motion Animations — Design

Date: 2026-06-21
Status: approved (brainstorm), pending implementation plan

## Goal

Four quality-of-life animations in the map TUI that make the bot's per-cycle
activity legible at a glance:

1. **Movement scaled to cooldown** — the player glides to its destination over
   the move's cooldown, arriving just before the next action.
2. **Gather swing** — a pickaxe/axe arcs a half-circle **clockwise** (12→3→6
   o'clock) during a gather cooldown.
3. **Combat swing** — a sword arcs the same half-circle **counterclockwise**
   (12→9→6 o'clock) during a fight cooldown.
4. **Planning thought-bubble** — a thought bubble at the **2 o'clock** position
   from the player sprite's head while the planner is deciding (planner latency
   is sometimes seconds-long; this gives a visible "thinking" cue).

## Background / current architecture

(From an exploration pass over `src/artifactsmmo_cli/tui/`.)

- The map is **player-centered**: the player sprite is always drawn at grid
  center (`map_pane.py` `is_player = tcol == half_w and trow == half_h`).
  "Movement" slides the *viewport center* tile-by-tile, not a sprite within the
  grid.
- **Render pipeline:** bot worker thread → `ThreadSafeBridge.notify`
  (`observer.py`) → `App.update_snapshot` (`app.py`) → `MapPane.update_snapshot`
  → (animation timer) `_tick` → `render()` → `_render_viewport` → per-tile
  `HalfBlockCompositor.compose` → Rich `Text`.
- **Coordinates:** world tiles `(wx,wy)` → grid cells (`TILE_W=8` chars ×
  `TILE_H=4` rows) → sub-pixels (each char-row packs 2 vertical pixels via the
  upper-half-block `▀`, fg=top, bg=bottom). A sprite is an 8×8 grid of glyph
  keys (`'.'` = transparent) plus a palette (`sprites.py` `Sprite`).
- **Timer:** there is NO global frame timer. `MapPane` creates an on-demand
  `set_interval(ANIM_FRAME_SECONDS=0.05, _tick)` only while a glide is playing
  (`MAX_ANIM_STEPS=12`), and tears it down when the glide index maxes out. It is
  **frame-count based**, not wall-clock based.
- **Movement frames:** `path_interpolate.py::glide_path(start, end, max_steps)`
  is pure — a subsampled Bresenham line of viewport-center tiles, no timing.
- **Action/cooldown data:** the only channel is the frozen `CycleSnapshot`
  (`ai/cycle_snapshot.py`), built at end-of-cycle in `player.py`. It carries
  `action: str` (a `repr()` like `Gather(copper_rocks)` / `Fight(chicken)` /
  `Move(x,y)` / `Rest`) and `cooldown_remaining: float` (seconds at snapshot
  time). There is **no** cooldown-expiry timestamp and **no** "planning"
  event — the snapshot only exists AFTER the cycle has decided and acted.
- **Animation state:** only movement; lives on the `MapPane` widget
  (`_anim_frames`, `_anim_index`, `_anim_timer`). No per-action state machine.
- **Compositor cache:** `HalfBlockCompositor.compose` is memoized by
  `(rows, palette, terrain_color)` — fine for distinct per-frame sprites (each
  is its own key); must NOT mutate a `Sprite` in place.

## Key design decisions (resolved in brainstorm)

- **Modes are mutually exclusive in time.** Planning is *between* actions;
  gliding = Move cooldown; swinging = Gather/Fight cooldown; resting/idle = Rest
  or no cooldown. So the player is in exactly ONE animation mode at any instant
  → one frame-selected player sprite per mode. **No multi-layer compositing is
  required** (the existing single-layer sprite-over-terrain compositor suffices).
- **Swings loop at a natural cadence** (~0.8 s per sweep), repeating until the
  cooldown ends — looks like real repeated chopping/striking, decoupled from the
  (long, 5–25 s) cooldown length.
- **Swings render inside the player's own 8×8 cell** as frame-selected sprites
  (tool glyph at successive clock positions). No neighbor-cell overwrite.
- **Add structured snapshot fields** rather than string-parsing `repr(action)`.
- **Add an explicit planning signal** rather than inferring from snapshot
  latency (inference also fires during cooldown waits, not just planning).

## Architecture

Three additive layers.

### 1. Data: `CycleSnapshot` + planning signal

- Add to `CycleSnapshot` (`ai/cycle_snapshot.py`):
  - `action_kind: str` — one of `"move" | "gather" | "fight" | "rest" | "other"`.
  - `action_target: str | None` — e.g. `"copper_rocks"`, `"chicken"`, or `None`.
  - `cooldown_expires: datetime | None` — absolute expiry (the renderer's time
    base). Populated from `WorldState.cooldown_expires` (already a `datetime`)
    at snapshot-build time in `player.py`; falls back to
    `now + cooldown_remaining` when only the float is known.
- Derive `action_kind`/`action_target` at the single snapshot-build site in
  `player.py` from the chosen `Action` object (its class), NOT from `repr()`.
  A tiny pure mapper `action_kind_of(action) -> (kind, target)` lives next to the
  snapshot (or in a small `ai/action_kind.py`) so it is unit-testable and has one
  source of truth.
- **Planning signal:** extend the observer/bridge (`tui/observer.py`) with
  `notify_planning(active: bool)`. `player.py` calls `notify_planning(True)`
  immediately before the decide/plan step and `notify_planning(False)` right
  after the snapshot is emitted (or the bridge clears it when a snapshot
  arrives). `WatchApp`/`MapPane` store `_planning_active: bool`. When the TUI is
  absent (headless) the calls are no-ops (observer already tolerates no
  subscriber).

### 2. Timer: persistent animation loop on `MapPane`

- Replace the on-demand glide timer with ONE persistent
  `set_interval(ANIM_FRAME_SECONDS, _tick)` started in `on_mount`.
- `_tick` calls `refresh()` only when an animation is active (gliding, swinging,
  or planning) — cheap idle guard so a resting/idle bot doesn't repaint
  needlessly. (Self-stop/restart optional; simplest is keep-running + idle guard.
  Decide in the plan; either is fine.)
- Time base is wall-clock (`time.monotonic()`), captured per snapshot as
  `_anim_start` plus the snapshot's `cooldown_expires`.

### 3. Frame selection: pure mode/clock logic + sprite art

- New pure module `tui/swing_frames.py`:
  - `current_mode(action_kind, planning_active, now, cooldown_expires) -> Mode`
    where `Mode ∈ {idle, glide, gather_swing, fight_swing, planning}`.
  - `swing_frame_index(elapsed_seconds, frame_count, sweep_seconds) -> int` —
    looping sweep position (`floor((elapsed % sweep) / sweep * frame_count)`).
  - `glide_progress(now, start, expires, arrive_fraction=0.9) -> float` in
    `[0,1]` — drives the existing `_anim_index` over the cooldown so the glide
    completes at `arrive_fraction` of the window.
  - All pure functions of numbers → directly unit-testable.
- `MapPane._tile_sprite_and_terrain` (player branch) consults `current_mode` and
  returns the matching sprite:
  - **idle/rest:** `PLAYER_SPRITE` (unchanged).
  - **glide:** `PLAYER_SPRITE` (the motion is the viewport slide; index driven by
    `glide_progress` instead of the fixed per-frame count).
  - **gather_swing:** `GATHER_SWING_FRAMES[swing_frame_index(...)]`.
  - **fight_swing:** `FIGHT_SWING_FRAMES[swing_frame_index(...)]`.
  - **planning:** `PLANNING_SPRITE`.
- New art in `sprites.py` (all 8×8, single-frame each):
  - `GATHER_SWING_FRAMES`: 5–7 poses, base player + a pickaxe/axe tool pixel
    cluster placed at successive **clockwise** clock positions (12 → 1:30 → 3 →
    4:30 → 6) on the player's right side.
  - `FIGHT_SWING_FRAMES`: same poses mirrored — sword on the **counterclockwise**
    arc (12 → 10:30 → 9 → 7:30 → 6) on the player's left side.
  - `PLANNING_SPRITE`: base player + a small thought-bubble pixel cluster at the
    **2 o'clock** offset from the head (upper-right). (Optional 2-frame bob can be
    added later; v1 may be static.)
  - Clock-position → 8×8 (col,row) offset is a small table/helper (shared by
    gather + fight, mirrored on X).

## Data flow (per cycle)

```
player.py:
  notify_planning(True)            # bubble appears
  decision = strategy.decide(...)  # the slow part
  ... select goal, plan ...
  action = execute(...)
  snapshot = CycleSnapshot(action_kind=..., action_target=..., cooldown_expires=...)
  observer.notify(snapshot)        # bridge clears planning → bubble off
  # (notify_planning(False) implicit on snapshot, or explicit)

MapPane (persistent ~50ms tick):
  mode = current_mode(snap.action_kind, _planning_active, now, snap.cooldown_expires)
  glide:   index = round(glide_progress(now, start, expires) * (len(frames)-1))
  swing:   frame = SWING_FRAMES[swing_frame_index(now - start, n, 0.8)]
  planning: PLANNING_SPRITE
  render → compose
```

## Components & isolation

| Unit | Responsibility | Depends on |
|---|---|---|
| `ai/action_kind.py` (or snapshot-local) | `Action` → `(kind, target)` | Action classes |
| `CycleSnapshot` (+3 fields) | carry action_kind/target/expiry | — |
| `tui/observer.py` (+`notify_planning`) | planning on/off channel | — |
| `tui/swing_frames.py` (new, pure) | mode + frame-index + glide-progress math | — |
| `sprites.py` (+frame sequences) | swing/planning art (8×8) | existing Sprite |
| `MapPane` | persistent timer; consult mode; pick frame | the above |

Each pure unit answers: what (mode/frame math, or art data), how (call with
numbers/get a Sprite), depends-on (nothing but stdlib / Sprite). `MapPane` stays
the only stateful integrator.

## Error handling / edge cases

- `cooldown_expires is None` (unknown) → fall back to `cooldown_remaining`; if
  both unknown, treat as idle (no glide/swing timing, just show base sprite).
- Cooldown already expired when snapshot arrives (`now >= expires`) → swing/glide
  clamps to final frame / idle (no negative progress).
- Planning signal stuck on (e.g. exception before snapshot) → bubble clears on
  the next snapshot regardless; planning is also auto-cleared on snapshot arrival
  so it cannot wedge.
- Headless / no TUI subscriber → all notify calls are no-ops (existing observer
  behavior).
- Move with zero/last-frame glide (start == end) → no glide, base sprite.
- Compositor cache: every swing/planning frame is a distinct immutable `Sprite`,
  so memoization stays correct; never mutate a Sprite in place.

## Testing

- **`swing_frames.py` (pure):** `current_mode` truth table over
  (action_kind × planning × now-vs-expiry); `swing_frame_index` looping/clamping;
  `glide_progress` monotonic 0→1 and reaches 1 at `arrive_fraction`.
- **`action_kind_of`:** each Action class maps to the right `(kind, target)`.
- **sprites:** each frame is 8×8, valid palette keys, transparent background;
  gather frames mirror fight frames on X.
- **observer:** `notify_planning` toggles subscriber state; snapshot clears it.
- **MapPane (light):** given a snapshot + clock, the player branch returns the
  expected sprite for each mode (using a fake clock).
- Coverage held at the project's gate (100%); any genuinely-untestable Textual
  glue (timer wiring) carved out with written justification per existing policy.

## Out of scope (YAGNI)

- Multi-layer overlay compositing (modes are exclusive → not needed).
- Easing curves beyond linear glide progress.
- Animations for other actions (deposit/craft/equip/withdraw) — they are
  workshop/bank interactions with no natural map gesture; treat as idle.
- Per-frame palette animation / color cycling.
- Bubble bob (optional polish; v1 static bubble).

## Open questions

None blocking. The persistent-timer self-stop-vs-idle-guard choice is left to the
implementation plan (both are acceptable; idle-guard is simplest).
