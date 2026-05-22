# Goal Tiers — P3a.3: Best-Attainable Gear Targets

Date: 2026-05-22
Status: Approved (design)

A refinement of P1's `CharacterObjective` (still shadow mode via P3a, no behavior
change to the live bot), fixing the "no gear ever pursued" gap the P3a.2 shadow
exposed.

## Goal

Make the Tier-1 gear target the best **attainable** item per slot — the
highest-`equip_value` item whose entire craft chain bottoms out in gatherables
(no drop-only/unknown component) — instead of the best in-game item. So a
reachable craftable item (e.g. a copper/iron weapon) becomes the target/root and
the strategy can walk the upgrade chain, rather than targeting a drop-gated
endgame item that `is_reachable` rejects, leaving gear unpursued.

## Problem (from the P3a.2 shadow)

P1 picks `target_gear[slot]` = highest `equip_value` item of that type, which is
typically an endgame item requiring a rare **monster/event drop** somewhere in
its chain. P3a.2's `is_reachable` (correctly) marks those unreachable, so **every
gear root is excluded** — the ranking collapsed to 8 skills + char level, and the
bot would never build any gear (no copper→iron→… progression).

## Design

All changes in `src/artifactsmmo_cli/ai/tiers/objective.py`.

### `is_attainable(code, game_data) -> bool` (module function, state-independent)
Structural, "attainable in principle at max progression" — does production bottom
out in gatherables with no drop/unknown/buy component? Cycle-safe.

```
is_attainable(code, game_data, _path=frozenset()):
    recipe = game_data.crafting_recipe(code)
    if recipe is not None:
        if code in _path: return False                      # cyclic recipe
        return all(is_attainable(mat, game_data, _path | {code}) for mat in recipe)
    return code in game_data._resource_drops.values()        # gatherable raw, else not attainable
```

This is distinct from strategy's `is_reachable`: `is_attainable` ignores current
skills/inventory/combat (the objective is the fixed perfect-sheet target);
`is_reachable` is the live, state-dependent filter the engine already applies.

### `CharacterObjective.from_game_data` — filter to attainable
When building `target_gear`, after ranking a slot's candidate items by
`(equip_value desc, code asc)`, keep only `is_attainable(code, game_data)` items,
then assign top-1 (and top-2 for paired ring/artifact slots). A slot with no
attainable item is omitted (as today). Result: `target_gear[slot]` = best
**attainable** item, the endpoint of a fully-craftable upgrade chain.

### Unchanged
`ObjectiveGap`, `equip_value`, the personality seam, the P2 graph, and the P3/3a
engine all stand — they now operate over attainable gear targets. The strategy's
`is_reachable` still applies per cycle (a target attainable in principle may not
be reachable *yet* at the current skill level — the frontier descends to the
reachable next step).

## Error handling
Pure, no API. `is_attainable` terminates via `_path`. Empty/sparse item table →
fewer/no target gear slots (as today). An item that is both craftable and
gatherable resolves via the craftable branch (materials must be attainable).

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`is_attainable`:** gatherable raw → True; craftable whose materials are all
  gatherable → True; multi-level craftable chain bottoming out in gatherables →
  True; drop-only/unknown item → False; craftable with one drop-only material →
  False; cyclic recipe → False.
- **`target_gear` attainable filter:** when the highest-value item for a slot is
  drop-only and a lower-value item is craftable-from-gatherables, the **craftable**
  one is targeted; a slot whose only items are drop-only is omitted; paired
  ring/artifact slots take the top-2 *attainable*.
- **Existing objective tests updated:** targeted items in the fixtures get
  recipes/resource-drops so they remain attainable and the prior best-per-slot /
  paired-slot assertions still hold (with attainability now required).
- Downstream P3a strategy tests already use craftable items → still pass; add/keep
  a check that a reachable craftable gear root now appears in `decide`'s ranking.

## Files
- Modify `src/artifactsmmo_cli/ai/tiers/objective.py` — `is_attainable`,
  `from_game_data` filter; export `is_attainable` in `tiers/__init__.py`.
- Modify `tests/test_ai/test_tiers_objective.py` (and any objective fixture used
  elsewhere) so targeted gear is attainable.

## Out of scope
- Buy-from-NPC / monster-drop as attainable sources (later phase; such items stay
  non-attainable and untargeted).
- Driving behavior (P3b), economy/tasks (P3c).
- Re-deriving the target as the character progresses — the target is the
  best-attainable endpoint; the strategy walks the reachable chain toward it.
