"""The one walk (`decompose_core`): feasibility and the next step together.
The Lean mirror (`Formal/Decompose.lean`) proves the general properties and the
differential binds the two; these pin the witnesses the proofs name, on the
Python side."""

from artifactsmmo_cli.ai.decompose_core import Act, OpenGate, Route, can_obtain, next_step, runs

UNBOUNDED = 10**9


def _ring(on_hand: dict[str, int], bar_gates: tuple[str, ...] = ()) -> tuple[dict, dict]:
    """copper_ring = 1 bar; copper_bar = 10 ore, yields 2; ore is gathered."""
    routes = {
        "ring": [Route("craft", 1, UNBOUNDED, (("bar", 1),))],
        "bar": [Route("craft", 2, UNBOUNDED, (("ore", 10),), bar_gates)],
        "ore": [Route("gather", 1, UNBOUNDED, ())],
    }
    return on_hand, routes


def test_runs_round_up_and_read_a_zero_yield_as_one():
    assert (runs(3, 2), runs(4, 2), runs(3, 0), runs(0, 5)) == (2, 2, 3, 0)


def test_from_nothing_the_first_leaf_is_the_ore():
    assert next_step("ring", 3, *_ring({})) == Act("ore", 0, 20, 20)


def test_with_the_ore_the_step_crafts_bar_runs():
    assert next_step("ring", 3, *_ring({"ore": 20})) == Act("bar", 0, 3, 2)


def test_the_deficit_not_the_whole_quantity_is_served():
    assert next_step("ring", 3, *_ring({"ring": 1, "ore": 20})) == Act("bar", 0, 2, 1)


def test_a_gated_route_opens_its_gate_first():
    assert next_step("ring", 3, *_ring({}, ("jewelrycrafting>=5",))) == OpenGate(
        "bar", 0, "jewelrycrafting>=5")


def test_satisfied_and_infeasible_have_no_step():
    assert next_step("ring", 3, *_ring({"ring": 3})) is None
    on_hand, routes = _ring({})
    del routes["ore"]
    assert next_step("ring", 1, on_hand, routes) is None
    assert can_obtain("ring", 1, on_hand, routes) is False


def test_capacity_binds_and_the_next_route_serves():
    routes = {"x": [Route("withdraw", 1, 4, ()), Route("gather", 1, UNBOUNDED, ())]}
    assert next_step("x", 4, {}, routes) == Act("x", 0, 4, 4)
    assert next_step("x", 5, {}, routes) == Act("x", 1, 5, 5)


def test_an_item_is_not_obtainable_through_itself():
    routes = {"a": [Route("craft", 1, UNBOUNDED, (("b", 1),))],
              "b": [Route("craft", 1, UNBOUNDED, (("a", 1),))]}
    assert can_obtain("a", 1, {}, routes) is False
    assert next_step("a", 1, {}, routes) is None


def test_a_cut_answer_is_not_reused_where_the_path_differs():
    """Item 1 is first reached under a path holding 2 (its only way in, cut),
    then from 0 directly, where 2 is open through ore 3: the answer is yes."""
    routes = {0: [Route("c", 1, UNBOUNDED, ((2, 1), (1, 1)))],
              1: [Route("c", 1, UNBOUNDED, ((2, 1),))],
              2: [Route("c", 1, UNBOUNDED, ((1, 1),)), Route("c", 1, UNBOUNDED, ((3, 1),))],
              3: [Route("g", 1, UNBOUNDED, ())]}
    assert can_obtain(0, 1, {}, routes) is True
    assert next_step(0, 1, {}, routes) == Act(3, 0, 1, 1)
