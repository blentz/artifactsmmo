"""Differential: the REAL `LevelSkill.apply` / `.is_applicable`
(`src/artifactsmmo_cli/ai/actions/level_skill.py`) must agree with the proved
Lean mirror `Formal.ActionApplicability.levelSkillApply` /
`levelSkillApplicable` (Oracle keys `level_skill_apply` /
`level_skill_applicable`).

`apply` optimistically sets `skills[skill] := target_level`; `is_applicable` is
`current < target AND a feasible in-skill grind rung exists`. The grind-rung
feasibility (`skill_grind_target(...) is not None`) is the opaque conjunct the
Lean model takes as `hasGrindRung`; this test DERIVES it from the REAL
`skill_grind_target` on live fixtures and feeds it to the oracle — so the opaque
flag is value-lockstepped end-to-end (exactly as the Lean comment documents).

Two fixtures pin both rung branches:
* `_gd_with_grind_rung` — gearcrafting has a level-1 obtainable rung (`trinket`),
  so `skill_grind_target` finds a rung at any skill level >= 1.
* `_gd_no_grind_rung` — the only gearcrafting recipe is level 10 with an
  UN-obtainable input, so no rung exists at the tested levels.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle

_SKILL = "gearcrafting"
_GATHER_SKILL = "alchemy"


def _gd_with_grind_rung() -> GameData:
    """A level-1 obtainable rung (`trinket` <- located gatherable `gear_ore`)
    plus a level-5 target (`widget`): `skill_grind_target` finds a rung for any
    current gearcrafting level >= 1."""
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="resource",
                            subtype="craft", crafting_skill=_SKILL,
                            crafting_level=5),
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill=_SKILL,
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    return gd


def _gd_no_grind_rung() -> GameData:
    """Only a level-10 gearcrafting recipe whose input is un-gettable — no
    obtainable in-level rung at the tested skill levels."""
    gd = GameData()
    gd._item_stats = {
        "lonely": ItemStats(code="lonely", level=10, type_="resource",
                            subtype="craft", crafting_skill=_SKILL,
                            crafting_level=10),
    }
    gd._crafting_recipes = {"lonely": {"phantom_ore": 2}}
    return gd


def _gd_gather_rung() -> GameData:
    """A GATHER-skill fixture: alchemy has a gatherable resource (`sunflower`
    at level 1) but its lowest CRAFTABLE recipe is level 5, so
    `skill_grind_target` finds NO rung yet `best_gather_resource_drop` does —
    pinning the gather arm of `is_applicable` (gathering grinds the skill)."""
    gd = GameData()
    gd._item_stats = {
        "small_potion": ItemStats(code="small_potion", level=5, type_="consumable",
                                  subtype="potion", crafting_skill=_GATHER_SKILL,
                                  crafting_level=5),
        "sunflower": ItemStats(code="sunflower", level=1, type_="resource",
                               subtype="alchemy"),
    }
    gd._crafting_recipes = {"small_potion": {"sunflower": 3}}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_skill = {"sunflower_field": (_GATHER_SKILL, 1)}
    gd._resource_locations = {"sunflower_field": [(4, 4)]}
    return gd


_RUNG_GD = _gd_with_grind_rung()
_NO_RUNG_GD = _gd_no_grind_rung()
_GATHER_GD = _gd_gather_rung()


def _state(gd: GameData, current: int, skill: str = _SKILL) -> WorldState:
    return scenario_state(
        ScenarioCharacter(name="t", level=5, skills={skill: current}), gd)


def _check(gd: GameData, current: int, target: int, skill: str = _SKILL) -> bool:
    """Assert Lean == Python for one (gd, current, target); return the observed
    has_grind_rung so callers can pin which branch was exercised. `has_rung`
    mirrors the REAL is_applicable rung conjunct: a craftable rung
    (`skill_grind_target`) OR a gatherable in-skill resource
    (`best_gather_resource_drop`)."""
    state = _state(gd, current, skill)
    action = LevelSkill(skill=skill, target_level=target)

    has_rung = (skill_grind_target(skill, state, gd) is not None
                or best_gather_resource_drop(skill, current, gd) is not None)
    py_app = action.is_applicable(state, gd)
    lean_app = run_oracle(
        "level_skill_applicable", [[current, target, 1 if has_rung else 0]]
    )[0]["applicable"]
    assert py_app == lean_app, (current, target, has_rung, py_app, lean_app)
    # model-consistency: is_applicable IS the Lean conjunction on the real flag
    assert py_app == (current < target and has_rung)

    py_level = action.apply(state, gd).skills[skill]
    lean_level = run_oracle("level_skill_apply", [[current, target]])[0]["level"]
    assert py_level == lean_level == target, (current, target, py_level, lean_level)
    return has_rung


@settings(max_examples=120, deadline=None)
@given(
    current=st.integers(min_value=1, max_value=8),
    target=st.integers(min_value=1, max_value=8),
)
def test_rung_present_matches_lean(current, target):
    """Rung fixture: current >= 1 always yields a rung, so applicability tracks
    the level gap alone (exercises `<`, `==`, `>` against target)."""
    assert _check(_RUNG_GD, current, target) is True


@settings(max_examples=120, deadline=None)
@given(
    current=st.integers(min_value=0, max_value=5),
    target=st.integers(min_value=6, max_value=12),
)
def test_no_rung_matches_lean(current, target):
    """No-rung fixture: under-target but no feasible rung → NOT applicable.
    Pins the grind-rung conjunct (kills a dropped rung check)."""
    assert _check(_NO_RUNG_GD, current, target) is False


@settings(max_examples=60, deadline=None)
@given(
    current=st.integers(min_value=1, max_value=4),
    target=st.integers(min_value=5, max_value=8),
)
def test_gather_rung_matches_lean(current, target):
    """Gather-skill fixture: no craftable rung, but a gatherable resource exists
    at level >= 1, so `is_applicable` is True via the gather arm — pins that arm
    (a mutant dropping best_gather_resource_drop makes py_app False while
    has_rung stays True → diverges)."""
    assert _check(_GATHER_GD, current, target, _GATHER_SKILL) is True


def test_boundary_cases_pinned():
    """Explicit boundaries the mutation anchors target."""
    # under-target with rung → applicable (kills apply off-by-one + guard drops)
    assert _check(_RUNG_GD, 1, 5) is True
    # at-target with rung → NOT applicable (kills the `>=` -> `>` guard flip)
    assert _check(_RUNG_GD, 5, 5) is True
    # over-target with rung → NOT applicable
    assert _check(_RUNG_GD, 6, 5) is True
    # under-target WITHOUT rung → NOT applicable (kills the rung-check drop)
    assert _check(_NO_RUNG_GD, 5, 10) is False
    # gather arm: under-target, no craftable rung but a gatherable → applicable
    assert _check(_GATHER_GD, 1, 5, _GATHER_SKILL) is True
