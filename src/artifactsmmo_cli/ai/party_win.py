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

from dataclasses import replace
from itertools import combinations

from artifactsmmo_cli.ai.catalogue_scope import CatalogueScope
from artifactsmmo_cli.ai.combat import is_winnable, party_boss, party_member
from artifactsmmo_cli.ai.fight_walk import loadouts, wear
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.group_fight_core import PartyMember, group_outcome
from artifactsmmo_cli.ai.loadout_win import fight_key, stockable_potions, wins_with_a_loadout
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK
from artifactsmmo_cli.ai.world_state import WorldState

PARTY_MONSTER_TYPES = frozenset({"boss", "raid_boss"})
"""The monster types a party may fight (changelog 6.0.0)."""

MAX_JOINERS = 2
"""Characters that may join the leader's fight (`participants`, max 2)."""

_WINS: "CatalogueScope[tuple[object, ...], tuple[tuple[str, ...], tuple[int, ...]] | None]" = CatalogueScope(4096)


def member_card(state: WorldState, game_data: GameData, monster: str, codes: tuple[str, ...],
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
                  monster: str) -> tuple[tuple[str, ...], tuple[int, ...]] | None:
    """The first winning party: its potion loadout (`loadouts` order) and its
    joiners, as indices into `state.party` (one joiner before two, then in
    `combinations` order). None when none wins, the monster is no boss, or
    `party` is empty."""
    if not state.party or game_data.monsters.types.get(monster) not in PARTY_MONSTER_TYPES:
        return None
    members = (state, *state.party)
    stockable = [stockable_potions(m, game_data) for m in members]
    key = (monster, tuple((tuple(s), fight_key(m, game_data)) for m, s in zip(members, stockable,
                                                                                  strict=True)))
    memo = _WINS.cache_for(game_data)
    if key not in memo:
        _WINS.remember(memo, key, _first_win(state, game_data, monster, stockable))
    return memo[key]


def _first_win(state: WorldState, game_data: GameData, monster: str,
               stockable: list[list[str]]) -> tuple[tuple[str, ...], tuple[int, ...]] | None:
    boss = party_boss(game_data, monster)
    for codes in loadouts(stockable[0], game_data):
        cards = [member_card(m, game_data, monster, codes, s)
                 for m, s in zip((state, *state.party), stockable, strict=True)]
        for size in range(1, min(MAX_JOINERS, len(state.party)) + 1):
            for joined in combinations(range(len(state.party)), size):
                if group_outcome(boss, [cards[0], *(cards[j + 1] for j in joined)]).win:
                    return codes, joined
    return None


def wins_as_a_party(state: WorldState, game_data: GameData, monster: str) -> bool:
    """Some party of this character and one or two of `state.party`, in some
    stockable potion loadout, wins the boss fight."""
    return winning_party(state, game_data, monster) is not None


def party_participants(state: WorldState, game_data: GameData, monster: str) -> tuple[str, ...]:
    """The characters a fight against `monster` takes along: the first winning
    party's joiners by name when only a party wins it (the solo arms of the
    drop gate lose at full HP: bare stats and every stockable potion loadout,
    or the learned record refuses the solo fight, `WorldState.lost_fights`),
    else none — a fight one character wins is fought alone."""
    if not state.party or game_data.monsters.types.get(monster) not in PARTY_MONSTER_TYPES:
        return ()
    rested = replace(state, hp=state.max_hp)
    if monster not in state.lost_fights and (is_winnable(rested, game_data, monster)
                                             or wins_with_a_loadout(rested, game_data, monster)):
        return ()
    party = winning_party(rested, game_data, monster)
    return () if party is None else tuple(state.party[j].character for j in party[1])
