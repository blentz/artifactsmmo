"""A server rejection that is CATEGORICAL must poison the action, not be retried.

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
from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
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


def test_the_memo_poisons_an_action_repr_like_it_poisons_a_goal():
    """The memo is subject-agnostic: same mark/is_doomed contract, keyed on any
    repr. Reusing it is the point — a second implementation is what this fix
    exists to stop."""
    memo = DoomedMemo()
    state = make_state(level=20)

    assert memo.is_doomed("Recycle(water_boost_potion×1)", state, cycle=1) is False
    memo.mark("Recycle(water_boost_potion×1)", state, cycle=1)

    assert memo.is_doomed("Recycle(water_boost_potion×1)", state, cycle=2) is True
    assert memo.is_doomed("Recycle(copper_ring×1)", state, cycle=2) is False


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


def test_the_player_wires_its_planner_to_the_refusal_memo(bundle_game_data):
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

    key = rejection_key(refused)
    assert key is not None
    player._rejected_actions.mark(key, player.state, cycle=player._cycle_counter)

    assert player.planner._surviving_actions([refused]) == [], (
        "the player's planner must consult the live refusal memo")
    assert player.planner._surviving_actions(
        [RecycleAction(code="copper_ring", quantity=1)]) != [], (
        "poisoning one item must not disturb another")


def test_a_refused_action_is_offered_again_after_the_reprobe_window():
    """Poisoning is a re-probe, not a permanent ban — a misclassified code must
    self-heal rather than disable an action for the session."""
    player = GamePlayer(character="C3P0")
    player.state = make_state(level=20)
    player.game_data = _make_planner_gd()

    refused = RecycleAction(code="water_boost_potion", quantity=1)
    key = rejection_key(refused)
    assert key is not None
    player._rejected_actions.mark(key, player.state, cycle=1)

    assert player._rejected_actions.is_doomed(key, player.state, cycle=2) is True
    assert player._rejected_actions.is_doomed(key, player.state, cycle=500) is False


def test_a_quantity_two_recycle_is_also_dropped_by_a_quantity_one_refusal():
    """The trap `_build_actions`' existing filter warns about: the executed
    action and the factory-built one can differ in quantity. A quantity-keyed
    poison would silently match nothing."""
    player = GamePlayer(character="C3P0")
    player.state = make_state(level=20)
    player.game_data = _make_planner_gd()

    key = rejection_key(RecycleAction(code="fire_boost_potion", quantity=1))
    assert key is not None
    player._rejected_actions.mark(key, player.state, cycle=1)

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
    assert player._rejected_actions.is_doomed(key, player.state, 0) is False

    def _refuse(*_args: object, **_kwargs: object) -> WorldState:
        raise ApiActionError(473, "Invalid item for recycling")

    monkeypatch.setattr(RecycleAction, "execute", _refuse)
    monkeypatch.setattr(GamePlayer, "_fetch_world_state",
                        lambda self, client: self.state)

    _state, outcome = player._execute(action, client=None)

    assert outcome == "error:HTTP_473"
    assert player._rejected_actions.is_doomed(
        key, player.state, player._cycle_counter) is True


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

    assert player._rejected_actions.is_doomed(
        key, player.state, player._cycle_counter) is False


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

    _state, outcome = player._execute(action, client=None)

    assert outcome == "error:already_equipped"
    # Next cycle: the identical step is no longer offered to the search.
    assert player._is_categorically_refused(action) is True
    assert player.planner._surviving_actions([action]) == []


def test_a_485_poisons_the_code_in_every_slot_it_could_be_offered_for():
    """Lor's loop rotated the SLOT (artifact2, artifact3) across four goals
    while the code stayed the same. Poisoning is keyed on (action kind, code),
    so refusing one slot refuses them all — otherwise the loop just walks to the
    next empty sibling."""
    player = GamePlayer(character="Lor")
    player.state = make_state(level=20, inventory={"lich_race_medal": 1})

    refused = EquipAction(code="lich_race_medal", slot="artifact2_slot")
    key = rejection_key(refused)
    assert key is not None
    player._rejected_actions.mark(key, player.state, player._cycle_counter)

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
