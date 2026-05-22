# Goal Tiers — P3b.1: Winnable Combat Target

Date: 2026-05-22
Status: Approved (design)

A focused follow-up to the P3b cutover, fixing the fight→lose→heal exposure the
first live trace showed.

## Goal

The monster the strategy fights (via `ReachCharLevel` → `GrindCharacterXP`) and
the fallback grind must be one the bot can actually **win** against, not just the
most XP-efficient. Gate the combat target by winnability (level + learned
win-rate); fall back to the conservative winnable picker when the XP-optimal pick
isn't winnable.

## Problem (from the P3b live trace)

`_build_goals` sets `farm_target = self._path_aligned_monster()` (cheapest-path-
to-max-level projection — maximises XP/cycle) and only falls back to
`_pick_winnable_monster()` when that returns `None`. `_path_aligned_monster`
does **not** check winnability, so at L1 it picked `yellow_slime`; the strategy's
`ReachCharLevel` mapped to `GrindCharacterXP(yellow_slime)`, the bot **lost**
(`error:fight_lost`), then `RestoreHP` (110) preempted to heal — a fight→lose→heal
exposure. `_pick_winnable_monster` already gates candidates on `level <= char`
plus win-rate (`success_rate >= 0.5`, `>= 5` samples), so the XP-optimal pick just
needs the same gate.

## Design

All changes in `src/artifactsmmo_cli/ai/player.py`.

### Module constants
Extract the thresholds currently inline in `_pick_winnable_monster` so both it
and the new check share one source:
```python
WIN_RATE_THRESHOLD = 0.5
MIN_WIN_SAMPLES = 5
```
`_pick_winnable_monster` uses these (replacing its local `WIN_RATE_THRESHOLD`/
`MIN_SAMPLES`).

### `_is_winnable(self, monster_code) -> bool`
```python
def _is_winnable(self, monster_code: str) -> bool:
    """A monster is winnable when it is at or below char level AND not observed
    losing (>= MIN_WIN_SAMPLES fights with success_rate < WIN_RATE_THRESHOLD).
    Unobserved at/under level → winnable (benefit of the doubt, but level-capped)."""
    level = self.game_data._monster_level.get(monster_code, 0)
    if level > self.state.level:
        return False
    if self.history is not None:
        samples = self.history.sample_count(f"Fight({monster_code})")
        if samples >= MIN_WIN_SAMPLES and self.history.success_rate(f"Fight({monster_code})") < WIN_RATE_THRESHOLD:
            return False
    return True
```

### Gate the combat target in `_build_goals`
```python
        farm_target = self._path_aligned_monster()
        if farm_target is None or not self._is_winnable(farm_target):
            farm_target = self._pick_winnable_monster()
```
So the XP-optimal pick is used only when winnable; otherwise the conservative
winnable picker (or `None`). When `farm_target` is `None`, no strategy
`ReachCharLevel` grind / fallback grind is built that cycle — combat is
suppressed and gear/skill steps (or recovery) drive instead.

### Consequence
- L1: path-aligned `yellow_slime` (level 2 > 1) → not winnable → fall back →
  `_pick_winnable_monster` picks a level-≤1 monster (e.g. chicken) or `None`. No
  losing fight.
- As char level rises and win-rate data accrues, the XP-optimal path-aligned pick
  is used whenever it's level-appropriate and not observed-losing.
- A monster that starts losing (≥5 samples, <50% wins) is excluded — the bot
  stops grinding it and the strategy routes elsewhere (gear/skill) or recovery.

### Unchanged / out of scope
- `tiers.prerequisite_graph.combat_capable`'s `monster_level <= char_level + 1`
  level gate stays (it only decides whether `ReachCharLevel` is a leaf vs
  gear-gated; a low-level monster keeps it a leaf regardless, and the actual
  fight target is now winnability-gated here). Tightening it is unnecessary and
  out of scope.
- No change to the strategy engine or `strategy_driver`; the player still feeds
  `farm_target` into `strategy_goal`/fallback — now winnable.

## Error handling
Pure selection logic, no API. `_is_winnable` reads `game_data._monster_level`
(0 when unknown → treated as ≤ level → winnable-by-level, then win-rate gate);
`history is None` → level-only gate.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`_is_winnable`:** over-level monster → False; at/under level, no history →
  True; at/under level, observed losing (≥5 samples, <50%) → False; at/under
  level, observed winning → True; unknown monster (level 0) with no history → True.
- **`_build_goals` gate:** when `_path_aligned_monster` returns an over-level
  monster, `farm_target` falls back to the winnable pick (assert the strategy/
  fallback grind targets the winnable one, not the over-level one); when path-
  aligned is winnable, it is kept.
- **No-winnable case:** all monsters over-level / observed-losing → `farm_target`
  None → no `GrindCharacterXP` adapter (strategy/fallback) built that cycle.
- Existing `_pick_winnable_monster` tests still pass with the extracted constants.

## Files
- Modify `src/artifactsmmo_cli/ai/player.py` — constants, `_is_winnable`,
  `_build_goals` gate, `_pick_winnable_monster` constant reuse.
- Modify `tests/test_ai/test_player.py` (and any monster-pick test).

## Out of scope
- Win-rate-aware `combat_capable` in tiers (kept level-gated; harmless).
- Tasks/economy into the frontier; retiring `priorities.py` (P3c).
