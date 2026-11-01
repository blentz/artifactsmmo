"""The fleet notices it is WEARING the trophy's price."""

from dataclasses import replace

from artifactsmmo_cli.ai.currency_turnin import TurnIn
from artifactsmmo_cli.ai.fleet_work import turn_in_due
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai.fixtures import coordination_now, make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data


def _player_with(tmp_path, name):
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character=name)
    player = GamePlayer(character=name)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player._coordination = store
    player.game_data = medal_game_data()
    return player, store


def _player_with_gd(tmp_path, name, game_data):
    """Like `_player_with`, but with a caller-supplied `game_data` — used by
    the second-dual-role-currency test, which needs a currency chain the
    shared `medal_game_data` fixture doesn't carry."""
    store = CoordinationStore(db_path=str(tmp_path / "coord.db"), character=name)
    player = GamePlayer(character=name)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player._coordination = store
    player.game_data = game_data
    return player, store


def _two_dual_role_currency_game_data():
    """`medal_game_data` plus a SECOND, independent dual-role currency chain
    (second_medal -> second_trophy, price 5, curator NPC) — residual 2's
    second-pass sibling-claim adoption needs two live dual-role currencies
    to be exercised at all."""
    gd = medal_game_data()
    gd._item_stats["second_medal"] = ItemStats(
        code="second_medal", level=5, type_="artifact")
    gd._item_stats["second_trophy"] = ItemStats(
        code="second_trophy", level=30, type_="artifact", hp_bonus=1)
    gd.world.npc_buy_currency["curator"] = {"second_trophy": "second_medal"}
    gd.world.npc_stock["curator"] = {"second_trophy": 5}
    return gd


class _NoHolderStore:
    """A coordination stub whose `claim_turn_in` fails for a reason OTHER
    than a live incumbent (an IntegrityError race or a swallowed
    SQLAlchemyError — see `CoordinationStore.claim_turn_in`'s docstring),
    so `turn_in_holder` genuinely reports nobody. Exercises the branch a
    real two-character race can't reliably reproduce in a fast test."""

    def sibling_holdings(self, now):
        return {}

    def claim_turn_in(self, item_code, now):
        return False

    def turn_in_holder(self, item_code, now):
        return None


def test_turn_in_resolves_when_the_fleet_wears_enough(tmp_path):
    player, _store = _player_with(tmp_path, "Robby")
    for sibling, worn in (("HAL", 3), ("R2D2", 3), ("C3P0", 2)):
        CoordinationStore(db_path=str(tmp_path / "coord.db"),
                          character=sibling).publish_holdings(
                              {"lich_race_medal": worn}, coordination_now())
    state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 1},
                       equipment={"artifact1_slot": "lich_race_medal"})

    player._resolve_turn_in(state, player.game_data)
    turn_in = player._turn_in

    assert turn_in is not None
    assert turn_in.item_code == "lich_race_trophy"
    assert turn_in.price == 10
    assert turn_in.currency == "lich_race_medal"
    assert turn_in.fleet_total == 10   # 1 worn + 8 sibling + 1 banked
    assert turn_in.buyer == "Robby"
    # The buyer has nothing to surrender to itself.
    assert player._recall is None


def test_no_turn_in_one_medal_short(tmp_path):
    player, _store = _player_with(tmp_path, "Robby")
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="HAL").publish_holdings({"lich_race_medal": 7}, coordination_now())
    state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 1},
                       equipment={"artifact1_slot": "lich_race_medal"})

    player._resolve_turn_in(state, player.game_data)

    assert player._turn_in is None
    assert player._recall is None


def test_a_character_below_the_item_level_does_not_claim_the_turn_in(tmp_path):
    """lich_race_trophy is level 20. A level-15 buyer would spend the fleet's
    medals on something it cannot wear.

    The level gate is an ELECTION gate only (fix-round-2), so this test pins
    what it still must forbid: with the fleet ready and NOBODY yet holding the
    claim, a level-15 character must not take the claim for itself. The store
    is re-read afterwards to prove that — asserting `_turn_in is None` alone
    would also pass for a character that claimed and then dropped the result."""
    player, store = _player_with(tmp_path, "HAL")
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="Robby").publish_holdings({"lich_race_medal": 9}, coordination_now())
    state = make_state(level=15, inventory={"lich_race_medal": 1})

    player._resolve_turn_in(state, player.game_data)

    assert player._turn_in is None
    # No sibling holds a claim either, so there is nothing to surrender toward.
    assert player._recall is None
    assert store.turn_in_holder("lich_race_trophy", coordination_now()) is None


