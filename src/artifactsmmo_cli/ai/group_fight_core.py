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

The walk tracks the boss's pool. Living members with initiative drink; if
every living member moves first and their damage finishes the boss, the party
wins before it acts. The boss hits its target among the living — highest
threat, ties by lowest pool, then lowest index — for `hit - hit // 10` and the
lowest living pool for `hit // 10` (the 90/10 targeting rule, in expectation);
every living member takes `area`, a negative total healing up to max HP. A pool
at or below 0 is dead: it no longer acts, drinks, is targeted or pays `area`
(live probe 2026-10-11: a 1-HP member died on turn 3 and its partner won
alone). The fight is lost only when every member is dead. A round's damage is
each first mover alive before the boss's turn and each late mover alive after
it, less `drain`; late movers then drink.

The guard ladder is the solo one over the full party, and the turn cap and the
reconstitution period are counted in actor turns (`N + 1` a round, the full
party's — conservative once a member dies)."""

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


def _target(members: list[PartyMember], pools: list[int]) -> int | None:
    """The living member with the highest threat, ties by lowest pool, then
    lowest index."""
    best: int | None = None
    for i, (m, pool) in enumerate(zip(members, pools, strict=True)):
        if pool <= 0:
            continue
        if best is None or (members[best].threat < m.threat
                            or (members[best].threat == m.threat and pool < pools[best])):
            best = i
    return best


def _lowest(pools: list[int]) -> int | None:
    """The lowest living pool, ties by lowest index."""
    best: int | None = None
    for i, pool in enumerate(pools):
        if pool > 0 and (best is None or pool < pools[best]):
            best = i
    return best


def _boss_turn(members: list[PartyMember], pools: list[int]) -> list[int]:
    target, low = _target(members, pools), _lowest(pools)
    out = []
    for i, (m, pool) in enumerate(zip(members, pools, strict=True)):
        if pool <= 0:
            out.append(pool)
            continue
        dmg = (m.area + (m.hit - m.hit // 10 if i == target else 0)
               + (m.hit // 10 if i == low else 0))
        out.append(min(pool - dmg, m.max_hp * SCALE) if dmg < 0 else pool - dmg)
    return out


def _drink_all(first: bool, members: list[PartyMember], pools: list[int],
               left: list[int]) -> None:
    for i, m in enumerate(members):
        if m.first is first and pools[i] > 0:
            pools[i], left[i] = drink(pools[i], m.max_hp * SCALE, m.restore * SCALE, left[i])


def _net_sum(members: list[PartyMember], pre: list[int], post: list[int]) -> int:
    """The members acting this round: a first mover alive before the boss's
    turn, a late mover alive after it."""
    return sum(m.net for m, a, c in zip(members, pre, post, strict=True)
               if (a > 0 if m.first else c > 0))


def _deadline(boss: PartyBoss, members: list[PartyMember], round_no: int) -> bool:
    """The fight cannot reach `round_no`: past the turn cap, or the boss
    reconstitutes first."""
    actor_turns = round_no * (len(members) + 1)
    return actor_turns > 2 * MAX_TURNS or (boss.recon > 0 and 2 * boss.recon <= actor_turns)


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
    boss_pool = boss.hp * SCALE
    if boss_pool <= 0:
        return GroupOutcome(True, 0, tuple(starts), zeros)
    pools, left = list(starts), [m.stock for m in members]

    def end(win: bool, turns: int) -> GroupOutcome:
        return GroupOutcome(win, turns, tuple(max(p, 0) for p in pools),
                            tuple(m.stock - k for m, k in zip(members, left, strict=True)))

    round_no = 0
    while True:  # the deadline ends the walk: actor turns grow every round
        round_no += 1
        if _deadline(boss, members, round_no):
            return end(False, round_no - 1)
        _drink_all(True, members, pools, left)
        if (all(m.first or p <= 0 for m, p in zip(members, pools, strict=True))
                and boss_pool - (_net_sum(members, pools, pools) - boss.drain) <= 0):
            return end(True, round_no)
        post = _boss_turn(members, pools)
        boss_pool -= _net_sum(members, pools, post) - boss.drain
        pools = post
        if all(p <= 0 for p in pools):
            return end(False, round_no)
        _drink_all(False, members, pools, left)
        if boss_pool <= 0:
            return end(True, round_no)
