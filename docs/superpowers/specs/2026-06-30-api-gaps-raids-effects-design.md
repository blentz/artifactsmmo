# API-gap closure: raid visibility + effects coverage audit

**Date:** 2026-06-30
**Status:** design (approved sections 1 & 2; pending spec review)

## Context & motivation

The bot consumes 16 of 24 API endpoint groups. An audit of the unconsumed groups
found only two with planner value; the rest are auth, monetization, or cosmetic.

This work closes those two gaps. It is also a prerequisite for a *later, separate*
investigation: assessing whether the artifactsmmo Discord surfaces game state
(events, raids, GE orders, announcements) that the API lacks or lags. Events and
GE orders are already API-consumed; **raids are the one Discord-relevant category
the bot cannot currently see.** Closing the raid gap gives that future comparison a
fair API baseline. Effects is an unrelated internal-robustness gap folded in here
because it is high-value and cheap.

Neither part touches a proven decision core (`predict_win`, the arbiter, the
planner). No formal-gate (Lean / differential / mutation) impact.

## Part 1 — Raid visibility

### Goal
Capture raid state from `/raids` and surface it to the human (TUI + log) and to
`WorldState`. **No participation goal, no new actions.** Raid bosses are
high-level shared-HP monsters that `is_winnable` vetoes at low level, and the API
exposes **no join/fight-raid action** — participation is implicit server-side when
a character fights the raid monster during an active window. Visibility only.

### API surface
- `GET /raids` → `RaidSchema[]`: `code`, `name`, `monster`, `schedule`
  (weekdays / UTC hours / duration), `status`
  (`upcoming` | `active` | `finished_success` | `finished_failure`),
  `next_start_at`, `participant_count`, `active_instance` (`RaidInstanceSchema` | null),
  `latest_instance`, `rewards`.
- `RaidInstanceSchema`: `starts_at`, `ends_at`, `status`, `total_hp`,
  `remaining_hp`, `participant_count`, `result`.
- (`/raids/{code}`, `/raids/{code}/leaderboard` exist but are not needed for
  visibility; out of scope.)

### Components
- `GameData._fetch_raids(client)` → `GET /raids`; `GameData._build_raids(objs["raids"])`
  stores a raid catalog: `self._raids: dict[str, RaidInfo]` keyed by code, holding
  the static parts (monster, monster location via the existing map index, schedule,
  rewards). Wired into `GameData.load` exactly like `_build_events`: added to the
  `fetched` dict, to the cached-reload branch (`RaidSchema.from_dict`), and to the
  `_build_*` call sequence.
- **Dynamic status is not static game data.** Raid `status` / `active_instance`
  change over time, so the *current* raid state refreshes at runtime, mirroring the
  concrete `active_events` path: `GamePlayer._fetch_active_events` (player.py:838)
  calls `/events/active` and populates `WorldState.active_events` (~player.py:922).
  A new `GamePlayer._fetch_active_raids` fetches `/raids`, filters `status ==
  "active"`, and populates `WorldState.active_raids` on the same refresh cadence.
  The static catalog (code/monster/schedule/rewards) caches with game data; the
  live status is refreshed — not baked into the TTL'd cache.
- `WorldState.active_raids: dict[str, ActiveRaid]` (new field, parallels
  `active_events`): currently-active raids with `monster`, `location`,
  `window_ends_at`, `remaining_hp`, `total_hp`. Populated on the periodic refresh.
- **Surfacing (the only consumer):** a log line when a raid is active
  (`raid active: {monster} @ {loc}, {remaining_hp}/{total_hp} hp, ends {t}`) and a
  small TUI indicator. No planner consumer by design.

### Data flow
`/raids` → GameData static catalog + periodic status refresh →
`WorldState.active_raids` → TUI / log. The future Discord comparison will read the
same `WorldState.active_raids` as its API baseline.

### Explicitly out of scope
No `RaidGoal`, no routing to raid monsters, no survivability check, no
leaderboard/reward-tier logic. Pure capture + display.

## Part 2 — Effects coverage audit

### Goal
Consume `/effects` (the authoritative effect registry) to turn the *lazy*,
discovered-by-accident coverage gap into an *eager* startup audit plus carveout
hygiene. **No combat-modeling change** — `predict_win` and its Lean proofs are
untouched.

### Current mechanism (unchanged by this work)
Effect codes are handled by explicit `elif code == "X"` chains in
`_build_monsters` / `_build_items`, guarded lazily by `GameDataCoverageError`
(carveout frozensets: `_MONSTER_EFFECT_CARVEOUTS`, `_ITEM_EFFECT_CARVEOUTS`,
`_RUNE_ABILITY_CARVEOUTS`). The guard fires only when a *loaded* monster/item
carries an unmapped code — a brand-new code on nothing-yet-loaded is invisible
until something carries it.

### Components
- `GameData._fetch_effects(client)` → `GET /effects`; `_build_effects` stores
  `self._effect_registry: dict[str, EffectInfo]` (code → metadata/description).
  Cached with static game data, wired into `load` like the others.
- During the existing `_build_monsters` / `_build_items` parse, collect
  `self._seen_effect_codes: set[str]` — every effect code encountered, whether
  mapped or carved. No parallel "modeled codes" list to keep in lockstep; the set
  is a byproduct of the parse already happening.
- `GameData._audit_effect_coverage()`, run after the builds, emits a startup
  report (log, **warn-level, never fails**):
  - `registry − seen` → "effect codes defined but on no current entity" — the
    early-warning watchlist to model *before* a monster carrying one appears.
  - `seen − registry` → data anomaly (a code in use the registry doesn't define).
  - `carveouts − registry` → stale-carveout hygiene.

### Enforcement split
The audit **warns**; it never hard-fails on a latent/unused code (blocking boot
for an effect nothing carries is too aggressive). The existing lazy
`GameDataCoverageError` remains the **hard gate** the moment a new code is actually
carried by a real monster/item. Eager visibility + lazy enforcement.

### Data flow
`/effects` → `_effect_registry`; parse → `_seen_effect_codes`; audit → log report.
No `WorldState`, no planner, no behavior change.

## Testing

- `_build_raids`: catalog parse (static parts) + active-status parse from
  `active_instance`; missing/`null` `active_instance`; each `status` value.
- `WorldState.active_raids` refresh: populated when a raid is active, cleared when
  none active, correct `remaining_hp` / `window_ends_at`.
- Surfacing: log line + TUI indicator render for an active raid; silent when none.
- `_audit_effect_coverage`: the three report cases (latent, anomaly, stale carveout)
  each produce the expected warning; a fully-covered registry produces none.
- Cache round-trip: raids + effects survive the game-data cache write/reload branch.

Coverage target follows the repo bar (100%, per project guidelines). No
formal-gate work — neither part touches a proven decision core.

## Boundaries / non-goals
- No raid participation, ever, in this spec.
- No auto-modeling of effects into `predict_win` (effects stay hand-modeled with
  their Lean proofs; the audit only reports).
- No Discord work — that is a separate, later spec gated on this baseline.