def test_a_below_level_holder_surrenders_to_a_siblings_live_claim(tmp_path):
    """CRITICAL (fix-round-2): the level gate must not gate the RECALL path.

    Live fleet: the trophy is level 20 and only Robby (27) can wear it, but
    the two medals that exist are WORN by R2D2 (16) and HAL (15). While rules
    3/4 gated candidate-building itself, a below-level holder built no
    candidate at all, so it never consulted `turn_in_holder`, never set
    `_recall`, and never surrendered — Robby waited forever and the whole
    feature was inert on the only fleet it was built for.

    A character holding units of a currency surrenders them whenever a sibling
    holds a live claim on the item that currency buys, whatever its level."""
    db_path = str(tmp_path / "coord.db")
    for sibling, worn in (("R2D2", 1), ("HAL", 1), ("C3P0", 8)):
        CoordinationStore(db_path=db_path, character=sibling).publish_holdings(
            {"lich_race_medal": worn}, coordination_now())

    robby, _ = _player_with(tmp_path, "Robby")
    robby._resolve_turn_in(
        make_state(level=27, inventory={}, bank_items={}), robby.game_data)
    assert robby._turn_in is not None
    assert robby._turn_in.buyer == "Robby"

    hal, _ = _player_with(tmp_path, "HAL")
    hal_state = make_state(level=15, inventory={}, bank_items={},
                           equipment={"artifact1_slot": "lich_race_medal"})
    hal._resolve_turn_in(hal_state, hal.game_data)

    assert hal._turn_in is not None
    assert hal._turn_in.item_code == "lich_race_trophy"
    assert hal._turn_in.buyer == "Robby"
    assert hal._recall == ("lich_race_medal", 1)


def test_the_incumbent_buyer_never_recalls_its_own_holding_from_itself(tmp_path):
    """The recall path must check WHOSE claim it found. An incumbent buyer
    whose own election candidate lapses (here: rule 3 — its artifact slots
    filled with something better, so the trophy stopped being an upgrade)
    would otherwise read its OWN live claim as a sibling's and start banking
    the medals it is holding the claim in order to spend."""
    player, _store = _player_with(tmp_path, "Robby")
    gd = player.game_data
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="HAL").publish_holdings({"lich_race_medal": 9}, coordination_now())
    state = make_state(level=27, inventory={"lich_race_medal": 1})
    player._resolve_turn_in(state, gd)
    assert player._turn_in is not None and player._turn_in.buyer == "Robby"

    gd._item_stats["strong_relic"] = ItemStats(
        code="strong_relic", level=1, type_="artifact", hp_bonus=100)
    later = make_state(
        level=27, inventory={"lich_race_medal": 1},
        equipment={"artifact1_slot": "strong_relic", "artifact2_slot": "strong_relic",
                  "artifact3_slot": "strong_relic"})
    player._resolve_turn_in(later, gd)

    assert player._turn_in is None
    assert player._recall is None


def test_a_below_level_holder_stands_down_when_no_sibling_holds_a_claim(tmp_path):
    """The recall path is driven by a LIVE CLAIM, never by a local readiness
    guess: with the fleet ready but the election not yet resolved by anyone,
    a below-level holder must keep wearing its medal (wearing IS the fleet's
    storage — `dual_role_currency.py`) rather than pre-emptively banking it."""
    db_path = str(tmp_path / "coord.db")
    CoordinationStore(db_path=db_path, character="C3P0").publish_holdings(
        {"lich_race_medal": 9}, coordination_now())

    hal, _ = _player_with(tmp_path, "HAL")
    hal._resolve_turn_in(
        make_state(level=15, inventory={}, bank_items={},
                   equipment={"artifact1_slot": "lich_race_medal"}),
        hal.game_data)

    assert hal._turn_in is None
    assert hal._recall is None


def test_upgrade_gate_blocks_a_purchase_the_picker_would_not_wear(tmp_path):
    """Even a fully-affordable, level-appropriate trophy is not bought if the
    character's own artifact slots are already better-occupied — rule 3."""
    player, _store = _player_with(tmp_path, "Robby")
    gd = player.game_data
    gd._item_stats["strong_relic"] = ItemStats(
        code="strong_relic", level=1, type_="artifact", hp_bonus=100)
    state = make_state(
        level=27, inventory={"lich_race_medal": 10},
        equipment={"artifact1_slot": "strong_relic", "artifact2_slot": "strong_relic",
                  "artifact3_slot": "strong_relic"})

    player._resolve_turn_in(state, gd)

    assert player._turn_in is None
    assert player._recall is None


