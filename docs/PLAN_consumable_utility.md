# PLAN: consumable utility — what to bring into a fight chain

USER 2026-10-09: "we may have overcorrected with always Resting. It should be
possible to calculate the maximum utility of each food item and figure out which
foods and potions we should bring into fights to optimize the fight outcome (a
win is good, but a win with minimal health loss means we can fight multiple
monsters without resting)."

## Rulings (2026-10-09)

- **Objective: XP per second.** The loadout of consumables is chosen to maximise
  XP per second of the whole fight loop — fight, recovery, and producing what it
  consumed — so it can also change WHICH monster is fought.
- **Price of a consumable:** held stock (bag, bank, utility slots) is free. With
  none held, its price is the cheaper of replacement time (make it: the
  acquisition walk) and gold value (buy it) — the classic build/buy.
- **Scope, first increment: all three** — out-of-fight food, in-fight heal
  potions (utility slots), boost potions (stat buffs), chosen jointly per fight.

## What exists (2026-10-09)

| Piece | Today |
|---|---|
| `combat.predict_win` / `combat_margin` | rounds-to-kill vs rounds-to-die; no in-fight potion |
| `expected_damage.expected_damage_per_fight` | HP lost per fight, no potion |
| `boost_selection.best_boost_potion` | best craftable-now boost by margin gain; feeds the potion guard |
| `potion_supply` / `potion_stock_target` | heal-potion stock sized to a marginal fight (6a644b58) |
| `consumable_selection` (proved) | which held food fits a deficit |
| RestoreHP | A* over Rest / UseConsumable / Craft; Rest priced in seconds |
| `tiers/band_target` | ranks monsters by MEASURED XP per action incl. upkeep (`fight_upkeep`) |
| `craft_vs_buy` (proved) | build-vs-buy verdict |
| `fight_loop_cost` | rest seconds per fight from damage |

Gap: nothing PREDICTS what a heal or boost potion does to a fight's HP loss,
so nothing can say that a potion lets the next fight start without a Rest.

## Increments

0. **Mechanics, from data.** Settle the server rules the model will encode,
   from `learning.db` (`consumables_expended_json`, `delta_hp`, fight logs) and
   the API schema: when a restore potion fires (HP threshold, once or every
   turn), how many are consumed per fight, when boosts apply, whether food can
   be eaten mid-chain only between fights. Each rule cited to its evidence; no
   rule from memory.
1. **Fight model with consumables** — pure core + Lean: an expected-value turn
   model `fight_outcome(player, monster, utility loadout) -> (win, turns,
   hp_lost, consumed)`, reusing `_expected_hit` so it cannot drift from
   `predict_win` (with no potions it must equal today's verdict and damage —
   a theorem and a differential).
2. **Price** — `consumable_price(code)`: 0 if held; else min(acquisition
   seconds, gold value ÷ gold-per-second), the gold rate read from the grind
   target as task worth does. Proved build/buy reused.
3. **Loop rate** — `xp_per_second(monster, loadout, food plan)`: XP per kill ÷
   (fight seconds + recovery seconds + Σ price(consumed)), recovery = the
   cheaper per HP of Rest and eating held/priced food. Pure core + Lean
   (monotonicity: more HP lost never raises the rate; a free item never lowers
   it).
4. **Choice** — the best loadout per candidate monster (two utility slots ×
   heal/boost candidates × food), searched exhaustively over the small set; the
   band target's counterfactual for monsters/loadouts not yet measured, the
   measured upkeep where it exists.
5. **Execution** — equip the chosen utility potions with a stock sized to the
   chain; RestoreHP eats held food when it is cheaper than resting (free held
   stock makes that the common case); production of priced stock through the
   existing supply / potion paths.
6. **Witness** — live: rests per fight, XP per hour, consumables per fight,
   before vs after, per character.

## Increment 0 — mechanics (settled 2026-10-09)

From the API's own effect text (game-data bundle `items[].effects`) and
`cycles.consumables_expended_json` over every recorded fight:

| Effect | Rule (API text) | Data |
|---|---|---|
| `restore` (utility: small/minor/… health potion) | "Restores X HP at the start of the turn if the player has lost more than 50% of their health points" — every such turn | 1–7 `small_health_potion` consumed per fight (514×3, 502×2, 438×1, 218×4, …) |
| `boost_dmg_<el>` | "+N% <el> damage at the start of the fight and for the rest of the fight" | 1 per fight (water 132, earth 64, air 54) |
| `boost_res_<el>` | "+N% <el> resistance at the start of fight" | — |
| `boost_hp` | "+N HP at the start of the fight and for the rest of the fight" | — |
| `heal` (consumable food) | "Heal N HP when the item is used" — out of combat | — |
| `antipoison`, `splash_restore` | poison cleanse; restores ANOTHER character | out of scope (solo fights) |

Open for increment 2: whether the gold rate is the right converter for a buy
price.

## Increment 1 — built (2026-10-09)

