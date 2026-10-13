# Fleet food role: price production, specialize the producer

Date: 2026-10-13. Sub-project 1 of 2 ("role specialization services the fleet";
sub-project 2, gear specialization in a same-tier fleet, follows and reuses §3).

## Intent (USER 2026-10-13)

- "The fleet needs a food maker role so that others can focus elsewhere."
- Objective: **maximum fleet XP throughput**. "Use food when it improves fight
  success odds or xp collection throughput, default to resting. Fleet
  advancement depends on ensuring each player is contributing to the group's
  advancement."
- XP that counts: **useful XP only** — character XP, plus skill XP only where
  the goal-action DAG still demands the level (`xp_demand`).
- **Held food stays free** (the 2026-10-09 ruling "free until used up" is kept).
  The price check moves to PRODUCTION: food is made only when making it beats
  resting.

## The live problem (learning.db, 2026-10-13 17:37–20:04Z, 769 cycles)

- 241 of 349 busy minutes (69%) went to fishing and cooking; 85 (24%) to fights.
  352 cooked fish for 106 fights. Fleet character XP: 3,160/h.
- All five characters hold `fisher` (`role_leases`). Each publishes 40–100 fish
  of demand (`material_demand`); every gear row is quantity 1.
- Real cost: Rest restores ~510 HP in ~67 s. One eat restores ~548 HP but draws
  ~2.8 fish at ~39 s of gathering each (~110 s). Self-made food is ~1.6x slower
  per HP than resting.

## Root causes (file:line on main @a05b8873)

1. **Stocking is never priced.** `grind_heal_prep.heal_prep_goal`
   (`grind_heal_prep.py:52`) stocks `food_carry(eaten)` = 4 × 20 = 80 units,
   where `eaten` comes from `recovery_choice` run with held food FREE. Once any
   stock exists, food wins the per-fight recovery choice and the 80-unit target
   makes the shortfall at replacement cost with no comparison against Rest.
2. **Food justifies its own production.** `xp_demand.demand_roots`
   (`xp_demand.py:31`) appends `ctx.supply_shortfall` ("fishing feeds cooking
   feeds the heal supply"), so food demand makes fishing XP "useful".
3. **Role demand counts units.** `role_selection.demand_by_role`
   (`role_selection.py:701`) sums raw quantity. 80 fish outweigh any quantity-1
   gear row, so the `fisher` share stays highest even split five ways
   (`_effective_demand`, `role_selection.py:311`).
4. **Everyone produces.** Nothing restricts food production to the role that
   owns fishing and cooking.

## Design

### §1 Production is priced (the stock target)

`heal_prep_goal`'s target splits into two quantities per food in the loadout:

- `carry` — as today, `food_carry(eaten)` from the chosen loadout (held free).
- `make_carry` — the carry of the recovery chosen with that food's held count
  set to 0, so every unit costs its replacement price
  (`consumable_price.replacement_price_of`, credited per §2). It is the carry
  only when food still beats Rest when every unit has to be made.

Target rule: if `make_carry > 0` and this character may produce food (§4), the
target is `carry` (as today). Otherwise the target is `min(carry, held)` —
withdraw only, never produce. Held food is still eaten free.

The recovery DP (`loop_rate_core.recovery_choice`, proved in
`Formal.LoopRate`) is unchanged; only its inputs differ.

### §2 Useful-XP credit on the make side

`consumable_price.make_seconds` today is `acquisition_actions × FIGHT_SECONDS`.
The credited price removes the seconds of acquisition actions whose skill is in
`ctx.skill_demand` (that XP is wanted anyway; those seconds are not a cost):

    credited_make_seconds = Σ over the unit's acquisition actions whose
                            skill ∉ ctx.skill_demand  of their seconds

A gather of fish while `fishing ∈ skill_demand` and a cook while
`cooking ∈ skill_demand` cost 0; once both levels are met, the full seconds
count. The buy side is unchanged; `replacement_price_of` stays min(make, buy).

**Ordering.** `skill_demand` must be known before the loadout is chosen. With
the shortfall dropped from `demand_roots` (next point), `xp_demand` no longer
reads the loadout,
so `_selection_context` (`player.py:4120`) computes `xp_demand` first, then the
loadout, then the shortfall.

**No self-justification.** `demand_roots` drops `ctx.supply_shortfall`. Fishing
and cooking are useful only when some gear/skill root's closure demands them.

### §3 Role demand in seconds of work

`demand_by_role` takes a new map `seconds_of_item: Mapping[str, Fraction]`
(per-unit acquisition seconds, `make_seconds` uncredited) and sums
`quantity × seconds_of_item[code]`. An item with no entry (no make route) is
skipped, as an item with no owning skill is today: it cannot be priced, so it
does not recruit. The
demand-splitting rule (`_effective_demand`, share / (others + 1)) and the
hysteresis are unchanged. Effect: a second `fisher` holder is recruited only
while the fisher share, split, still out-weighs every other role's.

### §4 Only the producer makes food

- `SelectionContext` gains `role: str | None` (the held role, `player._role`).
- §1's "may produce" = the held role owns BOTH skills of the food's make walk
  (`fisher`: fishing + cooking), or no character in the fleet holds such a role
  (a fleet with no fisher must not starve; this is the fallback, not the norm).
- A `fisher` holder serves the fleet through the existing
  `SUPPLY_BANK` / `SupplyBankGoal` path; nothing new there.
- The fleet shortfall (`consumable_floor.supply_shortfall`, `player.py:4122`)
  is published only for food whose `make_carry > 0` (food the fleet would
  still choose at replacement price). A fleet whose loadouts rest publishes no
  food demand, and `fisher` loses its demand.

### Non-goals

- Potions: unchanged (they decide fights; free-while-held stays).
- Gear specialization: sub-project 2.
- Real per-action seconds instead of `FIGHT_SECONDS` per action: out of scope
  (the walk's unit stays one fight-equivalent).

## Testing

TDD, all in `tests/test_ai/`:

- §1: the target is `min(carry, held)` when Rest beats food at replacement
  price; `carry` when food wins; held food is still carried free.
- §2: credited price drops the demanded skills' seconds; equals the full price
  with `skill_demand` empty; `demand_roots` no longer contains the shortfall;
  `xp_demand` is computed before the loadout.
- §3: seconds-weighted totals; an 80-fish row no longer out-weighs a gear row
  whose make seconds are larger; unpriced items do not recruit.
- §4: a non-producer gets withdraw-only; a fisher produces; with no fisher in
  the fleet anyone may produce; the shortfall omits food that fails §1.
- Mutation anchors for every new branch, in the same commit
  (`formal/diff/mutate.py`, `--check-anchors`).
- Proofs: `Formal.LoopRate` untouched. If `consumable_price_core` changes
  signature, its Lean model and differential test change with it.
- Full `formal/gate.sh` green before push.

## Live verification (learning.db, after restart)

Against the 17:37–20:04Z baseline:

- `role_leases`: at most one `fisher` holder while fishing/cooking XP is not
  demanded.
- Non-fisher busy time on fishing/cooking far below 69%; Rest used for recovery
  when no stock is held.
- Fleet character XP/h above 3,160.
