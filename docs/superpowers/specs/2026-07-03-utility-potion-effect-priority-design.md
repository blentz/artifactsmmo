# Utility-Potion Effect-Based Priority — Design

**Date:** 2026-07-03
**Status:** Approved (design)
**Branch target:** new branch off `main`

## Problem

At character level 10 the strategy arbiter froze character progression behind a
~30-level alchemy skill grind for a single utility-slot potion.

Trace evidence (`play-trace-Robby.jsonl`, 47.6 h, char level 10, alchemy 16):

```
chosen_root  = ObtainItem(code='enhanced_health_potion', quantity=1, slot='utility1_slot')  category=gear  contribution=2.5  cost=8
chosen_step  = ReachSkillLevel(skill='alchemy', level=45)
planner      = projected_cycles_to_max="inf",  path_blocked=true
```

`enhanced_health_potion` requires **alchemy craft level 45**; the character was
at **alchemy 16**. The bot ground alchemy XP by craft-spamming low recipes and
discarding the output — 34 `recall_potion` crafts + 58 `recall_potion` deleted,
116 `small_health_potion` crafts, `recall_potion` target climbing 11→67→147.
Meanwhile a working `small_health_potion` (alchemy level 5) was already equipped
in the utility slot and stocked.

### Root cause

Two independent contributors, both traceable to one category error — **treating
a consumable utility slot as best-in-slot-by-value, the way armor is treated.**

1. **Aspirational root.** `CharacterObjective.from_game_data` builds `target_gear`
   by `equip_value` ranking over **every** item type in `ITEM_TYPE_TO_SLOTS`,
   including `utility`. Live probe at char 10:
   - `target_gear[utility1_slot] = enhanced_health_potion` (level 45)
   - `target_gear[utility2_slot] = health_boost_potion`
   These endgame-BiS roots survive Tier-2 filtering because alchemy 45 is
   *reachable* (grindable), so they are never pruned.

2. **Unbounded urgency.** `strategy.py:576-581` applies `POTION_SUPPLY_URGENCY`
   (`= EMPTY_SLOT_URGENCY * PRIOR_COMBAT_GEAR / PRIOR_UTILITY_GEAR = 6.25`,
   times `PRIOR_UTILITY_GEAR = 2/5` → contribution **2.5**) to **any** utility
   `hp_restore` root whose equipped quantity is below the level-scaled baseline.
   It lacks the craftable-now gate that `target_potion_pure` already has
   (`potion_supply.py:47`). So the aspirational `enhanced_health_potion` root
   rides the 2.5 boost meant only to break the small alchemy-1→5 bootstrap
   deadlock, and becomes `chosen_root`, driving `ReachSkillLevel(alchemy, 45)`.

Gear `score == contribution` (cost is not a divisor for gear — confirmed at
`strategy.py:678` / `_learned_blend` returns value unchanged for gear), so the
under-counted `cost=8` is a red herring; the 2.5 urgency is the sole lever.

### Live root enumeration (probe, char 10 / alchemy 16)

| source | utility1 root | judged by |
|---|---|---|
| `target_gear` (BiS) | `enhanced_health_potion` (lvl 45) | `equip_value` |
| `target_gear` | `health_boost_potion` (utility2) | `equip_value` |
| `near_term_gear` | `small_health_potion` | craftable-now |
| `target_potion_pure` | `small_health_potion` | effect + craftable-now |

Both `enhanced` (target_gear) and `small` (near_term_gear) roots are emitted and
both receive the 2.5 urgency; `enhanced` wins the tiebreak. At bootstrap
(char 3 / alchemy 1) the probe shows **no** utility root from either armor
enumerator (`near_term_gear` level-gates `small` out; `target_potion_pure` is
`None`) — the only utility root present is the aspirational `enhanced` from
`target_gear`, which is why the original bootstrap urgency grinds toward 45.

## Principle

Utility / consumable slots are judged by **effect adequacy**, not by level-based
best-in-slot. A basic heal potion is the correct answer for a long time. The bot
levels the crafting skill *incidentally* over time, and only pursues a stronger
potion tier when the current tier is **inadequate** (a full stack cannot win a
required fight) or the **marginal utility** of stronger healing clears the grind
cost. Armor and weapons keep their level-based BiS progression unchanged.

## Phase 1 — Stop the premature grind (implement)

### 1. Level-exempt potion target

Add to `potion_supply.py`:

```python
def bootstrap_potion_target(state, game_data, effect="hp_restore") -> str | None:
    """The utility heal to pursue: the effect-best potion craftable NOW, or —
    when none is craftable yet — the cheapest-to-unlock heal (min crafting_level)
    so the arbiter can drive the first skill unlock. Level-exempt: a potion's
    item level never gates its selection (potions judged by effect, not level)."""
    craftable = target_potion_pure(state, game_data, effect)
    if craftable is not None:
        return craftable
    return _cheapest_heal_potion(game_data, effect)  # min crafting_level, tie by code
```

`_cheapest_heal_potion` scans `game_data.crafting_recipes` for `type_ == "utility"`
items with `getattr(stats, effect, 0) > 0` and a non-None `crafting_skill`,
returning the one with the smallest `crafting_level` (deterministic smallest-code
tie-break). This is the "next tier to ever unlock" and bounds the bootstrap grind
to that tier's craft level (e.g. `small_health_potion` → alchemy 5), never 45.

