# PLAN: re-justify potion stocking on combat survivability

Status: **NOT STARTED** — design agreed 2026-07-19, no code written.
Branch base: `fix/dynamic-rest-cost` @ `be902db2`.

## Why

`RestAction.cost` was a flat 10.0. Since `3a4994f4` it is
`rest_cost_pure(hp, max_hp) = max(3, ceil(missing%))/10`, i.e. 0.3 at a shallow
deficit and 10.0 only at a full one. Resting always refills to full.

The user's model: a potion is worth its own cooldown ONLY if it removes more
rest-seconds than it costs. Gather-crafting a potion never satisfies that — the
gather/craft legs dwarf the ≤100s the rest would have cost.

Three sites still encode the OPPOSITE rationale, in prose, as their stated
reason to exist:

| Site | Text |
|---|---|
| `goals/maintain_consumables.py:6` | "so the bot tops up its cupboard instead of falling back on the **slow Rest** action" |
| `consumable_supply.py:9-10` | "cook/brew more rather than **falling back on the slow Rest** action" |
| `tiers/means.py:172-173` | "so the bot **cooks/brews instead of resting** between fights" |

Those sentences are now false. They are the actual calibration bug — not the
urgency numbers.

## Key architectural finding (changes the shape of this work)

**`goal.value()` is not consumed by arbiter selection.** `arbiter_select.py:11-13,
78-131` selects by fixed ladder position (`GUARD_ORDER` → `COLLECT_REWARD_ORDER` →
step → `DISCRETIONARY_ORDER`) plus sticky-commit/band preemption, and
`planner.py:138-141` records that `value()` was removed from the planner heuristic
as inadmissible.

So tuning `MAINTAIN_CONSUMABLES_VALUE` (25.0), `RestoreHPGoal._HP_CRITICAL` (110.0),
or the heal-root urgency would be **theatre**. What decides craft-vs-rest is:

* `GuardKind.CRAFT_POTIONS` — `guards.py:278-279`, ladder index 11 (last), fires on
  `potion_supply.craft_potions_fires` (`potion_supply.py:135-179`), a **pure stock
  deficit predicate with no HP term and no rest-cost term at all**.
* `MeansKind.MAINTAIN_CONSUMABLES` — `means.py:66-79`, 4th in `DISCRETIONARY_ORDER`,
  fires on `heal_stock(...) < HEAL_STOCK_FLOOR` (`consumable_supply.py:19`, = 5).

Once either fires it outranks everything below it, regardless of how cheap resting
currently is. A full-HP bot with a stocked-but-below-floor cupboard still routes to
gather/craft.

## The correct justification

Potions have a real purpose the current rationale misses: **you cannot rest
mid-fight.** Utility-slot potions are consumed during combat, so their value is
surviving a fight you would otherwise lose — which is exactly how
`ProvisionMarginalFightGoal` already frames it (`provision_marginal_fight.py:14-16`,
`_TARGET_SLOT = "utility1_slot"`).

So the codebase currently holds **two contradictory theories** of why potions exist:
cupboard-topping (rest-avoidance, now false) and marginal-fight survivability
(combat, still true). This work deletes the first and generalises the second.

## Tasks

### Task 1 — make `craft_potions_fires` combat-justified
`potion_supply.py:135-179`. Add a combat-need term so the guard fires only when
potions change a COMBAT outcome, not merely when stock is low. Candidate condition:
the active means is combat AND the target monster is winnable-with-potions but not
comfortably winnable without. Reuse `ai/combat.is_winnable` — do NOT introduce a
second beatability notion (see `feedback_no_predict_win_in_goap_precondition`).

Keep the guard in its existing ladder slot (index 11). **Do not add a GuardKind** —
memory `project_craft_unlock_boosts`: a new GuardKind breaks the proven ladder;
reuse the slot.

### Task 2 — same for `MAINTAIN_CONSUMABLES`
`consumable_supply.py`, `means.py`. `HEAL_STOCK_FLOOR = 5` currently applies
whenever combat is the active means. Gate the top-up on the same combat-need
predicate rather than on stock alone.

### Task 3 — fix the three stale rationales
Rewrite the docstrings at `maintain_consumables.py:6`, `consumable_supply.py:9-10`,
`means.py:172-173` to state the combat justification. Also correct
`restore_hp.py:44-47` ("must exhaust every state cheaper than Rest's cost-10" — the
whole `relevant_actions` narrowing is justified by the old flat 10.0 and needs
re-deriving) and `planner.py:131` (stale ref "rest.py:51 = 10.0"; it is now
`rest.py:33` returning `rest_cost_pure`).

### Task 4 — Lean / oracle lockstep
Any `MeansKind`/`GuardKind` predicate change must move `decide_key.py`,
`DecideKey.lean`, and the Oracle together (memory `project_recycle_surplus`).
Confirm whether the guard predicate is in the proven ladder model before editing;
if it is, the theorem moves in the same commit.

