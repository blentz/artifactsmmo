"""One leg of a route's drop work (spec 2026-10-18 §2.8, plan B Task 12b).

`acquisition_cost.drop_work` lists the gather and drop-farm legs the price walk
takes, and `acquisition_cost.drop_work_actions` prices them; the prospecting
tool (`tool_objective.drop_tool_target`) is weighed against that price. The
leg carries its route's own kind, so the pricer reads which route it is rather
than re-deriving it from the catalogue (ruling T12m).
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.source_kind import SourceKind


@dataclass(frozen=True)
class DropLeg:
    """`units` of `item` the walk's `kind` route (GATHER or DROP) still owes,
    attempted at `source` (the resource or the monster). `surcharged` is
    whether the walk prices the leg's wins with the learned loss surcharge: a
    ready farm does, a farm behind gear the character lacks
    (`acquisition_cost._gated_drop_option`) does not, and a gather never
    fights."""

    kind: SourceKind
    source: str
    item: str
    units: int
    surcharged: bool