def test_no_coordination_store_is_inert(tmp_path):
    """The common case (single-character `play <name>`, no `--all`): no
    crash, no turn-in, no recall."""
    player = GamePlayer(character="Robby")
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    assert player._coordination is None
    gd = medal_game_data()
    state = make_state(level=27, inventory={"lich_race_medal": 20})

    player._resolve_turn_in(state, gd)

    assert player._turn_in is None
    assert player._recall is None


def test_a_losing_candidate_recalls_its_own_holdings_toward_the_winner(tmp_path):
    """Robby wins the claim using medals R2D2/C3P0/HAL published; when HAL
    later resolves for itself it must find Robby already holds the election
    and surrender exactly the medals the fleet needed from it."""
    db_path = str(tmp_path / "coord.db")
    for sibling, worn in (("R2D2", 3), ("C3P0", 3), ("HAL", 3)):
        CoordinationStore(db_path=db_path, character=sibling).publish_holdings(
            {"lich_race_medal": worn}, coordination_now())

    robby, _ = _player_with(tmp_path, "Robby")
    robby_state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 1})
    robby._resolve_turn_in(robby_state, robby.game_data)
    assert robby._turn_in is not None
    assert robby._turn_in.buyer == "Robby"

    hal, _ = _player_with(tmp_path, "HAL")
    hal_state = make_state(level=27, inventory={"lich_race_medal": 3},
                           bank_items={"lich_race_medal": 1})
    hal._resolve_turn_in(hal_state, hal.game_data)

    assert hal._turn_in is not None
    assert hal._turn_in.item_code == "lich_race_trophy"
    assert hal._turn_in.buyer == "Robby"
    assert hal._recall == ("lich_race_medal", 3)


def test_recall_surrenders_the_whole_holding_when_the_fleet_holds_a_surplus(tmp_path):
    """price=10, buyer wears 1 + banks 3, siblings wear 5/2/1 (fleet_total=12,
    surplus=2). A per-character shortfall quota (own - fleet-wide surplus)
    would let S2 and S3 surrender 0 — leaving the buyer stuck on 1+3+3=7 of
    10 forever while the fleet holds two MORE than it needs. Every losing
    candidate must instead surrender its FULL holding."""
    db_path = str(tmp_path / "coord.db")
    for character, worn in (("Robby", 1), ("S1", 5), ("S2", 2), ("S3", 1)):
        CoordinationStore(db_path=db_path, character=character).publish_holdings(
            {"lich_race_medal": worn}, coordination_now())

    robby, _ = _player_with(tmp_path, "Robby")
    robby_state = make_state(level=27, inventory={}, bank_items={"lich_race_medal": 3},
                             equipment={"artifact1_slot": "lich_race_medal"})
    robby._resolve_turn_in(robby_state, robby.game_data)
    assert robby._turn_in is not None
    assert robby._turn_in.buyer == "Robby"
    assert robby._turn_in.fleet_total == 12

    recalls: dict[str, int] = {}
    for sibling, worn in (("S1", 5), ("S2", 2), ("S3", 1)):
        player, _ = _player_with(tmp_path, sibling)
        state = make_state(level=27, inventory={"lich_race_medal": worn},
                           bank_items={"lich_race_medal": 3})
        player._resolve_turn_in(state, player.game_data)
        assert player._turn_in is not None
        assert player._turn_in.buyer == "Robby"
        assert player._recall == ("lich_race_medal", worn)
        recalls[sibling] = player._recall[1]

    assembled = 1 + 3 + sum(recalls.values())  # buyer's own worn + bank + every recall
    assert assembled >= 10


def test_a_second_dual_role_currency_still_recalls_behind_a_won_election(tmp_path):
    """RESIDUAL 2 (fix-round-3): `_adopt_sibling_claim` must run as a SECOND
    PASS for every currency this character did not just contest an election
    for — not only when the election phase produced no candidate at all.

    Robby wins the election for currency A (lich_race_medal) exactly as in
    `test_turn_in_resolves_when_the_fleet_wears_enough`. It ALSO holds 2
    units of a second, independent dual-role currency (second_medal) but is
    below `second_trophy`'s level-30 gate, so it never becomes a candidate
    for currency B — HAL (level 32) already won that election. Before the
    fix, `_adopt_sibling_claim` sat behind `if not candidates:`, and since
    Robby's currency-A candidacy made `candidates` non-empty, it never
    checked whether a sibling held a live claim on currency B — Robby would
    have kept wearing/carrying the second_medal units forever."""
    db_path = str(tmp_path / "coord.db")
    gd = _two_dual_role_currency_game_data()

    # Currency A ready for Robby, same shape as the single-currency test.
    for sibling, worn in (("HAL", 3), ("R2D2", 3), ("C3P0", 2)):
        CoordinationStore(db_path=db_path, character=sibling).publish_holdings(
            {"lich_race_medal": worn}, coordination_now())

    # Currency B: HAL (above the trophy's level gate) wins its election
    # first, funded by a third character's published units.
    CoordinationStore(db_path=db_path, character="Chewie").publish_holdings(
        {"second_medal": 5}, coordination_now())
    hal, _ = _player_with_gd(tmp_path, "HAL", gd)
    hal._resolve_turn_in(make_state(level=32, inventory={}, bank_items={}), gd)
    assert hal._turn_in is not None and hal._turn_in.buyer == "HAL"

    robby, _ = _player_with_gd(tmp_path, "Robby", gd)
    robby_state = make_state(
        level=27, inventory={"second_medal": 2}, bank_items={"lich_race_medal": 1},
        equipment={"artifact1_slot": "lich_race_medal"})

    robby._resolve_turn_in(robby_state, gd)

    assert robby._turn_in is not None
    assert robby._turn_in.item_code == "second_trophy"
    assert robby._turn_in.buyer == "HAL"
    assert robby._recall == ("second_medal", 2)


