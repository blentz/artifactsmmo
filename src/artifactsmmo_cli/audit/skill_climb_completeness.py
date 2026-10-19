"""Every routed `ReachSkillLevel(S, C+1)` plans, or is a NAMED wall.

Obligation O1 of the wave-3 resolution design (spec
`docs/superpowers/specs/2026-08-23-wave3-resolution-design.md` §3.5), restored
under its measured name (ruling AK, global gear objective): the cell is a
SKILL LEVEL, `C+1` with an XP-positive recipe or resource — not a character
tier. The gear objective (spec 2026-10-18 §2.4) makes `ReachSkillLevel` the
dominant root for every character, for days: `WhichPieceIsNext` sends a
skill-gated `L*` piece to `IsThisTargetBlocked`, whose answer is the next
level of the gating crafting skill. A skill the bot cannot raise is therefore
not a ranking that scores low — it is a stall with nothing behind it. "The bot
cannot raise this skill and cannot say why" must be impossible.

WHAT "THE CLIMB IS OPEN" MEANS, AND WHY IT IS NOT A SECOND MODEL
----------------------------------------------------------------
`ReachSkillGoal` is served by its grind's decomposition
(`craft_plan_gen._decompose_grind`), which opens only when the skill has
something XP-positive to make or gather — so "the goal is plannable from
here" IS `skill_is_grindable(S, C+1, state, game_data)`, and that is the
predicate this census calls. Nothing is reimplemented. It holds by either arm:

* a CRAFT arm: `skill_grind_target.has_grind_target` — an in-skill recipe at
  `crafting_level <= C` that is XP-positive (outside the server's zero-xp
  band) and recursively obtainable;
* a GATHER arm: `gather_skill_resource.best_gather_resource_drop` — for a
  skill that also gathers, the highest in-range resource, when it still pays.

The wall-diagnosis fields (`ClimbInventory`) re-read the SAME catalogue
predicates (`skill_xp_positive`, `skill_grind_target.is_obtainable`) to say
WHY a closed cell is closed. They are a decomposition of the production
answer, not a rival one: the suite pins that a cell is open iff an arm's
counter is positive.

THE GRID
--------
One cell per `(scenario, skill)` over `ai/scenario.SCENARIOS` x
`world_state.SKILL_NAMES`. Combat stats are DERIVED for every cell
(`scenario.derived_scenario_state`): with zero totals no monster is winnable,
every monster-drop leaf is unreachable, and the census would report walls that
belong to the harness, not the game.

ROUTED is what the root walk offers the character this cycle, driven as the
player drives it: the context carries the cycle's gear objective, attached by
the player's own `gear_objective_context.attach_gear_objective`, and
`resolve_root` is walked whole — the root AND its ordered alternatives,
because `strategy_driver._resolve_step_goal` falls through to an alternative
whenever the root's step goal comes back None. Every cell's verdict is asked
of its skill directly (`skill_is_grindable` at `C+1`), routed or not, so a
closed climb is found whether or not this cycle's walk happens to name it.

THE RESIDUALS (must be zero)
----------------------------
`SILENT_STALL` is the obligation itself: the root walk routes to
`ReachSkillLevel(S, C+1)` for a skill whose climb is closed. The arbiter is
handed a root the planner cannot serve, and no node says so.

`UNEXPLAINED` is the anti-laundering arm: a closed cell the wall taxonomy
cannot name. The four wall classes are built from POSITIVE evidence only,
never as an `else`, so this residual is reachable (`classify_gap`).

`SKILL_CATALOGUE_EMPTY` is the data-fault arm: a skill the catalogue offers
nothing at all. Without it `WALL_SKILL_TOPPED` would absorb a bundle whose
rows for a skill went missing and `--check` would exit 0 on corrupted input.

The four `WALL_*` classes are EXPLAINED closures: the CATALOGUE, not the walk,
stopped the climb, and they do not fail the gate. `routing_breakdown` prints
the residual's reach (the ROUTED subset) into the matrix on every run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.gear_objective_context import attach_gear_objective
from artifactsmmo_cli.ai.scenario import SCENARIOS, derived_scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.skill_grindable import skill_is_grindable
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.skill_grind_target import grind_model, is_obtainable
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState


class ClimbGap(Enum):
    """The verdict for one `(scenario, skill)` cell — one pass class, four
    named walls, three must-be-zero residuals."""

    OPEN = "open"
    """PASS: `skill_is_grindable(S, C+1)` holds, so `ReachSkillGoal` has at
    least one XP-positive recipe or resource to plan through."""

    WALL_SKILL_TOPPED = "wall_skill_topped"
    """No in-skill recipe and no in-skill resource sits ABOVE the current
    level. There is no climb left. An honest end, not a stall."""

    WALL_BELOW_FIRST_RECIPE = "wall_below_first_recipe"
    """The skill has content above but NOTHING at or below the current level —
    not one recipe, not one resource."""

    WALL_ALL_GREY = "wall_all_grey"
    """Recipes or resources are in reach and every one is in the server's
    zero-xp band, so grinding any of them can never raise the skill (the
    `sunflower_field`-at-alchemy-17 shape, live Robby 2026-08-05)."""

    WALL_UNOBTAINABLE = "wall_unobtainable"
    """XP-positive recipes are in reach and NOT ONE has a reachable material
    set: every recipe bottoms out in a leaf that is neither gathered nor
    dropped by a monster this character may fight."""

    SILENT_STALL = "silent_stall"
    """RESIDUAL. The root walk routes this character to
    `ReachSkillLevel(S, C+1)` — as the resolved root or as one of the ordered
    alternatives — and the climb is closed: an unplannable root with no node
    saying why."""

    UNEXPLAINED = "unexplained"
    """RESIDUAL. The cell is closed, the walk does not route to it, and none
    of the four walls holds. The census cannot say why either."""

    SKILL_CATALOGUE_EMPTY = "skill_catalogue_empty"
    """RESIDUAL, and a DATA fault: the catalogue offers this skill NOTHING —
    no recipe at any level, no resource at any level. A residual and not a
    wall because `WALL_SKILL_TOPPED` would otherwise absorb it, and `--check`
    would exit 0 on a corrupted catalogue (use API data or fail)."""


RESIDUALS = frozenset({ClimbGap.SILENT_STALL.value,
                       ClimbGap.UNEXPLAINED.value,
                       ClimbGap.SKILL_CATALOGUE_EMPTY.value})
"""The classes that must reach 0. The four `WALL_*` classes are EXPLAINED and
do not fail the gate."""

MIN_CELLS = 200
"""Blindness floor on the grid, enforced by `gen_skill_climb.py --check` and
not only by the suite: an EMPTY census satisfies "no residual", so "0 cells,
PASS 0" would otherwise print `GATE CLEAN`. `scripts/*` is coverage-omitted
and `census-gate.yml` runs the scripts without pytest, so the floor lives here,
where the script and the suite read the same number. 200 against 360 cells
today (45 scenarios x 8 skills)."""


@dataclass(frozen=True)
class ClimbInventory:
    """What the catalogue offers `skill` at level `level`, decomposed along the
    conjuncts `skill_is_grindable` reduces to. Every field is a COUNT or a
    code, never a verdict: `classify_gap` is the only place a verdict forms."""

    #: In-skill recipes with `crafting_level <= level`.
    in_level: int
    #: Of those, the ones outside the server's zero-xp band.
    xp_positive: int
    #: Of those, the ones whose whole recipe closure is reachable.
    obtainable: int
    #: In-skill recipes with `crafting_level > level` — is there a climb left.
    above: int
    #: Gatherable resources for this skill at `res_level <= level`.
    gather_in_level: int
    #: Gatherable resources for this skill above `level`.
    gather_above: int
    #: Whether the HIGHEST in-range resource still pays XP (False when there is
    #: none): `best_gather_resource_drop` picks the highest.
    gather_xp_positive: bool
    #: The drop item `best_gather_resource_drop` would grind, or None.
    gather_drop: str | None


@dataclass(frozen=True)
class ClimbResult:
    """One cell's answer. Flat and render-ready."""

    scenario: str
    skill: str
    level: int
    target: int
    open_climb: bool
    routed: bool
    inventory: ClimbInventory
    gap: str

    @property
    def passed(self) -> bool:
        return self.gap == ClimbGap.OPEN.value


