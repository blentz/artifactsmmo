"""Pure core: the per-turn terms of the closed-form fight model and the verdict
`predict_win` / `combat_margin` read from them (`docs/PLAN_consumable_utility.md`
increment 1; proved model `formal/Formal/FightOutcome.lean`, whose
`Formal.FightOutcome.closedWin_eq_predictWin` ties these terms to
`Formal.PredictWin.predictWin`; differentials `formal/diff/test_predict_win_diff.py`,
`formal/diff/test_combat_margin_diff.py`, `formal/diff/test_fight_outcome_diff.py`).

`combat.combat_terms` resolves a fight's stats into integers; this module turns
them into the closed form's quantities, in the exact ×10000 scale the steps use:

* `kill_step` — net per-round damage to the monster;
* `die_step` — net per-round damage to the player;
* `rounds_to_kill` — rounds until the monster dies behind its barrier
  (`kill_rounds`); ⌈monster HP × 10000 / kill_step⌉ without one;
* `effective_hp` — the player's HP at fight start (current HP, capped at max);
* `rounds_to_die` = ⌈effective_hp × 10000 / die_step⌉;
* `player_first` — who moves first (`combat.moves_first`: higher initiative, a tie
  to the higher HP, a tie on both to the monster);
* `exit` — which guard of the ladder decided the fight before the round count,
  in the order the closed form tests them.

The verdict and the margin are read from the terms, so both share one ladder
and the turn walk (`fight_outcome_core`) reads the same numbers."""

from dataclasses import dataclass
from enum import Enum

MAX_TURNS = 100
"""A fight unresolved by turn 100 is a loss (documented combat cap)."""

WIN_MARGIN = MAX_TURNS + 1
"""Sentinel margin for the die_step<=0 (out-sustain) win branch of `terms_margin`."""

LOSE_MARGIN = -(MAX_TURNS + 1)
"""Sentinel margin for all losing / unkillable branches of `terms_margin`."""

SCALE = 10000
"""The exact-integer scale of the per-round steps (×200 crit × ×100 percent ×
×100 percent, `Formal/PredictWin.lean`)."""

BARRIER_PERIOD = 5
"""The monster's turns between barrier refreshes (`kill_rounds`)."""


class FightExit(Enum):
    """The guard of the closed-form ladder that decided a fight, in ladder order."""

    NONE = "none"                    # every guard passed: the round counts decide
    NO_DAMAGE = "no_damage"          # raw_player <= 0
    UNKILLABLE = "unkillable"        # kill_step <= 0: out-healed / out-resisted
    OVER_CAP = "over_cap"            # rounds_to_kill > MAX_TURNS
    RECONSTITUTED = "reconstituted"  # the monster fully heals before it dies
    OUT_SUSTAIN = "out_sustain"      # die_step <= 0: the player cannot lose HP
    DEAD = "dead"                    # effective_hp <= 0: the fight starts lost


@dataclass(frozen=True)
class FightTerms:
    """The closed form's quantities for one fight (×10000 scale for the steps).
    `rounds_to_kill` is 0 when the ladder exits before it is defined
    (`NO_DAMAGE`, `UNKILLABLE`); `rounds_to_die` is 0 unless `exit` is `NONE`."""

    exit: FightExit
    kill_step: int
    die_step: int
    rounds_to_kill: int
    effective_hp: int
    rounds_to_die: int
    player_first: bool