def test_a_failed_claim_without_a_live_holder_reports_no_turn_in(tmp_path):
    player, _ = _player_with(tmp_path, "Robby")
    player._coordination = _NoHolderStore()
    state = make_state(level=27, inventory={"lich_race_medal": 20})

    player._resolve_turn_in(state, player.game_data)

    assert player._turn_in is None
    assert player._recall is None


def test_a_shortfall_the_fleet_cannot_pay_names_its_elected_farmer(tmp_path):
    """The ticket farm (live 2026-10-31): Robby and C3P0 farmed the same
    fleet medal shortfall. The sibling holding the election farms it; this
    character is told so (a not-ready turn-in naming the farmer), asks no
    buy, and surrenders nothing."""
    player, _store = _player_with(tmp_path, "C3P0")
    robby = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Robby")
    robby.publish_holdings({"lich_race_medal": 5}, coordination_now())
    assert robby.claim_turn_in("lich_race_trophy", coordination_now())
    state = make_state(level=30, inventory={"lich_race_medal": 4})
    player._resolve_turn_in(state, player.game_data)
    assert player._turn_in is not None
    assert player._turn_in.buyer == "Robby" and not player._turn_in.ready
    assert player._turn_in.fleet_total == 9
    assert player._recall is None
    # nobody holds it: no stand-down
    robby.release_turn_in("lich_race_trophy")
    player._resolve_turn_in(state, player.game_data)
    assert player._turn_in is None


def test_the_running_farm_takes_the_election_for_the_shortfall(tmp_path):
    """`_claim_currency_farm`: the character whose cycle runs a dual-role
    currency's farm holds the election for the sink it farms for, while the
    fleet cannot yet pay; a farm for any other item, or a fleet that can pay,
    claims nothing."""
    player, store = _player_with(tmp_path, "Robby")
    now = coordination_now()
    short = make_state(level=30, inventory={"lich_race_medal": 4})
    player._claim_currency_farm(GatherMaterialsGoal("event_ticket", {"event_ticket": 1},
                                                    farmed_for="lich_race_medal"),
                                short, player.game_data)
    assert store.turn_in_holder("lich_race_trophy", now) is None
    assert store.turn_in_holder("lich_race_medal", now) is None
    paid = make_state(level=30, inventory={"lich_race_medal": 10})
    player._claim_currency_farm(GatherMaterialsGoal("lich_race_medal", {"lich_race_medal": 11},
                                                    farmed_for="lich_race_trophy"),
                                paid, player.game_data)
    assert store.turn_in_holder("lich_race_trophy", now) is None
    player._claim_currency_farm(GatherMaterialsGoal("lich_race_medal", {"lich_race_medal": 10},
                                                    farmed_for="lich_race_trophy"),
                                short, player.game_data)
    assert store.turn_in_holder("lich_race_trophy", now) == "Robby"
    # A sibling now stands down on it.
    sibling, _ = _player_with(tmp_path, "C3P0")
    sibling._resolve_turn_in(make_state(level=30), sibling.game_data)
    assert sibling._turn_in is not None and sibling._turn_in.buyer == "Robby"


def test_a_not_ready_claim_is_no_turn_in_due():
    """`turn_in_due` and the equip reservation read only a claim the fleet can
    pay: the farmer's claim asks no buy and reserves no medal from its slot."""
    short = TurnIn("lich_race_trophy", "archaeologist", 10, "lich_race_medal", "Robby", 9)
    ready = replace(short, fleet_total=10)
    assert not short.ready and ready.ready
    assert not turn_in_due(replace(NO_PROFILE_CONTEXT, turn_in=short))
    assert turn_in_due(replace(NO_PROFILE_CONTEXT, turn_in=ready))


