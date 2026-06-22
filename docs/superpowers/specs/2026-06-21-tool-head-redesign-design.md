# Tool-Head Redesign + Craft Hammer — Design

Date: 2026-06-21
Status: approved (brainstorm), pending implementation plan
Extends: `2026-06-21-multitile-swing-design.md` (the merged two-tile swing system)

## Goal

The two-tile swing works but the gather tool reads as a comical copper diamond.
Replace the single `GATHER_HEAD` with proper tool heads, select the head by what
the bot is doing, and add a **craft hammer** so smelting bars animates too:

- **Gather** → **axe** (woodcutting) or **pickaxe** (mining), chosen by the
  gathered resource's skill; fishing/alchemy/unknown fall back to the pickaxe.
- **Combat** → **sword** (redesigned).
- **Craft of a bar** (`*_bar`) → **hammer**; other crafts → no swing (idle).

## Background (current merged state)

- `swing_overlay(mode, frame_index)` (`swing_frames.py`) returns
  `{(0,0): grip, offset: head}`; it hardcodes `GATHER_HEAD` for gather and
  `FIGHT_HEAD` for fight. `MapPane._swing_overlay(now)` computes mode + frame
  index and calls it; `_render_viewport` merges the head onto the arc-neighbor
  tile via `overlay_sprites`.
- `current_mode(action_kind, planning, elapsed, duration)` returns one of
  `IDLE/GLIDE/GATHER_SWING/FIGHT_SWING/PLANNING`. `action_kind` comes from
  `action_kind_of(action)` (`ai/action_kind.py`): Move/Gather/Fight/Rest → those
  kinds, else `"other"`. **Craft is "other" → idle.**
