"""Which character-XP sources are walled behind which skill levels.

`combat_deficit` already computes the gear chain WITH its crafting gate
(`DeficitStep.crafting_skill` / `crafting_level`); this census only reads that
chain and filters it to what is actually a wall. It is deliberately NOT a
second implementation of the chain — see `xp_gate_census.py`'s module
docstring for why that would drift.

The fixture world below is private to this module, not shared with any other
scenario. `feedback_scenario_declares_its_world` (project memory) records that
a shared `GameData` fixture across test modules has already produced three
vacuous measurements and one shipped false retraction — a world built for one
question silently answering a different one for whoever borrows it next. So
`gate_state` / `gate_game_data` here declare exactly the world this file's
five assertions need, calibrated against the SAME `combat_margin`/`combat_deficit`
this module exercises (not asserted from memory of the formula):

- `green_slime` (level 1, 1 hp, no attack): the character's starting
  `wooden_stick` (bare air attack) already wins it outright — `combat_deficit`
  returns `None`, so it is a live XP source, not a gated one.
- `troll` (level 2, 50 hp, fire attack 8): unwinnable with `wooden_stick`
  alone; closes with ONE item, `copper_axe` (weaponcrafting 3), a small gap
  above the character's held weaponcrafting 1.
- `wolf` (level 3, 200 hp, water attack 12): unwinnable with `wooden_stick`
  alone; the greedy walk's FIRST pick is `leather_vest` (gearcrafting 1 — a
  level the character already holds, so it is a real, already-craftable chain
  step, not a wall) and it does not close the fight alone. The walk's SECOND
  pick, `iron_sword` (weaponcrafting 10, ten levels above the held 1), closes
  it. `leather_vest` must NOT appear in `gated_xp_sources`'s output even
  though it is a real, non-empty chain step: that is what
  `test_a_step_the_character_can_already_craft_is_not_a_gate` is checking, and
  it is only a meaningful check because the chain genuinely contains such a
  step (a single-monster, single-step world could pass that assertion
  vacuously).

A fourth monster, `dragon` (level 4, 80 hp, earth attack 20), covers the
branch `gated_xp_sources` takes for a chain step with NO crafting gate at
all: its walk's first pick is `found_shield` (no `crafting_skill` — a found
item, not a craft), which does not close the fight and must be skipped
outright rather than reported as an open OR closed gate; its second pick,
`copper_axe`, closes it and is reported exactly like troll's.

Three gates result: `troll` -> `copper_axe` (weaponcrafting 1 -> 3, gap 2),
`dragon` -> `copper_axe` (weaponcrafting 1 -> 3, gap 2), and `wolf` ->
`iron_sword` (weaponcrafting 1 -> 10, gap 9), which is also what makes
`test_nearest_gate_first` a real ordering check instead of a single-element
list sorting itself.
"""

import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit.xp_gate_census import GatedSource, gated_xp_sources
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


@pytest.fixture
def gate_game_data() -> GameData:
    """One beatable monster, one small-gap gate, one large-gap gate — see the
    module docstring for the calibration this world is built from."""
    game_data = GameData()
    game_data._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"air": 2}),
        "leather_vest": ItemStats(code="leather_vest", level=1, type_="body_armor",
                                  resistance={"water": 80}, hp_bonus=40,
                                  crafting_skill="gearcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=1, type_="weapon",
                                attack={"water": 5},
                                crafting_skill="weaponcrafting", crafting_level=10),
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"fire": 6},
                                crafting_skill="weaponcrafting", crafting_level=3),
        "found_shield": ItemStats(code="found_shield", level=1, type_="shield",
                                  resistance={"earth": 80}),
    }
    game_data._monster_level = {"green_slime": 1, "troll": 2, "wolf": 3, "dragon": 4}
    game_data._monster_hp = {"green_slime": 1, "troll": 50, "wolf": 200, "dragon": 80}
    game_data._monster_attack = {"green_slime": {}, "troll": {"fire": 8},
                                 "wolf": {"water": 12}, "dragon": {"earth": 20}}
    game_data._monster_resistance = {"green_slime": {}, "troll": {}, "wolf": {},
                                     "dragon": {}}
    fill_monster_stat_defaults(game_data)
    return game_data


@pytest.fixture
def gate_state() -> WorldState:
    """Level 5, holding only the starting `wooden_stick`, default skill levels
    (weaponcrafting 1, gearcrafting 1 — from `make_state`'s defaults), which is
    what makes `leather_vest` (crafting_level 1) already-craftable and both
    `copper_axe` (3) and `iron_sword` (10) gated."""
    return make_state(level=5, hp=150, max_hp=150, equipment={},
                      inventory={"wooden_stick": 1})


def test_gap_is_levels_between_held_and_required() -> None:
    source = GatedSource(monster="wolf", monster_level=15, blocking_item="iron_sword",
                         item_type="weapon", skill="weaponcrafting",
                         required_level=20, held_level=6)
    assert source.gap == 14


def test_a_winnable_monster_is_not_a_gated_source(gate_state, gate_game_data) -> None:
    # green_slime is beatable with what the character wears now, so combat_deficit
    # returns None for it and it is already a live XP source.
    sources = gated_xp_sources(gate_state, gate_game_data)
    assert "green_slime" not in {s.monster for s in sources}


def test_an_unwinnable_monster_names_the_skill_that_gates_its_upgrade(
        gate_state, gate_game_data) -> None:
    sources = {s.monster: s for s in gated_xp_sources(gate_state, gate_game_data)}
    wolf = sources["wolf"]
    assert wolf.item_type == "weapon"
    assert wolf.skill == "weaponcrafting"
    assert wolf.required_level > wolf.held_level


def test_a_step_the_character_can_already_craft_is_not_a_gate(
        gate_state, gate_game_data) -> None:
    # A chain step whose crafting level is already held is not a wall; reporting
    # it would put an open gate in a list of closed ones.
    sources = gated_xp_sources(gate_state, gate_game_data)
    assert all(s.required_level > s.held_level for s in sources)


def test_nearest_gate_first(gate_state, gate_game_data) -> None:
    gaps = [s.gap for s in gated_xp_sources(gate_state, gate_game_data)]
    assert gaps == sorted(gaps)
