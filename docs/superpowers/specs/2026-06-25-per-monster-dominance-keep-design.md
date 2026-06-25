# Per-Monster-Aware Dominance Keep (Part 1) — Design

**Status:** approved-pending-review (brainstorm 2026-06-25)
**Scope:** Part 1 of "opportunistic trading". Make the dominance/keep decision for
weapons and armor judge a piece by its **per-monster** combat score against the
winnable near-level monster set, so a situationally-best low-tier piece is kept
while genuinely outclassed previous-tier gear is sold.

## Problem

`_is_equippable_dominated` (`ai/inventory_caps.py`) drops a piece's keep-cap to 0
(making it sellable/discardable) when an owned same-slot peer has a strictly
higher flat `equip_value` (sum of all attack elements + utility) AND covers its
skill_effects. The flat scalar **loses the element/crit matchup**: `fire_staff`
(L5, fire 16, crit 5) is marked dominated by `iron_sword` (L10, earth 24) even
though fire_staff wins against a fire-weak / earth-resistant monster; a high-crit
low-tier weapon (`copper_dagger`: L1, air 6, **crit 35**) likewise. (Confirmed
against live data: no weapon has poison/DoT — the situational axis is purely
element-vs-resistance and critical_strike, both already captured by the
per-monster `equipment/scoring.weapon_score` / `armor_score`.)

## Design

### 1. Winnable near-level monster set — `ai/combat_targets.py` (new)

`combat_target_monsters(state, game_data, history) -> list[str]`: the codes of
monsters whose level is within a band of the character and that are beatable:

```
LEVEL_BAND_BELOW = 5   # exclude trivially-low monsters we'd never choose to fight

def combat_target_monsters(state, game_data, history=None) -> list[str]:
    out = []
    for code, level in game_data.monster_levels.items():
        if level >= state.level - LEVEL_BAND_BELOW \
           and is_winnable(state, game_data, code, history):
            out.append(code)
    return out
```

Only a BELOW bound is needed — `is_winnable` already excludes monsters too hard to
beat (its `predict_win` arm), so the upper end is the beatability frontier, not a
fixed level offset. `is_winnable` is the existing combat verdict (`ai/combat.py:173`),
`monster_resistance(code)` / `monster_attack(code)` are the confirmed dict
accessors (`game_data.py:567,573`). The result is
MEMOIZED per selection cycle (see §5) — it is recomputed only when state.level or
the equipment changes, because the dominance check is called per inventory item.

### 2. Per-monster score vectors

For each candidate piece and each monster `m` in the set:
- weapon (`type_ == "weapon"`): `weapon_score(piece, game_data.monster_resistance(m))`
  (`Σ attack_elem × (100 − resist_elem%) × (200 + crit)`, exact-int, already proven).
