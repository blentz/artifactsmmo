"""O6: no `Decision` prices anything except through `route_price`.

A census that reports zero is worth exactly as much as its positive control. The
two `_detects_` tests below are that control: a synthetic module that violates
each rule must be FOUND by the same function that sweeps production. Without
them a census with an inverted predicate, a typo'd module name, or a glob that
matches nothing would report a green obligation forever.
"""

import pathlib

import pytest

from artifactsmmo_cli.audit.one_cost_model import (
    FUNNEL,
    MIN_DECISION_CLASSES,
    PRICING_PRODUCERS,
    render,
    sweep,
)

PACKAGE = (pathlib.Path(__file__).resolve().parents[2]
           / "src" / "artifactsmmo_cli" / "ai" / "decisions")


def test_production_has_one_cost_model() -> None:
    """THE OBLIGATION. Both residuals zero over the real package."""
    results = sweep(PACKAGE)
    assert results["second_pricer"] == []
    assert results["injected_pricer"] == []


def test_the_sweep_is_not_looking_at_nothing() -> None:
    """The floor. `test_decisions_dag` guards its own sweep the same way, and
    for the same reason: a census that discovers no `Decision` classes passes
    both residuals trivially."""
    found = sweep(PACKAGE)["decision_classes"]
    assert len(found) >= MIN_DECISION_CLASSES, found
    # The two wave-4 nodes are named explicitly, so a refactor that drops them
    # fails here rather than silently lowering what the census covers.
    names = {n.split(":", 1)[1] for n in found}
    assert {"IsAFightBlockingMe", "WhichSlotClosesTheFight"} <= names


def test_the_funnel_itself_is_exempt() -> None:
    """`route.py` imports the producers BY DESIGN — it is the funnel. If this
    ever fails, the exemption has stopped applying to the module that needs it
    and every later increment's pricing has nowhere legal to live."""
    assert (PACKAGE / FUNNEL).exists()
    text = (PACKAGE / FUNNEL).read_text()
    assert any(p.split(".")[-1] in text for p in PRICING_PRODUCERS), \
        "the funnel must actually import a pricing producer, or it is not one"


@pytest.mark.parametrize("producer", sorted(PRICING_PRODUCERS))
def test_detects_a_second_pricer(tmp_path, producer) -> None:
    """POSITIVE CONTROL, once per forbidden producer.

    Parametrized rather than written once because a suffix-matching bug would
    plausibly catch `acquisition_cost` and miss `acquisition_cost_core` — the
    two differ by a suffix, which is exactly where this predicate is fragile."""
    (tmp_path / "rogue.py").write_text(
        f"from artifactsmmo_cli.ai.{producer} import something\n")
    found = sweep(tmp_path)["second_pricer"]
    assert len(found) == 1, found
    assert producer in found[0]


def test_the_funnel_name_is_what_grants_the_exemption(tmp_path) -> None:
    """The exemption is keyed on the FILENAME, so the identical import in a
    differently-named module must be caught. Without this, a bug that exempted
    every file would be indistinguishable from a passing census."""
    body = "from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions\n"
    (tmp_path / FUNNEL).write_text(body)
    assert sweep(tmp_path)["second_pricer"] == []
    (tmp_path / "not_the_funnel.py").write_text(body)
    assert len(sweep(tmp_path)["second_pricer"]) == 1


@pytest.mark.parametrize("annotation", ["Callable[[str], int]",
                                        "Callable[[str, str], float]"])
def test_detects_an_injected_pricer(tmp_path, annotation) -> None:
    """POSITIVE CONTROL for the callback half. A `Decision` that takes a pricer
    as a parameter puts the cost model outside this census's reach — the
    `cost_of` shape that made `combat_deficit` a consumer invisible to its own
    name."""
    (tmp_path / "rogue.py").write_text(
        "class Rogue(Decision[MetaGoal]):\n"
        f"    def resolve(self, state, cost_of: {annotation}) -> None:\n"
        "        return None\n")
    results = sweep(tmp_path)
    assert len(results["injected_pricer"]) == 1, results
    assert "Rogue.resolve(cost_of)" in results["injected_pricer"][0]


def test_a_non_numeric_callable_parameter_is_allowed(tmp_path) -> None:
    """NOT VACUOUS IN THE OTHER DIRECTION. The rule is about injected COST
    MODELS, not about callbacks in general — a predicate that flagged every
    `Callable` would pass the control above while being wrong."""
    (tmp_path / "ok.py").write_text(
        "class Fine(Decision[MetaGoal]):\n"
        "    def resolve(self, state, name_of: Callable[[str], str]) -> None:\n"
        "        return None\n")
    assert sweep(tmp_path)["injected_pricer"] == []


def test_render_names_every_residual(tmp_path) -> None:
    """The CI log must say WHICH module offended, not just how many did."""
    (tmp_path / "rogue.py").write_text(
        "from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions\n")
    out = render(sweep(tmp_path))
    assert "O6_SECOND_PRICER 1" in out
    assert "rogue.py" in out and "acquisition_cost" in out


def test_detects_a_plain_import_not_just_from_import(tmp_path) -> None:
    """`import artifactsmmo_cli.ai.acquisition_cost` is the SAME violation as the
    `from ... import ...` form, and a sweep that only handled one would have
    reported a green obligation over the other.

    Both AST node kinds carry module names differently (`ast.Import.names` vs
    `ast.ImportFrom.module`), which is why this is a separate case and not a
    restatement of the control above."""
    (tmp_path / "rogue.py").write_text(
        "import artifactsmmo_cli.ai.acquisition_cost\n")
    found = sweep(tmp_path)["second_pricer"]
    assert len(found) == 1, found
    assert "acquisition_cost" in found[0]


def test_a_relative_import_form_is_still_matched(tmp_path) -> None:
    """Suffix matching on dotted segments, so a bare module name resolves too."""
    (tmp_path / "rogue.py").write_text("from acquisition_cost import x\n")
    assert len(sweep(tmp_path)["second_pricer"]) == 1


def test_an_ellipsis_arg_pricer_is_still_caught(tmp_path) -> None:
    """`Callable[..., int]` IS an injected pricer and is detected.

    Recorded because I expected the opposite. `Callable[..., int]` parses as a
    two-element slice tuple -- `Ellipsis` then `int` -- so the same predicate
    that reads `Callable[[str], int]` reads this too. The check is stronger than
    its docstring first claimed, and this pins the stronger behaviour so a later
    "simplification" cannot quietly narrow it."""
    (tmp_path / "rogue.py").write_text(
        "class Rogue(Decision[MetaGoal]):\n"
        "    def resolve(self, state, cost_of: Callable[..., int]) -> None:\n"
        "        return None\n")
    assert len(sweep(tmp_path)["injected_pricer"]) == 1


@pytest.mark.parametrize("annotation", [
    "Callable",                    # bare, no subscript slice at all
    "dict[str, int]",              # a Subscript that is not a Callable
    "Callable[int]",               # Callable with a non-tuple slice
    "Callable[[str], int, int]",   # Callable with a 3-element slice
])
def test_odd_annotations_do_not_crash_or_false_positive(
        tmp_path, annotation) -> None:
    """The predicate must return a clean False for annotations it cannot read,
    rather than raising or guessing."""
    (tmp_path / "odd.py").write_text(
        "class Odd(Decision[MetaGoal]):\n"
        f"    def resolve(self, state, f: {annotation}) -> None:\n"
        "        return None\n")
    assert sweep(tmp_path)["injected_pricer"] == []