def routed_skills(state: WorldState, game_data: GameData) -> frozenset[str]:
    """The skills the root walk would send this character to climb: every
    `ReachSkillLevel` it offers, root AND alternatives, on a context carrying
    the cycle's gear objective (`attach_gear_objective`, the player's own
    step). `history=None`: offline and deterministic."""
    ctx = attach_gear_objective(state, game_data, NO_PROFILE_CONTEXT, None)
    resolution = resolve_root(
        state, game_data, CharacterObjective.from_game_data(game_data), ctx, None)
    return frozenset(
        goal.skill
        for goal in (resolution.root, *resolution.alternatives)
        if isinstance(goal, ReachSkillLevel))


def climb_inventory(skill: str, state: WorldState,
                    game_data: GameData) -> ClimbInventory:
    """The evidence for one cell, read straight off the catalogue, over the
    SAME `grind_model` walk `has_grind_target` runs."""
    level = state.skills[skill]
    model = grind_model(state, game_data)
    in_level: list[str] = []
    above = 0
    for code, stats in game_data.all_item_stats.items():
        if stats.crafting_skill != skill or not game_data.crafting_recipe(code):
            continue
        if stats.crafting_level > level:
            above += 1
        else:
            in_level.append(code)
    xp_positive = [
        code for code in in_level
        if skill_xp_positive(game_data.all_item_stats[code].crafting_level, level)
    ]
    obtainable = [code for code in xp_positive if is_obtainable(code, model)]
    resource_levels = [res_level
                       for _, (res_skill, res_level) in game_data.resource_skills.items()
                       if res_skill == skill]
    gather_in = [lv for lv in resource_levels if lv <= level]
    return ClimbInventory(
        in_level=len(in_level),
        xp_positive=len(xp_positive),
        obtainable=len(obtainable),
        above=above,
        gather_in_level=len(gather_in),
        gather_above=len([lv for lv in resource_levels if lv > level]),
        gather_xp_positive=bool(gather_in) and skill_xp_positive(max(gather_in), level),
        gather_drop=best_gather_resource_drop(skill, level, game_data),
    )


