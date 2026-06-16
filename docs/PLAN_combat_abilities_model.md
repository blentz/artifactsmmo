# PLAN #1: model monster combat abilities in predict_win

**Priority:** 1 (first). **Status:** planned.
**Continuation of:** lifesteal in predict_win (267ce84) — same proven-core, net-step
machinery. Template: `docs/PLAN_combat_stats_haste_lifesteal.md`.

## Problem

`predict_win` models attack/resistance/crit/initiative/hp + lifesteal. Monsters
(elite/boss, 48 total) carry abilities it IGNORES → the bot over-predicts wins vs
them → losses (caught only REACTIVELY by the combat-veto). Mechanics (from effect
descriptions):

| effect | tier | mechanic | predict_win impact |
|---|---|---|---|
| **poison** | normal | turn 1: player loses N HP/turn (flat DoT) | raises player death rate (extra N/turn) |
| **barrier** | normal | +N HP shield at start + every 5 turns; absorbs all dmg until broken | raises monster effective HP (+N per 5 turns) |
| **burn** | elite | turn 1: DoT = 20% of player Σattack, −10% each turn | front-loaded decaying DoT on player |
| **healing** | boss | every 3 turns monster restores 10% HP | lowers net kill rate (regen) |
| **corrupted** | elite | each hit on monster −10% its resist to that element (→ negative) | HELPS player (monster softens over time) |
| **berserker_rage** | boss | <25% HP ⇒ +50% monster dmg (once) | monster dmg ramps near death |
| **frenzy** | boss | on monster crit ⇒ +60% self dmg till next turn | dmg variance |
| **void_drain** | boss | every 4 turns drain 10% player HP → heal self | DoT + regen |
| **protective_bubble** | boss | 65% resist to a rotating random element each turn | ~16% avg dmg reduction (1/4 elements) |
| **reconstitution** | boss | every 20 turns full heal | UNWINNABLE if kill takes >20 turns |

## Design decisions

- **Scope by tier.** Robby is low-level; he faces NORMAL monsters now, ELITE later,
  BOSS much later. Model in impact-order:
  1. **poison** (normal, flat DoT) — `dieStep` gains a flat per-turn term:
     effective player loss/turn += poison. Clean net-step extension (like lifesteal).
  2. **barrier** (normal) — raises monster effective HP. Conservative model: add the
     barrier amount to monsterHp for the rounds-to-kill (ignore the per-5-turn
     refresh first cut; a refresh model is a follow-up).
  3. **burn** (elite, decaying DoT) — front-loaded; conservative bound = model the
     turn-1 burn as a one-time effective-HP reduction OR a flat DoT upper bound.
  4. **healing** (boss regen) — lowers kill rate: like monster lifesteal but
     unconditional per-3-turns; fold into killStep as an averaged heal.
- **Conservative-by-default for the exotic boss abilities** (reconstitution,
  void_drain, protective_bubble, berserker_rage, frenzy): rather than exactly model
  each, treat a monster carrying an UNMODELED hardening ability as NOT-winnable-by-
  margin (predict win only with comfortable HP headroom) so the bot doesn't engage
  bosses it can't actually beat. `reconstitution` specifically ⇒ unwinnable unless
  kill ≤ 20 turns (a hard guard). This avoids modeling exotic mechanics the bot
  won't face for a long time while staying SAFE.
- **corrupted** HELPS the player — modeling it is optional (ignoring it is
  conservative/safe). Defer.

## Approach (per ability, proven-core)

Each modeled ability adjusts `killStep`/`dieStep`/effective-HP in the EXACT-integer
×10000 model. poison/healing are flat per-turn terms (net-step, like lifesteal).
barrier/burn/reconstitution change the HP pools or add turn caps. Re-prove
`predict_win_eq_sim` / monotonicity / maxturns each time (the generic ceilDiv/
simRoundsAux lemmas survive; the lean4 sorry-filler agent fills the re-proofs).
Python mirrors EXACTLY (integer). New monster-ability accessors (parse monster
effects, like monster_lifesteal). Differential exercises each ability ≠ 0 + guards;
mutations per term; re-verify Fight-for-drops reachability.

## Sequencing (sub-phases — land each through the gate)
1. poison (normal, simplest DoT) — proves the per-turn-DoT extension.
2. barrier (normal, effective-HP) — proves the HP-pool extension.
3. healing (regen) + burn (decaying DoT, elite).
4. Conservative boss-ability guard (reconstitution turn-cap + unmodeled-hardening
   margin) — cheap safety, big correctness for boss content.
Defer: corrupted (helps player), exact frenzy/berserker/void_drain/bubble models.

## Risk
predict_win gates Fight-for-drops planning AND composes with the combat-veto. Each
ability change must re-verify chicken→feather reachability and not destabilize the
veto. HIGH effort (multiple proven-core re-proofs). Land incrementally; each
sub-phase is independently gate-verifiable.
