# Fight odds, part B: the yes/no gates read the odds

Date: 2026-10-15. Follows `2026-10-15-fight-odds-design.md` (part A, live at
3e61fbec; burn ticks exact at 4f2c89bc).

## Intent (USER 2026-10-15)

- The yes/no fight gates (`predict_win`, `is_winnable` and every caller) decide
  on the exact win probability, not on the closed form's expected-round race.
- The threshold is **derived from loss cost**, per character × monster, with
  **0.8** as the default win rate until there is enough win/loss data to derive
  it (USER: "derived from loss cost, with 0.8 default win rate until we collect
  enough win/loss data to derive loss costs").
- Derivation: **losses may cost at most one won fight per kill** (USER: "Losses
  <= win cost"). Kept as derived even though measured values sit near 0.5
  (USER: "Keep the rule as derived").
- **A penalty below 0.75 win rate**, as a gear-routing signal (USER: "in theory,
  if all of our fights are below 75% win rates, we probably need better gear";
  chose "Gear-routing signal").
- Data scope: **per character × monster** (USER).

## The live problem

Exact odds against the closed-form verdict, at full HP, on live state
(2026-10-15 21:40Z, `probe_gate_vs_odds.py`):

| Character | Monster | `predict_win` | margin | P(win) |
|---|---|---|---|---|
| C3P0 (34) | cyclops | win | 1 | 0.5115 |
| R2D2 (35) | cultist_acolyte | win | 1 | 0.6890 |
| Robby (38) | imp | **lose** | 0 | 0.9997 |

- C3P0 held a cyclops kill task at P = 0.51: 52 losses in 140 fights since
  10-10. The task root (`decisions/root.py:_task_root`) asks `is_winnable`, which
  ends in `predict_win`.
- Robby is refused a sure win because `_die_step` still charges burn as
  `burn% × player attack` every round (part A fixed only the odds walk).
- Across C3P0's 47 monsters the odds are bimodal: every monster but cyclops,
  owlbear (0.017) and imp (0.001) is above 0.9999 or below 0.0001. The
  threshold decides the few fights near an even race; the burn base decides the
  rest.
- One uncached `fight_odds` call costs about 1 ms (mean over 47 monsters ×
  3 characters), 28 ms at worst.

Measured loss cost (learning.db `cycles` since 10-10; seconds of the fight's
cooldown plus the Rest and Move cooldowns until the next fight):

| Pair | wins | t_win | losses | t_loss | θ |
|---|---|---|---|---|---|
| R2D2 v owlbear | 339 | 94.7 | 260 | 90.3 | 0.488 |
| Robby v owlbear | 1305 | 87.6 | 103 | 81.6 | 0.482 |
| C3P0 v cyclops | 88 | 107.3 | 52 | 116.5 | 0.520 |
| C3P0 v vampire | 2128 | 54.1 | 60 | 36.9 | 0.406 |
| Lor v cyclops | 432 | 86.0 | 95 | 118.3 | 0.579 |
| R2D2 v rat | 158 | 66.1 | 7 | 118.9 | 0.643 |

A close won fight ends near 0 HP and rests about as long as a loss, so the
derived θ is near 0.5. In that range the 0.75 gear signal (§3) does the work.

## Design

### §1 One verdict

- `combat.predict_win(state, game_data, monster)` becomes
  `win_probability(state, game_data, monster) >= win_threshold(state, monster)`.
  Inputs are unchanged from part A's `win_probability`: `state.hp`, the best
  on-hand loadout, the worn restore potion.
- Every caller follows with no edit: `is_winnable`, the task root, the grind
  target cascade, `band_combat_target`, `tier_cleared`, `drop_fight_winnable`,
  `_party_pick`, `cheapest_path_to_level`, `combat_capable`, `beatable_count`,
  the REST_FOR_COMBAT guard, `_fight_ready`, and the censuses.
- `win_threshold(state, monster) = state.win_thresholds.get(monster,
  DEFAULT_WIN_THRESHOLD)`, `DEFAULT_WIN_THRESHOLD = Fraction(4, 5)`.
- `WorldState.win_thresholds: Mapping[str, Fraction]` (default empty), filled
  once per cycle beside `lost_fights` (`player._refresh_lost_fights`'s
  call sites). Ruling: on `WorldState`, not only inside
  `is_winnable(history)`, so callers without a history read the same θ. Two
  thresholds for one fight would be two authorities (the shape of several past
  livelocks). Cost if wrong: one more field on a frozen dataclass.
- `fight_walk`'s `LoopRate.win` stays `fight_outcome` (part A); ranking reads
  `xp_per_second`, which already carries P(win).

### §2 θ from loss cost

- `θ = t_loss / (t_win + t_loss)` per (character, monster), as an exact
  `Fraction` of integer seconds totals.
  - Expected seconds per kill is `t_win + (1 − p)/p × t_loss`. The rule "loss
    overhead per kill ≤ one won fight's cost" is `(1 − p)/p × t_loss ≤ t_win`,
    that is `p ≥ t_loss / (t_win + t_loss)`.
- Measured by a new `LearningStore` query over `cycles`, all levels and
  loadouts:
  - A fight is a `FightAction` cycle with outcome `ok` (win) or
    `error:fight_lost` (loss); other outcomes are skipped.
  - Its cost is its `actual_cooldown_seconds` plus the
    `actual_cooldown_seconds` of every `RestAction` and `MoveAction` cycle of
    the same character after it and before that character's next
    `FightAction`. A fight with no later fight is skipped (open window).
  - t_win and t_loss are the mean costs of wins and of losses.
- A pair gets a θ only with at least `MIN_WIN_SAMPLES` (5) wins **and** 5
  losses; otherwise it is absent and the default 0.8 applies.
- Ruling: samples are not scoped by level or loadout. Loss cost is rest plus
  the walk back, which gear barely moves. Cost if wrong: θ lags a gear change
  by the samples it takes to dilute the old ones.
- Known and accepted (USER chose per pair): a pair refused at the default is
  never fought, so it never gets data, and stays at 0.8.
- Ruling: the query reads a bounded window (the last 14 days of `cycles`) so a
  cycle's refresh stays cheap. Cost if wrong: older evidence is ignored.

### §3 The gear signal below 0.75

- `SECURE_WIN = Fraction(3, 4)`.
- `SelectionContext.combat_risky: bool`, true when the grind target
  (`ctx.combat_monster`) has `win_probability < SECURE_WIN` in the loadout the
  band picked. Set beside `combat_propped` in `player._selection_context`.
- `IsAFightBlockingMe` treats `combat_risky` like `combat_propped`: a risky
  target does not hide gear, so the walk asks the task horizon and the gear
  sheet first. When gear names nothing, `IsThereACombatTarget` still grinds the
  risky monster, so nothing walls.
- The task monster: `combat_deficit.has_combat_deficit` becomes "P(win) <
  max(θ, SECURE_WIN)", and `combat_deficit`'s chain "closes" at the same bar,
  so `WhichSlotClosesTheFight` aims at a secure fight, not a merely winnable
  one.

### §4 What stays closed form

- **Burn in `_die_step` is charged off the monster's attack**: `burn% ×
  monster attack × 100` (the first tick before rounding). The ticks decay, so it
  bounds every round's tick. It feeds the exits and `combat_margin`; Lean
  `predictWin`'s burn term changes to match; `fight_numbers`' `flat_burn`
  subtraction changes with it. Fixes Robby v imp at the margin.
- **`combat_margin` stays the closed-form round cushion**, used to rank gear in
  `combat_deficit` until part C. The invariant `predict_win ⇔ combat_margin > 0`
  is retired: `formal/diff/test_combat_margin_diff.py`'s sign check moves to
  `terms_win`, and `combat_margin`'s docstring says it is a ranking signal.
- **`is_winnable`'s monotonic-win shortcut is removed**
  (`_won_at_or_above_level`). It rescued a pessimistic formula; the odds are
  calibrated (part A's live check: buckets within 1 point), and the shortcut
  says "winnable" for a coin-flip fight until the first loss. The learned-loss
  veto (`loss_vetoed`: < 40% over 5 fights at this level in this loadout)
  stays.

### §5 Lean and liveness

- The liveness chain (`Liveness/WinnableGrounded.winnableAcrossBand_grounded`
  → `PerceptionRefresh` → `LevelingDescent`) grounds "a winnable monster in
  every band below 50" by kernel `decide` of `predictWin` over 49 witness rows.
  Under §1 each row must hold `winProb (fightOdds …) ≥ θ`.
- A kernel `decide` of `fightOdds` is infeasible: the Lean `tree` is unmerged,
  4^rounds leaves. Ruling: ground each row on the **worst-case race** instead.
  - New theorem in `FightOdds.lean`: if the fight is won with every player
    roll normal and every monster roll a crit (`pCrit := 0`, `mCrit := 100`, a
    single path), then `winProb (fightOdds t d …) = 1`, given `killNormal ≤
    killCrit`, `dieNormal ≤ dieCrit` and both chances ≤ 100.
  - The single path is cheap for the kernel. `1 ≥ θ` for every θ, so the
    theorem needs no bound on θ (the earlier `θ ≤ 0.99` hypothesis is dropped).
- Measured 2026-10-15 on the witness fixtures (`probe_witness_worst.py`):
  every band level 1–49 has a worst-case winner in band (2–13 monsters per
  level, no gap). Nine of today's 49 rows are below P 0.99 (L29 imp is 0.54),
  so `formal/sim/winnable_witness` re-picks rows among worst-case winners.
- No `sorry`, no new axiom.

### §6 Cost

- `fight_odds` is memoised on its value inputs (part A). The plan measures plan
  time per cycle on live state before and after, budget under 2×. If over, the
  cache grows; any shortcut that skips the walk must be proved exact.

## Testing

TDD in `tests/test_ai/`:

- §1: C3P0 v cyclops replay (P 0.5115) is not winnable at θ 0.8 and is at
  θ 0.5; a θ entry for one monster changes only that monster; `predict_win`
  equals `win_probability >= θ` on random fights.
- §2: θ from synthetic cycles (wins, losses, Rest and Move between fights,
  interleaved characters, an unrelated action in the window, a trailing open
  window); fewer than 5 wins or 5 losses gives no entry.
- §3: a risky grind target sends `IsAFightBlockingMe` to the gear arm; with no
  gear the walk still returns the grind; `has_combat_deficit` at P 0.7 with
  θ 0.5 is true.
- §4: burn charged off the monster's attack (imp: 15% × 45); Robby v imp
  replay is winnable; `is_winnable` no longer returns true off a higher-level
  win alone.
- Differential: `formal/diff` harnesses for `predict_win` (now the odds and θ),
  `combat_margin` (closed form only), the burn term, and the witness rows.
- Mutants for the threshold comparison, the θ formula, the 5-sample bar, the
  Rest/Move window, and `combat_risky`.
- Full `formal/gate.sh` green before push.

## Live check (after restart)

- No fight in the 0.5–0.8 bucket for a pair without a measured θ that allows
  it (`combat_loadout_outcome.p_win` against the pair's θ).
- C3P0 off the cyclops task, or on gear for it.
- Robby fights imp if it ranks.
- Fleet losses per hour down; fleet XP/h not down against 6,660/h (the
  4f2c89bc baseline).

## Non-goals

- Gear choice by odds (`pick_loadout`, `combat_deficit`'s margin ranking,
  initiative): part C.
- Party fights (`group_fight_core`, `wins_as_a_party`): unchanged.
- The respawn walk-back's layer transitions (part A residual).
