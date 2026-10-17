"""Pure core: a fight's exact ending distribution over crit rolls (spec
2026-10-15 fight-odds §1; proved model `formal/Formal/FightOdds.lean`,
differential `formal/diff/test_fight_odds_diff.py`).

`fight_outcome_core.fight_outcome` races the EXPECTED rounds: crit is its mean.
The server rolls one crit per turn per side (2026-10-15 fight logs: both of a
character's elements crit together), so a fight one round ahead on the mean can
be a coin flip: R2D2 v owlbear is margin 1 round and P(win) = 0.6308. This walk
branches on both rolls every round and merges identical states, so a round
holds at most `(r + 1)²` pool pairs per stock value.

THE ROUND. `RoundDamage` holds what one round charges, ×10000: `kill_normal` /
`kill_crit` to the monster, `die_normal` / `die_crit` to the player, each the
bare hit plus every term today's expected step charges beyond it (healing,
poison, greed, ... — `combat.fight_split`) except burn and lifesteal. Only
crits branch. A player turn first takes its burn tick, then applies `drink`
(start of turn, below half, one per turn while stock lasts), then hits;
`player_first` orders the two turns, exactly as `fight_outcome`. A monster
pool at or below 0 is a win, a player pool at or below 0 a loss, and any state
unresolved after `MAX_TURNS` rounds a loss in round `MAX_TURNS`. Pools are not
capped: a negative amount (a mean-modelled heal larger than the bare hit) only
raises a pool, as the mean model allows.

LIFESTEAL. Server logs 2026-10-17 (2,327 heals over three characters): a crit
heals its attacker `lifesteal`% of that turn's crit damage, rounded
(`combat.lifesteal_heal`: 15% of 165 is 25), capped at the attacker's max HP,
and a crit that kills heals nothing. So the heal rides the crit branch: after
a non-killing player crit the player pool rises by `p_heal`, after a monster
crit the monster pool by `m_heal`, each by `cure`. It used to be a mean folded
into every hit; a guaranteed 3.33 a round clears HP breakpoints a 25 on 30% of
turns does not (C3P0 v cyclops: 0.896 modelled, 0.807 observed over 161
fights, 0.816 exact).

BURN. The server's text: "On his first turn, apply a burn effect of {value}% of
your attack of all elements. The damage is applied each turn and decreases by
10% each time." Logs of 292 imp fights (2026-10-15): "applies a burn of 7" for
15% of the imp's attack 45 (the player's is 80), then ticks 7, 6, 5,
4, 3, 2, 1 at the start of the player's turns, before the player hits. The
monster burns on its first turn, so the first tick is the player's turn of
round 2 when the player moves first, of round 1 when the monster does. A tick
that takes the pool to 0 or below is a loss in that round. Each tick is 9/10 of
the last, rounded down (ruling: the logs of a 7 burn cannot tell this from "less
10% of the first", which differs by about 10 HP over a 22 burn).

THE EXITS. The closed form's guard ladder decides first, with probability 1:
the out-sustain exit is one win in `rounds_to_kill` at the starting pool; every
other exit and a dead start is one loss in round 0 (spec ruling: the exits
stay deterministic). With both crit chances 0 and no burn the walk equals
`fight_outcome`
(`Formal.FightOdds.fightOdds_noCrit`)."""

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

from artifactsmmo_cli.ai.fight_outcome_core import drink
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS, SCALE, FightExit, FightTerms, effective_player_hp

FIGHT_ODDS_CACHE = 4096
"""Distinct fights `fight_odds` keeps (value keys: frozen dataclasses and ints)."""


@dataclass(frozen=True)
class RoundDamage:
    """One round's charges, ×10000, and the crit chances in percent."""

    monster_hp: int
    kill_normal: int
    kill_crit: int
    p_crit: int
    die_normal: int
    die_crit: int
    m_crit: int
    burn: tuple[int, ...]
    """The burn ticks in order, ×10000 (`burn_ticks`); empty without burn."""
    p_heal: int = 0
    """The player's lifesteal heal on a crit turn, ×10000; 0 without lifesteal."""
    m_heal: int = 0
    """The monster's lifesteal heal on its crit turn, ×10000."""


@dataclass(frozen=True)
class Ending:
    """One way the fight ends, with its probability (`hp_end` ×10000)."""

    prob: Fraction
    win: bool
    turns: int
    hp_end: int
    used: int


def burn_ticks(burn_pct: int, monster_attack: int) -> tuple[int, ...]:
    """The burn ticks, ×10000, of a monster with `burn_pct`% burn and
    `monster_attack` summed over its elements: the first is the share rounded
    half up, each next 9/10 of the last rounded down, until 0 (module doc)."""
    tick = (2 * burn_pct * monster_attack + 100) // 200
    ticks: list[int] = []
    while tick > 0:
        ticks.append(tick * SCALE)
        tick = tick * 9 // 10
    return tuple(ticks)


def _tick(damage: RoundDamage, player_first: bool, round_no: int) -> int:
    """The burn tick of the player's turn in round `round_no` (module doc)."""
    index = round_no - 2 if player_first else round_no - 1
    return damage.burn[index] if 0 <= index < len(damage.burn) else 0


State = tuple[int, int, int]
"""`(monster pool, player pool, stock left)`."""


Roll = tuple[tuple[Fraction, int, int], ...]
"""`(probability, amount, heal)` per outcome of a crit roll."""


def _roll(pct: int, normal: int, crit: int, heal: int) -> Roll:
    """The two outcomes of one crit roll, without a zero-probability branch;
    only the crit heals."""
    branches = ((Fraction(100 - pct, 100), normal, 0), (Fraction(pct, 100), crit, heal))
    return tuple(b for b in branches if b[0] != 0)


