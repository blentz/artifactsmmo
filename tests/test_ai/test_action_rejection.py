"""A server rejection that is CATEGORICAL must become a model fact, not be retried.

Live 2026-08-23: C3P0 sent `Recycle(water_boost_potion x1)` 37 times over eight
hours, every one answered HTTP 473 "Invalid item for recycling". The recycle
model admits anything with a craft recipe whose skill gate is met, and
`water_boost_potion` has one (alchemy 10, and C3P0 is alchemy 13) — but the
server only recycles EQUIPMENT. Nothing carried the refusal back into the model,
so the identical impossible call was re-issued every few minutes against the
per-IP rate budget that binds the whole fleet.
"""

from artifactsmmo_cli.ai.action_rejection import (
    CATEGORICAL_REJECTIONS,
    is_categorical_rejection,
    rejection_key,
)
from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.refusal_fact_core import refusal_holds
from artifactsmmo_cli.ai.refusal_facts import RefusalFacts
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_intention_store import _break_engine
from tests.test_ai.test_strategy_driver import _make_planner_gd


def test_invalid_item_for_recycling_is_categorical():
    """473 says the item is not eligible for the action. No state change fixes
    that — a potion is never recyclable."""
    assert is_categorical_rejection(473) is True


def test_cooldown_is_not_categorical():
    """499 is the most common rejection in the log and is pure timing."""
    assert is_categorical_rejection(499) is False


def test_contingent_state_rejections_are_not_categorical():
    """Each of these is answered by the state changing, so poisoning the action
    would suppress work the bot must still do."""
    for code in (497, 492, 471, 478, 483, 486, 461, 436):
        assert is_categorical_rejection(code) is False, code


def test_unknown_codes_default_to_contingent():
    """A code nobody classified must stay retried. Defaulting the other way
    would silently disable actions on a rejection we do not understand."""
    assert is_categorical_rejection(599) is False


def test_already_equipped_is_categorical():
    """485 says the planner's per-code OCCUPANCY model disagrees with the
    server. Retrying cannot fix a wrong model — live 2026-08-22, Lor sent the
    same `Equip(lich_race_medal -> artifact2/3_slot)` 55 times in 50 minutes."""
    assert is_categorical_rejection(485) is True


def test_the_categorical_set_is_about_item_eligibility():
    """Every member says 'this action cannot succeed for this item' — six as a
    pure game-data fact, plus 485, which says our occupancy model is wrong (see
    the set's docstring for why that belongs and how it heals)."""
    assert frozenset({472, 473, 476, 485, 437, 441, 442}) == CATEGORICAL_REJECTIONS


def test_a_game_data_refusal_holds_until_the_item_is_redefined():
    """Phase 5-1: "not recyclable" is a fact about the item. It holds at any
    loadout, and only a change of the item's game-data type (a season reset
    redefining it) voids it."""
    assert refusal_holds(473, "utility", "utility", worn=False) is True
    assert refusal_holds(473, "utility", "utility", worn=True) is True
    assert refusal_holds(473, "utility", "ring", worn=False) is False


def test_already_equipped_holds_exactly_while_the_code_is_worn():
    """485 is a fact about the worn loadout, not the item: unequip the worn copy
    and the same equip succeeds."""
    assert refusal_holds(485, "artifact", "artifact", worn=True) is True
    assert refusal_holds(485, "artifact", "artifact", worn=False) is False


# ---------------------------------------------------------------------------
# The poison key must be QUANTITY-FREE.
#
# `_build_actions`' existing backoff filter carries a warning: it matches on
# `learning_key()` because the factory builds unsized actions (`Gather(x×1)`)
# while blocks are recorded from goal-sized ones (`Gather(x×47)`), so a repr
# match "would silently match nothing". Recycle has the same exposure — the log
# holds both `Recycle(water_boost_potion×1)` and `Recycle(fire_boost_potion×2)`.
#
# A categorical rejection is about the ITEM and the ACTION KIND. "water_boost_
# potion is not recyclable" holds at every quantity, so keying on quantity is
# both wrong and the way to walk into that trap.
# ---------------------------------------------------------------------------


def test_the_rejection_key_ignores_quantity():
    one = RecycleAction(code="water_boost_potion", quantity=1)
    two = RecycleAction(code="water_boost_potion", quantity=2)

    assert rejection_key(one) == rejection_key(two)
    assert rejection_key(one) is not None


def test_the_rejection_key_separates_action_kinds_on_the_same_item():
    """Being un-recyclable says nothing about being un-equippable."""
    recycle = RecycleAction(code="water_boost_potion", quantity=1)
    delete = DeleteItemAction(code="water_boost_potion", quantity=1)

    assert rejection_key(recycle) != rejection_key(delete)


def test_an_action_with_no_item_has_no_rejection_key():
    """Every categorical rejection is an item-eligibility fact, so an action
    carrying no item cannot be poisoned by one."""
    assert rejection_key(RestAction()) is None


