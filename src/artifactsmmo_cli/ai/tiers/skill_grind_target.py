"""Pick the in-skill item to craft NOW to gain XP toward a skill gate.

Among items that are same-skill, in-level, OBTAINABLE (every recipe input
reachable by gather/craft/winnable-drop) and XP-POSITIVE (the craft is not in the
server's zero-xp band), prefer the CHEAPEST CHAIN TO BUILD — `acquire_steps`,
counted in actions over the whole recipe closure — then the highest skill level
(more XP); a full tie keeps the FIRST-SEEN candidate (insertion order) — there is
no string/alphabetical tie-break. Returns None when no such in-skill recipe
exists — the caller (the LevelSkill action's is_applicable / grind expansion,
always same-skill, never cross-skill) then has no craftable rung. Inclusion is a
recipe-table + reachability fact, free of bank-freshness false positives (only
`acquire_steps` ordering reads holdings).

`reserved`: recipe-input codes of the COMMITTED objective that the grind must not
consume (Trace 2026-06-11 19:22: copper_helmet would have eaten the 5 bars held
for copper_legs_armor).

OBTAINABILITY (Trace 2026-06-13): `skill_grind_target("weaponcrafting")` used to
pick `wooden_staff` (needs un-gettable `wooden_stick`), whose GatherMaterials
GOAP-failed; the arbiter then fell CROSS-SKILL to a gearcrafting grind, abandoning
the committed weaponcrafting objective. The recursive `_obtainable` filter excludes
such items so the reachable `copper_dagger` wins.
"""

from artifactsmmo_cli.ai.drop_obtainability import drop_obtainable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.min_crafts import min_crafts
from artifactsmmo_cli.ai.min_gathers import min_gathers
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive
from artifactsmmo_cli.ai.tiers.skill_grind_selection import (
    GrindCandidate,
    skill_grind_selection_pure,
)
from artifactsmmo_cli.ai.world_state import WorldState

GRIND_ALLOWS_GREY = True
"""The grind's standing exemption from the 2026-07-06 grey directive, named so
the oracle call below reads as a POLICY and not as a magic literal.

A skill grind fights a grey mob for the RUNG'S MATERIAL, not for its xp, so the
directive's preference — "grind the skill and craft the better item instead of
farming greys for a soon-obsolete one" — is not an alternative to suppress in
favour of: it is precisely what this walk is selecting. The exemption is the
same one `GatherMaterialsGoal(skill_grind=True)` passes on the emission side
(`ai/goals/gathering.py`), and it is deliberately NOT widened to any other
caller — see `ai/grey_farm.py`'s module docstring for the three structural
exemptions and the directive they bend around."""


def is_obtainable(code: str, state: WorldState, game_data: GameData,
                  visited: frozenset[str]) -> bool:
    """Recursive reachability: an item is obtainable when it is a gatherable
    resource drop, a fightable monster drop, OR craftable with EVERY recipe
    input recursively obtainable. A craftable item whose chain bottoms out in an
    un-gettable leaf (e.g. wooden_stick) is NOT obtainable. Cycle-safe.

    The mob-drop arm is the shared oracle `drop_obtainable`, the SAME verdict
    `GatherMaterialsGoal` emits fights from. It used to be a private
    `winnable + spawn_known` walk that never consulted the grey policy, so this
    function could call a rung buildable while emission refused the only edge
    that built it — the wool/iron_ring livelock (see the oracle's docstring).
    Passing the grind's own `allow_grey` keeps the two answers identical."""
    if code in visited:
        return False
    recipe = game_data.crafting_recipe(code)
    if recipe is None:
        if code in game_data.resource_drops.values():
            return True
        return drop_obtainable(code, state, game_data, allow_grey=GRIND_ALLOWS_GREY)
    nxt = visited | {code}
    return all(is_obtainable(mat, state, game_data, nxt) for mat in recipe)


def build_grind_candidates(skill: str, state: WorldState,
                           game_data: GameData) -> list[GrindCandidate]:
    """Hoist every in-skill craftable into a `GrindCandidate` (whole-chain
    `acquire_steps` against inventory+bank, recursive obtainability). No
    reservation filter — the caller (`skill_grind_target`) applies its own
    single-set filter.

    `acquire_steps` is `min_gathers + min_crafts` over the recipe CLOSURE, the
    same proved lower bound the planner's reachability gate uses. The old
    one-level `mats_missing` count is gone: it priced `sticky_sword` (5 missing
    `copper_bar`, really 51 actions) below `apprentice_gloves` (6 missing
    `feather`, really 7) and cost live R2D2 129 grind cycles at zero xp. Full
    rationale on `skill_grind_selection._beats`.

    `recipe_closure` is built ONCE per call and shared across candidates, so the
    added cost is one closure walk per rung rather than one per material."""
    bank = state.bank_items or {}
    owned = {code: state.inventory.get(code, 0) + bank.get(code, 0)
             for code in set(state.inventory) | set(bank)}
    recipes = game_data.crafting_recipes
    candidates: list[GrindCandidate] = []
    for code, stats in game_data.all_item_stats.items():
        if stats.crafting_skill != skill:
            continue
        recipe = game_data.crafting_recipe(code)
        if not recipe:
            continue
        acquire_steps = (min_gathers(code, 1, recipes, owned)
                         + min_crafts(code, 1, recipes, owned))
        candidates.append(GrindCandidate(
            code=code,
            craft_skill=stats.crafting_skill,
            craft_level=stats.crafting_level,
            acquire_steps=acquire_steps,
            obtainable=is_obtainable(code, state, game_data, frozenset()),
            # No objective context in this standalone path: the live grind goes
            # through the LevelSkill action (its is_applicable calls
            # skill_grind_target for the rung); wanted has no bearing there.
            wanted=False,
            # The server's level_penalty band: a rung more than
            # GREY_SKILL_GAP-1 levels below the current skill pays NO craft xp,
            # so grinding it can never reach the gate it was invoked to open
            # (rationale + the 14h livelock on `skill_grind_selection_pure`).
            xp_positive=skill_xp_positive(stats.crafting_level,
                                          state.skills.get(skill, 0)),
        ))
    return candidates


def skill_grind_target(skill: str, state: WorldState, game_data: GameData,
                       reserved: frozenset[str] = frozenset()) -> str | None:
    candidates = [
        c for c in build_grind_candidates(skill, state, game_data)
        if not any(mat in reserved for mat in (game_data.crafting_recipe(c.code) or {}))
    ]
    chosen = skill_grind_selection_pure(skill, state.skills.get(skill, 0), candidates)
    return chosen or None
