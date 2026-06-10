"""Differential test: real Python `task_reserved_demand` / `consumes_reserved`
(`src/artifactsmmo_cli/ai/task_reservation.py`) must agree with the proved Lean
`reservedDemand` / `consumesReserved` (formal/Formal/TaskReservation.lean).

This bridges the model↔code gap for the P0 2026-06-09 task-material
reservation: the live predicate deciding whether a step-tier goal would EAT an
active items task's pooled materials is the SAME function the kernel proved
(1) inert when the task is done, (2) permissive on surplus, and (3) monotone
shrinking as the task progresses.

Item codes are small ints (stringified for the Python side); the same recipe
graph / task ctx / owned map is encoded flat for the oracle. Random graphs
include CYCLIC shapes (the Python visited-frozenset guard and the Lean
per-path visited list must agree). `owned` is split between inventory and
bank across runs so a mutant that drops the bank term is killed.
"""
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_reservation import consumes_reserved, task_reserved_demand
from formal.diff.oracle_client import run_oracle
from tests.test_ai.fixtures import make_state

FUEL = 12  # > max universe size (8) — the Lean fuel bound never binds.
N_ITEMS = 8


def _gd(recipes: dict[int, dict[int, int]]) -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        str(item): {str(sub): qty for sub, qty in subs.items()}
        for item, subs in recipes.items()
    }
    return gd


def _state(task_is_items: bool, task_code: int, total: int, progress: int,
           owned: dict[int, int], bank_split: bool):
    """WorldState with `owned` split inventory/bank when bank_split (else all
    inventory, bank None — the conservative branch)."""
    inv: dict[str, int] = {}
    bank: dict[str, int] | None = {} if bank_split else None
    for code, qty in owned.items():
        if bank_split and qty > 1:
            inv[str(code)] = qty // 2
            bank[str(code)] = qty - qty // 2
        else:
            inv[str(code)] = qty
    return make_state(
        task_code=str(task_code),
        task_type="items" if task_is_items else "monsters",
        task_total=total, task_progress=progress,
        inventory=inv, bank_items=bank,
    )


def _encode(recipes: dict[int, dict[int, int]], task_is_items: bool,
            task_code: int, total: int, progress: int, needed: list[int],
            owned: dict[int, int], queries: list[int]) -> list[int]:
    args: list[int] = []
    triples = [(item, sub, qty) for item, subs in recipes.items()
               for sub, qty in subs.items()]
    args.append(len(triples))
    for item, sub, qty in triples:
        args += [item, sub, qty]
    args += [1 if task_is_items else 0, task_code, total, progress]
    args.append(len(needed))
    args += needed
    args.append(len(owned))
    for code, qty in owned.items():
        args += [code, qty]
    args.append(len(queries))
    args += queries
    args.append(FUEL)
    return args


def _check(recipes, task_is_items, task_code, total, progress, needed, owned,
           bank_split):
    gd = _gd(recipes)
    state = _state(task_is_items, task_code, total, progress, owned, bank_split)
    queries = list(range(N_ITEMS))
    py_demand = task_reserved_demand(state, gd)
    py_consumes = consumes_reserved({str(n): 1 for n in needed}, state, gd)
    lean = run_oracle("task_reservation", [
        _encode(recipes, task_is_items, task_code, total, progress, needed,
                owned, queries),
    ])[0]
    assert py_consumes == lean["consumes"], (
        f"consumes mismatch: py={py_consumes} lean={lean['consumes']} "
        f"recipes={recipes} items={task_is_items} task={task_code} "
        f"{progress}/{total} needed={needed} owned={owned} split={bank_split}"
    )
    for idx, q in enumerate(queries):
        assert (str(q) in py_demand) == lean["demand_keys"][idx], (
            f"demand key mismatch at {q}: py={py_demand} lean={lean}"
        )
        assert py_demand.get(str(q), 0) == lean["demand_vals"][idx], (
            f"demand value mismatch at {q}: py={py_demand} lean={lean}"
        )


def _rand_recipes(rng: random.Random) -> dict[int, dict[int, int]]:
    """Random recipe graph over codes 0..N_ITEMS-1, cycles allowed, qty 0..5
    (0 exercises the zero-qty skip on both sides)."""
    recipes: dict[int, dict[int, int]] = {}
    for item in range(N_ITEMS):
        if rng.random() < 0.55:
            subs: dict[int, int] = {}
            for _ in range(rng.randint(1, 3)):
                subs[rng.randint(0, N_ITEMS - 1)] = rng.randint(0, 5)
            recipes[item] = subs
    return recipes


