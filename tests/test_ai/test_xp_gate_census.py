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
assertions need.

FIRST-ROUND DEFECT, and why this world looks the way it does now. An earlier
version of this fixture calibrated each monster's item pool IN ISOLATION
(`wolf` against `{wooden_stick, leather_vest, iron_sword}` alone, `troll`
against a pool that never included `iron_sword`, ...) and then merged all
five items into one shared `_item_stats` dict without re-running
`combat_deficit` against the MERGED pool. `combat_deficit`'s default
`candidates=None` walks the WHOLE catalogue for every monster, so the merge
silently changed every monster's real candidate set. A reviewer caught it by
calling `combat_deficit` directly against the shipped fixture: `wolf`'s real
chain was `copper_axe` (does not close) then `leather_vest` (closes on an
ALREADY-HELD gearcrafting level — not a gate at all), because `copper_axe`
out-scored `iron_sword` on raw margin gain against `wolf` too. `iron_sword`
was dead data nothing ever picked, `test_nearest_gate_first` degenerated to
`gaps = [2, 2, 2]` (three monsters landing on the same `copper_axe` gate), and
deleting `rows.sort(...)` from the implementation left the test passing
anyway. The brief's required property — "wolf's closing chain step is
genuinely gated above the character's weaponcrafting level" — was not met.

The fix is elemental isolation, not bigger numbers. Every monster below
resists 100% on the elements that would let an UNINTENDED weapon help it, so
each monster's real chain is decided by exactly the items this docstring
names, independent of whatever else shares the pool:

- `green_slime` (level 1, 1 hp, no attack, no resistance): the character's
  starting `wooden_stick` (air attack) already wins it outright —
  `combat_deficit` returns `None`, so it is a live XP source, not a gated one.
- `troll` (level 2, 80 hp, water attack 40, resists water 100% / fire 0%):
  resisting its OWN attack element fully would make `leather_vest` an
  outright win by itself (measured: it does, at 100% — the out-sustain branch
  fires and no fight ever needs `copper_axe`), so the vest's water resistance
  is throttled to 90%, not 100%, leaving real chip damage. `iron_sword`
  (water attack) is blocked outright by troll's 100% water resistance, so it
  can never be picked here regardless of what else is in the pool.
  Measured real chain: `leather_vest` (gearcrafting 1, ALREADY held — not a
  gate, margin -35 -> -1, does not close) then `copper_axe` (weaponcrafting
  1 -> 3, margin -1 -> 25, CLOSES).
- `wolf` (level 3, 200 hp, air attack 12, resists fire 100% / water 0%):
  the only element none of `leather_vest`/`found_shield` resist and troll
  doesn't gate is `air`, used here so `wolf`'s own attack doesn't overlap any
  armor piece's resistance — its chain is offense-only. `wolf` fully resists
  fire, so `copper_axe` contributes exactly zero margin against it (measured)
  and is never picked regardless of the shared pool. Measured real chain:
  `iron_sword` alone (weaponcrafting 1 -> 20, margin -86 -> 9, CLOSES) — one
  step, and it is the weaponcrafting item genuinely above the held level that
  the brief requires.
- `dragon` (level 4, 80 hp, earth attack 40, resists water 100% / fire 0%):
  covers the branch `gated_xp_sources` takes for a chain step with NO
  crafting gate at all. `found_shield` (earth resistance, no `crafting_skill`
  — a found item, not a craft) is throttled to 90% for the same out-sustain
  reason as `leather_vest`, so it genuinely does not close the fight alone;
  `iron_sword` is blocked by dragon's 100% water resistance the same way it
  is against troll. Measured real chain: `found_shield` (margin -35 -> -1,
  no gate, does not close, must be SKIPPED rather than reported open or
  closed) then `copper_axe` (weaponcrafting 1 -> 3, margin -1 -> 25, CLOSES).
