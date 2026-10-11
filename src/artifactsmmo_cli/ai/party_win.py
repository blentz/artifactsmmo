"""Does a party of this character and one or two of `state.party` win a boss
fight? The drop route's WINNABLE gate's party arm (docs/PLAN_group_fights.md
increment 2).

The server lets up to two other characters of the account join a fight
against a `boss` or `raid_boss` (`participants`, changelog 6.0.0). Each set of
one or two of `state.party` is tried with each utility-potion loadout the
character can stock (`loadout_win.stockable_potions`, `fight_walk.loadouts`,
as the solo arm): every member wears that loadout when it can stock it too,
else none, and starts at full HP. `group_fight_core.group_outcome` decides —
the proved party walk (`Formal.GroupFight`), in which a dead member leaves and
the rest fight on (live probe 2026-10-11).

The verdict is memoized per catalogue (`CatalogueScope`) on exactly what the
walk reads: the monster, and for every member its stockable potions and its
fight fields (`loadout_win.fight_key`)."""

from itertools import combinations

from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.combat import party_boss, party_member
from artifactsmmo_cli.ai.fight_walk import loadouts, wear
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.group_fight_core import PartyMember, group_outcome
from artifactsmmo_cli.ai.loadout_win import fight_key, stockable_potions
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.world_state import WorldState

PARTY_MONSTER_TYPES = frozenset({"boss", "raid_boss"})
"""The monster types a party may fight (changelog 6.0.0)."""

MAX_JOINERS = 2
"""Characters that may join the leader's fight (`participants`, max 2)."""

_WINS: "CatalogueScope[tuple[object, ...], tuple[tuple[str, ...], int] | None]" = CatalogueScope(4096)


def _member(state: WorldState, game_data: GameData, monster: str, codes: tuple[str, ...],
            stockable: list[str]) -> PartyMember:
    """`state` at full HP wearing `codes` when it can stock them all, else
    no potions."""
    worn = codes if all(code in stockable for code in codes) else ()
    projected, _code, restore, stock = wear(
        state, game_data, [(code, UTILITY_SLOT_MAX_STACK) for code in worn])
    member = party_member(projected, game_data, monster, restore, stock)
    return PartyMember(member.raw, member.net, member.hit, member.area, member.max_hp,
                       member.max_hp, member.first, member.threat, member.restore, member.stock)


def winning_party(state: WorldState, game_data: GameData,
                  monster: str) -> tuple[tuple[str, ...], int] | None:
    """The first winning party: its potion loadout (`loadouts` order) and how
    many of `state.party` join it (one before two). None when none wins, the
    monster is no boss, or `party` is empty."""
    if not state.party or game_data.monsters.types.get(monster) not in PARTY_MONSTER_TYPES:
        return None
    members = (state, *state.party)
    stockable = [stockable_potions(m, game_data) for m in members]
    key = (monster, tuple((tuple(s), fight_key(m, game_data)) for m, s in zip(members, stockable,
                                                                                  strict=True)))
    memo = _WINS.cache_for(game_data)
    if key not in memo:
        boss = party_boss(game_data, monster)
        found: tuple[tuple[str, ...], int] | None = None
        for codes in loadouts(stockable[0], game_data):
            cards = [_member(m, game_data, monster, codes, s)
                     for m, s in zip(members, stockable, strict=True)]
            for size in range(1, min(MAX_JOINERS, len(state.party)) + 1):
                if any(group_outcome(boss, [cards[0], *joined]).win
                       for joined in combinations(cards[1:], size)):
                    found = (codes, size)
                    break
            if found is not None:
                break
        _WINS.remember(memo, key, found)
    return memo[key]


def wins_as_a_party(state: WorldState, game_data: GameData, monster: str) -> bool:
    """Some party of this character and one or two of `state.party`, in some
    stockable potion loadout, wins the boss fight."""
    return winning_party(state, game_data, monster) is not None
