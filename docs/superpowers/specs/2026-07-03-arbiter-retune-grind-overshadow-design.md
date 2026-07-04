# Arbiter Retune — Grind Overshadow Fixes — Design

**Date:** 2026-07-03
**Status:** Approved (design)
**Branch target:** new branch off `main`

## Problem

Offline weight-landscape analysis (`StrategyEngine.decide` sweep + `plan Robby`,
harness pattern recorded in memory `project_tuning_analysis_grind_overshadow`)
found that grind goals overshadow legitimate goals, and the L50 capstone has no
gradient. The base ranking is healthier than a naive read suggests — when fully
geared with a real combat target, `ReachCharLevel(+2)=2.25` beats skill-grind
`2.04`, and an empty armor slot draws `EMPTY_SLOT_URGENCY=2.5`. The overshadowing
is mechanism-driven and specific:

1. **Occupied-slot gear upgrades are blind.** `iron_boots` (a ~5× stat-value gain
   over the equipped `copper_boots`) scores a flat **1.0**: `EMPTY_SLOT_URGENCY`
   (2.5) requires `current_code is None` (fails on any filled slot), and the
   marginal clips at `min(1, gain/GEAR_EQUIP_SCALE)`. So a filled slot can never
   out-score grinds or char-level. The bot wears starter copper forever. Weapon
   `COMBAT_READINESS` has no level gate; armor `EMPTY_SLOT` has a strict one —
   an inconsistency. (strategy.py:545-567)
2. **Skill-grind saturation.** `2.04 = PRIOR_COMBAT_CRAFT_SKILL(3/5) ×
   marginal(17/10) × balancing(2)`. Two ceilings hit simultaneously:
   `SKILL_GAP_CAP=3/2` (any gap≥2) and `BALANCE_MAX=2` (gather skills self-level,
   so crafting is perpetually "behind the leader"). Flat across all levels.
   `next_tier_cap` dampens the *step* (→NO_GRIND), not the root score.
   (strategy.py:534-544, strategy_blend.py:31-50)
3. **Sticky-lock.** `STICKY_DOMINANCE_RATIO=3/2`: a committed skill-grind (2.04)
   needs a challenger >3.06 to displace; even geared char-level (2.25) can't. A
   single `combat_monster=None` window (ungeared char 1.48 < skill 2.04) lets a
   grind win once, then locks. (strategy.py:124)
4. **No L50 capstone gradient.** `ReachCharLevel(50)` scores a flat **1.0** from
   L10→L48 — `CHAR_REACHABLE_HORIZON=10` is a hard cliff (gap 40 → reach 0 → no
   bonus). Only a `+2` bootstrap competes; the capstone is never directly
   pursued. (strategy.py:521-533, prerequisite_graph.py:140-146)
5. **CraftPotions guard lies about plannability.** `_recipe_producible`'s
   gatherable tier uses `any(mat gatherable)` instead of per-ingredient
   all-obtainable → the guard fires on a boost recipe the planner can't complete
   → `plan Robby` shows `CraftPotionsGoal: 149 nodes → NO PLAN` every cycle,
   violating the guard's stated "exclusive gating truth." (potion_supply.py:95-110)
6. **Geared-gate premise keys on the wrong gear set.** `_has_empty_armor_slot`
   iterates endgame `target_gear` (BiS, high-level) with `stats.level ≤
   state.level` → reports "geared" even when a near-term armor slot is empty
   (BiS not level-usable yet). (strategy.py:443-458)

## Principle

Gear up before grinding; keep skill-grind urgency proportional to how far a skill
trails its just-in-time recipe curve; give the L50 capstone a weak but real
midgame attractor. Preserve the proven invariants: empty-slot armor dominance
(GearPolicy) and leveling liveness (`GrindCharacterXP` still fires).

## Combined-tuning validation (already run)

Baseline-vs-tuned sweep (`scratchpad/sweep_tuned.py`, a `StrategyEngine` subclass
overriding `_marginal`) confirmed the combined ①②④ landscape:

| state | BASE chosen | TUNE chosen |
|---|---|---|
| L10 geared | `ReachCharLevel(12)` 2.25 | **`iron_boots` 2.5** (re-gears) |
| L10 ungeared | `iron_boots` 2.5 | `iron_boots` 2.5 (unchanged) |
| L25 geared | `ReachCharLevel(27)` 2.25 | **`iron_boots` 2.5** |
| L40 geared | `gearcrafting→40` **2.04** (grind!) | **`iron_boots` 2.5** |

