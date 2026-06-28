# Sub-project 2 — Unified Value Ruler — Design

**Status:** approved (brainstorm 2026-06-28) · **Epic:** Holistic Gear-Loadout
Architecture (`2026-06-28-gear-loadout-architecture-design.md`, on main).
**Branch:** `feat/gear-unified-ruler` (off main = gear sub-project A merged, tip `f5eabf71`).
**Build order:** sub-project 2 of 5 (A ✅ → **unified ruler** → B → {C, D}). The riskiest
sub-project — re-proves the value cores.

## Why

Gear value is computed by a **family of overlapping, partly-divergent** functions. The
headline bug: the delete-dominance gate (`inventory_caps._equip_value`) scores gear on a
**strictly weaker ruler** than selection (`tiers/equip_value.equip_value`) — it omits `dmg`
and `critical_strike`. So a higher-dmg/crit item wins at selection but cannot dominate at
the gate. Three monster-independent "raw" sums exist; only `_equip_value` diverges:

| | combat stats summed | efficiency stats | ×2 / nonToolBonus |
|---|---|---|---|
| `equip_value` (tiers) | atk,res,hp_restore,hp_bonus,**dmg,crit**,lifesteal,combat_buff | wisdom,prosp,inv,haste (1:1) | yes |
| `_equip_value` (inventory_caps) | atk,res,hp_restore,hp_bonus,lifesteal,combat_buff (**no dmg/crit**) | wisdom,prosp,inv,haste (1:1) | no |
| `strategic_value.combat_raw` | atk,res,hp_restore,hp_bonus,**dmg,crit**,lifesteal,combat_buff | split out, separately weighted | n/a |

`strategic_value` and `equip_value` already agree on the same 8-stat **`combat_raw`**.
Unify on it: one shared atom, one dispatch `gear_value(stats, purpose)`, every consumer
routed through it.

## Scope (approved decisions)

- **Rank-unify + define purposes.** Collapse the two monster-INDEPENDENT rulers
  (`equip_value` + `_equip_value`) into `gear_value(stats, Rank)`, fixing the dmg/crit
  divergence, and route all 9 rank/dominance consumers through it. Introduce the `purpose`
  type and DEFINE+PROVE `Combat`/`Gather` purposes, with the existing per-monster scorers
  (`weapon_score`/`armor_score`/`gather_score`) becoming thin specializations over
  `gear_value` — so `pick_loadout`/`pick_gather` **call sites stay byte-identical**.
  Generalizing those pickers' *signatures* to per-task purposes is sub-project **B**.
- **`strategic_value` stays a separate economics layer that SHARES the `combat_raw`
  primitive.** It keeps its per-stat efficiency weights + budget cap + horizon scaling, but
  its `combat_raw` input becomes the one shared `combat_raw` def — divergence into a third
  ruler becomes structurally impossible. Not folded into `gear_value` (weights/budget/horizon
  are economic policy, a different concern from raw-stat value).

## Core architecture

- **`combat_raw(stats) -> int`** = `attack + resistance + hp_restore + hp_bonus + dmg +
  critical_strike + lifesteal + combat_buff` (attack/resistance are the element-dict sums).
  THE single genuine-combat signal every ruler builds on. This is the dmg+crit fix:
  `_equip_value` omitted exactly `dmg` and `critical_strike`.
