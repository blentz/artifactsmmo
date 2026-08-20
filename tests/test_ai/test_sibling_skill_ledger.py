"""The fleet CAPABILITY board — `SkillLedger` and its two store methods.

`MaterialDemand` already lets a character publish "I need this and cannot make
it myself"; `SupplyClaim` elects exactly one producer to answer. Nothing let the
ASKER know whether asking was worth anything, so a skill-gated item priced
`UNOBTAINABLE_PER_UNIT` even when a sibling held the skill and was one craft
away. This is the consumer half.
"""

from datetime import datetime, timedelta, timezone

import pytest

from artifactsmmo_cli.ai.learning.coordination_store import (
    DEMAND_TTL_SECONDS,
    CoordinationStore,
)

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):  # type: ignore[no-untyped-def]
    return str(tmp_path / "coord.db")


def _store(db: str, character: str) -> CoordinationStore:
    return CoordinationStore(db_path=db, character=character)


def test_a_sibling_who_meets_the_gate_is_visible_to_the_asker(db: str) -> None:
    """THE POINT. Robby holds jewelrycrafting 15; C3P0 (at 8) can see it."""
    robby = _store(db, "Robby")
    robby.publish_skills({"jewelrycrafting": 15, "gearcrafting": 15}, NOW)

    seen = _store(db, "C3P0").sibling_skill_levels(NOW)

    assert seen["jewelrycrafting"] == 15
    assert seen["gearcrafting"] == 15


def test_levels_take_the_best_sibling_not_the_sum(db: str) -> None:
    """Skills do not POOL. One sibling at 15 makes the recipe reachable; three at
    8 do not, and summing would invent a capability the fleet does not have —
    the shape of error `sibling_holdings`' sum is right to make for UNITS and
    wrong for LEVELS."""
    for name, level in (("Robby", 15), ("HAL", 8), ("Lor", 8)):
        _store(db, name).publish_skills({"jewelrycrafting": level}, NOW)

    assert _store(db, "C3P0").sibling_skill_levels(NOW)["jewelrycrafting"] == 15


def test_a_characters_own_levels_are_excluded(db: str) -> None:
    """Same grounds as `sibling_holdings`: the caller has its own levels live in
    `state.skills`, which is fresher than anything it published."""
    c3p0 = _store(db, "C3P0")
    c3p0.publish_skills({"alchemy": 9}, NOW)

    assert "alchemy" not in c3p0.sibling_skill_levels(NOW)


def test_an_expired_row_stops_offering_its_skill(db: str) -> None:
    """A character that stopped playing stops offering its skills on the SAME
    clock that frees its role — the coordination system has exactly one liveness
    rule, and this table must not be a second one."""
    _store(db, "Robby").publish_skills({"jewelrycrafting": 15}, NOW)
    later = NOW + timedelta(seconds=DEMAND_TTL_SECONDS + 1)

    assert _store(db, "C3P0").sibling_skill_levels(later) == {}


def test_republishing_replaces_wholesale_rather_than_accumulating(db: str) -> None:
    """Upsert key is (character, skill), replaced wholesale like `HoldingLedger`.

    The flush-between-delete-and-insert matters here for the same reason it does
    there: UNIQUE(character, skill) would reject a same-skill republish whose
    DELETE the unit of work had not yet ordered ahead of the INSERT.
    """
    robby = _store(db, "Robby")
    robby.publish_skills({"jewelrycrafting": 15, "cooking": 3}, NOW)
    robby.publish_skills({"jewelrycrafting": 16}, NOW)

    seen = _store(db, "C3P0").sibling_skill_levels(NOW)
    assert seen == {"jewelrycrafting": 16}, "cooking should be gone, not stale at 3"


def test_zero_and_negative_levels_are_not_published(db: str) -> None:
    """An unlearned skill is not a capability; publishing it would let a sibling
    read 0 as an offer."""
    _store(db, "Robby").publish_skills({"jewelrycrafting": 0, "mining": 21}, NOW)

    assert _store(db, "C3P0").sibling_skill_levels(NOW) == {"mining": 21}


def test_a_naive_datetime_is_refused(db: str) -> None:
    """Every coordination method requires UTC — a naive stamp compares wrongly
    against the stored ISO string and would silently mis-expire rows."""
    with pytest.raises(ValueError):
        _store(db, "Robby").publish_skills({"mining": 1},
                                           datetime(2026, 8, 20, 12, 0, 0))
    with pytest.raises(ValueError):
        _store(db, "Robby").sibling_skill_levels(datetime(2026, 8, 20, 12, 0, 0))


def test_no_siblings_is_an_empty_map_not_a_failure(db: str) -> None:
    """Every single-character run takes this path; the sibling route must be
    silently ABSENT rather than wrong."""
    assert _store(db, "solo").sibling_skill_levels(NOW) == {}
