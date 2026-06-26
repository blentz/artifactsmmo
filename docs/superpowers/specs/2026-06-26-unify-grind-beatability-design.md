# Unify Grind Beatability (plan-screen ↔ execution) — Design

**Status:** approved-pending-review (brainstorm 2026-06-26)
**Scope:** DRY the duplicated "which monster can I grind" logic so the plan screen
(`path_next_action`) and the executor (`_winnable_farm_target`) always agree.

## Problem

Two code paths decide the grind monster with DIFFERENT beatability tests:

| Path | Beatability test | Result for L8 Robby |
|---|---|---|
| Projection `cheapest_path_to_level` (`learning/projections.py`) → drives the plan screen `path_next_action` and `projected_cycles_to_max` | `1 ≤ level ≤ sim_level+1` (level gate) + a bespoke ≥5-loss win-rate filter (`MIN_PATH_SUCCESS_RATE`). **Never calls `predict_win`.** | `cow` (level 8, 280 HP — level-OK, highest XP/cycle) |
| Runtime `_winnable_farm_target` (`player.py`) → drives `GrindCharacterXP` (what executes) | `combat.is_winnable` (predict_win + learned-loss veto + monotonic-win) | `green_slime` (cow fails `is_winnable`) |

So the plan screen shows "grind cows" while the logs show green_slime, and
`projected_cycles_to_max` (16590) assumes cow-speed XP the bot never earns. The
runtime cascade (`task > path-if-winnable > pick-winnable`) already consults the
projection's monster as `path_monster`, finds `is_winnable(cow)=False`, and falls
through to `pick_winnable=green_slime` — so the projection's optimistic pick is
silently discarded every cycle.

## Design — one beatability source

Make the projection use the SAME `combat.is_winnable` verdict the runtime uses.
Beatability then lives in exactly one function; the plan screen's first segment
equals the runtime's `path_monster`, so the cascade returns it and the display
matches execution.

### 1. Projection shell (`learning/projections.py::cheapest_path_to_level`)

The per-sim-level candidate filter becomes:

```
beatable = [ (code, lvl) for code, lvl in game_data.monster_levels.items()
             if 1 <= lvl <= sim_level + 1                       # can ATTACK (FightAction gate)
             and is_winnable(state, game_data, code, store) ]    # can WIN (the shared verdict)
```

- The bespoke `MIN_PATH_SUCCESS_RATE` / `MIN_PATH_SAMPLES` win-rate filter is
  **DELETED** — `is_winnable`'s learned-loss veto subsumes it (one source of truth).
- `is_winnable` uses the CURRENT `state` (gear/HP) for every projected `sim_level`
  — a documented approximation (the projection already doesn't model gear
  progression; see "Known limits"). The level gate still moves with `sim_level`.
- When no candidate survives at some `sim_level`, the projection returns
  `blocked=True, total_cycles=inf` — honest (the bot can't beat anything
  level-appropriate with current gear). At low levels green_slime survives, so in
  practice the path completes with an honest, slime-speed ETA.

### 2. Proven core (`formal/Formal/CheapestPath.lean`)

The missing piece was *winnability*, not the level gate (the `1 ≤ level ≤
simLevel+1` applicability gate is already mirrored consistently in both the
projection and `FightAction`, and differential-tested). So carry the
`is_winnable` verdict into the core as DATA: add a `winnable : Bool` field to the
`Monster` candidate and make `isBeatable simLevel m := (1 ≤ level) ∧ (level ≤
simLevel+1) ∧ m.winnable`. The shell computes `m.winnable = is_winnable(state,
game_data, code, store)` — the single beatability source. The greedy-pick, strict
`sim_level` termination, and `blocked`-when-no-candidate theorems are unchanged in
statement; ANDing a conjunct into `isBeatable` only shrinks the filtered set,
which those proofs already quantify over generically.

The `predict_win` / `is_winnable` cores are reused UNCHANGED (already proven).

### 3. Runtime + display — NO change

`_winnable_farm_target` already consults `_path_aligned_monster()` (the
projection's pick) gated by `is_winnable`. With the projection now yielding a
winnable monster, `path_winnable` is True and the cascade returns it directly;
`path_next_action = plan.next_action_monster` then equals what executes. No
change to player.py or the snapshot — the fix flows through.

## Components

| File | Change |
|---|---|
| `learning/projections.py` | `cheapest_path_to_level` beatable filter → `is_winnable`; delete the win-rate filter; import `combat.is_winnable` |
| `formal/Formal/CheapestPath.lean` | add `Monster.winnable : Bool`; `isBeatable` ANDs it (level gate kept as the mirrored FightAction invariant); theorem statements unchanged |
| `formal/Oracle.lean` + `formal/diff/test_cheapest_path_diff.py` | update for the new core input shape; the differential now feeds pre-filtered candidates |
| `formal/diff/mutate.py` | refresh CheapestPath anchors for the new shape |

## Data flow

`cheapest_path_to_level`: per sim_level → filter monsters by `is_winnable` (shell)
→ proven greedy pick over the filtered candidates → first segment = next grind
monster. The runtime `_path_aligned_monster` reads this; `_winnable_farm_target`
returns it (now winnable); the snapshot displays it. One monster, everywhere.

## Error handling / safety

- `is_winnable` raises on unknown monster stats (use-only-API-data). The candidate
  loop only iterates `monster_levels` codes, which have stats.
- `blocked=True` is the correct, honest outcome when nothing is winnable — not an
  error.
- No circular import (verified): `combat.py` imports `equipment.projection` and
  `learning.store`, NOT `learning.projections` — so `learning/projections.py`
  importing `combat.is_winnable` introduces no cycle. Direct top-level import.

## Testing

- Unit (`tests/test_ai/test_projections.py`): a tanky same-level monster (cow:
  level==char, high HP, predict_win False) is EXCLUDED from the path; a winnable
  lower monster (green_slime) is selected even though the cow has higher raw XP;
  `blocked=True` when no winnable monster exists; the next_action_monster equals
  what `_winnable_farm_target` returns for the same state.
- Cross-path consistency test: `cheapest_path_to_level(...).next_action_monster ==
  _winnable_farm_target()` (the regression lock for THIS bug).
- Formal: full `formal/gate.sh` green.

## Known limits (unchanged / documented)

- The projection scores all sim_levels with CURRENT gear (`is_winnable(state,…)`),
  so it doesn't credit future gear upgrades — it may project `blocked` or a long
  ETA where a geared-up bot would progress. This is the pre-existing
  "doesn't model gathering/crafting detours / gear progression" limit, now made
  explicit. Modeling gear progression in the projection is a separate, larger spec.

## Out of scope

- Modeling gear/skill progression inside the projection.
- Changing `predict_win` / `is_winnable` / `_winnable_farm_target`.
- The per-level XP-curve assumption (`max_xp` per level) — unchanged.
