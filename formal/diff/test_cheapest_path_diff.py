"""Differential test: real Python `cheapest_path_to_level` must agree
with the proved Lean `cheapestPath` GREEDY MODEL on STRUCTURAL outputs
(blocked-or-not, segment count, monster-code sequence).

Lean models the algorithm abstractly: given a list of monsters with
pre-computed Nat `xpPerCycle`, it picks the best beatable monster
level-by-level. Python's `xp_per_cycle` is a float derived from
`game_data.xp_per_kill(...) / DEFAULT_FIGHT_CYCLES` when there are
no observations. We drive Python WITHOUT observations (empty store)
and we pass Lean the integer `xp_per_kill` values directly. Since
both sides apply the SAME monotone scaling (divide by the same
constant), the GREEDY argmax is identical, and tie-breaking matches
because both iterate in the SAME insertion-ordered sequence.

OUT-OF-SCOPE for this diff (deliberately): the exact float
`total_cycles` and per-segment `cycles` values. The Lean model uses
integer ceiling division; the contract we PROVE and PIN is structural
(blocked / segment count / chosen monster per level). The actual
float arithmetic is a separate Python-side concern (already exercised
by the existing pytest suite for `cheapest_path_to_level`).
"""
import artifactsmmo_cli.ai.learning.projections as projections_module
from hypothesis import HealthCheck, given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.learning.store import LearningStore
from formal.diff.oracle_client import run_oracle
from tests.test_ai.fixtures import make_state


def _make_state(level: int, max_xp: int = 100):
    """Build a minimal WorldState via the shared fixture (defaults safe)."""
    return make_state(level=level, xp=0, max_xp=max_xp)


def _make_game_data(monsters: list[tuple[str, int, int]]) -> GameData:
    """monsters: list of (code, monster_level, monster_hp) in insertion order."""
    gd = GameData()
    gd._monster_level = {code: lvl for code, lvl, _ in monsters}
    gd._monster_hp = {code: hp for code, _, hp in monsters}
    gd._monster_type = {code: "normal" for code, _, _ in monsters}
    return gd


def _encode_args(current: int, target: int, max_xp: int, xp_in_level: int,
                 monsters_with_xp: list[tuple[int, int, int, int]]) -> list[int]:
    """[current, target, maxXp, xpInLevel, n, code0, lvl0, xpc0, winnable0, ...]"""
    args = [current, target, max_xp, xp_in_level, len(monsters_with_xp)]
    for code, lvl, xpc, winnable in monsters_with_xp:
        args += [code, lvl, xpc, 1 if winnable else 0]
    return args


def _expected_xp_per_kill(gd: GameData, code: str, char_level: int) -> int:
    """Mirror of the formula in Python, called when no observations exist."""
    return gd.xp_per_kill(code, char_level, wisdom=0)


def _python_structural(plan) -> dict:
    """Extract structural-only fields for the diff."""
    return {
        "blocked": plan.blocked,
        "n_segments": len(plan.segments),
        "monster_codes": [s.monster_code for s in plan.segments],
    }


def _run_python(current: int, target: int, monsters: list[tuple[str, int, int]],
                tmp_path, winnable_stub=None) -> dict:
    """Run the real Python with empty store (formula path only).

    winnable_stub: if provided, a callable(state, gd, code, store) -> bool that
    replaces is_winnable in the projections module so the verdict is deterministic.
    """
    store = LearningStore(db_path=str(tmp_path / f"p_{current}_{target}.db"),
                          character="hero")
    state = _make_state(level=current, max_xp=100)
    gd = _make_game_data(monsters)
    if winnable_stub is not None:
        orig = projections_module.is_winnable
        projections_module.is_winnable = winnable_stub
        try:
            plan = cheapest_path_to_level(target, state, store, gd)
        finally:
            projections_module.is_winnable = orig
    else:
        plan = cheapest_path_to_level(target, state, store, gd)
    store.close()
    return _python_structural(plan)


