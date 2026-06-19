# Level-50 reachability — the honest residual perimeter

**Status (2026-06-18): the perimeter is mapped, minimal, and irreducible.**
The level-50 reachability capstone for the perception-refreshed cycle,
`Formal.Liveness.LevelFiftyReachableP.ai_reaches_level_fiftyP`, proves

> `∀ s, GlobalInvariantsP s → ∃ k, (cycleStepPN k s).level ≥ 50`

with kernel axioms `{propext, Classical.choice, Quot.sound, xpToNextLevel,
xpToNextLevel_pos}` (identical to the original `LevelFiftyReachable` capstone).
This document is the authoritative statement of what that result rests on, why
each residual is irreducible **in the current model**, and what discharging it
would require. It is the close-out of the "prove AI completeness to level 50
against the openapi.spec snapshot, modulo as few assumptions as possible" effort.

The honest headline: **"modulo only LIV-001" is NOT reachable.** Three residuals
remain, of three DIFFERENT classes. All three share one root: the Lean model
abstracts a runtime/server quantity it cannot faithfully reproduce. Forcing any
of them to green would be a proof that tells a false story about the running bot
(see `[[feedback_proofs_tell_false_stories]]` / formal-development Phase 4).

---

## The three residuals

| # | Residual | Class | Where it lives | Dischargeable? |
|---|----------|-------|----------------|----------------|
| 1 | **LIV-001** (`xpToNextLevel` / `_pos`) | Trusted **axiom** | kernel axiom set | No — server owns the number |
| 2 | **WinnableAcrossBand** | **Faithfulness / differential** | `perceptionRefresh` arming | No — needs per-level gear+base stats the server doesn't expose |
| 3 | **BlockersQuietBelowCapInfinitelyOftenP** | Explicit **Lean hypothesis** | `GlobalInvariantsP.hfightFiresP` | In-model YES, but the discharge is a **false-story proof** — refused |

### 1. LIV-001 — the server xp-curve axiom

`Formal.Liveness.Measure.xpToNextLevel` (+ `xpToNextLevel_pos`). The number of xp
required to advance from level L is set by the game server and reported only at
runtime. The measure that drives every descent argument
(`Measure.measure`, noncomputable, lex 6-tuple) is well-founded only because this
quantity is positive and finite. There is no offline data that reproduces the
curve, and the openapi snapshot does not expose it as a closed form. This is the
one accepted, openapi-cited server axiom (per `[[project_liveness_axiom_split]]`,
server axioms carry per-axiom signoff + citation). **Irreducible by design.**

### 2. WinnableAcrossBand — a faithfulness residual, NOT a Lean hypothesis

`Formal.Liveness.GearTierLeveling.WinnableAcrossBand` (def line 54): for every
char level L ∈ [1,50) the live monster catalog contains a winnable, xp-positive,
not-over-leveled target. **It is satisfiable** (`winnableAcrossBand_satisfiable`).

It is NOT a hypothesis the capstone takes. It enters through the *faithfulness* of
`perceptionRefresh` (`PerceptionRefresh.lean:51`), which arms
`objectiveStepFires`/`objectiveStepIsFight` UNCONDITIONALLY below level 50. That
unconditional arming is the in-model image of production committing the
`ReachCharLevel` meta-goal whose plan leads with a fight — faithful to production
**only when a winnable in-band monster exists**. Brick 6 of the perception-refresh
extension (`formal/diff/test_perceive_arm_diff.py`) differentially CHARACTERIZES
exactly this: production arms iff `is_winnable` finds a target; where no winnable
target exists, production does NOT arm and the model OVER-approximates.

**Why it cannot be soundly discharged (Option C, scoped 2026-06-18 —
`docs/PLAN_winnable_across_band_discharge.md`):** validating "winnable at every
band" requires, per level L, the player's actual loadout (for nonzero attack) and
`max_hp` (for the damage race). Both compounding facts block a sound differential:

- **Attack is gear-derived.** `predict_win` (`src/.../ai/combat.py:89-93`):
  `raw_player = Σ _element_damage(p.attack[e], …); if raw_player <= 0: return
  False`. A no-gear character does zero damage and beats nothing.
- **Base stats per level are not server-exposed.** `projection.py:3-6`: the API
  reports only TOTAL stats (base + equipped gear), never base. There is no
  `base_hp`/`HP_PER_LEVEL` curve anywhere in `src/` or `formal/`.

Every way to supply `max_hp(L)` fails: base-hp = 0 makes the geared bot lose the
race almost everywhere (uninformative); an assumed base-hp(L) is unconstrained by
data (the verdict becomes an artifact of the guess). C1 (assumption-pinned
differential) therefore collapses into C2 (a full craft-closure + skill-gate +
equip gear-progression model), which is itself stat-assumption-laden because no
offline data reproduces gear totals without replaying crafting. **Irreducible
without the server exposing per-level base stats.**

### 3. BlockersQuietBelowCapInfinitelyOftenP — provable in-model, but dishonestly

