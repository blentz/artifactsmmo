# Equipment Profiles — Design

Date: 2026-07-08
Status: approved (design); implementation via phased plan
Builds on: the progression-tree selector (2026-07-06) and the dormant,
proven `strategic_value` scorer.

## Problem

`equip_value` (`tiers/equip_value.py` → `gear_value_core.rank_value`) is a
single unified ruler that sums combat stats (attack, resistance, hp_restore,
hp_bonus, dmg, critical_strike, lifesteal, combat_buff) AND utility stats
(wisdom, prospecting, inventory_space, haste) at **equal weight** (all ×2 in
the Rank ruler). The progression tree's gear branch scores every candidate
through it (`_structural_candidates` gain, `near_term_gear`), so a
high-utility, combat-weak item outranks a real weapon: the GAP-2 review
found `perfect_pearl` (prospecting 201) dominating artifact slots fleet-wide;
earlier probes showed `wolf_ears`/`mushmush_bow`/`old_boots` outranking real
weapons/boots. The `near_term_gear` fixed point can converge on a loadout
that is combat-WEAKER than what the character could wield — the bot equips
the shiny prospecting piece and then loses a fight it would have won.

The combat-vs-utility balance shifts across the game (early: survive and
level; mid: gear up; skilling/gathering/task phases: prospecting/wisdom pay
off). A single unified strategy cannot express that shift.

## What already exists (do not rebuild)

- **`strategic_value`** (`tiers/strategic_value.py`) — a proven, extracted,
  combat-vs-utility-weighted scorer: `combat_raw × combat_weight +
  wisdom×w + prospecting×w + inventory_space×w + haste×w`, with an
  `efficiency_budget` cap and `horizon=(num,den)` decay (efficiency decays
  toward max level; combat never scaled). Reuses `equip_value`'s
  `combat_raw_of` atom, so it cannot drift into a third combat ruler.
  **Zero production callers today** — tests only (`Formal/StrategicValue`
  + extraction back it).
- **`pick_loadout(purpose, ...)`** (`equipment/loadout_picker.py`) — the
  per-slot argmax that actually equips gear, already parameterized by
  purpose: `Rank` / `Combat(monster_attack, monster_resistance)` /
  `Gather(skill)`. `Combat(...)` is the combat-optimal loadout for a given
  monster; `Gather(skill)` is the gathering loadout. This is the existing
  equip-time axis (combat-vs-gather), NOT combat-vs-utility.
- **The tree gear branch** (`tiers/progression_tree.py`) —
  `_structural_candidates` gain = `equip_value(cand) − _item_value(equipped)`;
  `has_structural_upgrade` = `bool(_structural_candidates(...))`, the
  tier-aware band-adequacy leg; `decide_tree` picks the branch via
  `branch_pick_pure(band_adequate, gear_target_exists)` and the winner via
  `gear_target_pick`.
- **`inventory_profile` / `loadout_profiles`** — inventory-protection
  keep-sets only; they record what `pick_loadout` chose but do NOT
  influence gear selection. Out of scope here (untouched).

## Locked decisions (from brainstorm)

1. **Selection heuristic**: objective-driven + combat floor. The active
   objective picks the axis (fight/xp/gear/monster-task → COMBAT;
   gather/skill/gather-task/event-gather → UTILITY); a combat floor always
   overrides.
2. **Profile shape**: a named weight vector fed to `strategic_value`, wired
   into the PLANNING path (not just equip-time) so the tree pursues
   different gear per profile — genuinely different plans.
