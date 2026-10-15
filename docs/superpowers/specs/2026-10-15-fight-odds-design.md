# Fight odds: exact win probability prices the fight loop (part A)

Date: 2026-10-15.

## Intent (USER 2026-10-15)

- Combat calibration, option 1: the bot knows a fight's real odds and uses them
  wherever it decides about fights.
- Delivered in three parts, each with its own spec, plan and live check
  ("A then B then C"):
  - **A (this spec):** an exact win-probability core, and the fight loop's XP
    rate (`loop_rate`) priced by it. Potions become worth carrying against a
    risky fight. Every fight, a sure win included, is priced as an expectation
    over its crit endings, so a sure win's price changes wherever crits change
    its drinks or its end HP (Amendment 11).
  - **B:** the yes/no gates (`is_winnable`, `predict_win` and their ~12 callers)
    read the odds.
  - **C:** gear choice (`pick_loadout`, `combat_deficit`) ranks by the odds, so
    initiative has a value.
- Approved design: sections 1 and 2 as presented in chat, including pricing
  the walk back from the respawn tile.

## The live problem (learning.db and server fight logs, 2026-10-13..15)

- R2D2 (level 34) against owlbear: `combat_loadout_outcome` holds 569 fights,
  every one `predicted_win = 1`, 248 lost (44%). Robby (level 37): 1301 fights,
  87% won.
- **The per-hit model is exact.** 131 server fight logs
  (`get_character_logs_my_logs_name_get`, `content.fight.logs`) show R2D2 hitting
  for 64 + 77 = 141 (crit 96 + 116 = 212) and the owlbear for 83 (crit 125),
  which is what `fight_numbers` computes. One crit roll covers a whole turn:
  both of R2D2's elements crit together. Observed crit rates: 44.2% (model 45%)
  and 4.2% (model 5%). Every fight started at full HP, 785/785.
