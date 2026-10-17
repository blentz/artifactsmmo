# PLAN: barrier refresh

## Problem

The fight model charges a monster's `barrier` once, as extra HP
(`monster_hp + monster_barrier`, `combat.py`, `Formal.PredictWin.predictWin`).
The server re-raises it. Effect text (`GET /effects/barrier`):

> At the start of the fight and every 5 played turns, gain a protective barrier
> of {value} HP. All attacks are redirected to this barrier until it is destroyed.

Lor v king_slime, 2026-10-17 20:02:25 UTC, lost at 546/960 HP with P(win)
modelled 0.999. The log shows the barrier raised at fight start and refreshed
"to 100 HP" at turns 10 and 20 (the monster's 5th and 10th turns). Lor hits
for a flat 115 a round and needed 12 hits, not the 10 the flat add allows;
the monster got 11 turns, not 9. Over 23 fights at 960 max HP, 2 took 546 or
more damage; the model gave that 0.12%.

Live barrier monsters (2026-10-17): king_slime 100, goblin_guard 100,
rosenblood 500, dusk_beetle 200, sonnengott 350. None heals
(no healing, lifesteal or void drain), so the net kill amount a round deals
is all damage.

## Rules (from the logs; rulings marked)

* The barrier starts at its value. Damage goes to the barrier first; what is
  left over passes through to HP in the same hit ("dealt 51 damage (36
  absorbed, 15 through)").
* At the start of the monster's 5th, 10th, 15th ... turn (rounds 5, 10, 15 ...)
  the barrier is SET to its value ("refreshes its barrier to 100 HP").
* RULING (no monster-first barrier fight is on record: 83/83 player-first):
  the refresh is on the monster's OWN 5th turn whoever moves first. Player-first
  data rules out "every 5 global turns" (no refresh at turn 5). Cost if wrong:
  a monster-first refresh half a round late or early.
* RULING: the barrier absorbs the round's NET kill amount when positive, and a
  non-positive amount (a mean-modelled heal) goes to HP. Exact for every live
  barrier monster (none heals).

## Closed form (`fight_terms_core.kill_rounds`)

×10000: `H = hp·S`, `B = barrier·S`, kill step `k > 0`, period `P = 5`, first
block `L1 = P` when the player moves first (refresh after its 5th hit), else
`P − 1` (refresh before its 5th hit).

* `H + B ≤ L1·k` → `⌈(H + B) / k⌉` (dies in the first block).
* `P·k ≤ B` → `MAX_TURNS + 1` (a full block never gets through: OVER_CAP).
* else `g = P·k − B`, `H' = H − max(0, L1·k − B)`, `q = ⌈H'/g⌉ − 1`,
  `R = H' − q·g`, `j = ⌈(R + B)/k⌉`; rounds `= L1 + q·P + j`.

With `B = 0` this is `⌈H/k⌉`. Lor: `L1 = 5`, `g = 475`, `H' = 525`, `q = 1`,
`R = 50`, `j = 2` → 12.

## Walk (`fight_odds_core.fight_odds`)

State gains the barrier pool: `(monster, barrier, player, stock)`. A player hit
`absorb`s; the monster's turn in a round divisible by 5 sets the barrier before
it hits. Monster lifesteal heals HP, never the barrier.

## Group walk (`group_fight_core`)

`PartyBoss` carries `hp` and `barrier` apart. First movers' net is absorbed,
the boss turn refreshes (rounds divisible by 5), late movers' net less the
drain is absorbed. The gate's kill rounds use `kill_rounds` with the
monster-first block (never fewer rounds than either order).

## Lean

`Formal.PredictWin.killRounds` is the same closed form, proved against the
round walk (`predict_win_eq_sim`); lemmas: positive, antitone in the kill
step, monotone in HP and barrier, equal to `ceilDiv` at barrier 0.
`FightOdds.tree` gains the barrier pool; `fightOdds_noCrit` relates it to
`fightOutcome`.
`GroupFight` mirrors the group walk. Differentials compare Python's closed form
to the Lean simulation.

## Status

- [x] Python closed form + walk + group + tests; `expected_damage` counts the
      barrier too; the witness generator's counted-crit path carries it
- [x] Lean model + proofs (`.superpowers/sdd/barrier/lean-report.md`). Added
      hypotheses: barrier ≥ 0 (`fightOdds_noCrit`, `winProb_eq_one_of_worst`,
      `winProb_ge_critBound`, `groupOutcome_single`); boss HP > 0 or no
      barrier (`groupOutcome_single`); "not walled" for the `killRounds`
      monotonicity lemmas (the `maxTurns + 1` sentinel can sit below a long
      finite count); turn order kept for `GroupFight.killRounds_antitone`
      (a late mover joining an all-first party can turn 5 rounds into 6)
- [x] live probe: Lor at 546 reads 0.952 (was 0.999); `rest_pays` fires at
      ≤ 600 HP; modelled kill turns 17/19/21+ at 30/60/8% against 35/57/9%
      logged over 23 fights
- [x] gate green (rc 0); mutants, commit, push
