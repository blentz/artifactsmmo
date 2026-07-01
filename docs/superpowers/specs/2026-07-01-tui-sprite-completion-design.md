# TUI Sprite Completion — Design

**Date:** 2026-07-01
**Status:** Approved (design), pending implementation plan
**Branch (planning):** feat/next-tier-skill-grind-dampener (spec only; implementation gets its own branch)

## Problem

The TUI map renders game entities as 8x8 sprites. Curated sprites exist for a
subset of entity codes; everything else falls back to a tinted procedural blob
(`sprite_registry._build_fallback`). Current curated coverage:

| Category  | Curated | Keying                                            |
|-----------|---------|---------------------------------------------------|
| MONSTER   | 30      | per-code (real code passes through map_pane)      |
| NPC       | 6       | per-code (real code passes through map_pane)      |
| STRUCTURE | 5       | per-type, collapsed in map_pane (bank/door/GE/workshop/tasks_master) |
| RESOURCE  | 4       | generic per-skill (woodcutting/mining/fishing/alchemy) |

The map therefore shows generic blobs for most monsters and many NPCs. Goal:
draw the remaining monster and NPC sprites so the combat/exploration map reads
clearly, and add a lightweight audit so the curated list does not silently rot
as the game adds content.

## Scope

**In scope**
- Hand-authored sprites for all remaining **monster** codes.
- Hand-authored sprites for all remaining **NPC** codes.
- A **warn-level coverage audit** that reports uncurated monster/NPC codes at
  startup (mirrors the existing `/effects` coverage audit).

**Out of scope**
- Per-node resource sprites (resources stay generic per-skill). Excluded by
  decision — would require map_pane to key resources by node instead of skill.
- Per-workshop-skill or any new structure art. The 5 generic structure sprites
  already cover every distinct map content-type that map_pane routes; adding
  variety would require a map_pane routing change and buys little. Left as-is.
- Any change to the procedural fallback. It remains the safety net for
  uncurated codes; curated misses stay "expected behavior, not errors".

## Key structural fact

In `map_pane._build_tile_index`, **monster and NPC tiles carry the real game
code** into `(category, code)`:

```
index[xy]  = (SpriteCategory.MONSTER, code)      # real monster code
index[loc] = (SpriteCategory.NPC, npc_code)      # real npc code
```

Structures are collapsed to fixed codes (`"workshop"`, `"bank"`, ...). This is
why monster/NPC completion is a **pure data addition** — appending entries to
`MONSTER_SPRITES` / `NPC_SPRITES` in `sprites.py` — with **no logic change**,
while structures would need routing work (hence out of scope).

## Approach: family-binning

Distinctiveness-vs-effort tradeoff resolved as **hybrid family + distinct**:

- Each uncurated code is assigned to a **family** with a shared 8x8 base
  silhouette. Individuality comes from **palette** and, where useful, a small
  number of overpainted marking cells — the same technique slimes already use
  (one shape, four palettes).
- Candidate families: `blob`, `small_beast`, `humanoid`, `undead`, `flyer`,
  `serpent`, `plant`, `giant`, `insectoid`. Anything that fits none gets a
  bespoke `distinct` silhouette (e.g. spider, bird, tree already are).
- Binning is an **authoring-time** activity. There is **no runtime family
  engine** and no new abstraction. The output is ordinary `Sprite(...)` entries
  in the existing curated dicts. This keeps `sprite_registry` and `sprites.py`
  structurally unchanged — only data grows.
- New colors are added to `palette.py` as named constants (existing pattern).

Rationale: matches the established slime pattern, gives every creature a legible
identity, and avoids ~35+ fully bespoke grids while still allowing bespoke art
where a shape is genuinely unique.

## Coverage audit

New module (one behavioral class per file, per CLAUDE.md), modeled on the
existing effects coverage audit:

- At startup, read live `GameData`: the set of monster codes (from
  `all_monster_locations`) and NPC codes (from `npc_locations`).
- Compare against the curated dict keys (`MONSTER_SPRITES`, `NPC_SPRITES`).
- For any code present in-game but absent from the curated dict, log a
  **warning** listing the uncurated codes, grouped by category:
  `WARN uncurated monsters: [...]`, `WARN uncurated npcs: [...]`.
- **Non-fatal.** The fallback blob still renders these tiles. The audit exists
  to surface drift, not to block boot or fail a build.

The audit reads live `GameData`, so it needs **no snapshot fixture** and is
fully buildable and testable now (with a fixture `GameData`) even while the
game API is unreachable.

## Components / files

| File | Change |
|------|--------|
| `src/artifactsmmo_cli/tui/sprites.py` | Append monster + NPC `Sprite` entries (data only). |
| `src/artifactsmmo_cli/tui/palette.py` | Add any new named colors used by the new sprites. |
| `src/artifactsmmo_cli/tui/sprite_coverage_audit.py` | New: warn-level audit class. |
| Startup wiring (same site as the effects audit) | Invoke the sprite audit once. |
| `tests/test_tui/test_sprites.py` | Validate every new sprite (8x8 + palette integrity) via `validate_sprite`. |
| `tests/test_tui/test_sprite_coverage_audit.py` | New: audit warns on uncurated, silent on full coverage, over fixture GameData. |

Follows existing conventions: `validate_sprite` already enforces the 8x8 /
palette-key invariants, so the per-sprite test is a data-driven loop over the
new entries.

## Dependency / sequencing

The exact monster and NPC rosters are only available from the **live game API**,
which is currently returning **HTTP 502 (down)**. `learning.db` caches only a
handful of fought monster codes, not the universe; `openapi.json` carries schema,
not the code lists.

Consequences for the plan:

1. **Audit** (module + tests over fixture GameData): buildable now, no live data
   needed.
2. **Family binning + drawing**: gated on API recovery. When the API is back:
   fetch `/monsters` and `/npcs` (paginated), diff against curated keys to get
   the exact gap, bin each missing code into a family, author sprites.

The implementation plan will order the audit first (unblocked) and the drawing
second (gated), so progress is possible immediately.

## Testing

Success criteria per project standard: 0 errors, 0 warnings, 0 skipped, 100%
coverage.

- Every new sprite passes `validate_sprite` (8x8, defined palette keys).
- Audit: warns with the correct uncurated set given a fixture GameData that
  includes uncurated codes; emits nothing when the fixture is fully covered.
- No regression in existing `test_tui` suite.

## Non-goals / YAGNI

- No runtime family/archetype resolution engine — binning is authoring-time.
- No hard coverage test/fixture snapshot — drift is surfaced by the warn audit,
  consistent with the fallback-is-expected philosophy.
- No structure or resource sprite changes.