# ---------------------------------------------------------------------------
# End to end: the loop must actually stop.
#
# The two pure pieces above can both be correct while the wiring does nothing —
# that is exactly how the original bug survived. These pin the two seams:
# the mark side (a categorical refusal is recorded) and the consult side
# (`_build_actions` stops offering the action).
# ---------------------------------------------------------------------------


def test_the_player_wires_its_planner_to_the_refusal_facts(bundle_game_data):
    """The WIRING. `set_refusal_filter` is only useful if the player actually
    calls it, and the predicate it passes must read the live memo.

    An earlier version of this test asserted on `_build_actions`' output. That
    filter has since been removed: a goal may SYNTHESISE actions rather than
    select from that pool (`RecycleSurplusGoal` does), so filtering the pool
    missed the very action that caused this — the fleet restarted onto that
    version at 12:43Z 2026-08-23 and C3P0 resumed within seconds.
    """
    player = GamePlayer(character="C3P0")
    player.game_data = bundle_game_data
    player.state = make_state(level=20, inventory={"water_boost_potion": 3},
                              skills={"alchemy": 13})

    refused = RecycleAction(code="water_boost_potion", quantity=1)
    survivors = player.planner._surviving_actions([refused])
    assert survivors == [refused], "precondition: not refused yet"

    assert player._refusals.record(refused, 473, player.game_data) is not None

    assert player.planner._surviving_actions([refused]) == [], (
        "the player's planner must consult the live refusal facts")
    assert player.planner._surviving_actions(
        [RecycleAction(code="copper_ring", quantity=1)]) != [], (
        "poisoning one item must not disturb another")


def test_a_refusal_is_shared_by_the_fleet_and_survives_a_restart(tmp_path):
    """Phase 5-1: recorded once, in the learning DB, without a character — a
    sibling (or the same character after a restart) loads it and never
    re-sends the refused call."""
    gd = _make_planner_gd()
    gd._item_stats["water_boost_potion"] = ItemStats(
        code="water_boost_potion", level=1, type_="utility")
    db = str(tmp_path / "refusals.db")
    refused = RecycleAction(code="water_boost_potion", quantity=1)
    first = RefusalFacts(LearningStore(db, character="C3P0"))
    first.record(refused, 473, gd)
    first.record(refused, 473, gd)  # a re-refusal keeps one fact
    sibling = RefusalFacts(LearningStore(db, character="R2D2"))
    sibling.load()
    assert sibling.refused(refused, make_state(level=20), gd) is True
    # A season reset that redefines the item voids the fact.
    gd._item_stats["water_boost_potion"] = ItemStats(
        code="water_boost_potion", level=1, type_="ring")
    assert sibling.refused(refused, make_state(level=20), gd) is False


def test_no_store_keeps_facts_in_memory_only():
    facts = RefusalFacts(None)
    facts.load()
    refused = RecycleAction(code="water_boost_potion", quantity=1)
    assert facts.record(refused, 473, _make_planner_gd()) is not None
    assert facts.refused(refused, make_state(), _make_planner_gd()) is True
    assert facts.record(RestAction(), 473, _make_planner_gd()) is None
    assert facts.refused(RestAction(), make_state(), _make_planner_gd()) is False


def test_a_quantity_two_recycle_is_also_dropped_by_a_quantity_one_refusal():
    """The trap `_build_actions`' existing filter warns about: the executed
    action and the factory-built one can differ in quantity. A quantity-keyed
    poison would silently match nothing."""
    player = GamePlayer(character="C3P0")
    player.state = make_state(level=20)
    player.game_data = _make_planner_gd()

    player._refusals.record(RecycleAction(code="fire_boost_potion", quantity=1), 473,
                            player.game_data)

    assert player._is_categorically_refused(
        RecycleAction(code="fire_boost_potion", quantity=2)) is True


def test_a_473_from_the_server_poisons_the_action(monkeypatch, bundle_game_data):
    """The RECORD seam. Drives a real 473 through `_execute` and asserts the
    memo was marked — the consult side is worthless if nothing ever marks.

    Covers the categorical branch in `player.py`, which the coverage gate
    flagged as unexecuted even while every consult-side test was green.
    """
    player = GamePlayer(character="C3P0")
    player.game_data = bundle_game_data
    player.state = make_state(level=20, inventory={"water_boost_potion": 3},
                              skills={"alchemy": 13})

    action = RecycleAction(code="water_boost_potion", quantity=1)
    key = rejection_key(action)
    assert key is not None
    assert player._is_categorically_refused(action) is False

    def _refuse(*_args: object, **_kwargs: object) -> WorldState:
        raise ApiActionError(473, "Invalid item for recycling")

    monkeypatch.setattr(RecycleAction, "execute", _refuse)
    monkeypatch.setattr(GamePlayer, "_fetch_world_state",
                        lambda self, client: self.state)

    _state, outcome, _executed = player._execute(action, client=None)

    assert outcome == "error:HTTP_473"
    assert player._is_categorically_refused(action) is True


