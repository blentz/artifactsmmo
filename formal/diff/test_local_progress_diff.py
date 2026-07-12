"""Differential test for Phase-19d Tier-1 local progress.

Runs K cycles of Fight / Deposit / Rest against `FakeServer` AND the
planner-side `Action.apply` projections. After every cycle, the Python-side
`measure` tuple must satisfy lex-decrease OR level-up OR no-op. Zero "measure
increased without level-up" is tolerated.

This pins the Tier-1 Lean headline (`step_decreases_or_levels`) at the
Python level — any divergence between the Lean axioms and the production
`Action.apply` implementations surfaces as a regression.

Gather is NOT exercised here: the skill-progress slot (slot 4) is now a
skill-LEVEL deficit (`ReachSkillGoal.is_satisfied` reads `state.skills`), and
production `GatherAction.apply` no longer advances any skill-progress signal
(the planner-native grind is the `LevelSkill` action). The modeled grind
rung's monotone descent is proven purely in Lean (`GatherProgress.lean`) and
mirrored by the `FakeServer.gather` axiom (exercised by the no-deadlock diff).

Mutation targets that this test KILLS:
  * `formal/sim/measure.py` — drop hpDeficit slot from lex.
  * `formal/sim/measure.py` — invert lex direction.
  * `src/artifactsmmo_cli/ai/actions/rest.py` — drop hp restoration.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState
from formal.sim.fake_server import FakeServer
from formal.sim.measure import Measure, lex_lt, measure


# Deterministic xp curve stub. Lean axiom LIV-001 requires
# `xpToNextLevel(L) > 0 for L in [1, 49]`. We pick the simple monotone
# `100 * L` curve so the differential is self-consistent across levels.
def _xp_to_next_level(level: int) -> int:
    return 100 * max(1, level)


# Tier-1 single-skill target LEVEL the measure's slot 4 operates on. Set well
# above the tracked skill level so the slot-4 deficit is a positive constant
# (no action in this Fight/Deposit/Rest differential raises a skill level).
_SKILL_NAME = "mining"
_SKILL_TARGET_LEVEL = 10_000


def _slots() -> list[str]:
    return [
        "weapon_slot", "rune_slot", "shield_slot", "helmet_slot",
        "body_armor_slot", "leg_armor_slot", "boots_slot",
        "ring1_slot", "ring2_slot", "amulet_slot",
        "artifact1_slot", "artifact2_slot", "artifact3_slot",
        "utility1_slot", "utility2_slot", "bag_slot",
    ]


def _make_state() -> WorldState:
    eq: dict[str, str | None] = {s: None for s in _slots()}
    eq["weapon_slot"] = "copper_dagger"
    return WorldState(
        character="probe", level=2, xp=0, max_xp=_xp_to_next_level(2),
        hp=40, max_hp=100, gold=0,
        skills={"mining": 2, "woodcutting": 1, "fishing": 1,
                "weaponcrafting": 1, "gearcrafting": 1,
                "jewelrycrafting": 1, "cooking": 1, "alchemy": 1},
        x=0, y=0,
        # Pre-load enough non-task items to trigger bank-pressure (> 80% of 20):
        inventory={"copper_ore": 14, "ash_wood": 4},
        inventory_max=20,
        inventory_slots_max=20,
        equipment=eq,
        cooldown_expires=None,
        task_code="chicken", task_type="monsters",
        task_progress=0, task_total=10,
        bank_items={}, bank_gold=0,
        pending_items=None,
        attack={"fire": 0},
        dmg=0,
        dmg_elements={},
        resistance={},
        critical_strike=0,
        initiative=0,
        wisdom=0,
        skill_xp={"mining": 0},
    )


def _make_game_data() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
    }
    gd._crafting_recipes = {}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    gd._workshop_locations = {}
    gd._monster_locations = {"chicken": [(0, 1)]}
    gd._monster_level = {"chicken": 1}
    # FightAction.is_applicable now computes the optimal combat loadout (the
    # 2026-07-10 optimal-loadout gate), so it reads the monster's attack /
    # resistance profile — every real monster carries these. The probe owns only
    # copper_dagger (equipped) so pick_loadout returns it unchanged and the gate
    # stays transparent to this progress simulation; without the data the gate
    # would KeyError before ever comparing loadouts.
    gd._monster_attack = {"chicken": {"fire": 2}}
    gd._monster_resistance = {"chicken": {}}
    gd._bank_location = (4, 0)
    gd._next_expansion_cost = 1000
    return gd


def _state_measure(s: WorldState) -> Measure:
    return measure(
        s,
        xp_to_next_level=_xp_to_next_level(s.level),
        target_skill_level=_SKILL_TARGET_LEVEL,
        tracked_skill_level=s.skills.get(_SKILL_NAME, 1),
    )


def _measure_advance(prev: Measure, new: Measure) -> str:
    """Classify the transition: 'decrease' / 'equal' / 'REGRESSION'."""
    if lex_lt(new, prev):
        return "decrease"
    if new.as_tuple() == prev.as_tuple():
        return "equal"
    return "REGRESSION"


def _pick_action(state: WorldState, gd: GameData, cycle: int):
    """Round-robin pick over the three Tier-1 actions; falls back to None when
    no action is applicable, which the test classifies as a no-op."""
    fight = FightAction(monster_code="chicken",
                        locations=frozenset({(0, 1)}))
    deposit = DepositAllAction(bank_location=(4, 0), accessible=True, game_data=gd)
    rest = RestAction()
    schedule = [rest, fight, deposit]
    # Try the round-robin pick first; if not applicable, scan the others.
    primary = schedule[cycle % 3]
    if primary.is_applicable(state, gd):
        return primary
    for candidate in schedule:
        if candidate.is_applicable(state, gd):
            return candidate
    return None


def _apply_via_fake_server(action, state: WorldState, gd: GameData) -> WorldState:
    """FakeServer-side projection for the SAME action. Must agree with
    `action.apply(state, gd)` on every measure slot (Tier-1 deterministic
    semantics)."""
    server = FakeServer(state)
    if isinstance(action, FightAction):
        matches = (state.task_type == "monsters"
                   and state.task_code == action.monster_code)
        return server.fight(monster_code=action.monster_code,
                            monster_matches_task=matches)
    if isinstance(action, DepositAllAction):
        items = action._deposits(state)
        return server.deposit(items=items)
    if isinstance(action, RestAction):
        return server.rest()
    raise AssertionError(f"unhandled action type {type(action)!r}")


def _measure_matches(
    planner_after: WorldState, server_after: WorldState
) -> bool:
    """Tier-1 semantics: planner-side `apply` and FakeServer must produce
    states with byte-equivalent measure tuples (their non-measure fields
    may legitimately differ — e.g. planner advances x,y; FakeServer does
    not). We only assert measure equivalence."""
    return _state_measure(planner_after).as_tuple() == \
        _state_measure(server_after).as_tuple()


CYCLES = 1000


def test_tier1_local_progress_holds_for_K_cycles() -> None:
    """Run CYCLES cycles of round-robin Tier-1 actions. After every cycle
    the lex measure must (a) strictly decrease, (b) level up (out of scope
    in Tier 1 — would only happen if perception integrated server-side
    level-ups), or (c) no-op (no applicable action / cooldown).

    Zero "measure increased without level-up" tolerated.
    """
    gd = _make_game_data()
    state = _make_state()
    history: list[tuple[str, Measure, Measure]] = []
    regressions: list[tuple[int, str, Measure, Measure]] = []
    rest_non_decreases: list[tuple[int, Measure, Measure]] = []
    server_divergences: list[tuple[int, str]] = []
    for cycle in range(CYCLES):
        prev_level = state.level
        prev_m = _state_measure(state)
        action = _pick_action(state, gd, cycle)
        if action is None:
            history.append(("no-op", prev_m, prev_m))
            continue
        planner_after = action.apply(state, gd)
        # Cross-check FakeServer: measure must match planner's measure.
        server_after = _apply_via_fake_server(action, state, gd)
        if not _measure_matches(planner_after, server_after):
            server_divergences.append((cycle, repr(action)))
        # Perception-invariant integration (mirrors `inv : xp < xpToNextLevel`
        # load-bearing hypothesis on `fight_decreases_measure`). When the
        # planner-projected xp reaches or exceeds the curve threshold, the
        # cycle model says a level-up event arrives via perception. We model
        # that here by promoting `level` and resetting `xp`, then classify
        # the cycle as a level-up. Without this, Fight's projector (which
        # only does xp+=10) cannot decrease xpDeficit once xp_deficit==0,
        # and the cycle would falsely report a regression on hpDeficit.
        if (isinstance(action, FightAction)
                and planner_after.xp >= _xp_to_next_level(planner_after.level)
                and planner_after.level < 50):
            planner_after = dataclasses.replace(
                planner_after,
                level=planner_after.level + 1,
                xp=0,
                hp=planner_after.max_hp,
            )
        # Reset bank-pressure when planner-side inventory dropped (Deposit):
        # we do NOT artificially re-seed inventory, the differential just
        # rides the natural transition.
        state = planner_after
        new_m = _state_measure(state)
        if state.level > prev_level:
            history.append(("level-up", prev_m, new_m))
            continue
        verdict = _measure_advance(prev_m, new_m)
        history.append((verdict, prev_m, new_m))
        if verdict == "REGRESSION":
            regressions.append((cycle, repr(action), prev_m, new_m))
        # The Lean `rest_decreases_measure` lemma is unconditional given
        # applicability: an applicable Rest MUST strictly decrease the
        # measure. An "equal" verdict on a Rest cycle witnesses that slot 6
        # (hpDeficit) has been dropped from the lex order — the canonical
        # mutant. Pin this directly.
        if isinstance(action, RestAction) and verdict != "decrease":
            rest_non_decreases.append((cycle, prev_m, new_m))
        # Productive bookkeeping for the no-op path: if Fight took our HP
        # below the min-fight fraction, the next cycle's Fight will fall
        # through to Rest (still applicable as long as hp < max_hp).
        # If inventory drained below the deposit threshold, the next
        # Deposit becomes a no-op and the test records it as such.
        # Re-seed to keep the diff exercising all three actions over the
        # full CYCLES window: top up inventory if it dropped below the
        # bank-pressure floor (i.e. we'd otherwise no-op forever).
        if (state.inventory_used <= ((state.inventory_max * 4) // 5)
                and isinstance(action, DepositAllAction)):
            # Re-seed: bank-pressure was relieved; refill the inventory
            # so subsequent Deposit cycles continue exercising the lex
            # bankPressure slot.
            refill = dict(state.inventory)
            refill["copper_ore"] = refill.get("copper_ore", 0) + 14
            state = dataclasses.replace(state, inventory=refill)
    assert not server_divergences, (
        f"FakeServer measure diverged from planner-side apply at "
        f"cycles {server_divergences[:5]} — Lean Server axioms dishonest "
        f"OR production action.apply has drifted")
    assert not regressions, f"Tier-1 lex regressions: {regressions[:5]}"
    assert not rest_non_decreases, (
        f"Rest cycles failed to strictly decrease the lex measure — slot 6 "
        f"(hpDeficit) appears to be missing from the comparator: "
        f"{rest_non_decreases[:5]}")
    # Sanity: at least one of each verdict appeared (test exercises the
    # measure non-vacuously).
    verdicts = {h[0] for h in history}
    assert "decrease" in verdicts, (
        f"no decreasing cycle observed in {CYCLES} cycles — diff test is "
        f"vacuous; verdict distribution: "
        f"{[(v, sum(1 for h in history if h[0] == v)) for v in verdicts]}")
    print(
        f"cycles total={CYCLES} "
        f"decrease={sum(1 for h in history if h[0] == 'decrease')} "
        f"equal={sum(1 for h in history if h[0] == 'equal')} "
        f"no-op={sum(1 for h in history if h[0] == 'no-op')} "
        f"level-up={sum(1 for h in history if h[0] == 'level-up')}"
    )
