"""Differential: the real Python `accumulation_sell` integer core must agree
bit-for-bit with the proved Lean `Formal.AccumulationSell` defs
(`accumulationSteps` / `accumulationExcess`), via the `accumulation_sell` oracle.

This bridges the model↔code gap for the ratio-driven accumulation sell: the live
functions that decide the geometric severity (`accumulation_steps`, drives
`SellInventoryGoal.value`) and the sell-down-to-cap quantity
(`accumulation_excess`) are the SAME functions the kernel proved
(`below_gate_quiet`, `excess_sells_down_to_cap`, `steps_threshold`, …).
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.accumulation_sell import (
    accumulation_excess,
    accumulation_steps,
)
from formal.diff.oracle_client import run_oracle


@settings(max_examples=400)
@given(held=st.integers(min_value=0, max_value=5000),
       cap=st.integers(min_value=0, max_value=50))
def test_accumulation_core_matches_lean(held: int, cap: int) -> None:
    lean = run_oracle("accumulation_sell", [[held, cap]])[0]
    assert accumulation_steps(held, cap) == lean["steps"], (
        f"steps mismatch held={held} cap={cap} "
        f"py={accumulation_steps(held, cap)} lean={lean['steps']}")
    assert accumulation_excess(held, cap) == lean["excess"], (
        f"excess mismatch held={held} cap={cap} "
        f"py={accumulation_excess(held, cap)} lean={lean['excess']}")


def test_accumulation_boundaries_bind_against_lean() -> None:
    """Deterministic boundary pins (kill comparator/constant mutants the random
    search may miss): the ratio gate (held == 5*cap exactly), the severe step
    boundary (held == 32*cap → steps 5), and dominated (cap 0) sell-to-zero."""
    cases = [
        (10, 2),   # exactly 5*cap -> fires, excess 8, steps floor(log2(5))=2
        (9, 2),    # just below 5*cap -> excess 0
        (32, 1),   # severe boundary -> steps 5, excess 31
        (14, 0),   # dominated -> sell all 14, steps floor(log2(14))=3
    ]
    for held, cap in cases:
        lean = run_oracle("accumulation_sell", [[held, cap]])[0]
        assert accumulation_steps(held, cap) == lean["steps"], (held, cap)
        assert accumulation_excess(held, cap) == lean["excess"], (held, cap)
