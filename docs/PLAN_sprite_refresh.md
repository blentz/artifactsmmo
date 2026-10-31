# PLAN: sprite refresh (shaded ramps, tinted outlines, distinct silhouettes)

User decisions (2026-10-31): keep the 8x8 tile and the half-block renderer; redraw
the tileset in the trial style the user approved (`compare2.png` set: orc,
skeleton, goblin, green slime, tree) with the player head variant "D" (short
hair, eyes inset from the face edge, neck). Rendering cost is unaffected: the
segment renderer (perf/map-segment-render) caches per (sprite, terrain).

## Motivation

The old tileset drew every sprite as a flat fill inside a 1px INK ring. The ring
spent 28 of 64 pixels, every humanoid was the same rounded box with two eyes
(orc, ogre, skeleton, death knight, highwayman, acolyte...), and flat fills gave
no light or volume.

## Style rules (apply to every sprite)

1. **Ramps, lit from the top-left.** Each material is a `Ramp` (outline, dark,
   mid, light). Light pixels sit on the upper-left of a form, dark on the
   lower-right. The existing flat constants (`LEAF`, `TUNIC`, ...) stay as the
   ramp's `mid`, so their callers (roster colours, tests) keep working.
2. **Tinted outlines.** A sprite's outline is its main material's `outline`
   shade, not INK. INK stays for eyes/pupils only.
3. **Silhouette first.** Two different drawings must never share a silhouette
   (enforced by a test over every curated sprite; reramped variants share their
   base's rows by design and count as one drawing).
4. **Families reramp, not recolor.** Variants (slime colours, merchants, the 28
   roster-gap monsters) swap whole ramps by value (`reramp`), so they inherit
   the shading.

## Steps

- [x] `overlay_sprites`: a top key that collides with a base key of a different
      colour is renamed, so a swung tool (`h`/`m`/`l`) never recolours the
      target tile's sprite (live bug: the sword's `h` recoloured a vampire's
      hair). Test.
- [x] `palette.py`: `Ramp` value object + ramps; flat constants kept as mids.
- [x] `sprites.reramp(sprite, {old_ramp: new_ramp})` + tests (replaces `recolor`; with
      `shade_keys` / `palette_of` to build palettes from ramps).
- [x] Player (variant D) + `CharacterRoster` reramps the tunic ramp per slot.
- [x] Monsters: base shapes, then the reramped families.
- [x] NPCs, structures, resources. (The tailor's dress, not its apron, carries the
      dyed material, so the five merchant reramps read as different trades.)
- [x] Silhouette-uniqueness test.
- [x] Tool heads and thought cloud: unchanged (they already read well; their
      rows are pinned by the swing tests).
- [x] Contact sheet check (old vs new), full suite (9829 passed, 100% coverage).
- [x] Commit.

## Tooling

`scripts/preview_sprites.py` prints the tileset in the terminal. The trial was
judged from a PNG contact sheet rendered on both terrain colours (`grey50`
explored floor, `grey15` void): judge every batch on both.
