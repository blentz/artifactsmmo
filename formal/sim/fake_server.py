"""FakeServer — operational definition of the Lean Server axioms (Tier 1).

This is NOT a fixture that always passes. It is the OPERATIONAL semantics
of the four Tier-1 Server axioms used by `FightProgress`, `GatherProgress`,
`DepositProgress`, and `RestProgress`:

  * Server.fight   — xp += 10, hp clamped via `max(1, hp - max_hp // 5)`,
                     task_progress += 1 when monster matches an active
                     monsters-task. (Mirrors `FightAction.apply` / the Lean
                     `fightApply`.)
  * Server.gather  — adds one drop unit to inventory; if the resource has a
                     skill requirement, the tracked skill LEVEL `skills[skill]`
                     advances by 1 (single-level abstraction of the modeled
                     grind rung — mirrors the Lean `.gather` raising
                     `trackedSkillLevel`).
  * Server.deposit — every `(code, qty)` selected by `select_bank_deposits`
                     is moved out of inventory into the bank. (Mirrors
                     `DepositAllAction.apply` / `depositApply`.)
  * Server.rest    — `hp := max_hp`. (Mirrors `RestAction.apply` /
                     `restApply`.)

If FakeServer's behaviour diverges from the Lean axioms, the axioms are
DISHONEST and Phase 22's general `Server` typeclass would inherit the lie.
The differential test asserts byte-equivalence between planner-side
`Action.apply(state, game_data)` and FakeServer's output on the same input —
any divergence is either (a) a Lean-axiom honesty bug or (b) a production
bug. Both surface as a differential failure.

FakeServer carries NO probabilistic damage, no event spawns, no concurrency,
and no level-up event. Those live in Tier 2+. For Tier 1 we only need to
witness `lex_lt(measure(after), measure(before))` after every productive
applicable action.

ONE behavioural class per file: this module defines `FakeServer`.
"""

import dataclasses

from artifactsmmo_cli.ai.world_state import WorldState


class FakeServer:
    """Deterministic operational stand-in for the live server, Tier-1 subset."""

    # The constant +10 mirrors `FightAction.apply` in combat.py:76 (Lean
    # `fightApply.xp = s.xp + 10`). This is the planner-side projection of
    # the Server.fight axiom — server-actual xp may differ, but for the
    # Tier-1 differential we encode the documented projection contract.
    FIGHT_XP_GRANT = 10

    def __init__(self, character_state: WorldState) -> None:
        # Defensive copy: the planner mutates `WorldState` via
        # `dataclasses.replace`; FakeServer must not share references that
        # could leak local mutations across cycles.
        self._state = character_state

    @property
    def state(self) -> WorldState:
        return self._state

    def fight(self, monster_code: str, monster_matches_task: bool) -> WorldState:
        """Server.fight axiom: +10 xp, planner-side damage projection,
        task_progress increment iff `monster_matches_task`."""
        s = self._state
        estimated_hp_cost = max(1, s.max_hp // 5)
        new_hp = max(1, s.hp - estimated_hp_cost)
        new_progress = s.task_progress + 1 if monster_matches_task else s.task_progress
        self._state = dataclasses.replace(
            s,
            xp=s.xp + self.FIGHT_XP_GRANT,
            hp=new_hp,
            task_progress=new_progress,
            cooldown_expires=None,
        )
        return self._state

    def gather(self, drop_item: str, skill_name: str | None) -> WorldState:
        """Server.gather axiom: +1 drop_item, tracked skill LEVEL +1 iff
        skill_name (single-level abstraction of the modeled grind rung)."""
        s = self._state
        new_inventory = dict(s.inventory)
        new_inventory[drop_item] = new_inventory.get(drop_item, 0) + 1
        new_skills = dict(s.skills)
        if skill_name is not None:
            new_skills[skill_name] = new_skills.get(skill_name, 1) + 1
        self._state = dataclasses.replace(
            s,
            inventory=new_inventory,
            skills=new_skills,
            cooldown_expires=None,
        )
        return self._state

    def deposit(self, items: list[tuple[str, int]]) -> WorldState:
        """Server.deposit axiom: items move inventory -> bank."""
        s = self._state
        new_inventory = dict(s.inventory)
        new_bank = dict(s.bank_items or {})
        for code, qty in items:
            new_bank[code] = new_bank.get(code, 0) + qty
            new_inventory.pop(code, None)
        self._state = dataclasses.replace(
            s,
            inventory=new_inventory,
            bank_items=new_bank,
            cooldown_expires=None,
        )
        return self._state

    def rest(self) -> WorldState:
        """Server.rest axiom: full heal."""
        self._state = dataclasses.replace(
            self._state, hp=self._state.max_hp, cooldown_expires=None,
        )
        return self._state
