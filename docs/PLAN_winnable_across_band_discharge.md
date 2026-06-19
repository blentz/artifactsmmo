# PLAN: discharge / validate WinnableAcrossBand (Option C)

## Goal
Reduce or discharge the `WinnableAcrossBand` residual
(`Formal/Liveness/GearTierLeveling.lean:54`) that the level-50 proof rests on:
for every char level L ∈ [1,50), the monster catalog contains a WINNABLE,
XP-positive, not-over-leveled monster. Currently a satisfiable Lean hypothesis.
Target: validate it against the live game data (LIV-001 class) or prove it.

## Scouting finding (2026-06-18) — the base-stats shortcut is INFEASIBLE
A first hope was a "base-stats-only" differential: sweep L=1..49, run production's
real `is_winnable` on a NO-GEAR level-L character against the live monster catalog,
assert a winnable in-band target always exists (sound because gear only helps, so
base-wins ⇒ geared-wins). **This does not work**, for two compounding reasons:

1. **Attack is gear-derived.** `predict_win` (`src/.../ai/combat.py:89-93`) computes
   `raw_player = Σ _element_damage(p.attack[e], …)` and `if raw_player <= 0: return
   False`. Player `p.attack` comes from EQUIPPED WEAPONS (`projection.py` seeds from
   `state.attack` totals; a fresh char's weapon slot is empty). A no-gear character
   does ZERO damage → `predict_win` False → beats NOTHING. So the base-stats sweep
   would (correctly) report "winnable at no band" — useless.
2. **Base stats per level are NOT server-exposed.** `projection.py:3-6`: "The server
   reports only TOTAL stats (base + equipped gear), never base." The API
   `CharacterSchema` has only computed totals + the 11 gear slots; no base-stat-per-
   level curve, no `base_hp`/`HP_PER_LEVEL` anywhere in src/ or formal/. So even
   `max_hp`/survivability at level L cannot be set without ASSUMING a value.

What IS available (so the infrastructure is NOT the blocker):
- Live monster catalog with full combat stats loads offline
  (`formal/sim/game_data_snapshot.json`: monster_attack/hp/resistance/critical/
  initiative/level; validated vs live in `test_game_data_fixture_diff.py:98`).
- `is_winnable`/`predict_win` run on a hand-built level-L `WorldState`
  (`test_perceive_arm_diff.py` already does, lines 137-180); they read only flat
  fields, no live API needed.
- A level-sweep + real-picker harness already exists (`test_perceive_arm_diff.py:239`)
  — but it is synthetic on BOTH sides (hand-built monster + a fixed character).

## Consequence: WinnableAcrossBand needs a GEAR-PROGRESSION MODEL
To claim "winnable at every band L", the differential must supply, per L, a
realistic **loadout** (at least a weapon, for nonzero damage) AND a base-stat
vector (for hp/survivability). Neither is server-derivable; both must be modeled:

- **Weapon-at-L**: the cleanest proxy is "the best weapon with `item.level ≤ L`
  craftable from the live item catalog" — derivable as a max-attack filter over
  `item_stats` (no full craft-closure needed for an EXISTENCE proxy). This encodes
  the gear-tier guarantee (the bot crafts up the tiers).
- **Base hp/stats-at-L**: must be ASSUMED (e.g. a captured no-gear snapshot per
  level, or the documented level-1 base scaled by the server's level curve — which
  is not in the data). This assumption is irreducible from offline data.

So Option C does NOT cleanly discharge WinnableAcrossBand; it RELOCATES it to two
explicit data assumptions: (i) the gear-tier weapon-at-L model, (ii) the base-stat-
per-L vector. Both become named residuals (LIV-001 class) the differential pins.

## Options (honest)
- **C1 — assumption-pinned differential (MEDIUM, partial).** Build a 1-49 sweep:
  per L, equip the best `item.level ≤ L` weapon (from the live item catalog) + an
  assumed base-hp(L), run production's REAL `is_winnable`/picker vs the live monster
  catalog, assert a winnable in-band target exists ∀L. Outcome: WinnableAcrossBand
  is validated against live data UNDER the two named assumptions (i)(ii). Net: the
  residual set trades one abstract hypothesis for two concrete, differentially-
  checked data assumptions. Modest honesty upgrade; real work to build the loadout
  model; the base-stat assumption stays irreducible offline.
- **C2 — full gear-progression model (LARGE, multi-session).** Model craft-closure
  + skill-gates + equip-choice to derive the bot's actual loadout at each L, then
  prove/validate winnability. No live data reproduces the gear TOTALS without
  replaying crafting, so even this leans on a stat model. Not recommended as a
  near-term path.
- **C3 — accept WinnableAcrossBand as a documented LIV-001-class residual.** The
  level-50 result is already honest: "reaches 50 modulo {LIV-001, WinnableAcrossBand,
  BlockersQuietInfinitelyOften}". WinnableAcrossBand is satisfiable
  (`winnableAcrossBand_satisfiable`) and Brick 6 of the perception-refresh extension
  already differentially CHARACTERIZED it (production arms iff winnable). Documenting
  it as a server-data assumption (like LIV-001) is a defensible stopping point.

## Recommendation
C1 is the only near-term BUILDABLE reduction, but it is assumption-heavy and does
not reach "modulo only LIV-001" — it relocates WinnableAcrossBand to a gear model +
a base-stat assumption. Given that, C3 (document as a residual) is the honest
default, with C1 available if a concrete live-data check is wanted. The clean
"modulo only LIV-001" end-state is NOT reachable without the server exposing base-
stat-per-level data (or a full, assumption-laden gear+stat model). The OTHER
residual, `BlockersQuietInfinitelyOften` (the transience/fairness core), is
independently the harder of the two.

## Status
- 2026-06-18: scoped. Base-stats shortcut found infeasible (attack is gear-derived;
  base stats not server-exposed). Awaiting direction: C1 (assumption-pinned
  differential), C2 (full model, multi-session), or C3 (document as residual).
