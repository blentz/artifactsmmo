"""A repeatedly-failing action is blocked by its failure CLASS (USER
2026-10-09, "Classify by HTTP code"; proved in `Formal.FailureRecovery`)."""

import pytest

from artifactsmmo_cli.ai.failure_recovery_core import (
    LEARNED,
    STATE,
    STRUCTURAL,
    TRANSPORT,
    TRANSPORT_RETRY_CYCLES,
    blocked,
    failure_class,
    record_failure,
    tick,
)


@pytest.mark.parametrize(("outcome", "cls"), [
    ("error:fight_lost", LEARNED),
    ("error:already_equipped", LEARNED),
    ("error:HTTP_473", LEARNED),       # categorical: refusal_fact owns it
    ("error:HTTP_598", STRUCTURAL),    # content not at the tile
    ("error:HTTP_404", STATE),         # a sibling took the bank stock
    ("error:HTTP_478", STATE),
    ("error:HTTP_497", STATE),
    ("error:bank_locked", STATE),
    ("error:HTTP_500", TRANSPORT),
    ("error:network", TRANSPORT),
    ("error:other", TRANSPORT),
])
def test_the_class_of_each_outcome(outcome: str, cls: str) -> None:
    assert failure_class(outcome) == cls


class TestTheBlockTable:
    def test_a_transport_failure_blocks_then_expires(self) -> None:
        table = record_failure({}, "Gather(x)", TRANSPORT, frozenset())
        assert table == {"Gather(x)": (TRANSPORT_RETRY_CYCLES, None)}
        for _ in range(TRANSPORT_RETRY_CYCLES - 1):
            table = tick(table)
            assert blocked(table, frozenset()) == {"Gather(x)"}
        assert tick(table) == {}

    def test_a_structural_failure_holds_while_its_premise_does(self) -> None:
        """No number of ticks lifts it; a different active-event set does."""
        table = record_failure({}, "TaskCancel", STRUCTURAL, frozenset({"a"}))
        for _ in range(1000):
            table = tick(table)
        assert blocked(table, frozenset({"a"})) == {"TaskCancel"}
        assert blocked(table, frozenset({"a", "b"})) == frozenset()

    def test_learned_and_state_failures_add_no_block(self) -> None:
        assert record_failure({}, "Fight(rat)", LEARNED, frozenset()) == {}
        assert record_failure({}, "Withdraw(x)", STATE, frozenset()) == {}

    def test_recording_keeps_the_other_entries(self) -> None:
        table = {"A": (3, None)}
        assert record_failure(table, "B", TRANSPORT, frozenset()) == {
            "A": (3, None), "B": (TRANSPORT_RETRY_CYCLES, None)}
        assert table == {"A": (3, None)}
