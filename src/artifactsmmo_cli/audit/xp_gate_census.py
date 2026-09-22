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

THE UNIT IS THE MONSTER, NOT THE STEP, and getting that wrong inverts the
headline. `combat_deficit` sets `closes=True` only after the LAST appended step
wins the fight (`combat_deficit.py:295-342`), so EVERY step in the chain is
required — a monster needing jewelrycrafting +5 AND weaponcrafting +10 costs
+10, not +5. An earlier version of this census emitted one row per step and
sorted on the step's own gap; the +5 step then represented that monster near the
top of a list a reader treats as a priority order, and the report's `[:20]`
truncation could drop the step that actually binds. So a monster's real cost is
the MAX gap over its chain, the step carrying it is named `binding`, and the
per-step detail rides along underneath rather than competing with it.

WHAT THE NAMED GATE IS NOT. `combat_deficit` is called here with no `actions_of`,
so its greedy walk ranks candidates on RAW MARGIN GAIN. Per
`combat_deficit.py:270-276` only the PRICED ranking makes "lowest skill
requirement" and "cheapest unlock" coincide, because `acquisition_cost` prices a
skill gate as `unlock_actions` cycles. Unpriced, this census reports the chain
that closes the fight fastest in margin terms, which is not necessarily the
chain production would pursue. It is a measurement of where the walls are, not a
plan for opening them.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.combat_deficit import combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class GatedStep:
    """One chain step this character cannot yet craft, and the gate in front of it."""

    blocking_item: str
    item_type: str
    skill: str
    required_level: int
    held_level: int

    @property
    def gap(self) -> int:
        """Skill levels between what the character holds and what this step's
        gate asks. NOT the monster's cost on its own — see `GatedSource.gap`."""
        return self.required_level - self.held_level


@dataclass(frozen=True)
class GatedSource:
    """One unreachable character-XP source and every skill gate standing in it."""

    monster: str
    monster_level: int
    steps: tuple[GatedStep, ...]

    @property
    def gap(self) -> int:
        """The monster's REAL cost: the largest gap over its chain.

        Every step in a closing chain is required, so the fight opens only once
        the deepest gate does. The census orders on this — the nearest gate is
        the cheapest fight to unlock, and a shallower non-binding step must not
        be allowed to speak for the monster."""
        return max(step.gap for step in self.steps)

    @property
    def binding(self) -> GatedStep:
        """The step whose gap the monster's cost is. Ties break on the item code
        so the choice is semantic-stable rather than list-order dependent."""
        return max(self.steps, key=lambda s: (s.gap, s.blocking_item))


def gated_xp_sources(state: WorldState, game_data: GameData) -> list[GatedSource]:
    """Every monster this character cannot beat, with every crafting gate its
    closing chain stands behind, nearest binding gate first.

    A monster with no deficit is not returned: it is already a live XP source.
    A deficit whose `closes` is False is not returned either — nothing in the
    catalogue closes that fight, so it is a drop or spawn wall, not a skill gate,
    and naming it here would put an unopenable gate in a list of openable ones.
    A chain step with no crafting gate, or one whose level the character already
    holds, is not a wall and is skipped; a monster left with no gated step at all
    produces no row.

    A step's `code` can be appended TWICE by one chain (`combat_deficit.py:326`
    increments the projected inventory without removing the code from the pool),
    which is one gate observed twice, not two gates. Steps are deduplicated on
    `code` so a repeat cannot double-count or displace a distinct gate.
    """
    rows: list[GatedSource] = []
    for monster, monster_level in game_data.monster_levels.items():
        deficit = combat_deficit(state, game_data, monster)
        if deficit is None or not deficit.closes:
            continue
        steps: dict[str, GatedStep] = {}
        for step in deficit.chain:
            if step.crafting_skill is None:
                continue
            # `state.skills` is built by `world_state._require(...)` for every
            # trainable skill, so a missing key is missing API data, not a
            # level-0 character. Indexing rather than defaulting is the repo
            # rule (CLAUDE.md: use only API data or fail with an error) — a
            # silent 0 would INFLATE the gap and rank a phantom wall first.
            held = state.skills[step.crafting_skill]
            if held >= step.crafting_level:
                continue
            steps.setdefault(step.code, GatedStep(
                blocking_item=step.code,
                item_type=step.item_type,
                skill=step.crafting_skill,
                required_level=step.crafting_level,
                held_level=held,
            ))
        if not steps:
            continue
        rows.append(GatedSource(monster=monster, monster_level=monster_level,
                                steps=tuple(steps.values())))
    rows.sort(key=lambda s: (s.gap, s.monster))
    return rows
