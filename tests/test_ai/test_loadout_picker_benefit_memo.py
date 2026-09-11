"""`loadout_picker`'s cross-call `(purpose, code) -> benefit` memo, and the one
way it can be wrong.

The memo turns `_benefit(stats, purpose)` from a per-call answer into a
per-CATALOGUE one, which is the whole point: `combat_deficit`'s greedy chain
probes every candidate gear swap against the same monster, so it varies the
INVENTORY while holding the purpose fixed, and `pick_loadout_cached` cannot
absorb that (its key includes the inventory, so every probe is an honest miss
there while the per-item scores underneath are identical).

THE FAILURE MODE IS A KEY THAT DOES NOT NAME THE CATALOGUE. Two item catalogues
routinely carry the SAME CODE with DIFFERENT STATS — the committed bundle and
any test fixture both have an `iron_boots` — so a process-wide `(purpose, code)`
memo serves one catalogue's number for another's item. This module asserts the
INVARIANT rather than hunting for a collision: ask two catalogues that disagree
about one code and require two different answers. Both tests below FAIL (the
second pick comes back equal to the first) if the memo is keyed on
`(purpose, code)` alone, and the second also fails if it is keyed on
`(purpose, code)` per GameData WITHOUT the stored-`ItemStats` identity check.
"""

import dataclasses

import pytest

