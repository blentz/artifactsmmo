"""WalkGraph: the obtain model's routes as the one walk's graph
(`decompose_core`, `Formal/Decompose.lean`; Phase 2c-2b of
docs/PLAN_decision_architecture_redesign.md)."""

from collections.abc import Mapping
from dataclasses import dataclass

from artifactsmmo_cli.ai.decompose_core import Route as WalkRoute
from artifactsmmo_cli.ai.decompose_core import Step
from artifactsmmo_cli.ai.obtain_model.route import Route


@dataclass(frozen=True)
class WalkGraph:
    """The walk's input for one goal's closure. `sources[item][k]` is the
    obtain-model route behind `routes[item][k]`, so a step's route index names
    the route that serves it."""

    on_hand: Mapping[str, int]
    routes: Mapping[str, tuple[WalkRoute[str], ...]]
    sources: Mapping[str, tuple[Route, ...]]


@dataclass(frozen=True)
class WalkAnswer:
    """The one walk's answer: can `qty` be had, the next step toward it (None
    when the bag holds it or it cannot be had), and the legs behind a yes
    (`decompose_core.plan_legs`; proved to deliver, the step first)."""

    feasible: bool
    step: Step[str] | None
    graph: WalkGraph
    plan: tuple[Step[str], ...]