def test_a_cooldown_does_not_poison_the_action(monkeypatch, bundle_game_data):
    """The classifier's default direction, at the seam: a contingent rejection
    must leave the action available, or the bot disables its own work."""
    player = GamePlayer(character="C3P0")
    player.game_data = bundle_game_data
    player.state = make_state(level=20, inventory={"water_boost_potion": 3},
                              skills={"alchemy": 13})

    action = RecycleAction(code="water_boost_potion", quantity=1)
    key = rejection_key(action)
    assert key is not None

    def _cooldown(*_args: object, **_kwargs: object) -> WorldState:
        raise ApiActionError(499, "Character is on cooldown")

    monkeypatch.setattr(RecycleAction, "execute", _cooldown)
    monkeypatch.setattr(GamePlayer, "_fetch_world_state",
                        lambda self, client: self.state)

    player._execute(action, client=None)

    assert player._is_categorically_refused(action) is False


def test_a_485_from_the_server_poisons_the_equip(monkeypatch, bundle_game_data):
    """THE LOR LIVELOCK, bounded. 485 has its OWN branch in `_execute`, ahead of
    the `else` the poisoning used to live in, so before this fix a 485 could
    never be classified however categorical it was.

    Asserts BOTH halves: the outcome label is unchanged (`error:already_equipped`
    — the branch still completes an ordinary failed cycle, which is what the
    2026-06-10 comment asked for) AND the action is poisoned, so the planner's
    refusal filter drops it on the NEXT cycle instead of re-deriving it."""
    player = GamePlayer(character="Lor")
    player.game_data = bundle_game_data
    player.state = make_state(
        level=20, inventory={"lich_race_medal": 1},
        equipment={**make_state().equipment, "artifact1_slot": "lich_race_medal"})

    action = EquipAction(code="lich_race_medal", slot="artifact2_slot")
    key = rejection_key(action)
    assert key is not None
    assert player._is_categorically_refused(action) is False

    def _refuse(*_args: object, **_kwargs: object) -> WorldState:
        raise ApiActionError(485, "This item is already equipped")

    monkeypatch.setattr(EquipAction, "execute", _refuse)
    monkeypatch.setattr(GamePlayer, "_fetch_world_state",
                        lambda self, client: self.state)

    _state, outcome, _executed = player._execute(action, client=None)

    assert outcome == "error:already_equipped"
    # Next cycle: the identical step is no longer offered to the search.
    assert player._is_categorically_refused(action) is True
    assert player.planner._surviving_actions([action]) == []
    # Unequip the worn copy and the equip is offered again (Phase 5-1).
    player.state = make_state(level=20, inventory={"lich_race_medal": 2})
    assert player._is_categorically_refused(action) is False


def test_a_485_poisons_the_code_in_every_slot_it_could_be_offered_for():
    """Lor's loop rotated the SLOT (artifact2, artifact3) across four goals
    while the code stayed the same. Poisoning is keyed on (action kind, code),
    so refusing one slot refuses them all — otherwise the loop just walks to the
    next empty sibling."""
    player = GamePlayer(character="Lor")
    player.game_data = _make_planner_gd()
    player.state = make_state(
        level=20, inventory={"lich_race_medal": 1},
        equipment={**make_state().equipment, "artifact1_slot": "lich_race_medal"})

    refused = EquipAction(code="lich_race_medal", slot="artifact2_slot")
    assert player._refusals.record(refused, 485, player.game_data) is not None

    assert player._is_categorically_refused(
        EquipAction(code="lich_race_medal", slot="artifact3_slot")) is True
    # ...and spares a different code entirely.
    assert player._is_categorically_refused(
        EquipAction(code="copper_ring", slot="ring2_slot")) is False


def test_the_refusal_predicate_is_safe_before_the_world_is_sensed():
    """The planner holds this predicate from construction, before `plan_once`
    or `run` has fetched any state. "Not sensed yet" must answer False, not
    raise — an exception here would fire inside a per-action hot path on the
    very first search."""
    player = GamePlayer(character="C3P0")
    assert player.state is None

    assert player._is_categorically_refused(
        RecycleAction(code="water_boost_potion", quantity=1)) is False
    assert player.planner._surviving_actions(
        [RecycleAction(code="water_boost_potion", quantity=1)]) != []


def test_a_db_error_on_a_refusal_fact_is_reported_or_reads_as_empty(tmp_path, capsys):
    store = LearningStore(str(tmp_path / "broken.db"), character="C3P0")
    _break_engine(store)
    store.save_refusal_fact("RecycleAction", "water_boost_potion", 473, "utility")
    assert "save_refusal_fact failed" in capsys.readouterr().out
    assert store.load_refusal_facts() == []
