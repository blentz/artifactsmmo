"""`combat_deficit` — the gear gap that stands between a character and a fight.

The bug it fixes (live, C3P0 2026-08-20): the bot fought a monster its own
`predict_win` said it would lose, 42 times out of 42, because the only thing
linking "I lost" to "acquire gear" was a countdown. `combat_deficit` makes that
link a FACT: non-None while the fight is unwinnable, naming the acquisitions that
close it, and clearing itself the moment they land.

Ownership is expressed through `inventory`, never `equipment`. `project_loadout_stats`
computes a DELTA from server-authoritative totals, so `state.attack` already
includes worn gear; a fixture that puts a sword in `equipment` while leaving
`attack` empty describes an impossible character (wearing a 30-attack weapon with
0 total attack) and projects to zero damage. Same convention as
`test_weapon_winnability`.
"""

from artifactsmmo_cli.ai.combat_deficit import combat_deficit
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """A boar that a bare-handed character cannot scratch, and a gear ladder.

    `boar`: 200 hp, 10 earth attack, no resistances — damage and survival both
    decide the fight, which is what lets offense and defense stack.

    Calibrated against `combat_margin` (character at 100/100 hp):

    - bare              margin -101  (no weapon -> no damage at all)
    - `bronze_sword`    margin   -2  attack earth 16      — helps, NOT enough
    - `hide_vest`       margin -101  res earth 20, +40 hp — useless without a weapon
    - both together     margin   +1  WIN                  — the two-step chain
    - `steel_sword`     margin   +4  attack earth 30      — enough on its own
    - `cloth_cap`       no combat stats                   — never improves anything
    """
    gd = GameData()
    gd._item_stats = {
        "bronze_sword": ItemStats(code="bronze_sword", level=1, type_="weapon",
                                  attack={"earth": 16},
                                  crafting_skill="weaponcrafting", crafting_level=5),
        "steel_sword": ItemStats(code="steel_sword", level=1, type_="weapon",
                                 attack={"earth": 30},
                                 crafting_skill="weaponcrafting", crafting_level=10),
        "hide_vest": ItemStats(code="hide_vest", level=1, type_="body_armor",
                               resistance={"earth": 20}, hp_bonus=40,
                               crafting_skill="gearcrafting", crafting_level=5),
        "cloth_cap": ItemStats(code="cloth_cap", level=1, type_="helmet"),
    }
    gd._monster_level = {"boar": 1}
    gd._monster_hp = {"boar": 200}
    gd._monster_attack = {"boar": {"earth": 10}}
    gd._monster_resistance = {"boar": {}}
    fill_monster_stat_defaults(gd)
    return gd


def _state(**inventory: int):
    return make_state(level=1, hp=100, max_hp=100, equipment={}, inventory=dict(inventory))


def test_no_deficit_when_the_fight_is_already_winnable() -> None:
    """A winnable fight has NO deficit — the fact is None, not an empty chain.

    This is the clearing condition. A caller that blocks a fight "while the
    deficit is non-None" releases on its own once the gear lands: nothing to
    expire, no escalation ladder to exhaust, which is exactly what the countdown
    it replaces could not do.
    """
    assert combat_deficit(_state(steel_sword=1), _gd(), "boar") is None


def test_deficit_names_the_acquisition_that_closes_it() -> None:
    """A losing fight yields a deficit whose chain CLOSES, ending margin-positive."""
    deficit = combat_deficit(_state(), _gd(), "boar",
                             candidates=("steel_sword", "cloth_cap"))

    assert deficit is not None
    assert deficit.monster == "boar"
    assert deficit.baseline_margin < 0
    assert deficit.closes is True
    assert [s.code for s in deficit.chain] == ["steel_sword"]
    assert deficit.chain[-1].margin_after > 0


def test_chain_step_carries_the_skill_that_gates_it() -> None:
    """Each step names its crafting gate — the chain is fight <- gear <- SKILL.

    C3P0's real chain needed weaponcrafting 6->10 before `iron_sword` could be
    crafted at all, and jewelrycrafting 8->15 for `earth_ring`. A step that did
    not carry its gate would read as actionable when it is not.
    """
    step = combat_deficit(_state(), _gd(), "boar",
                          candidates=("steel_sword",)).chain[0]

    assert step.crafting_skill == "weaponcrafting"
    assert step.crafting_level == 10
    assert step.item_type == "weapon"


def test_chain_takes_the_largest_margin_gain_first() -> None:
    """Greedy on MARGIN, not on item value.

    The live failure was the opposite: a monster-blind `_best_by_value` scan chose
    `iron_boots` — already worn, and absent from all 24 items that improved the
    pig margin — while the weapon that actually moved `rounds_to_kill` went
    unbuilt for ten hours.
    """
    deficit = combat_deficit(_state(), _gd(), "boar")

    assert deficit.chain[0].code == "steel_sword"


def test_multi_step_chain_when_no_single_item_closes_it() -> None:
    """USER: "multiple upgrades before we can win that fight" is a normal outcome.

    Offense alone leaves the margin at -2; the vest that survives two more rounds
    carries it to +1. The chain stacks them instead of giving up, and there is no
    fallback to an easier monster.
    """
    deficit = combat_deficit(_state(), _gd(), "boar",
                             candidates=("bronze_sword", "hide_vest"))

    assert [s.code for s in deficit.chain] == ["bronze_sword", "hide_vest"]
    assert deficit.closes is True
    assert deficit.chain[0].margin_after < 0 < deficit.chain[1].margin_after


def test_deficit_that_nothing_closes_reports_an_empty_chain_not_a_crash() -> None:
    """No candidate improves the margin: the deficit is REAL and `closes` is False.

    Total by construction — the caller must distinguish "unwinnable and I know
    what to build" from "unwinnable and I do not", because only the first is
    progress.
    """
    deficit = combat_deficit(_state(), _gd(), "boar", candidates=("cloth_cap",))

    assert deficit is not None
    assert deficit.baseline_margin < 0
    assert deficit.closes is False
    assert deficit.chain == ()


def test_chain_is_bounded_by_max_chain() -> None:
    """The greedy walk is bounded so an unclosable deficit cannot spin."""
    deficit = combat_deficit(_state(), _gd(), "boar",
                             candidates=("bronze_sword", "hide_vest"), max_chain=1)

    assert len(deficit.chain) == 1
    assert deficit.closes is False


def test_default_candidate_pool_excludes_gear_above_the_characters_level() -> None:
    """The pool is what the character could actually equip, not the whole catalog."""
    gd = _gd()
    gd._item_stats["mythic_blade"] = ItemStats(code="mythic_blade", level=40,
                                               type_="weapon", attack={"earth": 500})

    deficit = combat_deficit(_state(), gd, "boar")

    assert "mythic_blade" not in [s.code for s in deficit.chain]
