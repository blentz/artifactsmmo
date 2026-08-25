"""The gear gap between a character and a fight it cannot win — as a FACT.

`predict_win` answers "do I beat this monster?" with a bool, and `combat_margin`
answers it with a signed margin. Neither says WHAT TO DO when the answer is no,
so nothing in the bot ever linked a lost fight to the gear that would win it.

What stood in for that link was a countdown: `GOAL_OSCILLATION` recovery put the
losing grind in a penalty box for 5 cycles, then 15, then raised `StuckExit`
(`player.py`). A countdown expires whether or not anything changed, so the loop
could not converge — live on C3P0 (2026-08-20) it re-fought the same pig 42 times,
lost 42 times, and the escalation ladder killed the session rather than fixing the
gear. `combat_loadout_outcome` holds all 42 rows as `(predicted_win=0, actual_win=0)`:
the model was right every time and the bot fought anyway.

`combat_deficit` is that missing link, and it is a fact rather than a timer:

  * `None` exactly when `predict_win` holds — so a caller that suppresses a fight
    "while the deficit is non-None" releases the moment the gear lands, with
    nothing to expire and no escalation to exhaust.
  * otherwise a `CombatDeficit` naming the acquisitions that close the margin,
    each carrying the crafting skill that gates it. C3P0's real chain was
    `iron_sword` -> `iron_armor` -> `earth_boost_potion` -> `earth_ring`
    (margin -10 -> +1), three of the four needing `iron_bar` and every one gated
    behind a skill level it did not have. That is the whole shape of the problem:

        fight deficit <- gear deficit <- skill deficit <- material deficit

    A single-item answer would have hidden three of those four layers.

USER (2026-08-20), on what to do when no one item is enough: "that just means we
need multiple upgrades before we can win that fight. the time it takes is just the
cost of progress." So the chain STACKS rather than giving up, and there is no
fallback to an easier monster.

Greedy on MARGIN, deliberately. The live failure was the opposite: `map_guard`'s
GEAR_REVIEW branch ranked upgrades with a monster-blind `_best_by_value` scan and
chose `iron_boots` — already worn, and absent from all 24 items that improved the
pig margin — while the weapon that actually moved `rounds_to_kill` went unbuilt
for ten hours.

Costs one `combat_margin` per candidate per step. That is fine for the read-only
`combat-deficit` diagnostic; a per-cycle caller must memoize (see
`equipment/loadout_cache.py` for the established read-set-keyed pattern).
"""

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass

from artifactsmmo_cli.ai.combat import combat_margin, predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.world_state import WorldState

MAX_CHAIN = 8
"""Bound on the greedy walk.

Not a modelling constant — a termination bound. The walk already stops when no
candidate improves the margin; this caps the pathological case where a long tail
of +1 items each improves it without ever closing the gap. C3P0's real chain was
4 steps.
"""


@dataclass(frozen=True)
class DeficitStep:
    """One acquisition in the chain, with the skill gate that stands in front of it.

    `crafting_skill` / `crafting_level` are carried because the gear layer is not
    the bottom of the chain: C3P0 could not craft `iron_sword` at weaponcrafting 6
    however many `iron_bar` it held. A step without its gate reads as actionable
    when it is not.
    """

    code: str
    item_type: str
    item_level: int
    crafting_skill: str | None
    crafting_level: int
    margin_after: int
    acquire_cost: float | None = None
    """Actions to acquire ONE of this step, from the caller's `cost_of`.

    None when the caller supplied no pricing. Recorded so the chain reads as a
    PLAN rather than a verdict: four steps costing 20 cycles each is a different
    decision from four costing 400.
    """


@dataclass(frozen=True)
class CombatDeficit:
    """Why this fight is lost, and what closes it.

    `closes` distinguishes "unwinnable and I know what to build" from "unwinnable
    and I do not" — a caller that blocks a fight on this fact must be able to tell
    those apart, because only the first one is progress.

    For a while it told them apart only for the reader: the `combat-deficit`
    diagnostic printed CLOSES / DOES NOT CLOSE and the production consumer,
    `deficit_upgrade_target`, branched on `chain` instead and committed to gear
    from the second case as readily as the first. `deficit_upgrade_target` now
    reads this field, which is the whole reason it exists.
    """

    monster: str
    baseline_margin: int
    chain: tuple[DeficitStep, ...]
    closes: bool


def _pool(state: WorldState, game_data: GameData,
          candidates: tuple[str, ...] | None) -> tuple[tuple[str, ItemStats], ...]:
    """Candidate (code, stats) pairs, in catalog order.

    Resolves stats ONCE here rather than in the greedy walk, so a caller-supplied
    code with no catalog entry is dropped at the boundary instead of surfacing as
    a None deep inside the scoring loop.
    """
    if candidates is None:
        return tuple(
            (code, stats)
            for code, stats in game_data.items.stats.items()
            if stats.type_ in ITEM_TYPE_TO_SLOTS and stats.level <= state.level
        )
    resolved = ((code, game_data.item_stats(code)) for code in candidates)
    return tuple((code, stats) for code, stats in resolved if stats is not None)


