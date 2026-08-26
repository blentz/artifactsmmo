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

from artifactsmmo_cli.ai.combat_deficit import (
    combat_deficit,
    deficit_upgrade_target,
    has_combat_deficit,
)
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

    deficit = combat_deficit(_state(), gd, "boar", actions_of=lambda code, slot: cost.get(code))

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
                             actions_of=lambda code, slot: cost.get(code))

    assert [s.code for s in deficit.chain] == ["steel_sword"]


def test_a_zero_cost_candidate_cannot_divide_by_zero() -> None:
    """An item already owned is priced 0 by the acquisition model. It cannot
    improve the margin (`pick_loadout` would already be wearing it), but the
    ranking must not be able to blow up if one ever is."""
    gd = _gd()

    deficit = combat_deficit(_state(), gd, "boar", actions_of=lambda code, slot: 0)

    assert deficit.closes is True


def test_without_a_cost_the_ranking_is_unchanged() -> None:
    """`actions_of` defaults to None so every existing caller keeps raw-margin
    ranking exactly — the same contract `route_options` gives its `store`."""
    gd = _gd()

    assert (combat_deficit(_state(), gd, "boar").chain[0].code
            == combat_deficit(_state(), gd, "boar", actions_of=None).chain[0].code
            == "steel_sword")


def test_each_step_records_what_it_cost() -> None:
    """The chain must be readable as a plan, not just a verdict: a four-step chain
    whose steps cost 20 and 400 cycles is a different decision from one whose
    steps all cost 20."""
    gd = _gd()

    step = combat_deficit(_state(), gd, "boar",
                          candidates=("steel_sword",),
                          actions_of=lambda code, slot: 37).chain[0]

    assert step.acquire_cost == 37.0


def test_has_combat_deficit_is_the_cheap_boolean_form() -> None:
    """The LATCH needs "is there a deficit", not "what closes it".

    `deficit_upgrade_target` walks every candidate; this is one `predict_win`.
    It runs every cycle in `GearLatch.update`, so the walk would be the wrong
    thing to put there.
    """
    gd = _gd()

    assert has_combat_deficit(_task_state(), gd) is True
    assert has_combat_deficit(_task_state(inventory={"steel_sword": 1}), gd) is False


def test_has_combat_deficit_agrees_with_the_full_walk() -> None:
    """The cheap form and the expensive one must never disagree about EXISTENCE,
    or the latch would arm for a deficit the gear chain then cannot name."""
    gd = _gd()
    for state in (_task_state(), _task_state(inventory={"steel_sword": 1})):
        assert has_combat_deficit(state, gd) is (
            combat_deficit(state, gd, "boar") is not None)


def test_has_combat_deficit_is_false_without_a_workable_monsters_task() -> None:
    gd = _gd()

    assert has_combat_deficit(_task_state(task_type="items"), gd) is False
    assert has_combat_deficit(_task_state(task_code=None, task_type=None), gd) is False
    assert has_combat_deficit(_task_state(task_progress=104), gd) is False


# ---------------------------------------------------------------------------
# `deficit_upgrade_target` — the missing causal link, "lose fight -> upgrade gear".
#
# `map_guard`'s GEAR_REVIEW branch picks what to build with a monster-BLIND
# `_best_by_value` scan. Live, that chose `iron_boots` — already worn, and absent
# from all 24 items that improved the pig margin — while the weapon that actually
# moved `rounds_to_kill` went unbuilt for ten hours. The latch knew a fight had
# been lost; nothing carried WHICH fight into the gear decision.
# ---------------------------------------------------------------------------


def _task_state(**over):  # type: ignore[no-untyped-def]
    base = dict(level=1, hp=100, max_hp=100, equipment={}, inventory={},
                task_code="boar", task_type="monsters", task_total=104,
                task_progress=0)
    base.update(over)
    return make_state(**base)


def test_target_is_the_deficits_first_step_against_the_task_monster() -> None:
    """The gear we build is the gear that closes the fight we are blocked on."""
    target = deficit_upgrade_target(_task_state(), _gd())

    assert target == ("steel_sword", "weapon_slot")


def test_no_target_when_the_task_monster_is_already_winnable() -> None:
    """Nothing to fix — the generic value scan should decide instead."""
    assert deficit_upgrade_target(_task_state(inventory={"steel_sword": 1}),
                                  _gd()) is None


def test_no_target_without_a_monsters_task() -> None:
    """An items task, or none at all, leaves the gear choice to the value scan.

    Scoped to the held task deliberately: after the tier-1 bypass closed, the
    monster we last LOST to is no longer the farm target, so "last loss" is a
    stale signal. The task is the thing we are actually blocked on, and working
    toward being able to fight it is how S-052 is honoured by a character that
    cannot fight it yet.
    """
    assert deficit_upgrade_target(_task_state(task_type="items"), _gd()) is None
    assert deficit_upgrade_target(_task_state(task_code=None, task_type=None),
                                  _gd()) is None


def test_no_target_for_a_finished_task() -> None:
    assert deficit_upgrade_target(_task_state(task_progress=104), _gd()) is None