def test_neither_this_character_s_own_claim_nor_a_payable_one_is_a_farm(tmp_path):
    """`_shortfall_farmer` reports only a SIBLING's claim the fleet cannot
    pay: this character's own farm claim is no stand-down, and a claim the
    fleet can pay is the purchase's (rules 1-5), never a farm."""
    player, store = _player_with(tmp_path, "Robby")
    assert store.claim_turn_in("lich_race_trophy", coordination_now())
    player._resolve_turn_in(make_state(level=30, inventory={"lich_race_medal": 4}),
                            player.game_data)
    assert player._turn_in is None
    # A below-level holder of nothing, the fleet able to pay: no farm reported.
    low, _ = _player_with(tmp_path, "R2D2")
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="HAL").publish_holdings({"lich_race_medal": 10},
                                                        coordination_now())
    low._resolve_turn_in(make_state(level=5), low.game_data)
    assert low._turn_in is None


def _medal_with_a_second_sink():
    """`medal_game_data` with a SECOND sink of the medal: the curator's
    banner, also 10 medals."""
    gd = medal_game_data()
    gd._item_stats["medal_banner"] = ItemStats(code="medal_banner", level=20, type_="artifact",
                                               hp_bonus=1)
    gd.world.npc_buy_currency["curator"] = {"medal_banner": "lich_race_medal"}
    gd.world.npc_stock["curator"] = {"medal_banner": 10}
    return gd


def test_a_farm_claims_only_the_sink_it_farms_for(tmp_path):
    """Review M3: a medal farm for the trophy holds the trophy's election
    only. The medal's other sink (the banner) stays open to a sibling."""
    player, store = _player_with_gd(tmp_path, "Robby", _medal_with_a_second_sink())
    now = coordination_now()
    player._claim_currency_farm(GatherMaterialsGoal("lich_race_medal", {"lich_race_medal": 10},
                                                    farmed_for="lich_race_trophy"),
                                make_state(level=30, inventory={"lich_race_medal": 4}),
                                player.game_data)
    assert store.turn_in_holder("lich_race_trophy", now) == "Robby"
    assert store.turn_in_holder("medal_banner", now) is None


def test_a_farmer_that_cannot_buy_lets_the_election_go_once_the_fleet_can_pay(tmp_path):
    """Review M4: HAL (level 15) farmed the shortfall and holds the trophy's
    election. Once the fleet holds the price, HAL fails the buyer's level
    gate (the trophy is level 20) and releases the claim the same cycle, so
    Robby, who can wear it, is elected at once instead of after `DEMAND_TTL`."""
    hal, store = _player_with(tmp_path, "HAL")
    now = coordination_now()
    assert store.claim_turn_in("lich_race_trophy", now)
    CoordinationStore(db_path=str(tmp_path / "coord.db"),
                      character="Robby").publish_holdings({"lich_race_medal": 9}, now)
    hal._resolve_turn_in(make_state(level=15, inventory={"lich_race_medal": 1}), hal.game_data)
    assert store.turn_in_holder("lich_race_trophy", now) is None
    robby, _ = _player_with(tmp_path, "Robby")
    robby._resolve_turn_in(make_state(level=27, inventory={"lich_race_medal": 9},
                                      equipment={"artifact1_slot": "lich_race_medal"}),
                           robby.game_data)
    assert robby._turn_in is not None and robby._turn_in.buyer == "Robby"


def test_equal_price_farms_go_to_the_shortfall_the_fleet_is_nearest_paying(tmp_path):
    """Review M2: two siblings farm two 10-unit sinks of two currencies. The
    one the fleet is nearer paying (6 of 10 over 2 of 10) is reported,
    whichever currency's name sorts first."""
    gd = _two_dual_role_currency_game_data()
    gd.world.npc_stock["curator"] = {"second_trophy": 10}
    player, _ = _player_with_gd(tmp_path, "C3P0", gd)
    now = coordination_now()
    hal = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="HAL")
    hal.publish_holdings({"lich_race_medal": 2, "second_medal": 6}, now)
    assert hal.claim_turn_in("lich_race_trophy", now)
    robby = CoordinationStore(db_path=str(tmp_path / "coord.db"), character="Robby")
    assert robby.claim_turn_in("second_trophy", now)
    player._resolve_turn_in(make_state(level=30), player.game_data)
    assert player._turn_in is not None
    assert (player._turn_in.item_code, player._turn_in.buyer) == ("second_trophy", "Robby")