- `hydra` (level 40, 5000 hp, 200 attack on every element, resists every
  element 100%): nothing in this catalogue can dent it or survive it —
  measured `combat_deficit(...).closes is False` at the module's default
  `max_chain`. This is the "drop/spawn wall, not a skill gate" case
  `gated_xp_sources`'s docstring names: a deficit exists but nothing closes
  it, so it must produce NO row, and `test_an_unclosable_deficit_is_not_a_gated_source`
  is the only test in this file that would catch a regression of that
  specific exclusion (coverage alone does not: `pyproject.toml` sets
  `branch = false`, so the `if deficit is None or not deficit.closes:
  continue` line reads covered whichever half of the `or` fired it, unless a
  fixture actually exercises the `closes is False` half).

Four gates result: `troll` -> `copper_axe` (gap 2), `dragon` -> `copper_axe`
(gap 2), `wolf` -> `iron_sword` (gap 19) — two DIFFERENT gaps, genuinely, so
`test_nearest_gate_first` compares real values instead of sorting a
single-element or all-equal list — and `hydra`, which contributes nothing.

SECOND-ROUND DEFECT: THE UNIT WAS THE STEP. The census emitted one row per
gated chain step and sorted on that step's own gap, but `combat_deficit` sets
`closes=True` only after the LAST step wins the fight — so every step is
required and a monster's cost is its DEEPEST gate, not its shallowest. A
shallow non-binding step could therefore represent its monster near the top of
a list the reader treats as a priority order, and the report's `[:20]`
truncation could cut the step that actually binds. `two_gate_state` below is
the world that exhibits it: the SAME catalogue, with the character's
gearcrafting at 0 instead of 1, which turns troll's already-held `leather_vest`
step into a genuine gate at gap 1 beside its binding `copper_axe` at gap 2.
Measured: troll's steps become `[leather_vest (gap 1), copper_axe (gap 2)]`,
its reported gap is 2, and it therefore does NOT outrank `dragon` (gap 2) on a
step it does not need alone. The chain itself is unchanged by the skill level —
`combat_deficit`'s pool is levels-and-stats, not craftability — so this varies
exactly one thing.

