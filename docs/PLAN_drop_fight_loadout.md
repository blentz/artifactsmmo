# PLAN: drop fights judged with the chosen loadout; the conditions census

USER 2026-10-10: "yes, judge drop fights with the chosen loadout, find the
loadouts and conditions required to successfully plan each item and from that
process, identify and fix planner bugs found."

## Evidence

Census after 522bf21c (docs/PLAN_census_fidelity.md): 114/321 recipes plan in
some cell; 207 do not, almost all `combat_blocked`. The DROP route's WINNABLE
gate (`obtain_model/drop_routes._fight_gates`) asks the bare stat-only
`is_winnable` at full hp: no utility potions. Live C3P0, in nearly the census
loadout, beats vampire 77/117 with a water boost; the gate says it cannot, so
no recipe needing `vampire_tooth` plans for it.

## Increment 1 — the WINNABLE gate wears its loadout

`WINNABLE` = bare `is_winnable` at full hp, OR some RUNNABLE utility-potion
loadout wins the fight walk: the loadouts `best_loadout.loadouts` enumerates
over `candidate_potions` (held, or with a replacement price), each walked by
`fight_outcome` exactly as `loop_rate` walks it. Food never decides a win (it
is eaten between fights), so the gate reads no food menu.

- Cold, like the bare check: no learned record. A fight lost often is priced
  by the loss-risk surcharge in `_drop_actions` and refused by the learned
  veto where a store is read; the route's existence is a stat question.
- Context: `NO_PROFILE_CONTEXT` for the prices, in BOTH drop paths
  (`ObtainModel._drop` and `drop_obtainability.fightable_droppers`), so the
  obtain model and the drop-fight selector keep one verdict.
- Execution: a drop fight in the committed plan is `ctx.fight_monster`; the
  cycle's loadout is chosen against it, and the CRAFT_POTIONS guard stocks and
  equips every potion that loadout wears before the fight. No new wiring.

## Increment 2 — the conditions census

For each recipe, the conditions under which it plans and the loadout its
hardest fight needs: a ladder of worlds, each granting one more condition over
the census character (`census_state`):

1. the census cell as is;
2. + every skill at the character level (brew/craft its own potions);
3. + gold (buy potions, pay crossings);
4. + the recipe's events live;
5. + the character level in steps of 5, up to 50 (the recipe's own skill stays
   at its craft level — see increment 2's status for why).

Per recipe: the first rung that plans, the gear and potion loadout the
hardest drop fight on the plan's path uses. A recipe that fails at the top
rung while every leaf has a source in that world is a PLANNER_BUG to fix.

## Increment 1 — built (2026-10-10)

As designed, with one change: the gate's candidate potions cannot be
`candidate_potions`, whose replacement PRICE walks the obtain model — which
asks this gate (an import cycle, and a recursion). `loadout_win.
stockable_potions` admits a usable potion the character can stock without a
price: held, craftable at its skill now (ingredients not walked), or sold for
gold by a located permanent vendor. The fight walk and the loadout enumeration
moved below the pricing (`fight_walk.py`, `held_stock.py`); the verdict is
memoized per catalogue on what the walk reads.

Effect:
- census recipes PASS 114 -> 133/321, nominal 103 -> 122;
- the census gear fixed point now reaches the live fleet's gear at level 30
  (death_knight_sword, royal skeleton set, slime_shield);
- open-rung walls 10 -> 9 (l47 weaponcrafting 40);
- drop walls 9 -> 2.

Cost: 0.62 s of a 28 s live `plan HAL`; census 40 s -> 73 s.

## Increment 2 — built (2026-10-10)

`audit/craft_conditions.py` + `scripts/gen_craft_conditions.py` ->
`docs/craft_completeness/CONDITIONS.md` (gate: `--check` fails on a recipe
whose top rung is a PLANNER_BUG). `CraftCell` gained `skills_at_level` and
`gold`; `CellResult.fights` names what wins each fight of a passing plan
(`bare`, the winning potion loadout, or `loses`).

The first ladder ended at "level 50, every skill 50": the grey-farm policy
(USER 2026-07-06) rightly refuses a grey drop for a recipe a near higher tier
makes obsolete, so a skill-50 character "could not" make cooked_beef. The
level rungs now keep the recipe's own skill at its craft level.

### Planner bugs found and fixed

1. **NPCs off the overworld were never indexed.** `_build_maps` kept only
   overworld NPC tiles, so the underground `sorceress` had no location:
   `fire_crystal` (9 recipes) could never be bought. And every NPC action
   travelled in "overworld", so the island's `sandwhisper_trader` was priced
   as a walk inside the main region. Now a walkable off-overworld NPC tile is
   indexed with its layer (`npc_layers`), and every NPC buy/sell action — the
   factory's and the four goal-built ones — travels in `npc_region`.
2. **A purchase currency's demand was ignored when the drop had recipe
   consumers.** `grey_farm_allowed` counted the currency arm only when no
   recipe consumed the drop: wool's own consumers are obsolete by skill 20,
   so the sheep was refused although wool buys the tailor's cloth for
   slime_shield (next tier far). steel_armor / steel_helm / steel_legs_armor
   / slime_shield planned at no character level. Live R2D2's root
   `ObtainItem(slime_shield)` had been declined `infeasible:cloth:no_route:`;
   on the fix it plans `[Withdraw(cloth), Withdraw(wool), Fight(sheep),
   NpcBuy(cloth@tailor)]`. The census classifier's currency check had the
   mirror fault (grey-blind) and called those cells PLANNER_BUG.

### What the ladder leaves (166 recipes plan at no rung)

- combat_blocked 110 — the census gear fixed point stalls at the level-30
  set (death_knight_sword, royal skeleton): no tier-4 gear's materials come
  from a monster that set + stockable potions beats. The prediction is not
  the cause: live predicted-loss fights won 27%, predicted wins lost 2.6%.
- material_unreachable 50 — jasper/astralyte/magical_cure/prime_fabric are
  sold only by `tasks_trader`, on a tile gated by the `tasks_farmer`
  achievement (0/100 on this account); enchanted_coin has no source. With
  the achievement, the census still cannot pass them: production routes a
  `tasks_coin` leaf to `ReachCurrencyGoal` in the obtain-item DECISION graph,
  which the census's raw GatherMaterials plan does not walk. Residual: an
  achievements rung, and a census verdict through the decision graph.
- grey_farm_suppressed 4 — policy: obsolete at the level the census reaches.
- crossing_unaffordable 2 — lava_underground_potion's enchanted_mushroom
  grows only in the raid area; the bridge from that restricted region to the
  underground is not modelled. Residual.