Skill grinds recede to 1.1–1.9 (below char/gear); gear-first preserved. Sticky
check: gear (2.5) breaks a committed gearcrafting lock at L10; a deeply-lagging
skill (weaponcrafting 2→25, decays little → ~1.9, threshold 2.85) can still lock
IF it arms sticky. Correction: a lagging near-term skill at `current=1` with a
runaway leader (balancing=2) reaches ~1.86, which DOES exceed the *ungeared*
char bootstrap (1.48) — so it can win outright and arm sticky in a
`combat_monster=None` / empty-armor window (not "never"). But ②'s progress-decay
makes the lock SELF-RELEASING: as the committed skill levels toward its target,
its value decays toward ~0.24, dropping below char-level so the sticky hold
breaks. Combined with ①'s self-limiters this cannot become a permanent livelock
(corroborated by the green liveness axiom check). This is the deferred ③
residual — revisit `StickySelect` only if live traces show a real lock.

## Changes

### ① Occupied-slot upgrade urgency (strategy.py `_marginal`, ObtainItem branch)

New constant `OCCUPIED_SLOT_UPGRADE_URGENCY = Fraction(5, 2)`. Add a branch AFTER
the `EMPTY_SLOT_URGENCY` branch. Note: empty and occupied-upgrade both score
`5/2`, so this is not a strict-score priority — the two apply to *different*
roots (different slots) and tie at 2.5, separated by the equip-value-gain
tiebreak. An empty slot's gain is the item's full strategic value while an
occupied upgrade's is a delta, so empty usually wins the tiebreak (not
guaranteed). This does not affect the proven `armor_strictly_dominates_empty_slot`
theorem (beating the do-nothing baseline, not empty-vs-occupied):

```python
elif (slot in self._combat_gear_slots(game_data) and slot != "weapon_slot"
        and current_code is not None
        and stats.level <= state.level
        and gain >= GEAR_EQUIP_SCALE):        # >= 2x the fixed-point scale
    marginal = max(marginal, Fraction(1)) * OCCUPIED_SLOT_UPGRADE_URGENCY
```

The `gain >= GEAR_EQUIP_SCALE` gate makes only large (~2×) upgrades fire; per-tier
gains shrink as gear improves, so the urgency self-limits and char-leveling
resumes once the bot is well-geared. **Ordering decision (approved):
gear-before-level** — an occupied 2× upgrade (2.5) outranks geared char-level
(2.25).

### ② Skill-grind progress-decay (strategy.py `_marginal`, ReachSkillLevel)

```python
current = state.skills.get(root.skill, 1)
gap = max(0, root.level - current)
progress = Fraction(current, max(1, root.level))
boost = (1 - progress) * min(Fraction(gap), SKILL_GAP_CAP) * SKILL_GAP_PER_LEVEL
return SKILL_MARGINAL + boost
```

Predicted (prior 3/5, balancing 2): skill=1/target=10 → 0.93; skill=5/10 → 1.14;
skill=8/10 → 0.60 — all below char-level. The endgame `root.level >=
max_skill_level` branch is unchanged.

### ④ Capstone gradient (strategy.py `_marginal`, ReachCharLevel)

New constant `CHAR_CAPSTONE_SCALE = Fraction(2, 5)`. When the gap exceeds the
reachable horizon (the capstone case), return a progress-scaled attractor:

```python
gap = max(0, root.level - state.level)
if gap >= CHAR_REACHABLE_HORIZON:   # >= (gap==10 is degenerate reach=0; keeps v40==33/25)
    return CHAR_MARGINAL + Fraction(state.level, root.level) * CHAR_CAPSTONE_SCALE
```

Scores 1.08/1.20/1.32 at L10/25/40 — a weak pull that stays below the +2
bootstrap (1.48) so it never triggers the e27779e items-task stand-down, and
below `EMPTY_SLOT_URGENCY` so gear-first holds. The existing `reach`/`per_level`
path (gap ≤ horizon, e.g. the +2 bootstrap) is unchanged.

### ⑤ Recipe-producible fix (potion_supply.py `_recipe_producible`)

Restructure the three independent tiers so each ingredient must be individually
satisfiable by (inventory+bank) OR (gold-buyable) OR (gatherable):

```python
def _recipe_producible(recipe, state, game_data):
    bank = state.bank_items or {}
    def obtainable(mat, qty):
        if state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty:
            return True
        if any(c == "gold" for _n, _p, c in game_data.npc_purchases(mat)):
            return True
        return mat in set(game_data.resource_drops.values())
    return all(obtainable(mat, qty) for mat, qty in recipe.items())
```

