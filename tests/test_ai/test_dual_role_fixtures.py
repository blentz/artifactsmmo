"""Game data for the lich-race currency chain, shared by the turn-in tests."""
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats


def medal_game_data() -> GameData:
    """A minimal GameData carrying the live lich-race chain: the medal is a
    wearable artifact AND the archaeologist's price for the trophy, so it is
    the dual-role case this module exists to recognise. `event_ticket` is
    spendable but not wearable (currency type); `novice_guide` is wearable
    but nothing takes it as payment — both are the negative cases."""
    gd = GameData()
    gd._item_stats = {
        "lich_race_medal": ItemStats(code="lich_race_medal", level=10, type_="artifact"),
        # hp_bonus=1 (not 0): Task 5's upgrade gate (`_resolve_turn_in` rule
        # 3) checks pick_loadout would actually WEAR the item — an
        # all-zero-stat artifact scores 0 benefit and the picker never fills
        # an empty slot with a zero-benefit candidate (`loadout_picker`'s
        # empty-slot gate), so a real reward artifact needs a genuine,
        # if minimal, stat to be a legitimate upgrade candidate in tests.
        "lich_race_trophy": ItemStats(code="lich_race_trophy", level=20, type_="artifact",
                                      hp_bonus=1),
        "novice_guide": ItemStats(code="novice_guide", level=10, type_="artifact"),
        "event_ticket": ItemStats(code="event_ticket", level=1, type_="currency"),
    }
    gd.world.npc_buy_currency = {
        "archaeologist": {"lich_race_medal": "event_ticket",
                          "lich_race_trophy": "lich_race_medal"},
    }
    gd.world.npc_stock = {
        "archaeologist": {"lich_race_medal": 100, "lich_race_trophy": 10},
    }
    return gd