def ceil_div(numerator: int, denominator: int) -> int:
    """⌈numerator / denominator⌉ for a positive denominator (`Formal.PredictWin.ceilDiv`)."""
    return -(-numerator // denominator)


def effective_player_hp(hp: int, max_hp: int) -> int:
    """Player HP at fight start: current HP capped at max_hp, or 0 if already dead."""
    return min(hp, max_hp) if hp > 0 else 0


def kill_rounds(monster_hp: int, barrier: int, kill_step: int, player_first: bool) -> int:
    """Rounds until a monster of `monster_hp` behind a `barrier` dies at a
    positive `kill_step` (×10000) a round; `MAX_TURNS + 1` when no block of
    hits gets through the barrier.

    The barrier's effect text: "At the start of the fight and every 5 played
    turns, gain a protective barrier of {value} HP. All attacks are redirected
    to this barrier until it is destroyed." Lor v king_slime, 2026-10-17: the
    barrier is raised at the start and SET back to full at the monster's 5th
    and 10th turns, and a hit's excess passes through ("36 absorbed, 15
    through"). So the hits come in blocks against one barrier each: the first
    `L1` hits (5 when the player moves first, its refresh following the
    player's 5th hit; 4 when the monster does, the refresh coming before the
    player's 5th hit — a ruling: no monster-first barrier fight is on record),
    then blocks of `BARRIER_PERIOD`. A block of `n` hits gets
    `max(0, n × kill_step − B)` through, so after the first block each full
    block gets `g = 5 × kill_step − B` through, and the last block needs
    `⌈(R + B) / kill_step⌉` hits for the `R` left. With no barrier this is
    ⌈H / kill_step⌉."""
    pool, shield = monster_hp * SCALE, barrier * SCALE
    first = BARRIER_PERIOD if player_first else BARRIER_PERIOD - 1
    if pool + shield <= first * kill_step:
        return ceil_div(pool + shield, kill_step)
    through = BARRIER_PERIOD * kill_step - shield
    if through <= 0:
        return MAX_TURNS + 1
    left = pool - max(0, first * kill_step - shield)
    blocks = ceil_div(left, through) - 1
    last = left - blocks * through
    return first + blocks * BARRIER_PERIOD + ceil_div(last + shield, kill_step)


def fight_terms(raw_player: int, kill_step: int, monster_hp: int,
                reconstitution: int, die_step: int, hp: int, max_hp: int,
                player_first: bool, barrier: int = 0) -> FightTerms:
    """The closed form's guard ladder over resolved integers. `kill_step` /
    `die_step` are `combat._kill_step_net` / `combat._die_step`; the monster's
    `barrier` refreshes (`kill_rounds`)."""
    effective_hp = effective_player_hp(hp, max_hp)
    if raw_player <= 0:
        return FightTerms(FightExit.NO_DAMAGE, kill_step, die_step, 0, effective_hp, 0, player_first)
    if kill_step <= 0:
        return FightTerms(FightExit.UNKILLABLE, kill_step, die_step, 0, effective_hp, 0, player_first)
    rounds_to_kill = kill_rounds(monster_hp, barrier, kill_step, player_first)
    if rounds_to_kill > MAX_TURNS:
        return FightTerms(FightExit.OVER_CAP, kill_step, die_step, rounds_to_kill,
                          effective_hp, 0, player_first)
    # Reconstitution: the monster regains ALL HP every N turns. If we can't kill it
    # strictly faster than that period, it fully heals before dying ⇒ unwinnable.
    if 0 < reconstitution <= rounds_to_kill:
        return FightTerms(FightExit.RECONSTITUTED, kill_step, die_step, rounds_to_kill,
                          effective_hp, 0, player_first)
    if die_step <= 0:
        return FightTerms(FightExit.OUT_SUSTAIN, kill_step, die_step, rounds_to_kill,
                          effective_hp, 0, player_first)
    if effective_hp <= 0:
        return FightTerms(FightExit.DEAD, kill_step, die_step, rounds_to_kill,
                          effective_hp, 0, player_first)
    rounds_to_die = ceil_div(effective_hp * SCALE, die_step)
    return FightTerms(FightExit.NONE, kill_step, die_step, rounds_to_kill,
                      effective_hp, rounds_to_die, player_first)


def terms_win(terms: FightTerms) -> bool:
    """The closed-form verdict: the out-sustain exit wins, every other exit
    loses, and otherwise the first mover wins the tied round."""
    if terms.exit is FightExit.OUT_SUSTAIN:
        return True
    if terms.exit is not FightExit.NONE:
        return False
    if terms.player_first:
        return terms.rounds_to_kill <= terms.rounds_to_die
    return terms.rounds_to_kill < terms.rounds_to_die


def terms_margin(terms: FightTerms) -> int:
    """Signed margin whose sign equals `terms_win`: the sentinels at the exits,
    else the round cushion `rounds_to_die - rounds_to_kill (+1 if first)`."""
    if terms.exit is FightExit.OUT_SUSTAIN:
        return WIN_MARGIN
    if terms.exit is not FightExit.NONE:
        return LOSE_MARGIN
    return terms.rounds_to_die - terms.rounds_to_kill + (1 if terms.player_first else 0)