Restores the guard's exclusive-gating invariant: it fires only when every
ingredient has a plannable acquisition edge. The 149-node no-plan search
vanishes at states like Robby's.

### ⑥ Geared-gate premise (strategy.py `_has_empty_armor_slot`)

Consult the near-term usable targets, not just endgame BiS. Iterate
`self.objective.near_term_gear(state)` (already keyed to `stats.level <=
state.level`) for combat armor slots; return True when such a slot is empty. This
makes the geared gate report ungeared while a near-term armor slot is unfilled,
so `EMPTY_SLOT_URGENCY` (or ①) fills it before char-level rises. Lower practical
impact (2.5 already beats char 2.25) but corrects the gate's premise. Must
re-validate with the sweep that it does not spuriously flip geared→ungeared for
fully-equipped states.

### Deferred ③

No code change. Documented residual: a deeply-lagging skill that arms sticky in a
no-gear/no-combat window can still lock (threshold 2.85 > gear 2.5). ② makes this
arming rare. Revisit `StickySelect` (Lean-proven) only if live traces show a real
lock.

## Formal / proof impact

- **No new theorems; no existing theorem broken.** `RankingComposition.lean`
  proves structural properties (`value = base × marginal × balancing`, monotone
  in marginal, positive-marginal-beats-zero-baseline, `armor_root_outranks_empty_baseline`).
  Every changed marginal stays strictly positive, so these hold. This is policy
  tuning within the proven composition — the same category as `EMPTY_SLOT_URGENCY`
  and `BAG_SLOT_URGENCY`.
- **GearPolicy** empty-slot dominance theorems (`armor_weakly/strictly_dominates_empty_slot`)
  are about `armor_score` (strategic value), not the `_marginal` urgency
  multipliers — unaffected by ①. Verify no premise references the urgency ordering.
- **Strategy differential** (`test_strategy_traversal_diff.py`) tests the
  *traversal* pure core, not the scoring — untouched by these `_marginal` edits.
- **Mutations:** update `STRATEGY_MARGINAL_MUTATIONS` anchors (they match literal
  `_marginal` source lines that move); add a new own-group mutation per change
  (①②④⑤⑥), each bound to its unit test (bag-slot lesson — not folded into the
  traversal-diff `STRATEGY_MUTATIONS`).
- **Liveness verify (load-bearing):** confirm ① (gear preempts char-level) does
  not starve `GrindCharacterXP` — `LevelingDescent` / `WinnableAcrossBand`
  require leveling to fire eventually. Because the ① urgency self-limits (gain <
  scale once well-geared), leveling resumes; confirm the proofs' fairness/measure
  assumptions still hold and re-run the liveness axiom check.

## Testing / gate

- Success criteria (repo bar): 0 errors, 0 warnings, 0 skipped, 100% coverage;
  `mypy src` clean; `./formal/gate.sh` green (serialized).
- Per-change unit tests in `tests/test_ai/` asserting the new scores (① iron_boots
  1.0→2.5; ② decay values; ④ capstone 1.08/1.20/1.32; ⑤ producible all-tier; ⑥
  ungeared when near-term slot empty).
- **Sweep regression:** a committed offline test that pins the tuned ranking at
  representative states (the BASE→TUNE table above), so a future edit that
  re-introduces the flat 2.04 or the occupied-slot blindness fails.
- **Live runtime verification (mandatory — green tests ≠ runtime-active,
  `feedback_verify_runtime_activation`):** run `uv run artifactsmmo plan Robby`
  after the change and confirm (a) an occupied-slot upgrade or capstone-gradient
  root actually appears/wins as expected, and (b) `CraftPotionsGoal` no longer
  reports `149 nodes → NO PLAN`.

## Files touched

- `src/artifactsmmo_cli/ai/tiers/strategy.py` — 2 new constants; `_marginal`
  (①②④); `_has_empty_armor_slot` (⑥).
- `src/artifactsmmo_cli/ai/potion_supply.py` — `_recipe_producible` (⑤).
- `formal/diff/mutate.py` — update `STRATEGY_MARGINAL_MUTATIONS`; add per-change
  mutation groups bound to unit tests.
- `tests/test_ai/` — unit tests + sweep regression.

## Out of scope

- ③ explicit sticky exemption (deferred; touches `StickySelect.lean`).
- Personality-specific retuning (BalancedPersonality only).
- Re-deriving `GEAR_EQUIP_SCALE` / prior constants — this retune works within them.