### Task 5 — tests
Existing pins that will move:
`test_tiers_guards.py:195-196,201` (`GUARD_ORDER[-1] is CRAFT_POTIONS`),
`test_maintain_consumables.py:111,141,162,194,219,321-322` (`HEAL_STOCK_FLOOR`),
`test_craft_potions.py:216,224` (`POTION_GATHER_BATCH`),
`test_potion_supply_integration.py:77` (ladder integration).
Add a regression test for the actual bug: full HP + empty cupboard + no combat
pressure must NOT route to gather/craft.

### Task 6 — full gate
`scripts/run_tests.sh`, `mypy`, `ruff check src tests`,
`bash formal/gate/check_extraction.sh`, `lake build && lake build oracle`,
`pytest formal/diff/`, `mutate.py`. Serialize — nothing else importing `src`.

### Task 7 — runtime verification (REQUIRED, not optional)
Green tests ≠ runtime-active (`feedback_verify_runtime_activation`). Re-run Robby
and count `CRAFT_POTIONS` / `MAINTAIN_CONSUMABLES` selections before vs after. The
pre-change baseline from the last trace: ~86% of cycles on wolf-fight survival,
potion gather/craft/equip 284×.

## Decisions (user, 2026-07-19) — all settled

1. **Stock speculatively, with lead time.** Do NOT gate on "already marginal";
   that fires too late given craft lead time.
2. **Skip boost/resist/antipoison.** Only `hp_restore` is in scope. The
   `unlock_boost_target` stall-breaker path in `craft_potions_fires` is a
   different purpose (flipping bare-unwinnable → winnable) and stays untouched.
3. **Keep `ProvisionMarginalFightGoal`** as the acute case; the guards handle the
   sustained one.
4. **Demand driver:** learned `history.hp_healed_per_fight` (actual potion
   consumption) first. With no history, marginality decides whether there is any
   need at all — comfortably-winnable ⇒ demand 0; marginal ⇒ size by
   `expected_damage_per_fight`. Explicitly NOT raw expected damage as the primary
   driver: resting already handles damage for free, so that would keep
   over-stocking for damage no potion was ever needed for.
5. **Lead time:** a named constant, `POTION_LEAD_FIGHTS = 10`, capped by the level
   ramp. Must be pinned by a test and a mutation anchor so it cannot drift.

## Finding that reshapes Task 1: the guard and the goal already disagree

`CraftPotionsGoal._baseline` (`craft_potions.py:75-95`) is ALREADY
consumption-aware:

```python
monster_demand = ceil(hp_need / potion_restore)
return min(max(level_baseline, monster_demand), UTILITY_SLOT_MAX_STACK)
```

but the guard `craft_potions_fires` uses ONLY `potion_baseline_pure` — the level
ramp, no consumption term. So the guard decides WHETHER to stock by one rule and
the goal decides HOW MANY by another. That divergence is a latent bug independent
of the Rest change.

It also shows the ramp is currently a **floor** (`max(level_baseline, demand)`),
which is exactly why a level-45 bot pursues 100 potions whether or not it ever
drinks one. Per decision 1 the ramp becomes the **cap** on speculation, with
consumption as the driver:

```
demand = ceil(hp_need_per_fight * POTION_LEAD_FIGHTS / restore)   # 0 when no need
target = min(demand, level_baseline)                             # ramp = CAP
```

Zero projected consumption ⇒ target 0 ⇒ guard never fires. That is what kills the
idle-bot stocking case.

### Revised Task 1
Extract ONE shared pure core (`potion_stock_target_pure`) computing the target,
and use it in BOTH `craft_potions_fires` and `CraftPotionsGoal._baseline`, so the
two can no longer diverge. New cores ship extracted (`project_mechanical_extraction`).

**Do NOT change `potion_baseline_pure` itself** — it is mirrored bit-for-bit by
`formal/Formal/PotionBaseline.lean` and feeds liveness proofs. Keeping it as the
cap keeps this out of proof-rewrite territory.

## Lean coupling (checked)

`craftPotionsFires` is an OPAQUE state field in Lean
(`Liveness/ProductionLadder.lean:202` — `def craftPotionsFires (s : State) : Bool :=
s.craftPotionsFires`), and `formal/diff/test_ladder_fires_diff.py:443-445` binds
slot 32 to the real Python predicate. So changing the predicate's internals moves
NO Lean formula; only scenario expectations in that diff test may need updating
where a scenario's declared value flips. Changing `potion_baseline_pure` WOULD move
a Lean formula — hence the constraint above.

## Risks

* Guard-ladder edits ripple into the proven ladder and the census; both have bitten
  before.
* Under-stocking is a real failure mode: the bot dies mid-fight with an empty
  utility slot. The combat predicate must be evaluated with craft LEAD TIME in mind,
  not only at the instant of need (see open question 1).
* `craft_potions_fires` currently has no HP input at all, so adding one widens its
  read-set — check the planner memo key (`project_planner_cpu_memoization`:
  memo-key = read-set).