def _margin_owning(state: WorldState, game_data: GameData, monster: str,
                   inventory: dict[str, int], code: str) -> int:
    """Margin against `monster` if the character also OWNED one `code`.

    Owning, not wearing: `predict_win` / `pick_loadout` already choose the best
    on-hand loadout per monster's resistances, so the honest question for "is this
    worth acquiring" is marginal — the same framing `weapon_winnability` uses.
    """
    trial = dict(inventory)
    trial[code] = trial.get(code, 0) + 1
    return combat_margin(dataclasses.replace(state, inventory=trial), game_data, monster)


def blocked_task_monster(state: WorldState) -> str | None:
    """The held monsters-task's code when it is still workable, else None."""
    if state.task_type != "monsters" or not state.task_code:
        return None
    if state.task_total == 0 or state.task_progress >= state.task_total:
        return None
    return state.task_code


def has_combat_deficit(state: WorldState, game_data: GameData) -> bool:
    """Is the held task's monster unwinnable? The CHEAP form of the same fact.

    `combat_deficit` walks every candidate to name what closes the gap; this is
    one `predict_win`. `GearLatch.update` runs every cycle and only needs to know
    THAT a deficit exists, so the walk would be the wrong thing to put there.

    Exactly equivalent to `combat_deficit(...) is not None` — pinned by a test,
    because if the two ever disagreed the latch would arm for a deficit the gear
    chain cannot name, and the character would review gear forever.
    """
    monster = blocked_task_monster(state)
    if monster is None:
        return False
    return not predict_win(dataclasses.replace(state, hp=state.max_hp),
                           game_data, monster)


def deficit_upgrade_target(
    state: WorldState,
    game_data: GameData,
    candidates: tuple[str, ...] | None = None,
    cost_of: Callable[[str], float] | None = None,
) -> tuple[str, str] | None:
    """`(item_code, slot)` to build next to make the HELD TASK's monster winnable.

    This is the causal link "lose fight -> upgrade gear" that the bot never had.
    `map_guard`'s GEAR_REVIEW branch sets its target with a monster-BLIND
    `_best_by_value` scan: live it chose `iron_boots`, already worn and absent
    from all 24 items that improved the pig margin, while the weapon that
    actually moved `rounds_to_kill` went unbuilt for ten hours. The gear latch
    knew a fight had been lost; nothing carried WHICH fight into the decision.

    Scoped to the HELD TASK rather than to the last loss, deliberately. Once the
    tier-1 bypass closed, an unwinnable task monster stops being the farm target,
    so "the monster we last lost to" is a stale signal that decays as soon as it
    matters. The task is what the character is actually blocked on — and building
    toward being able to fight it is how S-052 ("work a task you cannot discard")
    is honoured by a character that cannot fight it yet.

    Returns None when there is nothing to fix — no monsters task, one already
    finished, a monster already winnable, or a gap no gear closes. The generic
    value scan then decides, unchanged.

    That last clause is `deficit.closes`, and it used to be a lie. The call was
    pinned at `max_chain=1` and the guard read `deficit.chain`, so ANY item that
    moved the margin by one point was committed to as "the gear that wins this
    fight" — over the whole scenario corpus, 648 of 895 losing (character,
    monster) pairs returned a target that provably could not close. The visible
    end of it was `l47_depth3_amulet` vs `dusk_beetle`: margin -6, nine
    candidates all gaining exactly +1 at an identical (ceiling) price, and the
    walk picked among nine equally futile items by catalogue order — a level-25
    `emerald_amulet` for a level-47 character. No chain of ANY length closes
    that fight (measured: -6 -> -4 at depth 2, then nothing improves), so the
    pick was not a tie-break defect. It was a decision that should never have
    been taken.

    The bound is now the module's own `MAX_CHAIN` rather than 1, which costs
    depth but cannot change the ANSWER: the walk is greedy and prefix-stable, so
    the chain at depth k is the first k steps of the chain at depth 8. Measured
    over all 895 pairs, `chain[0]` differed between `max_chain=1` and
    `max_chain=8` in exactly 0 of them. Depth buys `closes` and nothing else —
    122 of the 648 futile pairs turn out to have a closing chain (30 at depth 2,
    59 by depth 3, 122 by depth 8) and keep the SAME first target, now honestly
    justified; the other 526 fall through to the value scan, which is what
    `strategy_driver`'s GEAR_REVIEW branch does with a None. GEAR_REVIEW still
    fires and still buys gear — only the monster-scoped claim is withdrawn when
    the monster cannot be reached by gear at all.

    `closes` subsumes the old `chain` check: it is set only immediately after a
    step is appended, so `closes` implies a non-empty chain.

    The slot is the first in `ITEM_TYPE_TO_SLOTS` order for the item's type, the
    same rule `UpgradeEquipmentGoal` uses, so the guard equips into a slot that
    accepts it.
    """
    monster = blocked_task_monster(state)
    if monster is None:
        return None
    deficit = combat_deficit(state, game_data, monster,
                             candidates=candidates, cost_of=cost_of)
    if deficit is None or not deficit.closes:
        return None
    step = deficit.chain[0]
    slots = ITEM_TYPE_TO_SLOTS.get(step.item_type, [])
    if not slots:
        # Totality guard, provably unreachable: an item can only improve the
        # margin by being picked into a loadout, which requires a slot — and the
        # default pool filters on `ITEM_TYPE_TO_SLOTS` besides. It stays because
        # `candidates` is caller-supplied and `slots[0]` would IndexError rather
        # than decline. Same idiom as `buy_source_venue.choose_buy_venue3`'s
        # unreachable arm.
        return None  # pragma: no cover
    return step.code, slots[0]


