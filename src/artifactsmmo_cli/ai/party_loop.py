"""The XP rate of farming a boss as a party (docs/PLAN_group_fights.md
increment 3; USER 2026-10-10: "use groups for boss xp, too. XP velocity matters
for leaderboard placement").

ONE LOOP is `loop_rate`'s: a fight from full HP, this character's recovery back
to full, and the price of what it drank — with the fight walked by
`group_fight_core.group_outcome` for the character and one or two of
`state.party` (`party_win`'s parties: each member wears the loadout when it can
stock it, else none). Two terms differ from a solo loop:

* XP — the server bases a party's XP on the group's AVERAGE level, floored
  (changelog 6.0.0; docs/PLAN_group_fights.md rule 3), with each character's
  own wisdom: `xp_per_kill(monster, average, wisdom)`.
* THE FIGHT'S SECONDS — `SECONDS_PER_TURN` per actor turn, `rounds × (N + 1)`
  turns for N members. The solo loop prices every fight at one typical
  cooldown, but a party fight against a boss runs many times longer: the
  probes' cooldowns were 29 s for 16 turns, 32 s for 17 and 45 s for 24 —
  2 s a turn less the leader's haste, which this leaves uncredited
  (conservative), and the full party's turns count after a member dies.

The rate is this character's own XP per second; what pulling the joiners off
their own work costs them is the coordination's question (increment 4)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from artifactsmmo_cli.ai.best_loadout import units_used
from artifactsmmo_cli.ai.best_loadout_core import pick_best
from artifactsmmo_cli.ai.combat import party_boss
from artifactsmmo_cli.ai.fight_terms_core import SCALE
from artifactsmmo_cli.ai.fight_walk import loadouts
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.group_fight_core import PartyMember, group_outcome
from artifactsmmo_cli.ai.held_stock import held_count
from artifactsmmo_cli.ai.loadout_win import stockable_potions
from artifactsmmo_cli.ai.loop_rate import EAT_SECONDS, FoodOffer, LoopRate
from artifactsmmo_cli.ai.loop_rate_core import consumed_seconds, recovery_choice, xp_per_second
from artifactsmmo_cli.ai.party_win import MAX_JOINERS, member_card, party_drinks
from artifactsmmo_cli.ai.world_state import WorldState

PARTY_XP_TYPES = frozenset({"boss"})
"""The monsters a party farms for XP: a raid boss pays through the raid
reward system instead (docs/PLAN_group_fights.md rule 2)."""

SECONDS_PER_TURN = 2
"""A fight's cooldown per actor turn, haste uncredited (see the module doc)."""


@dataclass(frozen=True)
class PartyLoop:
    """The best party loop against one boss: the loadout every member wears,
    the joiners (indices into `state.party`) and the loop."""

    loadout: tuple[str, ...]
    joiners: tuple[int, ...]
    rate: LoopRate


def _loop(state: WorldState, game_data: GameData, monster: str, codes: tuple[str, ...],
          joined: tuple[int, ...], cards: list[PartyMember], food: Sequence[FoodOffer],
          prices: Mapping[str, Fraction | None]) -> LoopRate | None:
    """One party's loop (see the module doc); None when it loses, pays no XP
(the boss grey to the party's average level), or a drink past the held units
has no replacement."""
    levels = [state.level, *(state.party[j].level for j in joined)]
    xp = game_data.xp_per_kill(monster, sum(levels) // len(levels), state.wisdom)
    if xp <= 0:
        return None
    outcome = group_outcome(party_boss(game_data, monster), [cards[0], *(cards[j + 1] for j in joined)])
    if not outcome.win:
        return None
    used = party_drinks(codes, outcome.used[0], game_data)
    consumed = consumed_seconds([(n, prices[code], held_count(code, state)) for code, n in used])
    if consumed is None:
        return None
    me = cards[0]
    hp_end = outcome.hp_end[0] // SCALE
    recovery, counts = recovery_choice(me.max_hp - hp_end, me.max_hp,
                                       [(f.restore, f.price, f.held) for f in food], EAT_SECONDS)
    eaten = tuple((f.code, k) for f, k in zip(food, counts, strict=True) if k > 0)
    fight = Fraction(SECONDS_PER_TURN * outcome.turns * (len(levels) + 1))
    # A party loop counts no bank trips (spec 2026-10-18 §2.10 covers the solo
    # loop): it always runs.
    return LoopRate(xp_per_second(xp, fight, recovery, consumed), xp, True, Fraction(1), fight, recovery,
                    consumed, me.max_hp, hp_end, used, eaten, True)


def best_party_loop(state: WorldState, game_data: GameData, monster: str,
                    prices: Mapping[str, Fraction | None],
                    food: Sequence[FoodOffer]) -> PartyLoop | None:
    """The party loop with the most XP per second against `monster` (fewer
    consumables, then the earlier loadout and party, on a tie); None with no
    `party`, against no `boss`, or when no party wins. `prices` are this
    character's candidate potions (`best_loadout.candidate_potions`)."""
    if not state.party or game_data.monsters.types.get(monster) not in PARTY_XP_TYPES:
        return None
    stockable = [list(prices), *(stockable_potions(m, game_data) for m in state.party)]
    found: list[tuple[tuple[str, ...], tuple[int, ...], LoopRate]] = []
    for codes in loadouts(list(prices), game_data):
        cards = [member_card(m, game_data, monster, codes, s)
                 for m, s in zip((state, *state.party), stockable, strict=True)]
        for size in range(1, min(MAX_JOINERS, len(state.party)) + 1):
            for joined in combinations(range(len(state.party)), size):
                rate = _loop(state, game_data, monster, codes, joined, cards, food, prices)
                if rate is not None:
                    found.append((codes, joined, rate))
    index = pick_best([(rate.xp_per_second, units_used(rate)) for _, _, rate in found])
    if index is None:
        return None
    codes, joined, rate = found[index]
    return PartyLoop(codes, joined, rate)
