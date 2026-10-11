"""Pure core: a party boss fight's expected-value outcome
(`docs/PLAN_group_fights.md` increment 1; proved model
`formal/Formal/GroupFight.lean`, differential `formal/diff/test_group_fight_diff.py`).

Up to three characters of one account fight a `boss` together. Each member's
numbers come from its own solo terms, split by who pays them:

* `net` — the member's share of the kill rate (its damage, less the bubble /
  sun-shield cut and the boss's heal from draining it);
* `hit` — what one boss hit costs it (attack, berserk, frenzy, greed);
* `area` — what every round costs it, targeted or not (poison, burn, void
  drain, mirror, less its own lifesteal).

The boss's `drain` is the kill-rate terms charged once per BOSS turn (its
lifesteal, its healing). For one member `net - drain` is the solo kill step
and `hit + area` the solo die step, so one member IS `fight_outcome`
(`Formal.GroupFight.groupOutcome_single`).

The round: members with initiative drink; in the kill round, if every member
moves first, the party wins before the boss acts. The boss hits its target —
highest threat, ties by lowest pool, then lowest index — for `hit - hit // 10`
and the lowest-pool member for `hit // 10` (the 90/10 targeting rule, in
expectation); every member takes `area`, a negative total healing up to max
HP. ANY member at or below 0 loses the fight (whether the rest may fight on is
unmeasured: the model never claims that win). Members without initiative then
drink; the kill round ends in a win.

The guard ladder is the solo one over the party, with the turn cap and the
reconstitution period counted in actor turns (`N + 1` a round)."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.fight_outcome_core import drink
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS, SCALE, FightExit, ceil_div, effective_player_hp


@dataclass(frozen=True)
class PartyMember:
    """One member's resolved integers (×10000 scale for the steps)."""

    raw: int
    net: int
    hit: int
    area: int
    hp: int
    max_hp: int
    first: bool
    threat: int
    restore: int
    stock: int


@dataclass(frozen=True)
class PartyBoss:
    """The boss's side: effective HP (barrier included), reconstitution, and
    the kill-rate terms charged once per boss turn."""

    hp: int
    recon: int
    drain: int


@dataclass(frozen=True)
class GroupOutcome:
    """A party fight's result; `hp_end` (×10000) and `used` per member."""

    win: bool
    turns: int
    hp_end: tuple[int, ...]
    used: tuple[int, ...]


def kill_rate(boss: PartyBoss, members: list[PartyMember]) -> int:
    """The party's summed kill rate per round."""
    return sum(m.net for m in members) - boss.drain


def kill_rounds(boss: PartyBoss, members: list[PartyMember]) -> int:
    """Rounds until the boss dies (a positive kill rate)."""
    return ceil_div(boss.hp * SCALE, kill_rate(boss, members))


def party_exit(boss: PartyBoss, members: list[PartyMember]) -> FightExit:
    """The guard ladder over the party (`Formal.GroupFight.gate`); `NONE` is
    returned for a fight the round walk decides (the dead-start test is the
    walk's)."""
    if all(m.raw <= 0 for m in members):
        return FightExit.NO_DAMAGE
    if kill_rate(boss, members) <= 0:
        return FightExit.UNKILLABLE
    actor_turns = kill_rounds(boss, members) * (len(members) + 1)
    if actor_turns > 2 * MAX_TURNS:
        return FightExit.OVER_CAP
    if boss.recon > 0 and 2 * boss.recon <= actor_turns:
        return FightExit.RECONSTITUTED
    if all(m.hit + m.area <= 0 for m in members):
        return FightExit.OUT_SUSTAIN
    return FightExit.NONE


def _target(members: list[PartyMember], pools: list[int]) -> int:
    """Highest threat, ties by lowest pool, then lowest index."""
    best = 0
    for i in range(1, len(members)):
        if (members[best].threat < members[i].threat
                or (members[best].threat == members[i].threat and pools[i] < pools[best])):
            best = i
    return best


def _lowest(pools: list[int]) -> int:
    """Lowest pool, ties by lowest index."""
    best = 0
    for i in range(1, len(pools)):
        if pools[i] < pools[best]:
            best = i
    return best


def _boss_turn(members: list[PartyMember], pools: list[int]) -> list[int]:
    target, low = _target(members, pools), _lowest(pools)
    out = []
    for i, (m, pool) in enumerate(zip(members, pools, strict=True)):
        dmg = (m.area + (m.hit - m.hit // 10 if i == target else 0)
               + (m.hit // 10 if i == low else 0))
        out.append(min(pool - dmg, m.max_hp * SCALE) if dmg < 0 else pool - dmg)
    return out


def _drink_all(first: bool, members: list[PartyMember], pools: list[int],
               left: list[int]) -> None:
    for i, m in enumerate(members):
        if m.first is first:
            pools[i], left[i] = drink(pools[i], m.max_hp * SCALE, m.restore * SCALE, left[i])


def group_outcome(boss: PartyBoss, members: list[PartyMember]) -> GroupOutcome:
    """Walk the party fight (`Formal.GroupFight.groupOutcome`); restores and
    stocks are non-negative."""
    if any(m.restore < 0 or m.stock < 0 for m in members):
        raise ValueError(f"party restore and stock must be non-negative: {members}")
    zeros = tuple(0 for _ in members)
    starts = [effective_player_hp(m.hp, m.max_hp) * SCALE for m in members]
    gate = party_exit(boss, members)
    if gate is FightExit.OUT_SUSTAIN:
        return GroupOutcome(True, kill_rounds(boss, members), tuple(starts), zeros)
    if gate is not FightExit.NONE or any(p <= 0 for p in starts):
        return GroupOutcome(False, 0, zeros, zeros)
    rounds = kill_rounds(boss, members)
    all_first = all(m.first for m in members)
    pools, left = list(starts), [m.stock for m in members]
    for round_no in range(1, rounds + 1):
        _drink_all(True, members, pools, left)
        if all_first and round_no == rounds:
            break
        pools = _boss_turn(members, pools)
        if any(p <= 0 for p in pools):
            return GroupOutcome(False, round_no, tuple(max(p, 0) for p in pools),
                                tuple(m.stock - k for m, k in zip(members, left, strict=True)))
        _drink_all(False, members, pools, left)
    return GroupOutcome(True, rounds, tuple(pools),
                        tuple(m.stock - k for m, k in zip(members, left, strict=True)))