- `ai/fight_terms_core.py`: the per-turn terms `predict_win` / `combat_margin`
  already computed (kill step, die step, effective HP, rounds, first mover,
  exits) as one pure function; `combat.combat_terms` resolves the stats once and
  both verdicts read the terms. 0 mismatches against the pre-extraction code on
  200,000 random states; new differential at CURRENT hp (incl. the dead start).
- `ai/fight_outcome_core.fight_outcome(terms, hp_start, max_hp, restore, stock)`:
  expected-value turn walk with the API `restore` rule (drink at the start of a
  player turn while `2*hp < max_hp`, ×10000 scale), from any starting HP so a
  chain can be walked.
- `Formal/FightOutcome.lean`: `closedWin_eq_predictWin` (bridge to
  `Formal.PredictWin`), `fightOutcome_noStock_win`, `used_le_stock`,
  `hpEnd_le_max`, `stock_mono` (more stock: win kept, hp_end and turns never
  lower). The spec's "a restore never raises the turn count" is FALSE (a potion
  turns a round-4 loss into a round-6 win); replaced by `turns_le_roundsToKill`
  and `win_turns_stock_indep`.
- Calibration (777 replayable `small_health_potion` fights): potions used exact
  48.8%, within ±1 87.3%; win verdict 765/777. The model over-predicts use
  (inherits the closed form's pessimistic monster bounds).

## Increments 2-3 — design (2026-10-09)

- **Gold → seconds:** the grind target's fight gold per loop cycle
  (`task_worth.fight_gold_rate` over `ctx.combat_monster` — the rate the USER
  ruled for task worth, "The grind target's gold") divided by
  `TYPICAL_FIGHT_COOLDOWN_SECONDS`. One converter, so a consumable's buy price
  and a task's gold cannot disagree. No grind target or zero rate: buying is
  unpriceable (infinite), making is the price.
- **Make → seconds:** `acquisition_actions(code, 1, …)` × 
  `TYPICAL_FIGHT_COOLDOWN_SECONDS` (the walk's unit is fight-equivalents, as
  `fight_loop_cost` declares).
- **Price:** 0 when held (bag, bank or utility slots); else min(make, buy).
- **Loop rate:** XP per kill ÷ (fight seconds + recovery seconds + Σ price of
  what the fight consumed), recovery from the fight's predicted `hp_end`
  (`fight_outcome`) as the cheaper of Rest (`rest_cooldown_seconds`) and eating
  (eat cooldown + the food's price), per HP missing.

## Increments 2-3 — built (2026-10-09)

Not wired into any decision.

- `ai/consumable_price_core.consumable_price(held, make_seconds, buy_gold,
  gold_per_second)`: 0 when held, else the cheaper available side (`make` on a
  tie), None when neither. `Formal/ConsumablePrice.lean` (pairs compared by
  cross-multiplication): `held_free`, `le_make`, `le_buy`, `price_mem`,
  `none_iff`, `mono_make`, `mono_gold`, `qle_trans`.
- `ai/consumable_price.consumable_price_of`: held = bag + bank + wearing utility
  slots; make = `acquisition_actions(code, 1)` × 30 s (None at
  `UNOBTAINABLE_PER_UNIT`); buy = cheapest gold `BUY` / `GE_FILL` source
  (`acquisition_cost.npc_price_of` / `ge_price_of`, made public); gold rate =
  `task_worth.fight_gold_rate` (made public) over `ctx.combat_monster` ÷ 30.
- `ai/loop_rate_core`: `recovery_seconds` (exact DP over (food, HP missing),
  per-food count bound ⌈m / restore⌉; one use of k units costs the FLAT eat
  cooldown + k × price — the published "flat, whatever the quantity" rule, not
  k × cooldown; a zero remainder rests 0 s, not the 3 s floor) and
  `xp_per_second`. `Formal/LoopRate.lean`: `recovery_le_rest`,
  `recovery_mono_missing`, `add_food_le`, `price_mono`, `free_food_le`,
  `countBound_covers`, `xpRate_zero`, `xpRate_den_pos`, `xpRate_antitone`,
  `rate_antitone_missing`.
- `ai/loop_rate.loop_rate(state, game_data, ctx, monster, loadout)`: utility
  slots projected to exactly the loadout (`project_equip` gained a `slot` and an
  empty-slot `None`), `fight_outcome` from the projected max HP
  (`combat.fight_max_hp`), fight = one 30 s cooldown, consumed = restores drunk
  + one per boost, priced; recovery over held foods; a `splash_restore` potion
  (heals ANOTHER character, API text) is refused (`GameData.effect_codes`).

Probe 2026-10-09 22:0xZ (live state, scratch DB copy), see the session report.
Findings for increment 4:
- A held food is free AND unbounded in the core (no per-food count): every
  recovery collapses to one 3 s use. Priced at replacement (stock removed) every
  food costs 60-450 s a unit and Rest wins every recovery.
- Unheld potions cost 120-1,268,160 s a unit (the walk includes skill grinds);
  at those prices every potion loadout loses to no potions wherever no potions
  wins. Only C3P0 vs vampire needs one (no potions loses; small_health_potion x5
  wins at 0.031 XP/s).
