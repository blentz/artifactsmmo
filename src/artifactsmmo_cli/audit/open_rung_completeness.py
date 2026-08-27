"""O1: every `ReachSkillLevel(S, C+1)` has an open, XP-positive rung — or the
graph emits a NAMED WALL.

Spec `docs/superpowers/specs/2026-08-23-wave3-resolution-design.md` §3.5,
obligation O1. Wave 3 puts `ReachSkillLevel` on the ONLY path from a
skill-gated gear target to work (`decisions/root.IsThisTargetBlocked` returns
it unconditionally, exactly as `decisions/obtain_item.CanICraftCurrentTier`
does), so a skill the bot cannot raise is no longer a ranking that scores low —
it is a stall with nothing behind it. "The bot cannot raise this skill and
cannot say why" must be impossible.

WHAT "AN OPEN RUNG" MEANS, AND WHY IT IS NOT A SECOND MODEL
-----------------------------------------------------------
`ReachSkillGoal` admits exactly one action — the `"skill_grind"`-tagged
`LevelSkill` (`goals/reach_skill.relevant_actions`) — so "the goal is
plannable from here" IS `LevelSkill(S, C+1).is_applicable(state, game_data)`,
and that is the predicate this census calls. Nothing is reimplemented: the
census asks production the same question the planner asks. `is_applicable`
is satisfied by either arm —

* a CRAFTABLE rung: `skill_grind_target.has_grind_target` — an in-skill recipe
  at `crafting_level <= C` that is XP-positive (outside the server's zero-xp
  band) and recursively obtainable;
* a GATHERABLE rung: `gather_skill_resource.best_gather_resource_drop` — for a
  skill that also gathers, the highest in-range resource, when it still pays XP.

The wall-diagnosis fields below (`rungs_in_level`, `rungs_xp_positive`,
`rungs_obtainable`, `gather_*`) re-read the SAME catalogue predicates
(`skill_xp_positive`, `skill_grind_target._obtainable`) to say WHY a closed
cell is closed. They are a decomposition of the production answer, not a rival
one: `test_open_rung_completeness` pins that a cell is open iff at least one
arm's counter is positive, so the two can never drift apart silently.

THE GRID
--------
One cell per `(scenario, skill)` over `ai/scenario.SCENARIOS` x
`world_state.SKILL_NAMES` — "every `(skill, level)` reachable across the
scenario set", read literally. The scenario set is the corpus every other
census in this repo plans against, and it is the only set of characters this
codebase declares rather than invents.

COMBAT STATS ARE FORCED ON, AND THAT IS THE WHOLE DIFFERENCE BETWEEN THIS
CENSUS AND A MEASUREMENT OF THE HARNESS. `ScenarioCharacter.derive_combat_stats`
defaults False, and its own docstring says why: under the harness's original
zero-stat states "`is_winnable` is False against EVERY monster (predict_win
sees 0 attack)". A rung's obtainability walk bottoms out in `drop_obtainable`,
so with the flag off EVERY monster-drop leaf in the catalogue is unreachable
and the census would report walls that are properties of the fixture. Measured
on the committed bundle: 77 closed cells with the flag off everywhere, 20 with
the scenarios AS COMMITTED (34 of the 44 opt the flag on), and 6 with it forced
on. The all-off figure moved 74 -> 77 when wave 6 added `l32_items_task`;
the other two did NOT move, which is the point of keeping all three. The
flag-off count is the vacuity diagnostic — a zero-stat character reports
walls that belong to the harness, not the bot — while `as_committed` and
the forced-on figure are the measure. A new cell that changed THOSE would
be a real finding rather than a regeneration. The flag is therefore forced on for every cell — the census derives the
combat totals a live character wearing that scenario's declared loadout would
report. The committed scenarios are NOT modified; `census_state` builds its own
copy. `test_the_zero_stat_harness_would_measure_the_fixture` pins the 74/20/6
spread so a later default flip cannot make this note quietly false.

THE RESIDUALS (must be zero)
----------------------------
`O1_SILENT_STALL` is the obligation itself: the root graph routes to
`ReachSkillLevel(S, C+1)` for a skill with no open rung. That is the silent
fall-through §3.5 names — the arbiter is handed a root the planner cannot
serve, and no node says so.

`O1_UNEXPLAINED` is the anti-laundering arm: a closed cell the wall taxonomy
below cannot name. The four wall classes are built from POSITIVE evidence
only, never as an `else`, precisely so this residual is reachable — see
`classify_gap`.

`SKILL_CATALOGUE_EMPTY` is the data-fault arm: a skill the catalogue offers
nothing at all. Without it `WALL_LADDER_TOPPED` would absorb a bundle whose
rows for a skill went missing and `--check` would exit 0 on corrupted input.

WHAT "0 RESIDUALS" DOES AND DOES NOT PROMISE. `O1_SILENT_STALL` is
`closed AND routed`, so its reach is the ROUTED subset, not all 344 cells.
Measured on the committed bundle: 241 cells are routed — alchemy, cooking,
fishing, mining and woodcutting 43 each (every scenario, via
`decisions/root._orphan_skill_roots`), jewelrycrafting 15, gearcrafting 9,
weaponcrafting 2 — i.e. all 8 skills, though weaponcrafting only at level 1.
This number has moved twice, both times because a SKILL stopped being invisible
to the root graph rather than because the census changed: 26 -> 194 when
`b39705eb` restored the standalone skill root (cooking, fishing, mining,
woodcutting), and 194 -> 236 when `_gear_nameable_skills` stopped restating
`objective._gear_candidates_by_type`'s candidate rule and started asking it —
the restatement had drifted, claiming alchemy's `utility` potions made it
gear-nameable when the sheet builder skips `utility` outright, so the orphan
rule declined the one skill it was written for. The six real walls this census
finds (weaponcrafting 35, 40 and 42, the epic's own L38-48 territory) sit
outside the residual's reach today. The other 100 cells are still swept, still
verdicted and still walled by name — they just cannot produce the must-be-zero
class.
`routing_breakdown` prints this scope into the matrix on every run, computed
rather than transcribed, so widening the routed set updates the claim itself.

The four `WALL_*` classes are EXPLAINED closures, in the shape the shed census
uses for its world limits: they say the CATALOGUE, not the graph, is what
stopped the climb, and they do not fail the gate. A `WALL_*` count of zero
would be a finding, not a success; the summary line prints it either way.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.scenario import SCENARIOS, ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.skill_grind_target import _obtainable
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState


class OpenRungGap(Enum):
    """The verdict for one `(scenario, skill)` cell — one pass class, four
    named walls, two must-be-zero residuals."""

    OPEN_RUNG = "open_rung"
    """PASS: `LevelSkill(S, C+1)` is applicable, so `ReachSkillGoal` has at
    least one XP-positive rung to plan through."""

    WALL_LADDER_TOPPED = "wall_ladder_topped"
    """No in-skill recipe and no in-skill resource sits ABOVE the current
    level. The catalogue has nothing further for this skill; there is no rung
    because there is no climb left. An honest end, not a stall."""

    WALL_BELOW_FIRST_RUNG = "wall_below_first_rung"
    """The skill has content above but NOTHING at or below the current level —
    not one recipe, not one resource. The character stands under the bottom of
    the skill's own ladder, which is a nameable fact about the catalogue."""

    WALL_ALL_RUNGS_GREY = "wall_all_rungs_grey"
    """Rungs are in reach and every one is in the server's zero-xp band, so
    grinding any of them can never open the gate it was invoked to open (the
    `sunflower_field`-at-alchemy-17 shape, live Robby 2026-08-05)."""

    WALL_RUNGS_UNOBTAINABLE = "wall_rungs_unobtainable"
    """XP-positive rungs are in reach and NOT ONE has a reachable material set:
    every recipe bottoms out in a leaf that is neither gathered nor dropped by
    a monster this character may fight."""

    O1_SILENT_STALL = "o1_silent_stall"
    """RESIDUAL. The root graph routes this character to
    `ReachSkillLevel(S, C+1)` — as the resolved root or as one of the ordered
    alternatives the driver falls through to — and the skill has NO open rung.
    This is §3.5's silent fall-through: an unplannable root with no node
    saying why."""

    O1_UNEXPLAINED = "o1_unexplained"
    """RESIDUAL. The cell is closed, the graph does not route to it, and none
    of the four walls above holds. The bot cannot raise the skill and this
    census cannot say why either — which is the same failure one layer out."""

    SKILL_CATALOGUE_EMPTY = "skill_catalogue_empty"
    """RESIDUAL, and a DATA fault rather than a graph one: the catalogue offers
    this skill NOTHING — no recipe at any level, no resource at any level.

    It is a residual and not a wall because `WALL_LADDER_TOPPED` would other-
    wise absorb it: a skill whose rows vanished from the bundle has
    `above == 0 and gather_above == 0` and would classify as the most benign
    name the taxonomy has ("an honest end"), and `--check` would exit 0 on a
    corrupted catalogue. No live cell reaches this arm, so it has no coverage
    from real data and would fire for the first time in exactly the data-loss
    case; `census-gate.yml` runs the eight scripts and no pytest, so the suite's
    wall-count pin does not protect CI. This is the project's
    use-API-data-or-fail rule applied to the census's own inputs."""


