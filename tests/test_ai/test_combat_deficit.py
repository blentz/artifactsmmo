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


def test_the_deficit_does_not_move_with_transient_hp() -> None:
    """THE D2 LESSON, replayed. "What gear closes this fight" is a different
    question from "should I fight right now", and only the second depends on
    current hp. Rest is an action the planner has.

    Found live: C3P0 at 1/385 hp reported `margin -21, chain DOES NOT CLOSE`
    while the same character at 385/385 reported `margin -10, chain CLOSES` —
    the GEAR PLAN flipping on hp alone. That is the same shape as the 7,000x
    iron-gear price swing `PLAN_iron_gear_acquisition` increment 2 fixed by
    asking route existence at restorable hp.

    The first version of this module argued the opposite ("a deficit computed at
    full hp would clear itself every time the character rested"). That reasoning
    was simply wrong: resting does not change `max_hp`, so a deficit measured
    there is STABLE, not cleared. Engagement at low hp is already prevented by
    `FightAction._structurally_applicable`'s hp floor and the RESTORE_HP guard —
    different gates, and this is not one of them.
    """
    gd = _gd()
    healthy = make_state(level=1, hp=100, max_hp=100, equipment={}, inventory={})
    hurt = make_state(level=1, hp=1, max_hp=100, equipment={}, inventory={})

    assert combat_deficit(hurt, gd, "boar") == combat_deficit(healthy, gd, "boar")


def test_a_fight_winnable_only_when_rested_has_no_gear_deficit() -> None:
    """The boundary case of the rule above: hurt and unwinnable NOW, but no gear
    would help — what it needs is a rest, and inventing a gear chain for it would
    send the character shopping instead of sleeping."""
    gd = _gd()
    hurt = make_state(level=1, hp=1, max_hp=100, equipment={},
                      inventory={"steel_sword": 1})

    assert combat_deficit(hurt, gd, "boar") is None


def test_ranking_is_margin_gain_PER_ACTION_when_a_cost_is_supplied() -> None:
    """THE JOIN. Clause (c) — "lowest skill requirements, prefer things we can
    build" — needs no rule of its own, because `acquisition_cost` already
    expresses a skill gate as `unlock_actions` CYCLES. Lowest skill requirement
    IS cheapest unlock, so preferring it is just preferring gain per action.

    Live shape: `combat-deficit C3P0` ranked on raw margin and chose
    `king_slime_sword` (weaponcrafting@15, C3P0 at 6) over `iron_sword`
    (weaponcrafting@10) — the FURTHER item, because its margin jump was bigger.
    """
    gd = _gd()
    # steel_sword gains more margin outright; bronze_sword gains less but is far
    # cheaper to get. Per action, bronze wins.
    cost = {"steel_sword": 400.0, "bronze_sword": 20.0, "hide_vest": 20.0}

    deficit = combat_deficit(_state(), gd, "boar", cost_of=cost.get)

    assert deficit.chain[0].code == "bronze_sword", (
        "ranked on raw gain, steel_sword wins; per action it does not")


def test_cost_ranking_still_requires_a_real_margin_gain() -> None:
    """Cheap is not a reason to acquire something that does not help. Only
    candidates that actually move the margin are ranked at all, so a free item
    with zero gain can never win on a ratio."""
    gd = _gd()
    cost = {"cloth_cap": 1.0, "steel_sword": 500.0}

    deficit = combat_deficit(_state(), gd, "boar",
                             candidates=("cloth_cap", "steel_sword"),
                             cost_of=cost.get)

    assert [s.code for s in deficit.chain] == ["steel_sword"]


def test_a_zero_cost_candidate_cannot_divide_by_zero() -> None:
    """An item already owned is priced 0 by the acquisition model. It cannot
    improve the margin (`pick_loadout` would already be wearing it), but the
    ranking must not be able to blow up if one ever is."""
    gd = _gd()

    deficit = combat_deficit(_state(), gd, "boar", cost_of=lambda code: 0.0)

    assert deficit.closes is True


def test_without_a_cost_the_ranking_is_unchanged() -> None:
    """`cost_of` defaults to None so every existing caller keeps raw-margin
    ranking exactly — the same contract `route_options` gives its `store`."""
    gd = _gd()

    assert (combat_deficit(_state(), gd, "boar").chain[0].code
            == combat_deficit(_state(), gd, "boar", cost_of=None).chain[0].code
            == "steel_sword")


def test_each_step_records_what_it_cost() -> None:
    """The chain must be readable as a plan, not just a verdict: a four-step chain
    whose steps cost 20 and 400 cycles is a different decision from one whose
    steps all cost 20."""
    gd = _gd()

    step = combat_deficit(_state(), gd, "boar",
                          candidates=("steel_sword",),
                          cost_of=lambda code: 37.0).chain[0]

    assert step.acquire_cost == 37.0


def test_default_candidate_pool_excludes_gear_above_the_characters_level() -> None:
    """The pool is what the character could actually equip, not the whole catalog."""
    gd = _gd()
    gd._item_stats["mythic_blade"] = ItemStats(code="mythic_blade", level=40,
                                               type_="weapon", attack={"earth": 500})

    deficit = combat_deficit(_state(), gd, "boar")

    assert "mythic_blade" not in [s.code for s in deficit.chain]