- **The verdict is the defect.** `predict_win` races expected rounds, with crit
  at its mean: rounds_to_kill 9, rounds_to_die 10, owlbear first (initiative
  250 > 200), margin 1, so "win". The exact probability over crit rolls is
  **0.631**; the logs show 88/131 = 67%. Of 253 losses, 192 end on turn 17
  (the owlbear's 9th hit), and every one of those has at least one owlbear crit.
- **Why nothing compensates.** `loop_rate` prices a predicted win at full XP and
  a predicted loss at 0 (`loop_rate.py:117`). `best_loadout` picks potions by
  that rate, so a potion is chosen only when the bare fight is predicted lost.
  A 63% fight is predicted won, so R2D2 carries none.
- **The lever.** Solo restore potions drink every player turn below 50% HP
  (`fight_outcome_core.drink`). Exact odds for R2D2 against owlbear:

  | Loadout | P(win) |
  |---|---|
  | none | 0.6308 |
  | `minor_health_potion` (+70, alchemy 20) | 1.0000 |
  | `health_potion` (+100, alchemy 30) | 1.0000 |

  `health_splash_potion` heals another character and has no effect solo
  (`fight_walk._restore_of` rejects it). Robby's 87% comes from moving first
  (`lich_race_medal`, +100 initiative) and a `lifesteal_rune`, not from the
  splash potion it wears.
- **After a loss** (learning.db, every R2D2 owlbear loss) the character is at
  the respawn tile `(0,0)` with `hp = 1`, then rests 100 s to full.
  `learning/fight_loop_cost.loss_cost` already prices the fight plus that Rest,
  and names the walk back as an open residual (`docs/PLAN_loss_risk.md`).
- The server's fight simulator (`/simulation/fight`) is members-only (HTTP 451).
  Fight logs and the store are the ground truth.

## Design

### §1 `fight_odds_core` (new pure core, Lean-bound)

One function walks every way a fight can end:

    fight_odds(terms, damage, hp_start, max_hp, restore, stock) -> tuple[Ending, ...]
    RoundDamage = (monster_hp, kill_normal, kill_crit, p_crit, die_normal, die_crit, m_crit)
    Ending = (prob: Fraction, win: bool, turns: int, hp_end: int, used: int)

`hp_end` is in the ×10000 scale, as in `FightOutcome`.

**Inputs.** `terms` is today's `FightTerms` (it decides the guard exits) and
`damage` is a `RoundDamage`, the crit split per side (Amendment 8):

- player: `kill_hit` (normal hit) and `kill_crit_hit`, both ×10000; `p_crit` in
  percent;
- monster: `die_hit` and `die_crit_hit`, both ×10000; `m_crit` in percent;
- the crit hit is the sum over elements of `round_half_up(element_damage × 3/2)`,
  the rounding the server applies (logs: 77 → 116, 83 → 125, 64 → 96);
- `kill_rest = kill_step − 50 × raw_player × (200 + p_crit)` and
  `die_rest = die_step − 50 × raw_monster × (200 + m_crit)`: everything today's
  expected step charges beyond the bare hit (monster healing, void drain,
  bubble and sun shield on the kill side; poison, burn, greed, berserker rage,
  frenzy, enchanted mirror and the player's mean lifesteal on the die side). It
  applies every round as a deterministic term with today's conservative
  bounds. Only crits branch. `RoundDamage` does not carry `kill_rest` and
  `die_rest` as fields: `fight_split` folds the rest into both amounts,
  `kill_normal = kill_hit + kill_rest`, `kill_crit = kill_crit_hit + kill_rest`,
  `die_normal = die_hit + die_rest`, `die_crit = die_crit_hit + die_rest`.

`fight_numbers` (`combat.py`) builds the split alongside `FightTerms` from the
same resolved integers, so the two cannot disagree.

**The walk.**

- The guard ladder exits decide exactly as today, with probability 1:
  `OUT_SUSTAIN` is one winning ending in `rounds_to_kill`; `NO_DAMAGE`,
  `UNKILLABLE`, `OVER_CAP`, `RECONSTITUTED`, `DEAD` and a non-positive starting
  pool are one losing ending in round 0. Ruling: the exits stay deterministic.
  Cost if wrong: a fight near an exit boundary keeps today's yes/no answer.
- Otherwise the walk tracks `(monster_pool, player_pool, stock)` with a
  probability, round by round. A player turn first applies `drink` (start of
  turn, below half, one per turn while stock lasts), then deals `kill_hit` with
  probability `1 − p_crit/100` or `kill_crit_hit` with `p_crit/100`, plus
  `kill_rest`. A monster turn deals `die_hit` or `die_crit_hit` with
  `m_crit/100`, plus `die_rest`. `player_first` orders the two turns, as in
  `fight_outcome`.
- A monster pool at or below 0 ends the fight as a win; a player pool at or
  below 0 ends it as a loss; any state unresolved after `MAX_TURNS` rounds is a
  loss.
- Identical states are merged each round (their probabilities summed), so a
  round holds at most `(r + 1)²` pool pairs per stock value.
- Probabilities are exact `Fraction`s; Lean uses `ℚ`.

**Lean (`formal/Formal/FightOdds.lean`, new).** Theorems:

- `fightOdds_sum_one`: the endings' probabilities sum to 1.
- `fightOdds_noCrit`: under the explicit hypotheses `pCrit = 0`, `mCrit = 0`,
  `killNormal = killStep`, `dieNormal = dieStep`, `monsterHp` equal in the
  damage and the terms, and `0 < monsterHp` (Amendment 3), the result is one
  ending with probability 1, equal to `fightOutcome` (win, turns, hp_end, used)
  over the terms. (Those sums are today's `kill_step` and `die_step` at
  zero crit, since `kill_hit = 50 × raw_player × 200`; so the odds walk
  generalises the existing walk rather than replacing it.)
- `fightOdds_win_mono_stock`: P(win) does not fall when the stock rises.
- `fightOdds_win_mono_hp`: P(win) does not fall when the starting HP rises,
  **with `stock = 0` only** (Amendment 2). With stock it is false: at hp 49
  of 100 the player drinks and wins, at hp 50 it does not drink and dies.

`Contracts.lean`, `Manifest.lean`, `Audit.lean` and `Oracle.lean` change with
the model. A new `formal/diff/test_fight_odds_diff.py` checks Python against
the oracle on random inputs.

**Unchanged in A:** `predict_win`, `combat_margin`, `is_winnable` and
`fight_outcome` keep their yes/no meaning and their proofs.

### §2 Pricing: `loop_rate` reads the odds

**The rate.** Over a long run, XP per second is expected XP per fight divided
by expected seconds per fight (renewal-reward). For the endings `e` of the
loadout's walk:

    E[xp]      = P(win) × xp_per_kill
    E[seconds] = FIGHT_SECONDS
               + Σ_e prob_e × (recovery(max_hp − hp_end_e) + consumed(used_e))
               + P(loss) × travel_seconds(RESPAWN_TILE, monster_tile)
    xp_per_second = E[xp] / E[seconds]

- A losing ending has `hp_end = 1` (the server leaves 1 HP), so its recovery
  prices `max_hp − 1` through the same `recovery_choice` (food or rest) a win
  uses. Potions drunk before the loss are still consumed.
- Payability (Amendment 7). A potion with a replacement price is priced per
  ending: each ending's drinks past the held units cost their price. A potion
  with NO replacement is judged once, over the expectation: the loadout is
  unpayable (`loop_rate` returns None) when `ceil(expected drinks) > held`. A
  rare deep ending that drinks past the held units does not veto it.
- `RESPAWN_TILE = (0, 0)`, cited to learning.db (every R2D2 owlbear loss row
  ends there). Ruling: this is observed server behaviour, not API data; it
  closes the `PLAN_loss_risk` residual. Cost if wrong: a moved respawn
  misprices a loss's walk back by its distance difference × 5 s.
- `monster_tile` is the monster's nearest fight tile to `RESPAWN_TILE`,
  priced by `cost_core.travel_seconds`. It is looked up only when
  `P(win) < 1` (a sure win has no walk back). The tiles are exactly the ones
  the action factory builds a `FightAction` from, on every layer
  (`ai/fight_tiles.fight_tiles`: the legacy overworld/event/open-raid index,
  an active raid's tiles, and interior/underground tiles); the fight-ahead
  guards (`best_loadout.fight_ahead_loadout`,
  `strategy_driver._fight_step_prep`) use the same set. A monster with no tile
  on any layer has no fight ahead (Amendment 6). Ruling: nearest to the
  respawn tile, not to the character, because the walk back starts there.
  Cost if wrong: none for a single-spawn monster.
- Residual: the walk back is priced on the tile's (x, y) alone, so a walk back
  into an interior or the underground is under-priced by its layer
  transitions.

**`LoopRate`** gains `p_win: Fraction`. `win` keeps today's yes/no value
(`fight_outcome`), so `band_target`'s `rate.win` gate does not change until
part B. `hp_end`, `used` and `eaten` become the expected values: `used` and
`eaten` rounded UP to whole units, `hp_end` rounded down to whole HP
(Amendment 1); `potion_carry` keeps reading `used`. `xp_per_kill` is the
kill's XP when `P(win) > 0` and 0 otherwise.

**`best_loadout` is unchanged.** It already ranks by `xp_per_second`, which now
carries the risk: against owlbear, R2D2's bare loadout earns `0.63 × xp` over
a fight plus `0.37 ×` (a 100 s rest and the walk back), and a
`minor_health_potion` loadout earns the full `xp` for its potion price. The
potion wins whenever it has a route (held, or a replacement price and
`potion_stockable`). R2D2 has alchemy 16, so the route is a sibling's craft or
a price. With no route, the discounted rate still ranks owlbear below targets
that pay better.

**The combat band** (`tiers/band_target.rank_rate`, Amendment 5): its
MODELLED rank reads `rate.xp_per_second` (the expected rate); the MEASURED
upkeep rank is unchanged. A monster the record says is beaten while the
model's odds are nil ranks at the model's rate, 0.

**Lean (`formal/Formal/LoopRate.lean`).** The expected rate is added;
`expectedXpRate_sure_win` proves that `P(win) = 1` gives `xpPerSecond` over the
same expected seconds, and `expectedXpRate_mono_p` that the rate does not fall
when `P(win)` rises (Amendment 4). `formal/diff/test_loop_rate_diff.py` extends to the
expected form.

### §3 Cache and cost

- `fight_odds` is memoised on its integer inputs (a value key that holds no
  reference, `feedback_cache_key_must_pin_its_object`), with a bounded
  `maxsize`.
- The plan measures `best_loadout`'s time per cycle before and after, on the
  live fleet state. Budget: under 2× today's.

### §4 Calibration record

- `combat_loadout_outcome` gains `p_win` (a REAL), the loadout's P(win) at
  fight time, recorded next to `predicted_win` in
  `GamePlayer._record_combat_outcome`. It is None on old rows AND on party
  fights, which the solo odds do not model (Amendment 10).
- `combat-loadout-report` prints predicted against observed win rate per
  probability bucket (tenths), over rows with `p_win` set. This is the
  evidence part B reads.

### Non-goals (parts B and C, or later)

- The yes/no gates (`is_winnable`, `predict_win`, `wins_with_a_loadout`, the
  rest-for-combat guard, drop routes, tier-cleared): part B.
- Gear choice and initiative (`pick_loadout`, `scoring.py:289`,
  `combat_deficit`): part C.
- Party fights (`group_fight_core`): unchanged.
- Crit-linked effects (lifesteal on crit, frenzy) stay at their means inside
  `kill_rest` / `die_rest`.

## Testing

TDD in `tests/test_ai/`:

- §1: no-crit equals `fight_outcome` on random terms; probabilities sum to 1;
  the R2D2-owlbear replay (785 HP, hits 141/212 and 83/125, crits 45%/5%,
  owlbear first) gives P(win) = 0.6308 to four places, and about
  1 − 5e-11 with `minor_health_potion` (a run of crits can still outrun a
  70 HP drink; the test asserts > 1 − 1e-9, Amendment 9); every guard exit returns one ending with
  probability 1; the turn cap ends unresolved states as losses.
- The crit split: `fight_numbers` on the live owlbear numbers gives
  `kill_crit_hit = 212 × 10000` and `die_crit_hit = 125 × 10000`.
- §2: with no crit on either side (one ending) the loop prices exactly as the
  one `fight_walk` walk did; with crits a sure win is an expectation over its
  endings (Amendment 11); a 63% fight's rate includes the
  loss recovery and the walk back from `(0,0)`; `best_loadout` chooses
  `minor_health_potion` over bare for R2D2's owlbear numbers when it is held.
- §4: the record writes `p_win`; the report buckets it.
- Lean: the theorems build; `#print axioms` clean; differentials agree.
- Mutation anchors for every new branch, in the same commit.
- Full `formal/gate.sh` green before push.

## Live verification (learning.db, after restart)

- R2D2's owlbear losses below 10% per hour, or R2D2 moves off owlbear to a
  target with a better rate.
- Fleet character XP/h no lower than the window 2026-10-15 00:19–01:34Z
  (9,220 XP in 1.24 h, about 7,400/h).
- New `p_win` rows: predicted and observed win rates within ±10 points in every
  bucket holding at least 30 fights.

## Amendments (2026-10-15, execution)

Changes made while building part A, each with its reason. The sections above
are already corrected.

1. **§2 LoopRate rounding.** `used` and `eaten` round UP, `hp_end` rounds
   down. Why: a potion (or food) used in some endings must still be carried;
   rounding the expectation down would carry none for a fight that sometimes
   drinks one.
2. **§1 `fightOdds_win_mono_hp` holds only with `stock = 0`.** Why: with a
   restore it is false. Counterexample: at hp 49 of 100 the player drinks
   (below half) and wins; at hp 50 it does not drink and dies.
3. **§1 `fightOdds_noCrit` needs `0 < monsterHp`** and states its hypotheses
   explicitly: `pCrit = 0`, `mCrit = 0`, `killNormal = killStep`,
   `dieNormal = dieStep`, and the same `monsterHp` in damage and terms. Why:
   at monster HP <= 0 `fightOutcome` reports round 0 (`roundsToKill` is 0)
   while the odds tree always plays round 1. A real monster has HP >= 1.
4. **§2 Lean names.** The theorems are `expectedXpRate_sure_win` and
   `expectedXpRate_mono_p` (the spec said `expectedXpPerSecond_sure_win`, and
   did not name the monotonicity).
5. **§2 the combat band.** The band's MODELLED rank reads
   `rate.xp_per_second`; the measured upkeep rank is unchanged; a
   record-beaten, model-nil monster ranks 0. Why: ranking a risky monster by
   its full kill XP put it above a sure one that pays better.
6. **§2 spawn tile.** Looked up only when `P(win) < 1`. The source is the
   action factory's `FightAction` tiles on every layer (`ai/fight_tiles`),
   shared with the factory, `best_loadout.fight_ahead_loadout` and
   `strategy_driver._fight_step_prep`. No tile on any layer means no fight
   ahead. Why (final review C1): `monster_locations` holds only the overworld
   and event tiles, so 12 fightable monsters (rat, bat, lich, ...) raised
   `no spawn tile` in `heal_prep_goal` and got no prep. Residual: the walk back
   is priced on (x, y) alone and under-prices cross-layer walk backs.
7. **§2 payability.** A priced potion is priced per ending; a potion with no
   replacement is payable when `ceil(expected drinks) <= held`. Why (final
   review I1): judging an unpriced potion per ending vetoed a held potion
   whenever any rare ending drank past the held units, stricter than the old
   one-walk rule.
8. **§1 signature.** `fight_odds(terms, damage, hp_start, max_hp, restore,
   stock)`. `RoundDamage` folds the rest terms into `kill_normal`,
   `kill_crit`, `die_normal` and `die_crit`. Why: the guard exits read
   `FightTerms`, and a folded amount is one input per branch.
9. **Testing.** With `minor_health_potion` P(win) is about 1 − 5e-11, not
   exactly 1: a run of crits can still outrun a 70 HP drink. The test asserts
   P(win) > 1 − 1e-9.
10. **§4.** `p_win` is None on old rows and on party fights. Why: the solo odds
    do not model a party fight.
11. **Intent / §2 sure-win pricing.** A sure win is no longer priced exactly as
    before: recovery, consumed seconds, drinks and food are expectations over
    the crit endings (an ogre fixture at P(win) = 1 with crits 30/0 recovers in
    36.5 s against 40 s before). Only a fight with no crit on either side (one
    ending) prices exactly as the one `fight_walk` walk did, and a test pins
    that equality.