RESIDUALS = frozenset({OpenRungGap.O1_SILENT_STALL.value,
                       OpenRungGap.O1_UNEXPLAINED.value,
                       OpenRungGap.SKILL_CATALOGUE_EMPTY.value})
"""The classes that must reach 0, mirroring the shed census's pair. The four
`WALL_*` classes are EXPLAINED and do not fail the gate."""

MIN_CELLS = 200
"""Blindness floor on the grid, enforced by `gen_open_rung.py --check` and not
only by the suite.

`--check`'s residual test is `[r for r in results if r.gap in RESIDUALS]`, and
an EMPTY census satisfies it — "0 cells, PASS 0" would print `GATE CLEAN` and
exit 0. The suite's floors cannot cover that path: `scripts/*` is
coverage-omitted and `census-gate.yml` runs the scripts without pytest. So the
floor lives here, where both the script and
`test_open_rung_completeness` read the same number.

200 against a current 288 (36 scenarios x 8 skills): enough headroom to retire
a scenario or two without flapping, far too tight for a collapsed sweep."""


@dataclass(frozen=True)
class RungInventory:
    """What the catalogue offers `skill` at level `level`, decomposed along the
    exact conjuncts `LevelSkill.is_applicable` reduces to.

    Every field is a COUNT or a code, never a verdict: `classify_gap` is the
    only place a verdict is formed, so the evidence and the judgement stay
    separable in the rendered matrix."""

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
    #: Whether the HIGHEST in-range resource still pays XP. `False` when there
    #: is no in-range resource at all — `best_gather_resource_drop` picks the
    #: highest, so a grey highest means every candidate is grey.
    gather_xp_positive: bool
    #: The drop item `best_gather_resource_drop` would grind, or None.
    gather_rung: str | None