def test_no_target_when_no_gear_closes_the_gap() -> None:
    """`closes=False` with an empty chain must not yield a phantom target."""
    assert deficit_upgrade_target(_task_state(), _gd(),
                                  candidates=("cloth_cap",)) is None


def test_no_target_for_a_chain_that_improves_the_margin_but_never_closes() -> None:
    """The gap the empty-chain check could not see: a NON-empty futile chain.

    `bronze_sword` alone moves the boar margin -101 -> -2 and then nothing else
    is on offer, so the walk names a chain and `closes` stays False. The old
    guard read `deficit.chain` and committed to it — "build this, it wins the
    fight" about an item that demonstrably does not. Live on the scenario corpus
    that was 648 of 895 losing (character, monster) pairs, and its most visible
    instance was a level-47 character being sent to craft a level-25
    `emerald_amulet` for +1 of a needed +6.

    The chain itself is still TRUE and still reported — `combat_deficit` names
    it, and the `combat-deficit` diagnostic prints it as DOES NOT CLOSE. What is
    withdrawn is only the guard's claim that building it wins this fight; a None
    here sends `strategy_driver`'s GEAR_REVIEW branch to the generic value scan,
    which still buys gear.
    """
    deficit = combat_deficit(_task_state(), _gd(), "boar",
                             candidates=("bronze_sword",))

    assert deficit is not None
    assert [s.code for s in deficit.chain] == ["bronze_sword"]
    assert deficit.chain[0].margin_after == -2
    assert deficit.closes is False

    assert deficit_upgrade_target(_task_state(), _gd(),
                                  candidates=("bronze_sword",)) is None


def test_a_target_is_returned_when_a_MULTI_step_chain_closes_the_gap() -> None:
    """Honouring `closes` must not shrink to "one item wins or nothing".

    `bronze_sword` alone reaches -2 and `hide_vest` alone is useless without a
    weapon; together they reach +1. The old `max_chain=1` call could not see
    that pair at all, so this fight read as unclosable — and if `closes` had
    been honoured at depth 1 it would have gone from a futile target to no
    target. It gets the first step of a chain that really does close instead.
    """
    target = deficit_upgrade_target(_task_state(), _gd(),
                                    candidates=("bronze_sword", "hide_vest"))

    assert target == ("bronze_sword", "weapon_slot")


def test_the_target_does_not_move_when_the_walk_is_given_more_depth() -> None:
    """Depth buys `closes`, never the ANSWER.

    The walk is greedy and prefix-stable: the chain at depth k is the first k
    steps of the chain at depth 8, so raising the bound cannot change which item
    the guard is sent to build. Measured over all 895 losing (scenario, monster)
    pairs on the committed bundle, `chain[0]` differed between `max_chain=1` and
    `max_chain=8` in exactly 0 of them. Pinned here on the fixture so a future
    non-greedy or lookahead ranking cannot quietly acquire that freedom.
    """
    gd = _gd()
    state = _task_state()
    deep = combat_deficit(state, gd, "boar",
                          candidates=("bronze_sword", "hide_vest"))
    shallow = combat_deficit(state, gd, "boar", max_chain=1,
                             candidates=("bronze_sword", "hide_vest"))

    assert deep is not None and shallow is not None
    assert deep.closes is True
    assert shallow.closes is False
    assert [s.code for s in deep.chain] == ["bronze_sword", "hide_vest"]
    assert deep.chain[0].code == shallow.chain[0].code


def test_the_target_is_PRICED_when_a_cost_is_supplied() -> None:
    """The guard must chase the same item the `combat-deficit` oracle reports.

    Unpriced, the walk ranks on RAW margin and takes the biggest jump regardless
    of reach — live that was `king_slime_sword`, gated behind a `jasper_crystal`
    C3P0 has no route to. Priced, it takes a cheap partial gain and actually
    gets there.
    """
    gd = _gd()
    cost = {"steel_sword": 400.0, "bronze_sword": 20.0}

    assert deficit_upgrade_target(_task_state(), gd) == ("steel_sword", "weapon_slot")
    assert deficit_upgrade_target(_task_state(), gd, actions_of=lambda code, slot: cost.get(code)) == (
        "bronze_sword", "weapon_slot")


def test_the_target_slot_matches_the_items_type() -> None:
    """Body armour must not be handed to the weapon slot — the guard equips into
    exactly the slot this returns."""
    target = deficit_upgrade_target(_task_state(inventory={"bronze_sword": 1}),
                                    _gd(), candidates=("hide_vest",))

    assert target == ("hide_vest", "body_armor_slot")


def test_default_candidate_pool_excludes_gear_above_the_characters_level() -> None:
    """The pool is what the character could actually equip, not the whole catalog."""
    gd = _gd()
    gd._item_stats["mythic_blade"] = ItemStats(code="mythic_blade", level=40,
                                               type_="weapon", attack={"earth": 500})

    deficit = combat_deficit(_state(), gd, "boar")

    assert "mythic_blade" not in [s.code for s in deficit.chain]