def combat_deficit(
    state: WorldState,
    game_data: GameData,
    monster: str,
    candidates: tuple[str, ...] | None = None,
    max_chain: int = MAX_CHAIN,
    cost_of: Callable[[str], float] | None = None,
) -> CombatDeficit | None:
    """The gear gap against `monster`, or None when the fight is already winnable.

    Args:
      state:      the character. Evaluated at `max_hp`, NOT current hp — see the
                  note at the top of the function body.
      game_data:  static world data.
      monster:    monster code.
      candidates: item codes to consider acquiring. Defaults to every equippable
                  at or below the character's level. Injectable so a caller can
                  narrow it to what is actually acquirable (`obtain_sources`)
                  without this core taking a dependency on the acquisition model.
      max_chain:  bound on the greedy walk.
      cost_of:    actions to acquire ONE of an item — in production
                  `acquisition_cost.acquisition_actions`. When supplied the walk
                  ranks on margin gain PER ACTION instead of raw gain, which is
                  what makes clause (c) fall out for free: `acquisition_cost`
                  already prices a skill gate as `unlock_actions` cycles, so
                  "lowest skill requirement" and "cheapest unlock" are the same
                  ordering and neither needs a rule of its own. Defaults to None
                  so every existing caller keeps raw-margin ranking exactly —
                  the same contract `route_options` gives its `store`.
    """
    # RESTORABLE hp, never current. "What gear closes this fight" is a different
    # question from "should I fight right now", and only the second depends on
    # how damaged we happen to be — rest is an action the planner has. Measured
    # live: C3P0 at 1/385 reported margin -21 with a chain that does NOT close,
    # and the same character at 385/385 reported -10 with one that does. A gear
    # plan that moves with transient hp is the same defect as the 7,000x iron-gear
    # price swing, fixed the same way (PLAN_iron_gear_acquisition increment 2),
    # and `tiers/objective.py` sets the precedent for building `rested` here.
    state = dataclasses.replace(state, hp=state.max_hp)
    if predict_win(state, game_data, monster):
        return None
    baseline = combat_margin(state, game_data, monster)
    pool = _pool(state, game_data, candidates)

    inventory = dict(state.inventory)
    chain: list[DeficitStep] = []
    current = baseline
    closes = False
    while len(chain) < max_chain:
        best: tuple[str, ItemStats] | None = None
        best_margin = current
        best_score = 0.0
        best_cost: float | None = None
        for code, stats in pool:
            margin = _margin_owning(state, game_data, monster, inventory, code)
            if margin <= current:
                continue  # cheap is no reason to acquire something that cannot help
            gain = margin - current
            cost = None if cost_of is None else cost_of(code)
            # `max(cost, 1.0)`: an item priced 0 is one already owned, which
            # cannot improve the margin anyway (`pick_loadout` would be wearing
            # it) — but the ranking must not be able to divide by zero if one is.
            score = float(gain) if cost is None else float(gain) / max(cost, 1.0)
            if best is None or score > best_score:
                best, best_margin, best_score, best_cost = (
                    (code, stats), margin, score, cost)
        if best is None:
            break
        best_code, best_stats = best
        inventory[best_code] = inventory.get(best_code, 0) + 1
        current = best_margin
        chain.append(DeficitStep(
            code=best_code,
            item_type=best_stats.type_,
            item_level=best_stats.level,
            crafting_skill=best_stats.crafting_skill,
            crafting_level=best_stats.crafting_level,
            margin_after=current,
            acquire_cost=best_cost,
        ))
        if predict_win(dataclasses.replace(state, inventory=inventory), game_data, monster):
            closes = True
            break
    return CombatDeficit(monster=monster, baseline_margin=baseline,
                         chain=tuple(chain), closes=closes)