def classify_gap(open_climb: bool, routed: bool,
                 inventory: ClimbInventory) -> ClimbGap:
    """The verdict for one cell.

    EVERY WALL ARM IS POSITIVE EVIDENCE, AND THERE IS NO `else` WALL: a
    taxonomy whose last arm is a catch-all can never report `UNEXPLAINED`.

    The routing test runs FIRST: a closed cell the walk routes to is the
    obligation's own failure whatever the catalogue reason is, and naming a
    wall would launder a live stall into an explanation. The empty-catalogue
    test runs before the topped-skill test, because "nothing above me" is true
    of a finished skill AND of a skill whose rows are gone."""
    if open_climb:
        return ClimbGap.OPEN
    if routed:
        return ClimbGap.SILENT_STALL
    if (inventory.in_level + inventory.above == 0
            and inventory.gather_in_level + inventory.gather_above == 0):
        return ClimbGap.SKILL_CATALOGUE_EMPTY
    if inventory.above == 0 and inventory.gather_above == 0:
        return ClimbGap.WALL_SKILL_TOPPED
    if inventory.in_level == 0 and inventory.gather_in_level == 0:
        return ClimbGap.WALL_BELOW_FIRST_RECIPE
    if inventory.xp_positive == 0 and not inventory.gather_xp_positive:
        return ClimbGap.WALL_ALL_GREY
    if (inventory.xp_positive > 0 and inventory.obtainable == 0
            and not inventory.gather_xp_positive):
        return ClimbGap.WALL_UNOBTAINABLE
    return ClimbGap.UNEXPLAINED


def run_census(game_data: GameData) -> list[ClimbResult]:
    """Every `(scenario, skill)` cell, in scenario-declaration order then
    `SKILL_NAMES` order — both fixed, so the matrix is byte-reproducible."""
    results: list[ClimbResult] = []
    for name, scenario in SCENARIOS.items():
        state = derived_scenario_state(scenario, game_data)
        routed = routed_skills(state, game_data)
        for skill in SKILL_NAMES:
            level = state.skills[skill]
            open_climb = skill_is_grindable(skill, level + 1, state, game_data)
            inventory = climb_inventory(skill, state, game_data)
            results.append(ClimbResult(
                scenario=name, skill=skill, level=level, target=level + 1,
                open_climb=open_climb, routed=skill in routed, inventory=inventory,
                gap=classify_gap(open_climb, skill in routed, inventory).value))
    return results


