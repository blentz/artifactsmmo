"""ReachCurrencyGoal: complete tasks until a currency (e.g. tasks_coin) reaches
a target, to fund a task-currency purchase (jasper_crystal @ tasks_trader).

max_depth is bounded by funding_cycles_pure (proved sufficient in
Formal.Liveness.CurrencyFunding.fundingCycles_sufficient), so the GOAP search has
enough depth to assemble the accept→progress→complete loop without the budget
timeout that pegged the planner before this capability existed."""

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

ACTIONS_PER_CYCLE = 3
"""Planning nodes per funding cycle: AcceptTask + one progress action
(Fight/Craft) + CompleteTask. This is EXACT for the planning `apply` model, not
optimistic: movement is FOLDED INTO each action's `apply` (AcceptTaskAction.apply
sets x,y directly — no separate MoveAction node), and the in-model `task_total`
is 1 so a SINGLE progress action satisfies CompleteTaskAction's
`task_progress >= task_total` gate. If either assumption ever changes — movement
de-folded into its own planning node, or in-model `task_total` raised above 1, or
a Craft-based task needing intermediate craft nodes — the real per-cycle node
count exceeds 3 and `max_depth` UNDER-provisions, silently reintroducing the
planner timeout this goal exists to prevent. Re-derive this constant if so."""
PRIORITY_WHEN_NEEDED = 1.0  # placeholder ranking; demand routing is C4
PRIORITY_WHEN_NEEDED = 1.0  # placeholder ranking; demand routing is C4


class ReachCurrencyGoal(Goal):
    """Drive the task loop until `currency` count reaches `target`."""

    def __init__(self, currency: str, target: int) -> None:
        self._currency = currency
        self._target = target

    def _on_hand(self, state: WorldState) -> int:
        bank = state.bank_items or {}
        return state.inventory.get(self._currency, 0) + bank.get(self._currency, 0)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return PRIORITY_WHEN_NEEDED

    def is_satisfied(self, state: WorldState) -> bool:
        return self._on_hand(state) >= self._target

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": {self._currency: self._target}}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Accept/Complete/Fight only. The in-model pending task is
        monsters-typed (AcceptTaskAction.apply), so a CraftAction can never
        progress it — keeping the ~320 crafts only flooded the h=0 search
        (live 2026-07-06: 24K nodes / 10s cheap-pass timeout with crafts;
        milliseconds without). Execution replans against the server's REAL
        task each cycle, so an items task is worked by the task machinery,
        not by this in-model projection.

        Task 6c: every admitted FightAction also gets a companion swap
        (self-guarding OptimizeLoadoutAction) so a suboptimal equipped
        weapon can't stall the loop with no way to fix it (Task 6b
        regression, mirrored here). Deduped by monster_code — this goal is
        search-flood sensitive, so one swap per distinct monster, not one
        per fight."""
        fight_actions = [a for a in actions if isinstance(a, FightAction)]
        seen_monsters: set[str] = set()
        swap_actions: list[Action] = []
        for fight in fight_actions:
            if fight.monster_code in seen_monsters:
                continue
            seen_monsters.add(fight.monster_code)
            swap_actions.append(OptimizeLoadoutAction(
                target_monster_code=fight.monster_code, game_data=game_data))
        return [a for a in actions
                if isinstance(a, (AcceptTaskAction, CompleteTaskAction))
                ] + fight_actions + swap_actions

    @property
    def max_depth(self) -> int:
        """Conservative WORST CASE: on_hand=0 and the minimum possible floor=1 give
        the MOST cycles (== target), so this depth is always enough for any
        actual on_hand>=0 / floor>=1 (Formal...fundingCycles_sufficient). `max_depth`
        is a PROPERTY (Goal.max_depth) — no state/gd available, hence the static
        worst case. funding_cycles_pure is the LIVE proved-core caller."""
        cycles = funding_cycles_pure(0, self._target, 1)
        return max(ACTIONS_PER_CYCLE, cycles * ACTIONS_PER_CYCLE)

    def __repr__(self) -> str:
        return f"ReachCurrency({self._currency}, {self._target})"