- The snapshot carries `action_target` (gather resource code / fight monster /
  "x,y"); for craft today it is `None` (CraftAction wasn't mapped).
- `game_data` is held by `MapPane`. Resource→skill is available
  (`game_data.resource_skills` / the same lookup `_SKILL_TO_RESOURCE_KEY` uses);
  item recipes via `game_data.crafting_recipe(code)`.
- Grey palette: `STEEL = "#888a85"` (medium grey), `STONE = "#babdb6"` (light
  grey); `BARK` = handle. Sprites are 8×8, `validate_sprite`-checked.

## Art (8×8 head sprites; `m`=STEEL medium-grey, `l`=STONE light-grey, `h`=BARK)

1px haft at col 3, head at top, reused at all arc offsets (no rotation).

```
AXE_HEAD                PICKAXE_HEAD            HAMMER_HEAD             SWORD (FIGHT_HEAD)
........                ........                ........                ...l....
........                ........                ........                ..lll...
.mmmmmml                .lmmml..                ..mmm...                ..mmm...
.mmmmmml                llmmmll.                ..mmm...                ..mmm...
.mmmmmml                .lmmml..                ..mmm...                ..mmm...
...h....                ...h....                ...h....                ...h....
...h....                ...h....                ...h....                ...h....
........                ........                ........                ........
```

- **AXE_HEAD:** medium-grey head offset on the haft — 2px left (cols 1-2) + haft
  (col 3) + 3px right (cols 4-6), 3px tall (rows 2-4); light-grey blade 1px×3px on
  the outer long edge (col 7). Palette `{m: STEEL, l: STONE, h: BARK}`.
- **PICKAXE_HEAD:** medium-grey head centred on the haft (cols 2-4, rows 2-4); two
  light-grey triangles tapering outward each side (left cols 0-1, right cols 5-6),
  3px tall.
- **HAMMER_HEAD:** pickaxe minus all light-grey — medium-grey block (cols 2-4,
  rows 2-4) on the haft. Palette `{m: STEEL, h: BARK}`.
- **SWORD (FIGHT_HEAD):** vertical blade (the axe rectangle rotated) centred on the
  haft (cols 2-4, rows 2-4); a single light-grey pickaxe-style triangle at the tip
  (row 0 col 3, row 1 cols 2-4). Palette `{m: STEEL, l: STONE, h: BARK}`.
- **Haft length −15%:** the player-tile grip drops from 3px to 2px
  (`grip_overlay` steps `k in (1, 2)` instead of `(1, 2, 3)`).

## Architecture

### Head selection moves into `MapPane._swing_overlay`

`swing_overlay` becomes head-agnostic:
`swing_overlay(mode, frame_index, head: Sprite) -> dict[(dcol,drow), Sprite]` —
places the passed `head` at the arc offset + a grip at `(0,0)`; `{}` for
non-swing modes. The arc side is decided by `mode` (gather/craft → right/CW,
fight → left/CCW).

`MapPane._swing_overlay(now)` picks the head from `action_kind` + `action_target`
+ `game_data`:
- `GATHER_SWING` → axe if the resource's skill is woodcutting, pickaxe if mining,
  else pickaxe (fishing/alchemy/unknown fallback).
- `FIGHT_SWING` → sword (`FIGHT_HEAD`).
- `CRAFT_SWING` → hammer **iff** `action_target` is a bar; otherwise return `{}`
  (no swing).
- non-swing modes → `{}`.

A small pure helper `gather_head(skill: str | None) -> Sprite` (in `sprites.py`)
maps a skill name to AXE/PICKAXE/pickaxe-default, so the mapping is unit-testable
without a widget. The bar test is `_is_bar(code, game_data)` — true when the item
exists and its code ends with `_bar` (the in-game convention for all smeltable
bars; copper_bar, iron_bar, steel_bar, gold_bar, mithril_bar, …). Implemented as a
tiny helper so it is testable and has one source of truth.

### New craft mode

- `action_kind_of` (`ai/action_kind.py`): add `CraftAction → ("craft", action.code)`.
- `swing_frames.Mode`: add `CRAFT_SWING`.
- `current_mode`: map `action_kind == "craft"` → `CRAFT_SWING` (gated by the same
  `0 < elapsed < duration` cooldown window as the other swings).
- `swing_overlay`: `CRAFT_SWING` uses the gather (right/CW) offsets.

Modes stay mutually exclusive in time. Glide / planning / movement timing /
snapshot+observer layer are untouched. The bar-gate (craft-but-not-a-bar → `{}`)
keeps non-bar crafts as idle.

### No tool while walking

No tool overlay shows during movement. By design the glide only animates on a
`move` snapshot (`current_mode` → `GLIDE` → no head), but a server-state position
correction arriving on a swing cycle could build glide frames while `action_kind`
is a swing kind, showing a tool mid-slide. Guard it explicitly:
`MapPane._swing_overlay` returns `{}` whenever a glide is in progress — i.e.
`self._anim_frames` is non-empty and the glide has not finished
(`now - self._anim_start` < the glide window). The player is "walking" → no
pickaxe/sword/hammer is drawn until it arrives.

## Components & isolation

| Unit | Responsibility | Depends on |
|---|---|---|
| `sprites`: AXE/PICKAXE/HAMMER/SWORD heads, `gather_head(skill)` | tool art + skill→gather-head map | Sprite, palette |
| `ai/action_kind.action_kind_of` | +Craft → ("craft", code) | CraftAction |
| `swing_frames`: `Mode.CRAFT_SWING`, `current_mode`, `swing_overlay(…, head)` | mode + head-agnostic overlay | sprites |
| `MapPane._swing_overlay` / `_is_bar` | head selection + bar gate | game_data, sprites, swing_frames |

## Data flow (per render frame, swing active)

```
mode = current_mode(snap.action_kind, planning, elapsed, cooldown_remaining)
head = None
if mode is GATHER_SWING: head = gather_head(game_data.resource_skill_of(snap.action_target))
elif mode is FIGHT_SWING: head = FIGHT_HEAD
elif mode is CRAFT_SWING and _is_bar(snap.action_target, game_data): head = HAMMER_HEAD
overlay = swing_overlay(mode, swing_frame_index(...), head) if head else {}
# _render_viewport merges head onto the arc-neighbor tile + grip onto player tile
```

## Error handling / edge cases

- `action_target is None` (unknown resource/craft) → skill lookup returns None →
  gather falls back to pickaxe; craft bar-check is False → `{}` (idle).
- Resource skill not woodcutting/mining (fishing/alchemy) → pickaxe fallback.
- Craft of a non-bar (boots, planks, rings) → `{}` → idle, no swing.
- Off-screen neighbor tile → not in the render loop (clipped); unchanged.
- All heads are 8×8 `validate_sprite`-clean immutable Sprites; compositor cache
  stays correct.

## Testing

- Each head sprite valid 8×8 with defined palette keys; HAMMER_HEAD has no
  light-grey (`l`) pixels; SWORD tip is light-grey, blade medium-grey, centred.
- `gather_head`: woodcutting → AXE_HEAD, mining → PICKAXE_HEAD, None/other →
  PICKAXE_HEAD.
- `_is_bar`: `copper_bar` → True, `copper_boots` → False, `None` → False.
- `action_kind_of(CraftAction(code="copper_bar")) == ("craft", "copper_bar")`.
- `current_mode("craft", …)` → `CRAFT_SWING` within the cooldown window, IDLE
  after / when planning.
- `swing_overlay(mode, i, head)` places the passed `head` at the arc offset
  (gather/craft right, fight left) + grip at `(0,0)`; `{}` for non-swing.
- `MapPane._swing_overlay`: gather of a woodcutting resource → axe; of a mining
  resource → pickaxe; fight → sword; craft of `*_bar` → hammer; craft of a
  non-bar → `{}`; idle/planning → `{}`. (Build a `GameData` test double exposing
  the resource-skill + recipe lookups, mirroring existing TUI test doubles.)
- No tool while walking: with glide frames present and `now` inside the glide
  window, `_swing_overlay` returns `{}` even for a gather/fight/craft snapshot;
  once the glide window has elapsed the overlay returns to normal.
- Grip is 2px (haft −15%).
- 100% coverage held; the `on_mount` pragma remains the only carve-out.

## Out of scope (YAGNI)

- Per-frame head rotation (single static head reused across arc offsets).
- Distinct fishing/alchemy tools (pickaxe fallback).
- Animating non-bar crafts.
- Any change to glide, planning bubble, movement timing, or the snapshot/observer
  plumbing beyond mapping CraftAction in `action_kind_of`.