@dataclass(frozen=True)
class RungResult:
    """One cell's answer. Flat and render-ready, like `ShedResult`."""

    scenario: str
    skill: str
    level: int
    target: int
    open_rung: bool
    routed: bool
    inventory: RungInventory
    gap: str

    @property
    def passed(self) -> bool:
        return self.gap == OpenRungGap.OPEN_RUNG.value


def census_state(scenario: ScenarioCharacter, game_data: GameData) -> WorldState:
    """`scenario` as a WorldState with the combat totals a live character
    wearing its declared loadout would report.

    `derive_combat_stats=True` is forced (module docstring): with it off the
    obtainability walk's monster-drop arm is dead for every item in the
    catalogue and the census measures the harness. `scenario_state` RAISES on
    an equipped code the catalogue does not know, which is the behaviour this
    census wants — a missing catalogue entry must fail loudly, never shrink
    the grid."""
    return scenario_state(
        dataclasses.replace(scenario, derive_combat_stats=True), game_data)


def routed_skills(state: WorldState, game_data: GameData) -> frozenset[str]:
    """The skills the ROOT GRAPH would send this character to grind.

    `resolve_root` is the wave-3 walk itself, driven whole — root AND the
    ordered `alternatives`, because `strategy_driver._resolve_step_goal` walks
    the alternatives whenever the root's step goal comes back None, so an
    alternative is every bit as routable as the head.

    `history=None`: the census is offline and must be deterministic, the same
    rule `shed_reachability_completeness.drive_selector` states."""
    resolution = resolve_root(
        state, game_data, CharacterObjective.from_game_data(game_data),
        NO_PROFILE_CONTEXT, None)
    return frozenset(
        goal.skill
        for goal in (resolution.root, *resolution.alternatives)
        if isinstance(goal, ReachSkillLevel))


