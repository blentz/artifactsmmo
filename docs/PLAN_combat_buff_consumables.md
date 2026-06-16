# PLAN #3: model combat buff consumables (utility-slot potions)

**Priority:** 3. **Status:** planned. **Depends on:** #1 (shares predict_win combat model).

## Problem

Combat buff potions are `type=utility` items equipped in `utility1/2_slot`, active for
the fight. Their effects are dropped by the parser → valued 0 → never equipped (the
novice_guide pattern), AND ignored by predict_win. Effects:

| effect | item | mechanic | model |
|---|---|---|---|
| `boost_dmg_<elem>` | enchanted_boost_potion +20% | +20% that element's dmg whole fight | raises player damage → killStep |
| `boost_res_<elem>` | diabolic_elixir +12% | +12% that element's resist, fight start | reduces monster dmg → dieStep |
| `boost_hp` | health_boost_potion +250 | +250 HP whole fight | raises effective HP |
| `restore` | enchanted_health_potion +300 | restore 300 HP when below 50% (per turn) | conditional in-fight heal |
| `antipoison` | enchanted_antidote +200 | removes 200 poison/turn | counters poison (needs #1 poison) |

(Note: `restore`/`boost_hp` were deferred from the consumable Stage-1 fix precisely
because they are fight-active utility, not instant heals — they belong here.)

## Two parts

### (a) VALUE utility buffs — cheap (flat-utility lockstep, like haste)
Parse `boost_dmg_*`/`boost_res_*`/`boost_hp`/`restore` into ItemStats (a combined
"combat-buff value" scalar, or per-effect fields), fold into equip_value/armor_score/
_equip_value so the bot EQUIPS buff potions into utility slots. Same parse→value→
EquipValueAugmented/Bridges/extraction/diff/mutation lockstep. Gets utility gear used.

### (b) MODEL buffs in predict_win — proven-core (with #1)
- `boost_dmg_<elem>`: add to the player's dmg% for that element BEFORE the rawPlayer
  element-damage sum → bigger raw → bigger killStep.
- `boost_res_<elem>`: add to the player's resistance for that element → smaller
  raw_monster → bigger dieStep.
- `boost_hp`: add to playerMaxHp / effective_hp.
- `restore`/`antipoison`: conditional per-turn — model as a per-turn heal / poison
  cancel in the net step (compose with #1 poison).
Since the bot picks the loadout (incl. utility slots) BEFORE the fight, project the
equipped buffs into the stats predict_win consumes (extend project_loadout_stats to
fold utility-slot buff effects). Re-prove the predict_win theorems for the new terms.

## Sequencing
1. Part (a) value — cheap, immediately equips buff gear. Land first (no predict_win).
2. Part (b) predict_win — after #1's predict_win machinery exists (boost_dmg/res/hp
   are clean killStep/dieStep/HP additions; restore/antipoison compose with #1's
   per-turn DoT/heal terms).

## Risk
Part (a) low (the established lockstep). Part (b) proven-core, shares #1's re-proof
burden; do after #1's poison/DoT terms exist so restore/antipoison have something to
cancel. Verify the utility-slot projection doesn't perturb the existing loadout pick.
