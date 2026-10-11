"""Differential tests for group fights increment 1 (`docs/PLAN_group_fights.md`).

1. The live party walk (`ai/group_fight_core.group_outcome`) must agree with
   the proved `Formal.GroupFight.groupOutcome` on random parties of one to
   three members, including every guard exit, threat ties and the 90/10 split.
2. A one-member party must be the solo walk (`fight_outcome` over
   `fight_terms`) — `Formal.GroupFight.groupOutcome_single`, checked on the
   live code.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_terms_core import fight_terms
from artifactsmmo_cli.ai.group_fight_core import PartyBoss, PartyMember, group_outcome
from formal.diff.oracle_client import run_oracle

_member = st.builds(
    PartyMember,
    raw=st.integers(min_value=-2, max_value=60),
    net=st.one_of(st.integers(min_value=-5000, max_value=0),
                  st.integers(min_value=10_000, max_value=600_000)),
    hit=st.one_of(st.integers(min_value=-500, max_value=0),
                  st.integers(min_value=5_000, max_value=900_000)),
    area=st.one_of(st.just(0), st.integers(min_value=-200_000, max_value=300_000)),
    hp=st.integers(min_value=-5, max_value=2500),
    max_hp=st.integers(min_value=0, max_value=2000),
    first=st.booleans(),
    threat=st.integers(min_value=0, max_value=3),
    restore=st.integers(min_value=0, max_value=800),
    stock=st.integers(min_value=0, max_value=8),
)
_boss = st.builds(
    PartyBoss,
    hp=st.integers(min_value=0, max_value=1500),
    recon=st.one_of(st.just(0), st.just(0), st.integers(min_value=1, max_value=150)),
    drain=st.one_of(st.just(0), st.integers(min_value=-1000, max_value=200_000)),
)


def _args(boss: PartyBoss, members: list[PartyMember]) -> list[int]:
    out = [boss.hp, boss.recon, boss.drain, len(members)]
    for m in members:
        out += [m.raw, m.net, m.hit, m.area, m.hp, m.max_hp, 1 if m.first else 0,
                m.threat, m.restore, m.stock]
    return out


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(st.tuples(_boss, st.lists(_member, min_size=0, max_size=3)),
                      min_size=1, max_size=25))
def test_group_outcome_matches_lean(cases):
    rows = run_oracle("group_fight", [_args(b, ms) for b, ms in cases])
    for (boss, members), row in zip(cases, rows, strict=True):
        got = group_outcome(boss, members)
        assert (got.win, got.turns, list(got.hp_end), list(got.used)) == (
            row["win"], row["turns"], row["hp_end"], row["used"]), (boss, members)


@settings(max_examples=300, deadline=None)
@given(boss=_boss, m=_member)
def test_one_member_is_the_solo_walk(boss, m):
    terms = fight_terms(m.raw, m.net - boss.drain, boss.hp, boss.recon, m.hit + m.area,
                        m.hp, m.max_hp, m.first)
    solo = fight_outcome(terms, m.hp, m.max_hp, m.restore, m.stock)
    got = group_outcome(boss, [m])
    assert (got.win, got.turns, got.hp_end, got.used) == (
        solo.win, solo.turns, (solo.hp_end,), (solo.used,))


def test_focus_fire_and_the_tank_against_lean():
    """Pinned parties the random draw rarely builds: equal threat focuses the
    lowest pool; a high-threat tank takes the 90 % and the weakest the 10 %; a
    pool of exactly 0 is dead."""
    weak = PartyMember(10, 20_000, 400_000, 0, 100, 100, True, 0, 0, 0)
    strong = PartyMember(10, 20_000, 400_000, 0, 200, 200, True, 0, 0, 0)
    tank = PartyMember(10, 20_000, 400_000, 0, 200, 200, True, 5, 0, 0)
    exact = PartyMember(10, 20_000, 500_000, 0, 100, 100, True, 0, 0, 0)
    boss = PartyBoss(20, 0, 0)
    cases = {
        # two hits empty the pool to exactly 0: a pool of 0 is dead
        (boss, (exact, strong)): (False, 2, (0, 2_000_000), (0, 0)),
        # equal threat: the weak member takes every hit and dies in round 3
        (boss, (weak, strong)): (False, 3, (0, 2_000_000), (0, 0)),
        # the tank takes 360k a hit, the weak 40k; all move first, so the boss
        # acts 4 times before the round-5 kill
        (boss, (weak, tank)): (True, 5, (840_000, 560_000), (0, 0)),
    }
    rows = run_oracle("group_fight", [_args(b, list(ms)) for b, ms in cases])
    for ((b, ms), expected), row in zip(cases.items(), rows, strict=True):
        got = group_outcome(b, list(ms))
        assert (row["win"], row["turns"], tuple(row["hp_end"]), tuple(row["used"])) == expected
        assert (got.win, got.turns, got.hp_end, got.used) == expected