- **`gear_value(stats, purpose) -> int`**, `purpose ∈`:
  - **`Rank`** = `2 * (combat_raw + wisdom + prospecting + inventory_space + haste) +
    nonToolBonus`, `nonToolBonus = 0 if subtype == "tool" else 1`. The unified
    monster-independent ruler (bit-identical to today's `equip_value`).
  - **`Combat(monster_attack, monster_resistance)`** = type-dispatched per-monster scorer:
    `weapon` type → offense `(Σ atk·max(0,100−res%)) · (200+crit)` augmented `2·raw +
    nonToolBonus` (today's `weapon_score`); else → defense `Σ monster_atk·res% +
    hp_bonus + wisdom + prospecting + inventory_space + haste + lifesteal + combat_buff`
    (today's `armor_score`).
  - **`Gather(skill)`** = signed `skill_effects.get(skill, 0)` (today's `gather_score`;
    pickers minimize it).
- `gear_value` is the proved CORE. `equip_value`, `weapon_score`, `armor_score`,
  `gather_score`, `inventory_caps._equip_value` become specializations/wrappers over it;
  call sites unchanged.

## Consumer migration + the one behavior change

- **Rank consumers (9 sites)** → `gear_value(stats, Rank)`:
  - 7 `equip_value` callers (unchanged behavior — Rank is bit-identical to `equip_value`):
    `tiers/objective.py:230,276,300`, `tiers/strategy.py:368`,
    `tiers/prerequisite_graph.py:37`, `goals/progression.py:477`,
    `progression_reserve.py:59-65`.
  - 2 `_equip_value` dominance-gate callers: `inventory_caps.py:301,321`.
- **`strategic_value`** → its `combat_raw` argument is supplied by the shared `combat_raw`
  def; weights/budget/horizon unchanged. Consumer `strategy._equip_gain` (decide_key
  protection field) unchanged.
- **Combat/Gather consumers** (`equipment/scoring.pick_loadout`/`pick_gather_loadout`,
  `inventory_caps._score_vector`) → call sites unchanged; the scorers delegate to
  `gear_value`.

**The one documented behavior change:** the delete-dominance gate now scores on `dmg` +
`critical_strike` (the real fix — a higher-dmg/crit item can finally dominate a peer) plus
the `nonToolBonus` tiebreak. Safe because the gate ALREADY separately requires a dominating
peer to cover the dominated item's `skill_effects` (the tool-coverage guard in
`_is_equippable_dominated`), so a non-tool cannot dominate a tool whose gather value isn't
otherwise covered. Regression-tested with an explicit case.

## Formal lockstep (re-proof scope — the heaviest in the epic)

The *formulas don't change* (Rank = today's `equip_value`; Combat/Gather = today's scorers);
the proofs are **restatements over the unified `combat_raw` core** plus two genuinely-new
results. No role theorem is weakened.

- **`combat_raw`** — new `def` + a "Rank monotone non-decreasing in combat_raw" lemma.
- **`EquipValueAugmented` (Rank)** — `equipValue_strict_of_strict_raw`,
  `equipValue_tiebreaks_nontool_over_tool`, restated on `gear_value(·, Rank)`; add
  per-stat **monotonicity**.
- **`EquipmentScoring` trio (Combat/Gather)** — `weapon_score_nonneg`, `armor_score_nonneg`,
  `pickslot_score_optimal`, `pickGatherSlot_score_optimal` restated as the `Combat`/`Gather`
  branches of `gear_value`; `pick_loadout` optimality rides on `gear_value(·, Combat)`.
- **`StrategicValue`** — `strategicValue`'s `combat_raw` input is the shared def;
  `strategicValue_nonneg` + per-stat monotonicity kept; `Bridges9` re-pinned.
- **`PurposeRouting`** — align its `combatScore`/`gatherScore` as the Combat/Gather dispatch
  (natural home for the purpose split).
- **`DecideKey`** — unchanged (consumes `strategic_value`'s protection delta; interface
  stable). Verify its `Contracts.lean` example still elaborates.
- **Extraction/bridges**: regenerate `Extracted/EquipValue`, `Extracted/EquipmentScoring`,
  `Extracted/StrategicValue`; re-pin `Bridges7/8/9`. `Contracts.lean` exact-pins for every
  restated theorem; `Manifest.lean` roster updated.
- **Differential**: `gear_value` (all 3 purposes) ≡ oracle on random `(stats, monster_attack,
  monster_resistance, skill)`. **Mutation**: drop each `combat_raw` summand, the
  `nonToolBonus`, and each per-purpose term — every mutant must die.

## Module layout

- **`ai/gear_value_core.py`** (pure, extracted, proved): `combat_raw(...)`,
  `gear_value(fields, purpose)`, and the purpose value-objects (`Rank`, `Combat`, `Gather`
  — pure data, share the module per the one-class-per-file data exemption).
- **`ai/gear_value.py`** (wrapper): `ItemStats`→core adapter; re-exports `equip_value`,
  `weapon_score`, `armor_score`, `gather_score` as `gear_value` specializations so existing
  imports keep working unchanged.
- `tiers/equip_value.py`, `inventory_caps._equip_value`, `equipment/scoring.py`,
  `tiers/strategic_value.py` → delegate to the core (keep their public names).
- Watch the import layering: `gear_value_core.py` is a leaf (plain data); `gear_value.py`
  imports `ItemStats` (leaf) only — no cycle with `game_data`/`inventory_caps`/`tiers`.

## Testing & rollout

- **Regression lock**: `gear_value(Rank)` reproduces today's `equip_value` integer ordering
  on all live items; `Combat`/`Gather` reproduce today's `pick_loadout`/`pick_gather` picks
  EXACTLY (no loadout changes — only the dominance gate's behavior changes).
- **Documented change test**: a case where an item with higher dmg/crit now dominates at the
  delete gate where it didn't before, and a case proving the `skill_effects`-coverage guard
  still blocks a non-tool from dominating an un-covered tool.
- Full unit suite ≥ current bar (100%); full `formal/gate.sh` green; serialize gate/mutation
  vs a live `artifactsmmo play`.

## Out of scope / non-goals (→ later sub-projects)

- Generalizing `pick_loadout`/`pick_gather` *signatures* to per-task purposes;
  `PurposeRouting` task→purpose mapping; the bounded `predict_win` local-search improver — all
  sub-project **B**.
- Profiles / dedup / bank-space (C); learned per-monster loadout (D); modeling the 9 carved
  rune abilities (the "Player rune abilities" follow-on).
- Re-deriving the deferred efficiency-stat weights (inventory_space/haste) — they keep their
  current parity hold; this sub-project only unifies the `combat_raw` plumbing.
