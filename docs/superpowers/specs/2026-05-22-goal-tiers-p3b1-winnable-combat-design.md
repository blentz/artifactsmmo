# Goal Tiers — P3b.1: Winnable Combat Target

Date: 2026-05-22
Status: Approved (design)

A focused follow-up to the P3b cutover, fixing the fight→lose→heal exposure the
first live trace showed.

## Goal

The monster the strategy fights (via `ReachCharLevel` → `GrindCharacterXP`) and
the fallback grind must be one the bot can actually **win** against, not just the
most XP-efficient. Winnability combines a **combat-stat prediction** (player
attack/resistance/HP vs monster attack/resistance/HP) with a **learned-win-rate
veto** (observed losses override an optimistic prediction). Gate the combat
target by winnability; fall back to the conservative winnable picker when the
XP-optimal pick isn't winnable.

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

### Player combat stats on `WorldState` (`world_state.py`)
The character schema already carries server-computed totals (base + gear):
`attack_fire/earth/water/air`, `res_fire/earth/water/air`. `WorldState` keeps
only `hp/max_hp`. Add two frozen fields (default empty so existing constructions
keep working):
```python
attack: dict[str, int] = field(default_factory=dict)       # element -> attack
resistance: dict[str, int] = field(default_factory=dict)   # element -> resistance %
```
`from_character_schema` populates them: `attack = {el: getattr(char,
f"attack_{el}", 0) for el in ("fire","earth","water","air")}` (drop zeros),
likewise `resistance` from `res_{el}`.

### Combat estimator — `src/artifactsmmo_cli/ai/combat.py`
Pure `predict_win(state, game_data, monster_code) -> bool` using a simplified
documented damage model (per-element attack reduced by the defender's
resistance %; ignores crit / dmg-bonus / turn-order nuance — flagged below):
```
ELEMENTS = ("fire", "earth", "water", "air")
def _dmg(attack: dict, resist: dict) -> int:
    return sum(max(0, round(attack.get(e, 0) * (1 - resist.get(e, 0) / 100))) for e in ELEMENTS)

predict_win(state, game_data, code):
    m_hp  = game_data.monster_hp(code)
    p_dmg = _dmg(state.attack, game_data.monster_resistance(code))
    if p_dmg <= 0: return False                      # can't damage it
    m_dmg = _dmg(game_data.monster_attack(code), state.resistance)
    if m_dmg <= 0: return True                        # it can't damage us
    rounds_to_kill = ceil(m_hp / p_dmg)
    rounds_to_die  = ceil(state.max_hp / m_dmg)
    return rounds_to_kill <= rounds_to_die            # we drop it no later than it drops us
```
Add `GameData.monster_hp(code) -> int` (mirrors `monster_attack`/`monster_resistance`).

### Shared thresholds + `_is_winnable` (`player.py`)
Extract the thresholds inline in `_pick_winnable_monster` to module constants
`WIN_RATE_THRESHOLD = 0.5`, `MIN_WIN_SAMPLES = 5` (both `_pick_winnable_monster`
and the new check use them).

```python
def _is_winnable(self, monster_code: str) -> bool:
    """Winnable when the combat-stat prediction says we win AND we have not been
    observed losing it (>= MIN_WIN_SAMPLES fights under WIN_RATE_THRESHOLD).
    Learned losses veto an optimistic stat prediction."""
    if self.history is not None:
        samples = self.history.sample_count(f"Fight({monster_code})")
        if samples >= MIN_WIN_SAMPLES and self.history.success_rate(f"Fight({monster_code})") < WIN_RATE_THRESHOLD:
            return False
    return predict_win(self.state, self.game_data, monster_code)
```

The stat prediction replaces the old `monster_level <= char_level` proxy (stats
are the real signal). `_pick_winnable_monster` filters candidates by
`_is_winnable` and returns the highest-level winnable monster (or `None`).

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
- L1: stat prediction vs `yellow_slime` (higher attack/HP) → lose → not winnable
  → path-aligned pick rejected → `_pick_winnable_monster` returns a monster the
  stats say we beat (e.g. chicken) or `None`. No losing fight.
- Under-equipped (low/zero attack) → `predict_win` False for most monsters →
  `farm_target` `None` → no combat grind; the strategy routes to gear (build a
  weapon) — the intended "need gear to level" behavior.
- A monster the stats over-rate but we actually lose (≥5 samples, <50%) → win-rate
  veto excludes it; the bot stops grinding it.

### Unchanged / out of scope
- `tiers.prerequisite_graph.combat_capable`'s level gate stays (it only decides
  whether `ReachCharLevel` is a leaf vs gear-gated; the actual fight target is
  now winnability-gated here).
- No change to the strategy engine / `strategy_driver`; the player feeds the now-
  winnable `farm_target` into `strategy_goal`/fallback.

## Error handling
Pure logic, no API. `predict_win`: monster with no stats → `monster_hp` 0 →
`rounds_to_kill` 0 → win (harmless; unknown monsters are rare and low-stakes);
empty player `attack` → `p_dmg` 0 → not winnable (correctly routes to gear).
`history is None` → win-rate veto skipped (stat prediction only). `WorldState`
new fields default empty, so non-schema constructions are unaffected.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`WorldState.from_character_schema`:** populates `attack`/`resistance` from the
  `attack_*`/`res_*` fields (zeros dropped); default empty otherwise.
- **`predict_win`:** player out-damages → win; monster out-damages (kills first)
  → lose; zero player attack → lose; zero monster attack → win; resistance reduces
  effective damage (a high-resistance defender survives more rounds).
- **`GameData.monster_hp`:** returns hp or 0 when unknown.
- **`_is_winnable`:** stat-predicted win + no losing record → True; stat-predicted
  loss → False; stat-win but observed losing (≥5 samples, <50%) → False;
  `history None` → stat prediction only.
- **`_pick_winnable_monster`:** returns the highest-level `_is_winnable` monster;
  `None` when none are winnable.
- **`_build_goals` gate:** path-aligned monster that isn't winnable → `farm_target`
  falls back to the winnable pick; winnable path-aligned pick is kept; no winnable
  monster → no `GrindCharacterXP` adapter built.

## Files
- Modify `src/artifactsmmo_cli/ai/world_state.py` — `attack`/`resistance` fields +
  `from_character_schema` population.
- Create `src/artifactsmmo_cli/ai/combat.py` — `predict_win`.
- Modify `src/artifactsmmo_cli/ai/game_data.py` — `monster_hp(code)` getter.
- Modify `src/artifactsmmo_cli/ai/player.py` — constants, `_is_winnable`
  (stat + win-rate), `_pick_winnable_monster` rework, `_build_goals` gate.
- Modify tests: `tests/test_ai/test_world_state*.py`, new `test_combat.py`,
  `test_game_data.py`, `test_player.py`.

## Simplified combat model (flagged for review)
`predict_win` uses per-element `attack × (1 − resistance%)` summed, and a
rounds-to-kill ≤ rounds-to-die comparison from full HP. It **ignores** critical
strikes, damage-bonus effects, haste/turn-order, and consumable use mid-fight —
a deliberate first-cut heuristic. The learned-win-rate veto corrects systematic
mis-predictions over time. A higher-fidelity model (documented crit/dmg formula)
can replace `predict_win` later without touching callers.

## Out of scope
- Win-rate-aware `combat_capable` in tiers (kept level-gated; harmless).
- Tasks/economy into the frontier; retiring `priorities.py` (P3c).
