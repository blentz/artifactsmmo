"""Fight action for GOAP planning."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_fight_my_name_action_fight_post import sync as action_fight
from artifactsmmo_api_client.models.fight_request_schema import FightRequestSchema
from artifactsmmo_api_client.models.fight_result import FightResult

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.cost_core import learned_cost_pure
from artifactsmmo_cli.ai.actions.gather_apply_core import (
    GatherInv,
    apply_monster_drops_pure,
)
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.nearest_tile import nearest_or_error
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_MIN_FIGHT_HP_FRACTION = 0.3
"""Don't start a fight below this HP fraction — rest/heal first."""

LOADOUT_PENALTY = 5.0
"""Added to Fight cost when the loadout is suboptimal for the monster, so the
planner sequences OptimizeLoadout before the fight (player executes plan[0] only).
Must stay < one swap's cost (optimize_loadout.SWAP_COST_PER_SLOT * 2) so the
penalty orders swap-before-fight without making the swap itself non-favorable."""


@dataclass
class FightAction(Action):
    """Move to and fight a monster. Movement is folded into cost and execute."""

    tags: ClassVar[frozenset[str]] = frozenset({"combat", "produces_char_xp"})

    monster_code: str
    locations: frozenset[tuple[int, int]] = field(default_factory=frozenset, repr=False)

    _MIN_FREE_SLOTS = 1  # combat can drop loot; need at least 1 free capacity

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.locations or state.inventory_free < self._MIN_FREE_SLOTS:
            return False
        monster_level = game_data.monster_level(self.monster_code)
        if not (state.hp_percent > _MIN_FIGHT_HP_FRACTION and monster_level <= state.level + 2):
            return False
        # LOWER level gate: xp_per_kill > 0, NOT the old hard window
        # `monster_level >= max(1, level-1)`. The documented XP curve zeroes
        # out at char_level - monster_level >= 10, so a monster too far below
        # serves no leveling objective and is naturally excluded — while a
        # slightly-below monster stays fightable. The old window caused the P0
        # no-combat deadlock (2026-06-09): at level 4 the only stat-winnable
        # monsters (chicken L1, yellow_slime L2) were below max(1,4-1)=3, so
        # neither the picker nor this gate ever admitted a fight. The UPPER
        # bound (level+2 suicide guard) stays. Lean lockstep:
        # formal/Formal/ActionApplicability.lean (xpPositive gate).
        # Capability is decided upstream by is_winnable (predict_win); this gate
        # stays structural. The XP curve zeroes out at char_level - monster_level
        # >= 10, so xp_per_kill > 0 is the leveling-relevant lower bound. The old
        # `best_eq >= monster_level - 1` term conflated GEAR LEVEL with capability
        # and contradicted is_winnable (deadlock 2026-06-29: L3 char, level-1 gear,
        # winnable green_slime L4 rejected). Removed; suicide upper bound kept above.
        return game_data.xp_per_kill(self.monster_code, state.level) > 0

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = nearest_or_error(state.x, state.y, self.locations, "combat")
        estimated_hp_cost = max(1, state.max_hp // 5)
        new_hp = max(1, state.hp - estimated_hp_cost)
        new_progress = (
            state.task_progress + 1
            if state.task_type == "monsters" and state.task_code == self.monster_code
            else state.task_progress
        )
        # Model the loot: a kill yields the monster's drops, so the planner can
        # plan "fight chicken -> feather" for a GatherMaterials over a monster-drop
        # material. Without this, GatherMaterials(feather) was unplannable (the
        # fight made no progress toward the drop) and the bot fell to char-grind
        # forever (trace 2026-06-14 230824). One unit of each drop per kill
        # (optimistic; the per-cycle replan corrects for actual rates), capped at
        # inventory_max via the proved gather core so the planner never mints past
        # capacity. inventory is NOT a baseline-contract field (ApplyBaseline).
        inv = GatherInv(used=state.inventory_used, cap=state.inventory_max,
                        item_count=state.inventory)
        drops = tuple(d for d, _rate, _mn, _mx in game_data.monster_drops(self.monster_code))
        inv = apply_monster_drops_pure(inv, drops)
        return dataclasses.replace(
            state,
            xp=state.xp + 10,
            hp=new_hp,
            x=dest[0],
            y=dest[1],
            inventory=dict(inv.item_count),
            cooldown_expires=None,
            task_progress=new_progress,
            task_lifecycle_phase=derive_task_lifecycle_phase(
                state.task_code, new_progress, state.task_total
            ),
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = nearest_or_error(state.x, state.y, self.locations, "combat")
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        static = 10.0 + dist
        if history is None:
            base = learned_cost_pure(static, 0.0, 1.0, has_history=False)
        else:
            learned = history.action_cost(repr(self), default=static, window=50)
            rate = history.success_rate(repr(self), window=50)
            base = learned_cost_pure(static, learned, rate, has_history=True)
        # Per-slot comparison: pick_loadout returns every slot (including None
        # placeholders), state.equipment only carries filled slots. Direct
        # dict-equality always disagrees on shape. Match the per-slot pattern
        # used in GrindCharacterXPGoal._loadout_optimal and
        # OptimizeLoadoutAction._swap_plan.
        optimal = pick_loadout(
            Combat(game_data.monster_attack(self.monster_code),
                   game_data.monster_resistance(self.monster_code)),
            state, game_data,
        )
        if any(state.equipment.get(slot) != code for slot, code in optimal.items()):
            base += LOADOUT_PENALTY
        return base

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = nearest_or_error(state.x, state.y, self.locations, "combat")
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_fight(client=client, name=state.character, body=FightRequestSchema())
        result = Action._raise_for_error(result, f"Fight {self.monster_code}")
        new_state = WorldState.from_character_schema(
            result.data.characters[0],
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )
        # Detect defeat: API returns 200 OK on loss; result.data.fight.result == LOSS.
        # Raise so the player loop records outcome=error:fight_lost and learning
        # doesn't fold near-death zero-XP cycles into action_cost/success_rate.
        if result.data.fight.result == FightResult.LOSS:
            raise RuntimeError(f"fight_lost: {self.monster_code} (turns={result.data.fight.turns})")
        return new_state

    def __repr__(self) -> str:
        return f"Fight({self.monster_code})"
