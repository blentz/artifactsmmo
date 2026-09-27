"""Differential: the real `ready_core.ready_routes` (through the real `Policy`)
must agree with the kernel-proved `Formal.ObtainModelReady.readyRoutes` over
random policies and route lists.

Routes are drawn from every `SourceKind` and `GateKind`, with a small `via`
alphabet so SELL routes collide on the item sold (the first-buyer rule) and
GATHER routes mix primary and secondary droppers. `via` strings are interned
to naturals for the oracle; only equality of `via` matters to either side.
"""

import itertools

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, Policy
from artifactsmmo_cli.ai.obtain_model.ready_core import ready_routes
from artifactsmmo_cli.ai.obtain_model.route import Route
from artifactsmmo_cli.ai.source_kind import SourceKind
from formal.diff.oracle_client import run_oracle

_gate = st.builds(lambda kind, sat: Gate(kind, "subject", sat),
                  st.sampled_from(list(GateKind)), st.booleans())
_route = st.builds(
    lambda kind, via, primary, gates: Route("item", kind, f"v{via}", 1, 1, tuple(gates),
                                            primary=primary),
    st.sampled_from(list(SourceKind)), st.integers(0, 3), st.booleans(),
    st.lists(_gate, max_size=4))
_POLICY_FIELDS = 11
_policy = st.builds(Policy, *[st.booleans()] * _POLICY_FIELDS)


def _encode(route: Route) -> list:
    return [route.kind.value, int(route.via[1:]), int(route.primary),
            [[g.kind.value, int(g.satisfied)] for g in route.gates]]


def _flags(policy: Policy) -> list[int]:
    return [int(policy.all_gather_routes), int(policy.gather_skill_gate),
            int(policy.craft_skill_gate), int(policy.event_vendors), int(policy.spawn_known),
            int(policy.allow_grey), int(policy.vendor_routes), int(policy.ge_routes),
            int(policy.task_rewards), int(policy.fight_gold), int(policy.drop_routes)]


def _oracle(policy: Policy, routes: list[Route]) -> list:
    args = [*_flags(policy), [_encode(r) for r in routes]]
    return run_oracle("obtain_model_ready", [args])[0]["ready"]


@settings(max_examples=400)
@given(policy=_policy, routes=st.lists(_route, max_size=12))
def test_ready_routes_matches_oracle(policy: Policy, routes: list[Route]) -> None:
    python = [_encode(r) for r in ready_routes(routes, policy)]
    lean = _oracle(policy, routes)
    assert python == lean, f"policy={policy} routes={routes}: py={python} lean={lean}"


def test_every_single_gate_route_matches_oracle() -> None:
    """Exhaustive over what `Policy` decides per route: every policy x source
    kind x gate kind x verdict x primary, one gate per route. Random lists
    reach a BUY route whose only relevant gate is false too rarely to pin the
    vendor switches (two mutants survived 400 random examples); this does not
    rely on luck. One oracle batch: 2048 policies x 10 kinds x 13 gates x 2 x 2."""
    policies = [Policy(*flags) for flags in itertools.product((False, True), repeat=_POLICY_FIELDS)]
    cases = [(policy, Route("item", kind, "v0", 1, 1, (Gate(gate, "subject", sat),), primary=primary))
             for policy, kind, gate, sat, primary in itertools.product(
                 policies, SourceKind, GateKind, (False, True), (False, True))]
    lean = run_oracle("obtain_model_ready", [
        [*_flags(p), [_encode(r)]] for p, r in cases])
    for (policy, route), answer in zip(cases, lean, strict=True):
        python = [_encode(r) for r in ready_routes([route], policy)]
        assert python == answer["ready"], f"{policy} {route}: py={python} lean={answer['ready']}"


def test_first_open_buyer_wins_on_both_sides() -> None:
    """The witness `readyRoutes_sell_first` is about: a closed first buyer
    yields to the next open one, and a third buyer of the same item is dropped."""
    closed = Route("gold", SourceKind.SELL, "v1", 5, 5, (Gate(GateKind.VENDOR_TRADEABLE, "a", False),))
    open_ = Route("gold", SourceKind.SELL, "v1", 4, 4, (Gate(GateKind.VENDOR_TRADEABLE, "b", True),))
    third = Route("gold", SourceKind.SELL, "v1", 3, 3, ())
    routes = [closed, open_, third]
    assert ready_routes(routes, LEGACY) == (open_,)
    assert _oracle(LEGACY, routes) == [_encode(open_)]