@settings(max_examples=200, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000_000),
    task_is_items=st.booleans(),
    task_code=st.integers(min_value=0, max_value=N_ITEMS - 1),
    total=st.integers(min_value=1, max_value=12),
    progress=st.integers(min_value=0, max_value=14),
    needed=st.lists(st.integers(min_value=0, max_value=N_ITEMS - 1),
                    min_size=1, max_size=3),
    owned_qty=st.dictionaries(st.integers(min_value=0, max_value=N_ITEMS - 1),
                              st.integers(min_value=0, max_value=130),
                              max_size=N_ITEMS),
    bank_split=st.booleans(),
)
def test_python_matches_lean(seed, task_is_items, task_code, total, progress,
                             needed, owned_qty, bank_split):
    recipes = _rand_recipes(random.Random(seed))
    _check(recipes, task_is_items, task_code, total, progress, needed,
           owned_qty, bank_split)


# ---------------------------------------------------------------------------
# Pinned production trace (2026-06-09): helmet(2) <- 6 x bar(1) <- 10 x ore(0);
# items task = copper_bar (1), 0/11; the step's needed = {copper_helmet (2)}.
# ---------------------------------------------------------------------------

_TRACE_RECIPES = {2: {1: 6}, 1: {0: 10}}


def test_trace_helmet_deferred_binds_against_lean():
    """5 bars held, task 0/11 → deferred (5 <= demand 11) on BOTH sides."""
    _check(_TRACE_RECIPES, True, 1, 11, 0, [2], {1: 5}, bank_split=False)
    gd = _gd(_TRACE_RECIPES)
    state = _state(True, 1, 11, 0, {1: 5}, bank_split=False)
    assert consumes_reserved({"2": 1}, state, gd) is True


def test_trace_surplus_allowed_binds_against_lean():
    """17 bars held (strictly above demand 11) → allowed on BOTH sides."""
    _check(_TRACE_RECIPES, True, 1, 11, 0, [2], {1: 17}, bank_split=False)
    gd = _gd(_TRACE_RECIPES)
    state = _state(True, 1, 11, 0, {1: 17}, bank_split=False)
    assert consumes_reserved({"2": 1}, state, gd) is False


def test_trace_done_allowed_binds_against_lean():
    """Task complete (11/11) → nothing reserved, allowed on BOTH sides."""
    _check(_TRACE_RECIPES, True, 1, 11, 11, [2], {1: 5}, bank_split=False)
    gd = _gd(_TRACE_RECIPES)
    state = _state(True, 1, 11, 11, {1: 5}, bank_split=False)
    assert task_reserved_demand(state, gd) == {}
    assert consumes_reserved({"2": 1}, state, gd) is False


def test_surplus_boundary_binds_against_lean():
    """owned == demand (11 bars vs demand 11) is NOT surplus → deferred; one
    more bar flips it. Kills the `<=` → `<` boundary mutant."""
    _check(_TRACE_RECIPES, True, 1, 11, 0, [2], {1: 11}, bank_split=False)
    _check(_TRACE_RECIPES, True, 1, 11, 0, [2], {1: 12}, bank_split=False)
    gd = _gd(_TRACE_RECIPES)
    at_demand = _state(True, 1, 11, 0, {1: 11}, bank_split=False)
    above_demand = _state(True, 1, 11, 0, {1: 12}, bank_split=False)
    assert consumes_reserved({"2": 1}, at_demand, gd) is True
    assert consumes_reserved({"2": 1}, above_demand, gd) is False


def test_non_items_task_reserves_nothing_binds_against_lean():
    """A monsters task reserves nothing even with bars held. Kills the
    'ignore the task_type gate' mutant."""
    _check(_TRACE_RECIPES, False, 1, 11, 0, [2], {1: 5}, bank_split=False)
    gd = _gd(_TRACE_RECIPES)
    state = _state(False, 1, 11, 0, {1: 5}, bank_split=False)
    assert task_reserved_demand(state, gd) == {}
    assert consumes_reserved({"2": 1}, state, gd) is False