Every number and every chain in this docstring was read off a live call to
`combat_deficit`/`gated_xp_sources` against the exact fixture below during
development (see `.superpowers/sdd/PLAN_season9_t1_objective_audit/task-5-report.md`,
fix-round section, for the recorded output, and `final-fix-report.md` for the
two-gate re-measurement), not inferred from the formula or carried over from the
per-monster calibration that turned out to be wrong.
"""

import pytest

from artifactsmmo_cli.ai.combat_deficit import CombatDeficit, DeficitStep
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.audit import xp_gate_census
from artifactsmmo_cli.audit.xp_gate_census import GatedSource, GatedStep, gated_xp_sources
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


@pytest.fixture
def gate_game_data() -> GameData:
    """Five monsters, each isolated (by 100%-resisting the elements that would
    let an unintended weapon help it) so its real `combat_deficit` chain is
    decided only by the items this module's docstring names. See the module
    docstring for the measured chain each monster actually produces."""
    game_data = GameData()
    game_data._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"air": 2}),
        "leather_vest": ItemStats(code="leather_vest", level=1, type_="body_armor",
                                  resistance={"water": 90},
                                  crafting_skill="gearcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=1, type_="weapon",
                                attack={"water": 40},
                                crafting_skill="weaponcrafting", crafting_level=20),
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"fire": 6},
                                crafting_skill="weaponcrafting", crafting_level=3),
        "found_shield": ItemStats(code="found_shield", level=1, type_="shield",
                                  resistance={"earth": 90}),
    }
    game_data._monster_level = {"green_slime": 1, "troll": 2, "wolf": 3,
                                "dragon": 4, "hydra": 40}
    game_data._monster_hp = {"green_slime": 1, "troll": 80, "wolf": 200,
                             "dragon": 80, "hydra": 5000}
    game_data._monster_attack = {
        "green_slime": {},
        "troll": {"water": 40},
        "wolf": {"air": 12},
        "dragon": {"earth": 40},
        "hydra": {"fire": 200, "water": 200, "earth": 200, "air": 200},
    }
    game_data._monster_resistance = {
        "green_slime": {},
        "troll": {"water": 100, "fire": 0},
        "wolf": {"fire": 100, "water": 0},
        "dragon": {"fire": 0, "water": 100},
        "hydra": {"fire": 100, "water": 100, "earth": 100, "air": 100},
    }
    fill_monster_stat_defaults(game_data)
    return game_data


@pytest.fixture
def gate_state() -> WorldState:
    """Level 5, holding only the starting `wooden_stick`. Every skill level
    this fixture's gates depend on is set EXPLICITLY here rather than
    inherited from `make_state`'s defaults — the first-round defect showed
    this world is sensitive enough that a future change to those shared
    defaults must fail this module loudly, not silently recalibrate it.
    weaponcrafting 1 gates `copper_axe` (3) and `iron_sword` (20); gearcrafting
    1 is exactly `leather_vest`'s requirement (1), which is what makes it
    already-craftable rather than a wall."""
    return make_state(level=5, hp=150, max_hp=150, equipment={},
                      inventory={"wooden_stick": 1},
                      skills={"weaponcrafting": 1, "gearcrafting": 1})


@pytest.fixture
def two_gate_state() -> WorldState:
    """`gate_state`, with gearcrafting at 0 instead of 1 — the ONE difference.

    That turns troll's `leather_vest` chain step (gearcrafting 1) from an
    already-craftable step into a genuine gate at gap 1, standing beside its
    binding `copper_axe` gate at gap 2. It is the minimal world in which a
    monster has two gates of DIFFERENT depth, which is the only shape that can
    tell per-step ranking from per-monster ranking apart."""
    return make_state(level=5, hp=150, max_hp=150, equipment={},
                      inventory={"wooden_stick": 1},
                      skills={"weaponcrafting": 1, "gearcrafting": 0})


def test_step_gap_is_levels_between_held_and_required() -> None:
    step = GatedStep(blocking_item="iron_sword", item_type="weapon",
                     skill="weaponcrafting", required_level=20, held_level=6)
    assert step.gap == 14


def test_a_monsters_gap_is_its_deepest_gate_not_its_shallowest() -> None:
    """Every step in a closing chain is required, so the fight opens only once
    the deepest gate does. Reporting the shallowest would price a monster at a
    level that does not buy the fight."""
    source = GatedSource(monster="wolf", monster_level=15, steps=(
        GatedStep(blocking_item="gold_ring", item_type="ring",
                  skill="jewelrycrafting", required_level=10, held_level=5),
        GatedStep(blocking_item="iron_sword", item_type="weapon",
                  skill="weaponcrafting", required_level=20, held_level=10),
    ))
    assert source.gap == 10
    assert source.binding.blocking_item == "iron_sword"


def test_a_winnable_monster_is_not_a_gated_source(gate_state, gate_game_data) -> None:
    # green_slime is beatable with what the character wears now, so combat_deficit
    # returns None for it and it is already a live XP source.
    sources = gated_xp_sources(gate_state, gate_game_data)
    assert "green_slime" not in {s.monster for s in sources}


def test_an_unwinnable_monster_names_the_skill_that_gates_its_upgrade(
        gate_state, gate_game_data) -> None:
    sources = {s.monster: s for s in gated_xp_sources(gate_state, gate_game_data)}
    wolf = sources["wolf"].binding
    assert wolf.item_type == "weapon"
    assert wolf.skill == "weaponcrafting"
    assert wolf.required_level > wolf.held_level


def test_a_step_the_character_can_already_craft_is_not_a_gate(
        gate_state, gate_game_data) -> None:
    # A chain step whose crafting level is already held is not a wall; reporting
    # it would put an open gate in a list of closed ones.
    sources = gated_xp_sources(gate_state, gate_game_data)
    assert all(step.required_level > step.held_level
               for s in sources for step in s.steps)
    # troll's leather_vest step (gearcrafting 1, exactly what gate_state holds)
    # is the one this excludes, so troll is left with copper_axe alone.
    troll = {s.monster: s for s in sources}["troll"]
    assert [step.blocking_item for step in troll.steps] == ["copper_axe"]


def test_nearest_gate_first(gate_state, gate_game_data) -> None:
    gaps = [s.gap for s in gated_xp_sources(gate_state, gate_game_data)]
    assert gaps == sorted(gaps)


def test_a_multi_gate_monster_is_ranked_on_the_binding_step(
        two_gate_state, gate_game_data) -> None:
    """The I1 regression test. troll's chain needs gearcrafting +1 AND
    weaponcrafting +2; the fight costs +2. Under per-step rows sorted on the
    step's own gap, the +1 step would put troll at the head of the list — ahead
    of dragon, which is genuinely the same price — and a reader taking the top
    of that list as a priority order would conclude gearcrafting +1 unlocks a
    fight it does not."""
    sources = {s.monster: s for s in gated_xp_sources(two_gate_state, gate_game_data)}
    troll = sources["troll"]
    assert [step.blocking_item for step in troll.steps] == ["leather_vest", "copper_axe"]
    assert [step.gap for step in troll.steps] == [1, 2]
    assert troll.gap == 2
    assert troll.binding.blocking_item == "copper_axe"
    # And the shallow step does not buy troll a better rank than dragon, whose
    # single gate is the same copper_axe at the same depth.
    assert sources["dragon"].gap == 2
    assert [s.monster for s in gated_xp_sources(two_gate_state, gate_game_data)] == [
        "dragon", "troll", "wolf"]


@pytest.fixture
def open_gate_state() -> WorldState:
    """`gate_state`, with weaponcrafting at 3 — enough for `copper_axe`.

    troll and dragon then have closing chains whose every step the character can
    already craft, so they are unwinnable TODAY but behind no skill gate at all.
    They must produce no row: a monster in this list is a monster a skill level
    would unlock, and one with an empty gate list is a different finding
    (the gear is craftable now; something else is in the way)."""
    return make_state(level=5, hp=150, max_hp=150, equipment={},
                      inventory={"wooden_stick": 1},
                      skills={"weaponcrafting": 3, "gearcrafting": 1})


def test_a_closing_chain_with_no_remaining_gate_produces_no_row(
        open_gate_state, gate_game_data) -> None:
    sources = {s.monster for s in gated_xp_sources(open_gate_state, gate_game_data)}
    assert sources == {"wolf"}


def test_a_repeated_chain_code_is_one_gate_not_two(monkeypatch, gate_state) -> None:
    """`combat_deficit.py:326` increments the projected inventory without
    removing the code from the pool, so one chain can append the same code
    twice. That is one gate observed twice: counted twice it would double a
    monster's step list and consume two slots of the report's top 20."""
    step = DeficitStep(code="iron_sword", item_type="weapon", item_level=1,
                       crafting_skill="weaponcrafting", crafting_level=20,
                       margin_after=9)
    monkeypatch.setattr(xp_gate_census, "combat_deficit",
                        lambda state, game_data, monster: CombatDeficit(
                            monster=monster, baseline_margin=-86,
                            chain=(step, step), closes=True))
    game_data = GameData()
    game_data._monster_level = {"wolf": 3}

    sources = gated_xp_sources(gate_state, game_data)

    assert len(sources) == 1
    assert [s.blocking_item for s in sources[0].steps] == ["iron_sword"]


def test_a_missing_skill_level_fails_loudly_rather_than_defaulting(
        monkeypatch, gate_game_data) -> None:
    """`world_state` builds `skills` with `_require(...)` for every trainable
    skill, so an absent key is missing API data. A `.get(skill, 0)` default
    would silently INFLATE the gap — a phantom wall ranked first — which is
    exactly what "use only API data, or fail with an error" forbids."""
    stateless = make_state(level=5, hp=150, max_hp=150, equipment={},
                           inventory={"wooden_stick": 1}, skills={"gearcrafting": 1})
    with pytest.raises(KeyError, match="weaponcrafting"):
        gated_xp_sources(stateless, gate_game_data)


def test_an_unclosable_deficit_is_not_a_gated_source(gate_state, gate_game_data) -> None:
    # hydra is unwinnable AND nothing in the catalogue closes it (closes=False)
    # — a drop/spawn wall, not a skill gate. Reporting it would put an
    # unopenable gate in a list of openable ones.
    sources = gated_xp_sources(gate_state, gate_game_data)
    assert "hydra" not in {s.monster for s in sources}