def cure(pool: int, heal: int, cap: int) -> int:
    """`pool` after a lifesteal heal of `heal`, capped at `cap`; a heal never
    lowers a pool (Lean `FightOdds.cure`)."""
    return max(pool, min(pool + heal, cap))


Key = tuple[bool, int, int, int]
"""`(win, turns, hp_end, used)`: what makes two endings the same."""


def _add_ended(into: dict[Key, Fraction], key: Key, prob: Fraction) -> None:
    into[key] = into.get(key, Fraction(0)) + prob


def _add_state(into: dict[State, Fraction], key: State, prob: Fraction) -> None:
    into[key] = into.get(key, Fraction(0)) + prob


@lru_cache(maxsize=FIGHT_ODDS_CACHE)
def fight_odds(terms: FightTerms, damage: RoundDamage, hp_start: int, max_hp: int,
               restore: int, stock: int) -> tuple[Ending, ...]:
    """Every ending of the fight from `hp_start` with `stock` restore potions of
    `restore` HP (see the module doc), merged, in a fixed order."""
    if restore < 0 or stock < 0:
        raise ValueError(f"restore {restore} and stock {stock} must be non-negative")
    pool = effective_player_hp(hp_start, max_hp) * SCALE
    if terms.exit is FightExit.OUT_SUSTAIN:
        return (Ending(Fraction(1), True, terms.rounds_to_kill, pool, 0),)
    if terms.exit not in (FightExit.NONE, FightExit.DEAD) or pool <= 0:
        return (Ending(Fraction(1), False, 0, 0, 0),)
    max_pool, restore_pool = max_hp * SCALE, restore * SCALE
    kills = _roll(damage.p_crit, damage.kill_normal, damage.kill_crit, damage.p_heal)
    hits = _roll(damage.m_crit, damage.die_normal, damage.die_crit, damage.m_heal)
    m_cap = damage.monster_hp * SCALE
    ended: dict[Key, Fraction] = {}
    states: dict[State, Fraction] = {(damage.monster_hp * SCALE, pool, stock): Fraction(1)}
    for round_no in range(1, MAX_TURNS + 1):
        after: dict[State, Fraction] = {}
        for (monster, player, left), prob in states.items():
            tick = _tick(damage, terms.player_first, round_no)
            if terms.player_first:
                _player_then_monster(round_no, tick, monster, player, left, prob, stock,
                                     max_pool, restore_pool, m_cap, kills, hits, ended, after)
            else:
                _monster_then_player(round_no, tick, monster, player, left, prob, stock,
                                     max_pool, restore_pool, m_cap, kills, hits, ended, after)
        states = after
        if not states:
            break
    for (_, _, left), prob in states.items():
        _add_ended(ended, (False, MAX_TURNS, 0, stock - left), prob)
    return tuple(Ending(p, win, turns, hp_end, used)
                 for (win, turns, hp_end, used), p in sorted(ended.items()))


def _player_then_monster(round_no: int, tick: int, monster: int, player: int, left: int,
                         prob: Fraction, stock: int, max_pool: int, restore_pool: int, m_cap: int,
                         kills: Roll, hits: Roll,
                         ended: dict[Key, Fraction], after: dict[State, Fraction]) -> None:
    if tick > 0 and player - tick <= 0:
        _add_ended(ended, (False, round_no, 0, stock - left), prob)
        return
    player, left = drink(player - tick, max_pool, restore_pool, left)
    for pk, kill, p_heal in kills:
        if monster - kill <= 0:
            _add_ended(ended, (True, round_no, player, stock - left), prob * pk)
            continue
        healed = cure(player, p_heal, max_pool)
        for ph, hit, m_heal in hits:
            if healed - hit <= 0:
                _add_ended(ended, (False, round_no, 0, stock - left), prob * pk * ph)
            else:
                _add_state(after, (cure(monster - kill, m_heal, m_cap), healed - hit, left),
                           prob * pk * ph)


def _monster_then_player(round_no: int, tick: int, monster: int, player: int, left: int,
                         prob: Fraction, stock: int, max_pool: int, restore_pool: int, m_cap: int,
                         kills: Roll, hits: Roll,
                         ended: dict[Key, Fraction], after: dict[State, Fraction]) -> None:
    for ph, hit, m_heal in hits:
        if player - hit <= 0 or (tick > 0 and player - hit - tick <= 0):
            _add_ended(ended, (False, round_no, 0, stock - left), prob * ph)
            continue
        drunk, rest = drink(player - hit - tick, max_pool, restore_pool, left)
        healed_monster = cure(monster, m_heal, m_cap)
        for pk, kill, p_heal in kills:
            if healed_monster - kill <= 0:
                _add_ended(ended, (True, round_no, drunk, stock - rest), prob * ph * pk)
            else:
                _add_state(after, (healed_monster - kill, cure(drunk, p_heal, max_pool), rest),
                           prob * ph * pk)


def win_probability(endings: Sequence[Ending]) -> Fraction:
    """P(win): the summed probability of the winning endings."""
    return sum((e.prob for e in endings if e.win), Fraction(0))


def odds_clear(p_win: Fraction, theta: Fraction) -> bool:
    """The fight gates' one verdict on the odds: P(win) AT LEAST `theta` (Lean
    `θ ≤ winProb`, `WinnableGrounded.rowWinnable_sound`), so a θ measured
    exactly at the odds clears. Every gate reads it — `combat.predict_win`,
    `combat.secure_win`, the drop gate's potion loadouts (`loadout_win`), the
    band's potion arm — and `formal/diff/test_odds_verdict_diff.py` pins it
    against the Lean tree."""
    return p_win >= theta