3. **Combat floor**: BOTH a plan-gate (UTILITY only when band-adequate;
   else forced COMBAT) and an equip-gate (winnability swap to the combat
   loadout when the profile pick would lose the cycle's planned fight).

## Architecture

### 1. Profiles as weight vectors

```
class ProfileKind(Enum): COMBAT; UTILITY

@dataclass(frozen=True) ProfileWeights:
    combat_weight: int
    wisdom: int; prospecting: int; inventory_space: int; haste: int
    # (mirrors strategic_value's existing weight surface)

PROFILE_WEIGHTS: dict[ProfileKind, ProfileWeights]
  COMBAT  = combat dominant (STRATEGIC_SCALE), utility stats ~0
            → ranking ≈ today's combat_raw (weapons/armor win)
  UTILITY = combat kept at a nonzero FLOOR, utility stats weighted up
```

`strategic_value` is made **weight-parameterized**: the weight vector
(today module constants derived in `strategic_weights.py`) becomes an
argument. The proofs generalize — the weights were already a value,
merely constant. `PROFILE_WEIGHTS[COMBAT]` is calibrated so COMBAT-profile
ranking reproduces the combat-only ordering (utility contributes ~0);
`PROFILE_WEIGHTS[UTILITY]` is the tunable knob (Phase 5).

### 2. Profile selector — the single tuning surface

```
def profile_for(chosen_root: MetaGoal, band_adequate: bool) -> ProfileKind:
    if not band_adequate:                 # PLAN-GATE floor
        return ProfileKind.COMBAT
    if is_utility_objective(chosen_root):
        return ProfileKind.UTILITY
    return ProfileKind.COMBAT

def is_utility_objective(root: MetaGoal) -> bool:
    # root category ∈ {skill, gather, gather-type task, event-gather}
    # fight / xp / gear (ObtainItem) / monster-task → False (COMBAT)
```

Pure, total, isolated. The heuristic starts as this category table and can
grow (horizon-aware, phase-aware) without touching consumers — this is the
"heuristic we improve over time" the user asked to keep malleable.

`is_utility_objective` reads the tree's existing root categories
(`root_category` in strategy.py); no new taxonomy.

### 3. Pursuit wiring (the "different plans" mechanism)

Thread the active profile through the tree's gear-candidate scoring,
replacing flat `equip_value` with `strategic_value(stats, weights)`:
- `near_term_gear(state, profile)` — best usable-now per slot under the
  profile's weights.
- `_structural_candidates(state, gd, objective, profile)` — gain =
  `strategic_value(cand, weights) − strategic_value(equipped, weights)`.
- `_item_value` baseline → profile-aware (same weights).

**No-circularity rule (INVARIANT):** `band_adequate` /
`has_structural_upgrade` answer a combat-readiness question and are ALWAYS
computed under `PROFILE_WEIGHTS[COMBAT]`, independent of the active
profile. Profile depends on `band_adequate`; `band_adequate` never depends
on the active profile. `has_structural_upgrade` keeps a fixed COMBAT-weights
call; only the post-branch candidate SELECTION uses the active profile.
This is a hard DAG with no feedback edge.

### 4. The two floors

- **Plan-gate** — inside `profile_for` (§2): `not band_adequate → COMBAT`.
  The tree never chases prospecting gear while combat-inadequate.
- **Equip-gate** — at the loadout-fielding site (`player.py`'s loadout
  resolution / `pick_loadout` consumer): compute the active-profile
  loadout; if a fight is planned this cycle and that loadout is not
  `is_winnable` against the planned monster, swap to `pick_loadout(Combat
  (monster_attack, monster_resistance))` (the combat purpose already
  exists). Never field a losing loadout into a fight.

Per-action equip purposes (`Combat` for FightAction, `Gather` for
GatherAction) are unchanged — the profile adds utility-stat weighting to
PURSUIT and the winnability swap to EQUIP; it does not replace the
per-action purpose machinery.

### 5. Interaction with the tree branch (orthogonal axes)

The GEAR/XP branch pivot (`branch_pick_pure(band_adequate,
gear_target_exists)`) is unchanged and COMBAT-computed. Profile is a second
axis over it:
- GEAR + COMBAT → pursue best combat upgrade (today's behavior).
- GEAR + UTILITY → pursue best utility upgrade (reachable only when
  band-adequate, per plan-gate).
- XP branch is a combat objective → COMBAT profile (loadout worn while
  grinding is combat, subject to the equip-gate).

## Formal plan

- `strategic_value` weight-parameterization: the weight vector moves from
  module constant to argument; existing theorems re-hold with the value
  generalized (no vacuity — the constant is one instance).
- `profile_for` proven total + the plan-gate invariant
  `¬band_adequate → profile = COMBAT`.
- Equip-gate: prove the fielded loadout is `is_winnable` whenever a fight
  is planned (composes with the existing FightAction winnability gate; no
  new combat model).
- Band-adequacy proofs unchanged (COMBAT-weights, as today).
- Mutation + differential arms: `profile_for` (selector table + plan-gate),
  the profile-parameterized `strategic_value`, the no-circularity
  COMBAT-pinned `has_structural_upgrade`.
- Zero-vacuousness: every new hypothesis gets a witness; the COMBAT-profile
  calibration (utility ~0) is pinned by a test asserting COMBAT-profile
  ranking == the pre-change `equip_value` combat ordering on a gear set.

## Testing — the profile scenario net

New scenarios in `tests/test_ai/scenarios/`:
- **plan-gate**: combat-inadequate char with a high-prospecting artifact
  available → tree pursues the WEAPON, not the artifact (profile forced
  COMBAT).
- **utility pursuit**: combat-adequate char on a gather/skill objective →
  tree pursues/wears utility gear (UTILITY profile active).
- **equip-gate**: UTILITY-profile char with a fight queued whose utility
  loadout loses → the fielded loadout swaps to combat (winnability).
- **regression / bug-gone**: the `equip_value`-dominance cases
  (perfect_pearl-over-weapon, wolf_ears-over-weapon) re-run under COMBAT
  profile → the weapon now wins, proving the flat-parity bug is fixed.
- Liveness: each scenario totalizes + non-empty plan + bounded search
  (join the band-liveness dimensions where a band scenario gains a profile).

## Phases

1. **Parameterize**: `strategic_value` weights as argument + `ProfileKind`
   / `PROFILE_WEIGHTS` presets + COMBAT-calibration pin. Pure, unwired.
   Gate green.
2. **Selector**: `profile_for` + `is_utility_objective` + plan-gate, pure +
   Lean (total + plan-gate invariant). Unwired. Gate green.
3. **Wire pursuit**: thread profile into `near_term_gear` /
   `_structural_candidates` / `_item_value`; pin `has_structural_upgrade`
   to COMBAT weights (no-circularity); profile scenario net (plan-gate +
   utility-pursuit + bug-gone). Gate green.
4. **Equip-gate**: winnability swap at the loadout-fielding site; equip-gate
   scenario. Gate green.
5. **Flip + tune**: run live shadow; calibrate `PROFILE_WEIGHTS[UTILITY]`
   on real traces (the weight vector is the knob). Ship.

Each phase lands independently valuable and gate-green.

**Phase 1 SHIPPED**: ProfileKind + PROFILE_WEIGHTS (COMBAT zeroes efficiency,
UTILITY floors combat + lifts efficiency) + score_for_profile + calibration
pins (combat-beats-prospecting bug-gone, non-vacuous vs equip_value).
Unwired.

**Phase 2 SHIPPED**: profile_for + is_utility_objective (plan-gate floor); Lean profileFor totality + planGate_forces_combat + utility_iff; differential + 3 kill-checked mutants. Unwired. Phase-3 obligation recorded: feed the selector the ENACTED root (not the in-flight one) to avoid circularity.

## Risks

- **Calibration of the COMBAT preset**: if utility weights aren't driven
  low enough, COMBAT profile still leaks utility bias. Mitigated by the
  Phase-1 pin: COMBAT-profile ranking must equal the pre-change combat
  ordering on a fixture gear set (exact, not approximate).
- **Profile flapping** at the band-adequacy edge (adequate ⇄ inadequate
  flips COMBAT ⇄ UTILITY, churning pursuit): if observed in shadow, apply
  hysteresis on `band_adequate` (mirrors the tree's sticky-commitment
  precedent). Flag, don't pre-build.
- **`is_utility_objective` mis-classification**: a task whose type is
  ambiguous (mixed gather+fight) could pick the wrong profile; the equip-gate
  is the safety net (a wrong UTILITY pick that can't fight gets swapped).
- **strategic_value's horizon/budget** currently defers inventory_space and
  haste at parity 1000 — Phase 1 must decide their profile weights
  explicitly rather than inherit the dormant defaults.