def rung_inventory(skill: str, state: WorldState,
                   game_data: GameData) -> RungInventory:
    """The evidence for one cell, read straight off the catalogue.

    The obtainability walk is `skill_grind_target._obtainable` with the
    gatherable-drop union hoisted once — the SAME private walk
    `has_grind_target` runs, deliberately, so the census's decomposition and
    production's verdict cannot answer differently."""
    level = state.skills[skill]
    gatherable = game_data.gatherable_drop_items()
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
    obtainable = [code for code in xp_positive
                  if _obtainable(code, state, game_data, frozenset(), gatherable)]

    resource_levels = [res_level
                       for _, (res_skill, res_level) in game_data.resource_skills.items()
                       if res_skill == skill]
    gather_in = [lv for lv in resource_levels if lv <= level]
    return RungInventory(
        in_level=len(in_level),
        xp_positive=len(xp_positive),
        obtainable=len(obtainable),
        above=above,
        gather_in_level=len(gather_in),
        gather_above=len([lv for lv in resource_levels if lv > level]),
        gather_xp_positive=bool(gather_in)
        and skill_xp_positive(max(gather_in), level),
        gather_rung=best_gather_resource_drop(skill, level, game_data),
    )


def classify_gap(open_rung: bool, routed: bool,
                 inventory: RungInventory) -> OpenRungGap:
    """The verdict for one cell.

    EVERY WALL ARM IS POSITIVE EVIDENCE, AND THERE IS NO `else` WALL. That is
    the whole anti-vacuity design: a taxonomy whose last arm is a catch-all
    can never report `O1_UNEXPLAINED`, and a residual that cannot fire is a
    census that cannot fail. Two real holes are left open on purpose and both
    land in the residual — a skill whose highest in-range resource is
    XP-positive but has no drop item (so `best_gather_resource_drop` returns
    None while `gather_xp_positive` is True), with or without XP-positive
    recipes beside it. `test_the_unexplained_residual_can_fire` exhibits one.

    The routing test runs FIRST because a closed cell the graph routes to is
    the obligation's own failure whatever the catalogue reason is: naming a
    wall the graph never consults would launder a live stall into an
    explanation."""
    if open_rung:
        return OpenRungGap.OPEN_RUNG
    if routed:
        return OpenRungGap.O1_SILENT_STALL
    if (inventory.in_level + inventory.above == 0
            and inventory.gather_in_level + inventory.gather_above == 0):
        # BEFORE the topped-ladder arm, not after: "nothing above me" is true
        # of a finished skill AND of a skill whose catalogue rows are gone, and
        # only the ordering tells them apart. Getting this backwards is how a
        # data-loss defect wears the most reassuring name in the taxonomy.
        return OpenRungGap.SKILL_CATALOGUE_EMPTY
    if inventory.above == 0 and inventory.gather_above == 0:
        return OpenRungGap.WALL_LADDER_TOPPED
    if inventory.in_level == 0 and inventory.gather_in_level == 0:
        return OpenRungGap.WALL_BELOW_FIRST_RUNG
    if inventory.xp_positive == 0 and not inventory.gather_xp_positive:
        return OpenRungGap.WALL_ALL_RUNGS_GREY
    if (inventory.xp_positive > 0 and inventory.obtainable == 0
            and not inventory.gather_xp_positive):
        return OpenRungGap.WALL_RUNGS_UNOBTAINABLE
    return OpenRungGap.O1_UNEXPLAINED


def run_census(game_data: GameData) -> list[RungResult]:
    """Every `(scenario, skill)` cell, in scenario-declaration order then
    `SKILL_NAMES` order — both fixed vocabularies, so the matrix is
    byte-reproducible."""
    results: list[RungResult] = []
    for name, scenario in SCENARIOS.items():
        state = census_state(scenario, game_data)
        routed = routed_skills(state, game_data)
        for skill in SKILL_NAMES:
            level = state.skills[skill]
            open_rung = LevelSkill(skill=skill, target_level=level + 1
                                   ).is_applicable(state, game_data)
            inventory = rung_inventory(skill, state, game_data)
            results.append(RungResult(
                scenario=name, skill=skill, level=level, target=level + 1,
                open_rung=open_rung, routed=skill in routed,
                inventory=inventory,
                gap=classify_gap(open_rung, skill in routed, inventory).value))
    return results