def _run_lean(current: int, target: int, monsters: list[tuple[str, int, int]],
              winnable_per_code: dict[str, bool] | None = None) -> dict:
    """Drive Lean with the SAME inputs Python sees, pre-computing
    xp_per_cycle as integer xp_per_kill (sharing the same monotone scaling
    with Python's float xp_per_kill / 30 — argmax is identical).

    winnable_per_code: maps monster code -> winnable bool fed into Lean.
    Defaults to True for all monsters (matching the old behaviour).
    """
    code_to_id = {code: idx + 1 for idx, (code, _, _) in enumerate(monsters)}
    gd = _make_game_data(monsters)
    # CRITICAL: pass the FINAL sim_level (= target - 1) when computing xp_per_kill.
    # But Python recomputes per sim_level (level scales the formula). For STRUCTURAL
    # agreement across a multi-level walk we restrict the diff to SINGLE-STEP plans
    # (target = current + 1), where each monster has ONE xp_per_kill value tied
    # to sim_level = current.
    assert target == current + 1, "diff restricted to single-step plans"
    if winnable_per_code is None:
        winnable_per_code = {code: True for code, _, _ in monsters}
    monsters_with_xp = [
        (code_to_id[code], lvl, _expected_xp_per_kill(gd, code, current),
         winnable_per_code.get(code, True))
        for code, lvl, _ in monsters
    ]
    raw = run_oracle("cheapest_path",
                     [_encode_args(current, target, 100, 0, monsters_with_xp)])[0]
    # Map Lean's int codes back to the Python string codes
    id_to_code = {v: k for k, v in code_to_id.items()}
    return {
        "blocked": raw["blocked"],
        "n_segments": raw["n_segments"],
        "monster_codes": [id_to_code[c] for c in raw["monster_codes"]],
    }


# --- Property-based diff: single-step plans (one level up) ---------------------

@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    char_level=st.integers(min_value=1, max_value=8),
    n_monsters=st.integers(min_value=0, max_value=5),
    seed=st.integers(min_value=0, max_value=10_000),
)
def test_single_step_structural_matches(tmp_path, char_level, n_monsters, seed):
    """Single-level cheapest-path: blocked/segment-count/monster choice
    must agree with Lean greedy model.

    All monsters are treated as winnable (is_winnable=True stub) so this test
    focuses purely on the level-gate + greedy-xp structure.
    """
    rng_levels = [(seed >> (2 * i)) & 0xF for i in range(n_monsters)]
    rng_hps = [40 + ((seed >> (3 * i + 1)) & 0x3F) for i in range(n_monsters)]
    monsters = [
        (f"m{i}", max(1, lvl), hp)  # ensure level >= 1 (zero filtered separately)
        for i, (lvl, hp) in enumerate(zip(rng_levels, rng_hps))
    ]
    codes = [code for code, _, _ in monsters]
    winnable_stub = lambda state, gd, code, store: True  # noqa: E731
    winnable_per_code = {code: True for code in codes}
    py = _run_python(char_level, char_level + 1, monsters, tmp_path,
                     winnable_stub=winnable_stub)
    lean = _run_lean(char_level, char_level + 1, monsters,
                     winnable_per_code=winnable_per_code)
    assert py["blocked"] == lean["blocked"], (py, lean)
    assert py["n_segments"] == lean["n_segments"], (py, lean)
    assert py["monster_codes"] == lean["monster_codes"], (py, lean)


# --- Deterministic pinned scenarios -------------------------------------------

def test_target_met_no_segments(tmp_path):
    py = _run_python(5, 5, [("chicken", 1, 60)], tmp_path)
    assert py == {"blocked": False, "n_segments": 0, "monster_codes": []}


def test_target_below_no_segments(tmp_path):
    py = _run_python(10, 5, [("chicken", 1, 60)], tmp_path)
    assert py == {"blocked": False, "n_segments": 0, "monster_codes": []}