`Formal.Liveness.FightFairnessP.BlockersQuietBelowCapInfinitelyOftenP`
(`FightFairnessP.lean:120`): infinitely often, below the cap, none of the 14
`objectiveStepBlockers` (the housekeeping chores: deposit, discard, sell, craft-
relief, gear-review, claim, task-complete/cancel, rest) fires on the refreshed
selection state. This is the SOLE runtime obligation of the capstone's
`hfightFiresP` — Brick 4 reduced it to this hypothesis alone, discharging the old
`CombatPersistent` in-model (the perception-refresh extension's net win).

**The whole fairness tower collapses to "reach a `Settled` state":**
`BlockerSettled.Settled` (12 cleared conditions) is `cycleStep`-invariant
(`Settled_cycleStep`) and discharges the entire obligation
(`combatScheduled_of_settled`), and `SettledReach.reach_fifty_of_eventually_settled`
turns level-50 reachability into `∃K, Settled (cycleStepN K s)`. The only in-model
obstacle to reaching `Settled` was the un-armable `objectiveStepFires`
(`Settled_unreachable_without_perception`) — which `perceptionRefresh` now supplies.

**Why it is in-model PROVABLE:** each chore one-step-clears its own fire condition
(`BlockerQuieting.lean`, 13/14; reachUnlockLevel bounded by the ≤5 gap), and
**nothing re-arms the opaque chore flags** — neither `applyActionKind` (it only
ever sets `hasOverstockItems`/`selectBankDepositsNonempty`/`sellableInventoryNonempty`/
`craftReliefFires`/`gearReviewFires`/`pendingItemsNonempty` to `false`) nor
`perceptionRefresh` (it touches ONLY the two objective Bools). So along the
`cycleStepP` trajectory the armed-chore set is monotone-decreasing; after finitely
many steps all chores are quiet and `objectiveStep` is selected forever. A
settled-reachability theorem would discharge the hypothesis with NO new
assumptions.

**Why that discharge is REFUSED (the honesty boundary):** the real bot DOES
re-arm chores — fighting and gathering add items, inventory fills, and
`hasOverstockItems` becomes true again. The real bot satisfies the property
because chores are **fast-transient** (a single deposit/discard clears pressure
for many subsequent fights), NOT because chores are **absent**. The model's
"never re-arm" is unfaithful: the in-model and real trajectories diverge at the
first re-armed chore, so the in-model theorem is not a sound over-approximation of
the real bot's fairness — it proves the right `Prop` for a reason that is false of
the system. Shipping it would relocate the assumption into an abstraction that
lies, exactly the dishonest-proof pattern the gate's Phase-4 review exists to
reject. A FAITHFUL discharge must model inventory composition + the chore-rate vs
fight-rate transience the abstraction omits — a major model extension, and one
with no differential test that can validate it offline (it would need a live
multi-cycle bot run). **Kept as a named, NOT-differentially-validated residual.**

---

## Taxonomy — why these are genuinely different

- **LIV-001** is a *number the server owns*. Trusted axiom, cited.
- **WinnableAcrossBand** is a *number the server owns* (per-level gear+base stats),
  surfacing as a *faithfulness* gap that Brick 6 differentially characterizes but
  cannot validate without that number.
- **BlockersQuiet** is a *dynamics the runtime owns* (inventory composition over
  time). In-model it is a theorem; faithful to the bot it is a transience/rate
  property the abstraction cannot express.

All three are the same irreducible shape — **the model abstracts a runtime/server
quantity it cannot faithfully reproduce.** "Modulo only LIV-001" would require the
server to expose per-level base stats (kills #2) AND the model to track inventory
dynamics (kills #3). Neither is available; neither can be faked honestly.

## What was actually achieved (the perimeter is minimal)

The residual set went from a large bag of runtime assumptions to these three
named, characterized items. In particular the perception-refresh extension
(2026-06-18, `[[project_perception_refresh_extension]]`) moved `CombatPersistent`
/ `hperc` from an ASSUMPTION to an in-model proven fact, and O5.4
(`[[project_o54_select_differential]]`) bound the entire ladder to production +
mutation-enforced it, so the Lean selection is no longer trusted-by-assertion.
B-0 (`[[project_b0_bootstrap_reach]]`) put the bootstrap window's reach-to-bank in
the model with no perception/fairness hypothesis. What remains is irreducible
without new server data or a major faithfulness-modeling effort — both out of
reach of an honest offline proof.

## If the boundary is to be pushed later

- **#2:** capture per-level base stats from a live geared character per level
  (the C2 effort), or persuade the server to expose a base-stat curve. Then
  WinnableAcrossBand becomes a `GameDataFixture`-style data obligation.
- **#3:** extend the State model with inventory composition and prove a
  chore-rate < fight-rate transience, then build a live multi-cycle differential
  to validate it. Until then, in-model settled-reachability is a *sanity*
  property (the model does not deadlock on chores) and must NOT be presented as a
  discharge of the real-bot obligation.
