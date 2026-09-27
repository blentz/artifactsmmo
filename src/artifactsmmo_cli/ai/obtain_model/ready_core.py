"""The pure selection behind `ObtainModel.ready`, mirrored by
`formal/Formal/ObtainModelReady.lean::readyRoutes`.

Kept apart from the model so the differential harness
(`formal/diff/test_obtain_model_ready_diff.py`) can drive it with arbitrary
route lists, no game data needed. The kernel-checked properties of the Lean
mirror:
- soundness: every route returned is from the input and ready under the policy;
- order: the result is a sublist of the input, so priority order is kept;
- completeness: every ready non-SELL route is returned;
- SELL: at most one route per item sold, and it is the first ready one.
"""

from collections.abc import Sequence

from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.source_kind import SourceKind


def ready_routes(routes: Sequence[Route], policy: Policy) -> tuple[Route, ...]:
    """The routes usable under `policy`, in input (priority) order. A SELL
    route keeps only the first usable buyer per item sold: buyers come highest
    price first, so a later one is strictly worse."""
    out: list[Route] = []
    sold: set[str] = set()
    for route in routes:
        if not policy.ready(route):
            continue
        if route.kind is SourceKind.SELL:
            if route.via in sold:
                continue
            sold.add(route.via)
        out.append(route)
    return tuple(out)