def summary_line(results: list[RungResult]) -> str:
    """One-line completeness metric: cells, distinct `(skill, level)` pairs,
    PASS count, walled count, and every must-be-zero residual — including
    `skill_catalogue_empty`, so a bundle that lost a skill is visible in the
    headline and not only in the `--check` failure list."""
    walls = sum(1 for r in results
                if r.gap.startswith("wall_"))
    stalls = sum(1 for r in results if r.gap == OpenRungGap.O1_SILENT_STALL.value)
    unexplained = sum(1 for r in results
                      if r.gap == OpenRungGap.O1_UNEXPLAINED.value)
    absent = sum(1 for r in results
                 if r.gap == OpenRungGap.SKILL_CATALOGUE_EMPTY.value)
    pairs = {(r.skill, r.level) for r in results}
    routed = sum(1 for r in results if r.routed)
    return (f"{len(results)} cells over {len(pairs)} distinct (skill, level) "
            f"pairs; PASS {sum(1 for r in results if r.passed)}; "
            f"routed {routed}; walled {walls}; "
            f"o1_silent_stall {stalls}; o1_unexplained {unexplained}; "
            f"skill_catalogue_empty {absent}")


def routing_breakdown(results: list[RungResult]) -> str:
    """Which skills the graph actually routes to, and how many cells each.

    THE RESIDUAL'S SCOPE, STATED OUT LOUD. `o1_silent_stall` is
    `closed AND routed`, so a skill the graph never routes to can only ever be
    reported as an EXPLAINED wall, never as the residual — a "0 residuals"
    headline over 288 cells therefore promises less than the cell count
    implies. Computed rather than transcribed so the claim cannot rot: a
    scenario that widens the routed set updates this line by itself."""
    counts: dict[str, int] = {}
    for r in results:
        if r.routed:
            counts[r.skill] = counts.get(r.skill, 0) + 1
    routed = sum(counts.values())
    skills = ", ".join(
        f"{skill} {counts[skill]}"
        for skill in sorted(counts, key=lambda name: (-counts[name], name)))
    return (f"residual scope: {routed} of {len(results)} cells are ROUTED "
            f"({len(counts)} of {len(SKILL_NAMES)} skills) — {skills or 'none'}. "
            f"A closure in an unrouted skill can only be an explained wall.")


def render_matrix(results: list[RungResult]) -> str:
    """The cell x verdict matrix. Pure markdown — the generator script owns
    the file write."""
    lines = [
        "# O1 Open-Rung Completeness — Matrix",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_open_rung.py`.",
        ">",
        "> Obligation O1 (wave-3 resolution design §3.5): every "
        "`ReachSkillLevel(S, C+1)` reachable across the scenario set has an "
        "open, XP-positive rung, or the graph emits a named wall. The verdict "
        "column is `LevelSkill(S, C+1).is_applicable` — the one predicate "
        "`ReachSkillGoal`'s only action offers — cross-read against the "
        "catalogue evidence beside it.",
        ">",
        "> `routed` is what `decisions/root.resolve_root` would actually send "
        "this character to grind (root + alternatives). A closed cell that is "
        "routed is `o1_silent_stall`, the residual the obligation exists for.",
        ">",
        "> Every field `classify_gap` reads is a column here, so a verdict can "
        "be reconstructed from the row alone: `g-in`/`g-above` are the "
        "in-range and above-range resource counts and `g-xp+` is whether the "
        "HIGHEST in-range resource still pays XP — the three that separate "
        "`wall_all_rungs_grey` from `wall_below_first_rung`.",
        "",
        summary_line(results),
        "",
        routing_breakdown(results),
        "",
        "| Scenario | Skill | C | Target | Verdict | routed | in-level | "
        "xp+ | obtainable | above | g-in | g-above | g-xp+ | gather rung |",
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
            f"| `{inv.gather_rung}` |")
    lines.append("")
    return "\n".join(lines) + "\n"