### 2. Emit the potion root; remove utility from armor enumerators

- `prerequisite_graph.objective_roots`: emit
  `ObtainItem(code, slot=slot)` for `slot, code` in a new
  `objective.utility_potion_targets(state)` — which returns
  `{utility1_slot: bootstrap_potion_target(state, gd)}` when that target is
  non-None. Present at **every** character level, including bootstrap.
- `CharacterObjective.from_game_data`: **skip `type_ == "utility"`** when building
  `target_gear`. Kills the `enhanced_health_potion` / `health_boost_potion`
  aspirational roots.
- `CharacterObjective.near_term_gear`: **skip `type_ == "utility"`**. The
  dedicated potion root above now covers utility at all levels; the armor
  enumerator handles armor/weapon/tool only.

Rationale for a dedicated source rather than reusing `near_term_gear`: potions
are level-exempt (judged by effect); `near_term_gear`'s `stats.level <= state.level`
filter is an armor rule and would still wrongly drop the bootstrap potion at
low char level. Keeping potion selection in the supply module also preserves the
single-source-of-truth already shared by the CRAFT_POTIONS guard and
`CraftPotionsGoal`.

### 3. Gate the urgency

`strategy.py:576-581` — fire `POTION_SUPPLY_URGENCY` only when the root is the
supply target:

```python
elif (stats.type_ == "utility"
        and stats.hp_restore > 0
        and root.code == bootstrap_potion_target(state, game_data)
        and equipped_potion_qty(state, root.code) < potion_baseline_pure(...)):
    marginal = max(marginal, Fraction(1)) * POTION_SUPPLY_URGENCY
```

With the aspirational roots removed (step 2) this is belt-and-suspenders, but it
keeps the invariant explicit and guards against any other utility heal root ever
being enumerated.

### Expected behavior after Phase 1

- **Char 10 / alchemy 16:** potion root = `small_health_potion`; urgency stocks
  the baseline stack; once met, `equipped >= baseline` stops the urgency;
  char-leveling (2.25) and smaller skill grinds (~2.04) win. The
  `enhanced_health_potion` root no longer exists.
- **Bootstrap (char 3 / alchemy 1):** potion root = cheapest heal
  (`small_health_potion`, level-exempt); urgency drives
  `ReachSkillLevel(alchemy, 5)`; the CRAFT_POTIONS guard takes over once alchemy
  reaches 5. Never grinds past the cheapest tier.

## Phase 2 — Adequacy-driven tier-up (design only, not implemented here)

Pursue a *stronger* potion tier (grind its craft skill) only when one holds:

- **(a) Inadequacy.** With a full baseline stack of the current best-craftable
  potion equipped, `predict_win` is still `False` for an in-band monster the bot
  must beat for progression/survival. Requires potion-stack-aware `predict_win`
  (credits N potions of `hp_restore` across a fight) and the in-band monster set.
- **(b) Marginal-worth.** The strategic-value gain of the next tier exceeds the
  grind cost, gated by a skill-gap horizon analogous to
  `CHAR_REACHABLE_HORIZON` — the tier-up root scores above competing smaller
  grinds only when `gain / (skill_gap × per_level_cost)` clears a threshold.

Mechanism sketch: a distinct `POTION_TIERUP_URGENCY` that fires on the
next-tier potion root (min `crafting_level` strictly above the current best
craftable) only when (a) or (b) holds; otherwise that root sits at its base gear
score. Deferred: needs combat-model work (`predict_win` with a potion stack) and
a worth threshold, and its own differential + mutation coverage.

## Testing / gate

- Success criteria per repo: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- New pure cores (`bootstrap_potion_target`, `_cheapest_heal_potion`) get unit
  tests in `tests/`.
- Strategy scoring carries Lean proofs (`Formal.GearPolicy`). Utility is not in
  `_combat_gear_slots`, so the empty-slot armor-dominance proofs are expected
  untouched; but removing `utility` from `target_gear` changes `gap()` /
  `gear_fraction`, so the differential + mutation gate (`gate.sh`) must be
  re-run and any anchor drift refreshed. Serialize gate runs (no concurrent bot
  / src imports).
- Regression: replay the Robby scenario (char 10, alchemy 16, small stocked) and
  assert `chosen_root` is char-level or a small skill grind — never
  `ObtainItem(enhanced_health_potion)`.

## Files touched (Phase 1)

- `src/artifactsmmo_cli/ai/potion_supply.py` — add `bootstrap_potion_target`,
  `_cheapest_heal_potion`.
- `src/artifactsmmo_cli/ai/tiers/objective.py` — skip `utility` in `target_gear`
  (`from_game_data`) and `near_term_gear`; add `utility_potion_targets`.
- `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` — emit utility-potion
  roots in `objective_roots`.
- `src/artifactsmmo_cli/ai/tiers/strategy.py` — gate `POTION_SUPPLY_URGENCY`
  branch on `root.code == bootstrap_potion_target(...)`.
- `tests/` — unit tests for the new cores + Robby regression.
