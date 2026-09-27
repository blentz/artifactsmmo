"""Feasibility: the answer to "can I get at least one unit of this item?"."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.obtain_model.gate import Gate


@dataclass(frozen=True)
class Feasibility:
    """`ok` is the verdict. When it is False, the two fields say why, one level
    deep (a caller can ask `feasible` again about a missing input):

    `blocking_gates`: the unsatisfied enforced gates on the item's routes that
    the policy admits but that are not ready (a skill below level, a monster
    not winnable, a vendor not tradeable now, ...).

    `missing_inputs`: inputs of the item's READY routes that are themselves
    infeasible (a craftable item whose recipe needs something unobtainable)."""

    ok: bool
    blocking_gates: tuple[Gate, ...] = ()
    missing_inputs: tuple[str, ...] = ()