def test_no_beatable_monsters_blocks(tmp_path):
    winnable_stub = lambda state, gd, code, store: True  # noqa: E731
    winnable_per_code = {"dragon": True}
    py = _run_python(1, 2, [("dragon", 50, 9999)], tmp_path,
                     winnable_stub=winnable_stub)
    lean = _run_lean(1, 2, [("dragon", 50, 9999)],
                     winnable_per_code=winnable_per_code)
    assert py["blocked"] is True
    assert lean["blocked"] is True
    assert py["n_segments"] == lean["n_segments"] == 0


def test_empty_monster_list_blocks(tmp_path):
    py = _run_python(1, 2, [], tmp_path)
    lean = _run_lean(1, 2, [])
    assert py == lean == {"blocked": True, "n_segments": 0, "monster_codes": []}


def test_greedy_picks_higher_xp_per_kill(tmp_path):
    """At char L1: chicken (L1, HP60) vs slime (L2, HP70).
    slime has higher xp_per_kill (level boost). slime should win."""
    monsters = [("chicken", 1, 60), ("slime", 2, 70)]
    winnable_stub = lambda state, gd, code, store: True  # noqa: E731
    winnable_per_code = {"chicken": True, "slime": True}
    py = _run_python(1, 2, monsters, tmp_path, winnable_stub=winnable_stub)
    lean = _run_lean(1, 2, monsters, winnable_per_code=winnable_per_code)
    assert py["monster_codes"] == lean["monster_codes"] == ["slime"]
    assert py["blocked"] is lean["blocked"] is False


def test_unbeatable_filtered_out(tmp_path):
    """ogre (L10) is unbeatable at L1 (>L1+1); chicken (L1) wins."""
    monsters = [("chicken", 1, 60), ("ogre", 10, 9999)]
    winnable_stub = lambda state, gd, code, store: True  # noqa: E731
    winnable_per_code = {"chicken": True, "ogre": True}
    py = _run_python(1, 2, monsters, tmp_path, winnable_stub=winnable_stub)
    lean = _run_lean(1, 2, monsters, winnable_per_code=winnable_per_code)
    assert py["monster_codes"] == lean["monster_codes"] == ["chicken"]


def test_plus_one_boundary_beatable(tmp_path):
    """slime at L2 IS beatable at char L1 (the +1 margin)."""
    monsters = [("slime", 2, 70)]
    winnable_stub = lambda state, gd, code, store: True  # noqa: E731
    winnable_per_code = {"slime": True}
    py = _run_python(1, 2, monsters, tmp_path, winnable_stub=winnable_stub)
    lean = _run_lean(1, 2, monsters, winnable_per_code=winnable_per_code)
    assert py["blocked"] is lean["blocked"] is False
    assert py["monster_codes"] == lean["monster_codes"] == ["slime"]


def test_plus_two_boundary_unbeatable(tmp_path):
    """monster at L3 is NOT beatable at char L1 (the +1 margin is exact)."""
    monsters = [("wolf", 3, 80)]
    winnable_stub = lambda state, gd, code, store: True  # noqa: E731
    winnable_per_code = {"wolf": True}
    py = _run_python(1, 2, monsters, tmp_path, winnable_stub=winnable_stub)
    lean = _run_lean(1, 2, monsters, winnable_per_code=winnable_per_code)
    assert py["blocked"] is lean["blocked"] is True


def test_tie_first_wins(tmp_path):
    """Two monsters with same xp_per_kill: Python dict iter order = insertion."""
    # Identical (level, hp) → identical xp_per_kill → first inserted wins.
    monsters = [("alpha", 1, 60), ("beta", 1, 60)]
    winnable_stub = lambda state, gd, code, store: True  # noqa: E731
    winnable_per_code = {"alpha": True, "beta": True}
    py = _run_python(1, 2, monsters, tmp_path, winnable_stub=winnable_stub)
    lean = _run_lean(1, 2, monsters, winnable_per_code=winnable_per_code)
    assert py["monster_codes"] == lean["monster_codes"] == ["alpha"]