- armor (`type_ in ARMOR_TYPES = {helmet, body_armor, leg_armor, boots, shield}`):
  `armor_score(piece, game_data.monster_attack(m))` (monster attack-element vs
  the piece's resistance + flat utility, exact-int, already proven).

The score VECTOR for a piece is `[score(piece, m) for m in monster_set]` (stable
monster order).

### 3. Pareto-dominated criterion — `ai/dominance_pareto.py` (new proven core)

A peer **Pareto-dominates** a piece iff it scores ≥ on EVERY monster and strictly
higher on at least one:

```
def pareto_dominates(peer_scores: list[int], item_scores: list[int]) -> bool:
    return (all(p >= i for p, i in zip(peer_scores, item_scores))
            and any(p > i for p, i in zip(peer_scores, item_scores)))
```

The piece is **kept** (cap ≥ 1) iff it is the strictly-best choice against at
least one winnable monster — equivalently, NOT Pareto-dominated by enough owned
peers to fill its slots. This feeds the EXISTING proved fold
`_is_dominated_pure(peers, slot_count)` (owned qualifying-peer count ≥ slot_count)
UNCHANGED — only the per-peer `higher` verdict changes from `equip_value`-higher
to `pareto_dominates(peer_vec, item_vec)`.

### 4. Shell wiring — `_is_equippable_dominated`

```
monsters = combat_target_monsters(state, game_data, history)   # memoized
if not monsters or stats.type_ not in (WEAPON ∪ ARMOR_TYPES):
    <fall back to today's flat equip_value dominance — unchanged>
else:
    item_vec = score_vector(item, monsters)
    for peer:  higher = pareto_dominates(score_vector(peer, monsters), item_vec)
    return _is_dominated_pure([(fits, higher, covers, owned) …], slot_count)
```

Empty monster set (nothing winnable near level — e.g. very low or very high
character level) → flat `equip_value` fallback, so there is NO behavior change
until the bot has real combat targets. Rings/amulets/artifacts/utility/bag keep
the flat-`equip_value` path (not "armor"; mixed-stat — out of scope).

### 5. Performance (CPU is a known sensitivity)

`_is_equippable_dominated` runs per inventory item inside `useful_quantity_cap`,
which runs per item in `overstocked_items` / `bank_drain` / accumulation. To avoid
an O(items × peers × monsters) blowup each cycle:
- `combat_target_monsters` is memoized on a `(state.level, equipment-signature)`
  key (a small dict cache on GameData or a per-cycle token).
- `monster_resistance` / `monster_attack` are static catalog reads (already cached
  in GameData).
- If profiling still shows a hotspot, precompute each owned weapon/armor's score
  vector once per cycle and pass the map in (a follow-up; not in the first cut).

## Components

| File | Responsibility |
|---|---|
| `ai/combat_targets.py` (new) | `combat_target_monsters` — winnable near-level set, memoized |
| `ai/dominance_pareto.py` (new) | `pareto_dominates` pure core + `score_vector` helper |
| `ai/inventory_caps.py` (modify) | `_is_equippable_dominated` per-monster path + flat fallback |
| `formal/Formal/DominancePareto.lean` (new) | `paretoDominates` def + theorems |
| `formal/diff/test_dominance_pareto_diff.py` (new) | core differential |

## Error handling / safety

- Empty monster set → flat fallback (no change). Missing monster_resistance/attack
  → use only API data (the accessors raise on unknown — `predict_win`'s contract).
- Never sell an EQUIPPED piece (the equipped-floor of 1 in `useful_quantity_cap_pure`
  is downstream and unchanged).
- A piece best vs ≥1 winnable monster is kept even if low flat value — the whole point.

## Theorem roles (`DominancePareto.lean`)

- `pareto_implies_geq` — `paretoDominates peer item ⇒ ∀ k, item[k] ≤ peer[k]`
  (a kept piece is never beaten everywhere — the keep is sound).
- `pareto_irreflexive` — `¬ paretoDominates v v` (a piece never dominates itself;
  with `_is_dominated_pure` this stops a single unique piece being sold).
- `pareto_needs_strict` — `paretoDominates peer item ⇒ ∃ k, item[k] < peer[k]`
  (equal-everywhere peers do NOT dominate → ties keep one via EQUIPPABLE_KEEP).

These bind through `test_dominance_pareto_diff.py` (real `pareto_dominates` +
`score_vector` vs the Lean oracle) + mutation anchors (drop the `all`, drop the
`any`, flip ≥/>). The proved `_is_dominated_pure` fold and `weapon_score`/
`armor_score` cores are reused unchanged.

## Testing

- Unit (`tests/test_ai/test_per_monster_dominance.py`): `combat_target_monsters`
  level-band + winnable filter; `pareto_dominates` truth table; `score_vector`;
  `_is_equippable_dominated` — fire_staff NOT dominated by iron_sword when a
  fire-weak monster is in the set; copper_dagger (crit) kept; a strictly-outclassed
  weapon (same element, lower attack+crit) IS dominated; empty-set flat fallback;
  armor symmetry; equipped-piece never zero. 100% coverage.
- Formal: full `formal/gate.sh` green.

## Out of scope

- Rings / amulets / artifacts / utility / bag (mixed-stat; flat `equip_value`).
- Changing `weapon_score` / `armor_score` / `predict_win` / `pick_loadout`.
- Precomputed per-cycle score-vector threading (perf follow-up if profiling needs it).
- Modelling player-inflicted DoT (no such weapon effect exists in the live API).

## Constants (confirmed)

| Constant | Value | Meaning |
|---|---|---|
| `LEVEL_BAND_BELOW` | 5 | monsters this far below char level still count (upper end = beatability frontier via `is_winnable`) |
| keep criterion | strictly-best-vs-some | Pareto: kept iff not out-scored-or-tied everywhere |
