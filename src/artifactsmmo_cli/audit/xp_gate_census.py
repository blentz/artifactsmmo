"""Which character-XP sources are unreachable, and which skill level gates each.

Character XP is the primary currency and fights are its source, but a fight the
character cannot win pays nothing. Closing that fight needs gear, and the gear
needs a crafting skill level — the secondary currency T1 has to price. This
census names that chain for every monster the character cannot beat.

It reads `combat_deficit`, which already computes the chain WITH its gate:
`DeficitStep` carries `crafting_skill` and `crafting_level` because "the gear
layer is not the bottom of the chain" (C3P0 could not craft `iron_sword` at
weaponcrafting 6 however many `iron_bar` it held). Re-deriving recipes here
would be a second implementation of a question production already answers, and
the two would drift.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.combat_deficit import combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class GatedSource:
    """One unreachable character-XP source and the skill level that gates it."""

    monster: str
    monster_level: int
    blocking_item: str
    item_type: str
    skill: str
    required_level: int
    held_level: int

    @property
    def gap(self) -> int:
        """Skill levels between what the character holds and what the gate asks.
        The census orders on this: the nearest gate is the cheapest to open."""
        return self.required_level - self.held_level


def gated_xp_sources(state: WorldState, game_data: GameData) -> list[GatedSource]:
    """Every monster this character cannot beat, with the crafting skill and level
    gating each chain step it cannot yet make, nearest gate first.

    A monster with no deficit is not returned: it is already a live XP source.
    A deficit whose `closes` is False is not returned either — nothing in the
    catalogue closes that fight, so it is a drop or spawn wall, not a skill gate,
    and naming it here would put an unopenable gate in a list of openable ones.
    A chain step with no crafting gate, or one whose level the character already
    holds, is not a wall and is skipped.
    """
    rows: list[GatedSource] = []
    for monster, monster_level in game_data.monster_levels.items():
        deficit = combat_deficit(state, game_data, monster)
        if deficit is None or not deficit.closes:
            continue
        for step in deficit.chain:
            if step.crafting_skill is None:
                continue
            held = state.skills.get(step.crafting_skill, 0)
            if held >= step.crafting_level:
                continue
            rows.append(GatedSource(
                monster=monster,
                monster_level=monster_level,
                blocking_item=step.code,
                item_type=step.item_type,
                skill=step.crafting_skill,
                required_level=step.crafting_level,
                held_level=held,
            ))
    rows.sort(key=lambda s: (s.gap, s.monster, s.blocking_item))
    return rows