def test_strict_greater_replaces(tmp_path):
    """Higher xp_per_kill ALWAYS replaces a lower running best."""
    monsters = [("low", 1, 10), ("high", 1, 200)]
    winnable_stub = lambda state, gd, code, store: True  # noqa: E731
    winnable_per_code = {"low": True, "high": True}
    py = _run_python(1, 2, monsters, tmp_path, winnable_stub=winnable_stub)
    lean = _run_lean(1, 2, monsters, winnable_per_code=winnable_per_code)
    assert py["monster_codes"] == lean["monster_codes"] == ["high"]


def test_zero_xp_per_kill_blocks(tmp_path):
    """When the only beatable monster's xp_per_kill is 0 (char level is at
    least 10 above monster level → penalty=0.0), the plan MUST block: zero
    xp/cycle means infinite cycles, no progress. Pins the
    `best_xp_per_cycle <= 0` branch (mutation 3)."""
    # char L11 vs monster L1 → diff=10 → penalty=0.0 → xp_per_kill = 0.
    # The monster IS beatable (1 ≤ 1 ≤ 11+1) but yields nothing.
    monsters = [("chicken", 1, 60)]
    state = make_state(level=11, xp=0, max_xp=100)
    gd = _make_game_data(monsters)
    # Sanity: confirm xp_per_kill = 0 at char L11.
    assert gd.xp_per_kill("chicken", 11) == 0
    store = LearningStore(db_path=str(tmp_path / "p_zero.db"), character="hero")
    # Stub is_winnable to True: the zero-xp block is triggered by xp=0, not
    # the winnable gate. Using a stub avoids monster_attack KeyError from the
    # minimal GameData fixture (no attack data loaded).
    winnable_stub = lambda s, g, code, h: True  # noqa: E731
    orig = projections_module.is_winnable
    projections_module.is_winnable = winnable_stub
    try:
        plan = cheapest_path_to_level(12, state, store, gd)
    finally:
        projections_module.is_winnable = orig
    store.close()
    assert plan.blocked is True, "zero xp_per_kill must trigger blocked branch"
    # The Lean greedy with xpPerCycle=0 also blocks (stepLevel_all_zero_blocks).
    code_to_id = {"chicken": 1}
    lean = run_oracle("cheapest_path",
                      [_encode_args(11, 12, 100, 0, [(1, 1, 0, 1)])])[0]
    assert lean["blocked"] is True


def test_winnable_false_skips_to_winnable(tmp_path):
    """A level-OK monster with winnable=False must be skipped in favour of a
    lower-level monster with winnable=True.

    Setup: char L1, target L2.
      - 'hard' (L2, HP200): level-OK (+1 margin), but is_winnable returns False.
      - 'easy' (L1, HP60): level-OK, is_winnable returns True.

    Python must pick 'easy'; Lean (fed winnable=0 for 'hard') must also pick
    'easy'. This case KILLS the cheapest_path: drop is_winnable filter mutant.
    """
    monsters = [("hard", 2, 200), ("easy", 1, 60)]
    winnable_map = {"hard": False, "easy": True}
    winnable_stub = lambda state, gd, code, store: winnable_map[code]  # noqa: E731
    winnable_per_code = {"hard": False, "easy": True}
    py = _run_python(1, 2, monsters, tmp_path, winnable_stub=winnable_stub)
    lean = _run_lean(1, 2, monsters, winnable_per_code=winnable_per_code)
    assert py["blocked"] is False, f"Python should not block: {py}"
    assert lean["blocked"] is False, f"Lean should not block: {lean}"
    assert py["monster_codes"] == ["easy"], f"Python should pick easy: {py}"
    assert lean["monster_codes"] == ["easy"], f"Lean should pick easy: {lean}"
