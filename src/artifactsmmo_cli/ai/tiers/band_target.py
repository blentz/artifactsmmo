"""The monster to farm: the best winnable NORMAL monster in the next uncleared
tier's band.

Replaces an unbounded argmax. `cheapest_path_to_level` filtered candidates with
`1 <= lvl <= sim_level + 1` — a floor of literally 1, dating to ed676b81
(2026-05-18) — and it is tier 2 of `GamePlayer._winnable_farm_target`, ranking
above the windowed picker at tier 3. So `combat_picker`'s correct
`[char_level - 1, char_level + 2]` window never got a vote and four of five live
characters were grinding 4 to 10 levels below themselves (2026-08-23).

No explicit level floor appears here, and none is wanted. The band IS the floor:
a tier's monsters sit between that rung and the next, so a target far below the
character cannot be drawn in the first place. A character whose LEVEL has
outrun its TIER — Robby at 30 with T20 uncleared — correctly keeps fighting the
tier it is stuck on; its constraint is gear, not target selection.

None means the band holds nothing winnable, which is a GEAR wall and must be
reported as such rather than papered over with a monster from a lower tier.
"""

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.tier_ladder import normal_band
from artifactsmmo_cli.ai.tiers.tier_progress import next_uncleared_tier
from artifactsmmo_cli.ai.world_state import WorldState


def band_combat_target(state: WorldState, game_data: GameData,
                       history: LearningStore | None) -> str | None:
    """Best winnable normal monster in the next uncleared tier's band, by XP."""
    tier = next_uncleared_tier(state, game_data, history)
    if tier is None:
        return None
    winnable = [code for code in normal_band(game_data, tier)
                if is_winnable(state, game_data, code, history)]
    if not winnable:
        return None
    return max(winnable, key=lambda code: (game_data.xp_per_kill(code, state.level),
                                           code))