def summary_line(results: list[ClimbResult]) -> str:
    """One-line completeness metric: cells, distinct `(skill, level)` pairs,
    PASS, routed, walled, and every must-be-zero residual."""
    walls = sum(1 for r in results if r.gap.startswith("wall_"))
    stalls = sum(1 for r in results if r.gap == ClimbGap.SILENT_STALL.value)
    unexplained = sum(1 for r in results if r.gap == ClimbGap.UNEXPLAINED.value)
    absent = sum(1 for r in results if r.gap == ClimbGap.SKILL_CATALOGUE_EMPTY.value)
    pairs = {(r.skill, r.level) for r in results}
    routed = sum(1 for r in results if r.routed)
    return (f"{len(results)} cells over {len(pairs)} distinct (skill, level) "
            f"pairs; PASS {sum(1 for r in results if r.passed)}; "
            f"routed {routed}; walled {walls}; "
            f"silent_stall {stalls}; unexplained {unexplained}; "
            f"skill_catalogue_empty {absent}")


def routing_breakdown(results: list[ClimbResult]) -> str:
    """Which skills the walk routes to, and how many cells each: the
    residual's scope, computed so the claim cannot rot. A closure in an
    unrouted skill can only ever be an explained wall."""
    counts: dict[str, int] = {}
    for r in results:
        if r.routed:
            counts[r.skill] = counts.get(r.skill, 0) + 1
    routed = sum(counts.values())
    skills = ", ".join(
        f"{skill} {counts[skill]}"
        for skill in sorted(counts, key=lambda name: (-counts[name], SKILL_NAMES.index(name))))
    return (f"residual scope: {routed} of {len(results)} cells are ROUTED "
            f"({len(counts)} of {len(SKILL_NAMES)} skills) — {skills or 'none'}. "
            f"A closure in an unrouted skill can only be an explained wall.")


def render_matrix(results: list[ClimbResult]) -> str:
    """The cell x verdict matrix. Pure markdown — the script owns the write."""
    lines = [
        "# Skill-Climb Completeness — Matrix",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_skill_climb.py`.",
        ">",
        "> Obligation O1 (wave-3 resolution design §3.5): every "
        "`ReachSkillLevel(S, C+1)` the root walk routes to across the scenario "
        "set can plan, or is a named wall. The verdict column is "
        "`skill_is_grindable(S, C+1)` — the predicate `ReachSkillGoal`'s "
        "decomposition opens on — cross-read against the catalogue evidence "
        "beside it.",
        ">",
        "> `routed` is what `decisions/root.resolve_root` would send this "
        "character to climb (root + alternatives), on a context carrying the "
        "cycle's gear objective. A closed cell that is routed is "
        "`silent_stall`, the residual the obligation exists for.",
        ">",
        "> `g-in`/`g-above` are the in-range and above-range resource counts "
        "and `g-xp+` is whether the HIGHEST in-range resource still pays XP.",
        "",
        summary_line(results),
        "",
        routing_breakdown(results),
        "",
        "| Scenario | Skill | C | Target | Verdict | routed | in-level | "
        "xp+ | obtainable | above | g-in | g-above | g-xp+ | gather drop |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        verdict = "PASS" if r.passed else f"**{r.gap}**"
        inv = r.inventory
        lines.append(
            f"| {r.scenario} | {r.skill} | {r.level} | {r.target} | {verdict} "
            f"| {'yes' if r.routed else '-'} | {inv.in_level} "
            f"| {inv.xp_positive} | {inv.obtainable} | {inv.above} "
            f"| {inv.gather_in_level} | {inv.gather_above} "
            f"| {'yes' if inv.gather_xp_positive else '-'} "
            f"| `{inv.gather_drop}` |")
    lines.append("")
    return "\n".join(lines) + "\n"