from artifactsmmo_cli.ai.equipment import loadout_picker
from artifactsmmo_cli.ai.equipment.loadout_picker import (
    _BENEFIT_MEMO,
    BENEFIT_MEMO_MAX_ENTRIES,
    pick_loadout,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather, Rank, purpose_key
from tests.test_ai.fixtures import make_state

_PURPOSE = Combat(monster_attack={"fire": 100}, monster_resistance={}, player_attack={})
"""A monster that hits for fire and resists nothing, so `armor_score`'s defense
term (Σ mon_atk · res) is the only term that can separate the two catalogues'
`iron_boots` — and the offense term is 0 for both (no player attack)."""

_STRONG = ItemStats(code="iron_boots", level=1, type_="boots",
                    resistance={"fire": 50})
"""Worth equipping against `_PURPOSE`: 50% fire resistance against a 100-fire
monster is a strictly positive benefit, so the empty-slot gate lets it in."""

_WORTHLESS = ItemStats(code="iron_boots", level=1, type_="boots")
"""The SAME CODE with no stats at all: benefit exactly 0, which the empty-slot
gate (`best_score <= 0`) refuses to fill a bare slot with. Same code, opposite
verdict — that is what makes it a catalogue-collision probe."""


def _catalogue(stats: ItemStats) -> GameData:
    game_data = GameData()
    game_data._item_stats = {stats.code: stats}
    return game_data


def _holding_boots() -> object:
    return make_state(level=5, inventory={"iron_boots": 1})


@pytest.fixture(autouse=True)
def _isolated_memo() -> None:
    """Every test here reasons about what the memo holds, so it starts empty.

    Production never needs this — a catalogue's entries die with the catalogue —
    but tests run in one process and a leftover entry would make a miss look like
    a hit (or the reverse)."""
    _BENEFIT_MEMO.clear()


def test_two_catalogues_disagreeing_about_one_code_get_two_answers() -> None:
    """THE INVARIANT. `iron_boots` is worth equipping in one catalogue and not in
    the other, and asking the first must not answer for the second.

    Keyed on `(purpose, code)` process-wide this fails: the second pick reads the
    first catalogue's benefit for `iron_boots` and equips a worthless item."""
    state = _holding_boots()

    strong = pick_loadout(_PURPOSE, state, _catalogue(_STRONG))
    worthless = pick_loadout(_PURPOSE, state, _catalogue(_WORTHLESS))

    assert strong["boots_slot"] == "iron_boots"
    assert worthless["boots_slot"] is None

    # ...and in the other order, so neither catalogue is merely winning by being
    # asked first.
    _BENEFIT_MEMO.clear()
    worthless_first = pick_loadout(_PURPOSE, state, _catalogue(_WORTHLESS))
    strong_second = pick_loadout(_PURPOSE, state, _catalogue(_STRONG))
    assert worthless_first["boots_slot"] is None
    assert strong_second["boots_slot"] == "iron_boots"


def test_swapping_a_catalogue_under_one_gamedata_is_not_a_hit() -> None:
    """A per-GameData scope is NOT sufficient on its own.

    ~30 fixtures in this suite rebind `gd._item_stats = {...}` on a GameData they
    have already used, and the live loader rebuilds a catalogue in place too. The
    scope key does not change when that happens — the GameData object is the same
    one — so a `(purpose, code)` entry inside the scope would still be served. The
    stored `ItemStats` identity check is what turns it into a miss: the swapped
    catalogue hands back a DIFFERENT object for the same code."""
    game_data = _catalogue(_STRONG)
    assert pick_loadout(_PURPOSE, _holding_boots(), game_data)["boots_slot"] == "iron_boots"

    game_data._item_stats = {"iron_boots": _WORTHLESS}
    assert pick_loadout(_PURPOSE, _holding_boots(), game_data)["boots_slot"] is None


def test_the_memo_actually_serves_across_calls() -> None:
    """The positive control: without it every test above would pass on a memo
    that never hits, and the whole change would be inert.

    Two picks over the SAME catalogue and purpose with DIFFERENT inventories —
    exactly the shape `combat_deficit`'s candidate probe generates, and exactly
    what `pick_loadout_cached` must miss on. The second pick must not re-score
    `iron_boots`."""
    game_data = _catalogue(_STRONG)
    game_data._item_stats["copper_ring"] = ItemStats(
        code="copper_ring", level=1, type_="ring", resistance={"fire": 5})

    scored: list[str] = []
    real_benefit = loadout_picker._benefit

    def _counting(stats: ItemStats, purpose: object) -> int:
        scored.append(stats.code)
        return real_benefit(stats, purpose)

    loadout_picker._benefit = _counting
    try:
        pick_loadout(_PURPOSE, make_state(level=5, inventory={"iron_boots": 1}), game_data)
        assert scored == ["iron_boots"]
        pick_loadout(_PURPOSE, make_state(
            level=5, inventory={"iron_boots": 1, "copper_ring": 1}), game_data)
    finally:
        loadout_picker._benefit = real_benefit

    # The ring is new and gets scored (twice: ring1_slot and ring2_slot share a
    # code, and the second slot's candidate is the same object, so it hits).
    assert scored == ["iron_boots", "copper_ring"]


def test_the_rank_class_and_a_rank_instance_key_the_same() -> None:
    """`gear_value` accepts the bare `Rank` CLASS as well as an instance
    (`purpose is Rank or isinstance(purpose, Rank)`) and live callers use both —
    `tiers/equip_value` passes the class, `empty_slot_fills` an instance. The
    memo normalizes the class to its field-less instance, so the two share
    entries instead of the class raising out of `purpose_key`."""
    game_data = _catalogue(_STRONG)
    state = _holding_boots()

    by_class = pick_loadout(Rank, state, game_data)
    by_instance = pick_loadout(Rank(), state, game_data)
    assert by_class == by_instance

    keys = list(_BENEFIT_MEMO.cache_for(game_data))
    assert keys == [(purpose_key(Rank()), "iron_boots")], keys


def test_the_bound_evicts_the_oldest_entry() -> None:
    """The bound is real, not decorative: the live bot's purposes churn with
    every monster the planner considers, for the life of the process. Eviction is
    in INSERTION order (`_benefit_of` deliberately skips `move_to_end`), so the
    first purpose asked is the first retired."""
    assert BENEFIT_MEMO_MAX_ENTRIES > 0
    game_data = _catalogue(_STRONG)
    cache = _BENEFIT_MEMO.cache_for(game_data)
    _BENEFIT_MEMO.max_entries = 2
    try:
        for skill in ("mining", "woodcutting", "fishing"):
            pick_loadout(Gather(skill), _holding_boots(), game_data)
    finally:
        _BENEFIT_MEMO.max_entries = BENEFIT_MEMO_MAX_ENTRIES
    assert len(cache) == 2
    assert (purpose_key(Gather("mining")), "iron_boots") not in cache


def test_an_unknown_purpose_is_refused_rather_than_merged() -> None:
    """`purpose_key` is the memo's injectivity guarantee. A purpose outside the
    closed set has no key, and inventing one ("other") would merge two unrelated
    purposes into one entry."""
    with pytest.raises(TypeError, match="purpose"):
        pick_loadout("not a purpose", _holding_boots(), _catalogue(_STRONG))


def test_the_key_names_every_field_of_every_purpose() -> None:
    """A field added to `Combat` or `Gather` without being added to `purpose_key`
    is a memo that serves one purpose's answer for another. Asserted against the
    dataclasses themselves so the failure lands on the day the field is added."""
    combat = Combat(monster_attack={"fire": 1}, monster_resistance={"water": 2},
                    player_attack={"earth": 3})
    for field in dataclasses.fields(Combat):
        other = dataclasses.replace(combat, **{field.name: {"air": 99}})
        assert purpose_key(other) != purpose_key(combat), field.name
    for field in dataclasses.fields(Gather):
        assert field.name == "skill"
    assert purpose_key(Gather("mining")) != purpose_key(Gather("fishing"))
    assert not dataclasses.fields(Rank)
