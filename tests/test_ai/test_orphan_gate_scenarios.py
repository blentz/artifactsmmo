"""The gathering-demand gate, driven over the REAL walk (`resolve_root`), not
over `_orphan_skill_roots` called directly with an injected `offered`.

Three suites, all against the committed bundle
(`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`, loaded exactly as
`scripts/gen_open_rung.py` loads it — see `conftest.bundle_game_data`) so
neither suite nor the offline census can disagree about the data. Neither
makes an API call.

(A) `TestOrphanGroupNeverEmpties` pins the spec's two predictions about the
NEGATIVE branch and the anti-`Wait` floor: the orphan group never empties
across every entry in `ai.scenario.SCENARIOS`, and cooking — which gathers
nothing and so never enters the third conjunct — is the reason why.

(B) `TestGatheringDemandPositiveBranch` closes a real gap the brief's sweep
left open: no committed scenario demanded a gathering skill through
`resolve_root` from a GEAR SIBLING, so "the skill is KEPT when something
genuinely needs it" had only ever been proven by
`test_orphan_skill_roots_demand.py`'s unit tests, which call
`_orphan_skill_roots` directly with a hand-built `offered` list. This suite
drives the SAME shape end to end, seeded from an `ObtainItem` gear sibling.

(C) `TestCookingDemandsFishing` drives THE CANONICAL CHAIN — `cooking rung ->
`cooked_shrimp` -> `shrimp` -> fishing@10` — end to end through the real
`resolve_root`. It is the regression pin for the TWO-PASS demand fix; read the
next section for what it replaced.

ON FISHING VS. MINING — A CONCERN THAT TURNED OUT TO BE THE BUG. This module
originally said the brief's fishing shape "does not reach `resolve_root`
against the COMMITTED bundle, and the reason is structural, not a fixture
gap", and gave this reason:

* `_orphan_skill_roots`'s `demand` was computed from `offered = [root,
  *ordered]` — the walk's OWN root plus its gear siblings and the trunk —
  BEFORE the orphan roots (including cooking's own `ReachSkillLevel`) are
  appended to the resolution. Cooking's own rung was therefore never a member
  of the set `gather_demand` reads, so it could not seed demand for anything,
  fishing included, no matter what the catalogue contained.

That reasoning was correct and the conclusion drawn from it was wrong: it is a
description OF THE DEFECT, not of the catalogue. Read alongside the second
finding, which still stands —

* Exhaustively over all 522 items in the committed bundle, the ONLY item that
  consumes any fish-gathered material (`shrimp`, `golden_shrimp`, `gudgeon`,
  `trout`, `bass`, `salmon`, `swordfish`, `lava_fish`, `algae`, `shell`,
  `small_pearls`, `holey_boot`) above fishing@1 is `cooked_shrimp`
  (`cooking`, needs `shrimp`, fishing@10) — a `consumable`, which is not a
  gear-sheet candidate (`_gear_nameable_skills`'s docstring) and is excluded
  from `combat_deficit`'s pool too (`ITEM_TYPE_TO_SLOTS` has no `consumable`
  entry), so it can never become `root` or a gear sibling either. The one
  `utility`-type item gated above fishing@1 (`enhanced_health_splash_potion`,
  alchemy@50, needs `lava_fish`/fishing@50) IS eligible for
  `WhichSlotClosesTheFight`'s combat-deficit pool, but is dominated in its
  cost-per-margin greedy walk by cheaper level-10 boost potions in every
  monster/state combination tried — confirmed by an exhaustive sweep over
  every monster in the bundle at level 50 with otherwise-adequate gear.

— the two together say something much stronger than "this bundle happens not
to have the shape": NO gear root can EVER demand fishing, so COOKING is
fishing's only demand route, and cooking is itself an orphan. A gate that
cannot see one orphan's demand for another therefore did not narrow fishing,
it DELETED it — for every character, including the three on the live fleet
(HAL, C3P0, Lor) whose cooking rung genuinely could not be served without it.

`_orphan_skill_roots` is now TWO-PASS: conjuncts 1 and 2 decide a candidate
set, the candidates seed `gather_demand` alongside `offered`, and only then is
conjunct 3 applied. The chain reaches `resolve_root` against this very bundle
— see (C) — so the substitution the rest of this docstring used to argue for
is no longer needed. MINING stays in suite (B) on its own merits: it seeds
from an ordinary UN-blocked `ObtainItem` gear SIBLING, which is the other
seeding arm and the one (C) does not exercise.
"""

import dataclasses

from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.scenario import SCENARIOS
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.audit.open_rung_completeness import census_state


class TestOrphanGroupNeverEmpties:
    """The gate, driven over the census scenario set through the REAL walk.

    The spec makes two predictions and this pins both: the orphan group never
    empties (so `Wait` stays unreachable), and cooking is the floor that
    guarantees it. Runs `resolve_root` rather than `_orphan_skill_roots`
    directly, because the walk is what production calls.

    NOT marked `integration`: the sweep loads the committed bundle and makes
    no API call, and the pre-commit hook runs `-m "not integration"` — a
    marker here would hide this suite from the gate it exists to protect
    (controller ruling).
    """

    def test_the_orphan_group_never_empties_across_the_scenario_set(
            self, bundle_game_data):
        """Measured today: cooking admitted in 44 of 44 scenarios, the group
        empty in 0 of 44.

        Would this still pass with the third conjunct deleted from
        `_orphan_skill_roots`? Yes — deleting a FILTER can only add roots, not
        remove the floor — so this test does not kill a conjunct-3 mutant on
        its own; it kills a mutant that breaks the floor itself (e.g. cooking
        wrongly excluded from admission, or the third conjunct inverted to
        `and` so cooking must ALSO be "in demand" — cooking is never in
        `gather_demand`'s output since it gathers nothing, so an inverted
        conjunct empties every scenario where no OTHER orphan is admitted
        either). `TestGatheringDemandPositiveBranch` below covers the
        conjunct-3-deleted mutant that this sweep structurally cannot.
        """
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        empty = []
        for name, scenario in SCENARIOS.items():
            state = census_state(scenario, gd)
            res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
            skill_roots = [g for g in (res.root, *res.alternatives)
                           if isinstance(g, ReachSkillLevel)]
            if not skill_roots:
                empty.append(name)
        assert empty == [], (
            f"{len(empty)} scenarios lost every skill root, which is the "
            f"`Wait` fall-through this seam exists to prevent: {empty}")


def _mining_gated_state(bundle_game_data, mining: int):
    """A character whose `boots_slot` target is `iron_boots` — unblocked on
    the crafting-skill gate but whose material closure (`iron_bar` ->
    `iron_ore`) bottoms out at mining@10 — built from `l24_fisher_cooking_rung`
    by `dataclasses.replace`.

    HAND-BUILT RATHER THAN TAKEN AS-IS FROM `SCENARIOS`, because no committed
    scenario combines: (1) combat stats strong enough that `gear_target_tier`
    (`tier_progress.gear_target_tier`) clears past rung 1 to the iron rung —
    `l24_fisher_cooking_rung`'s `_IRON_SET` loadout already does this; (2)
    `gearcrafting >= 10` so `iron_boots` (crafting_level 10) is NOT
    skill-blocked, which would route through `ReachSkillLevel('gearcrafting',
    ...)` instead and never surface `iron_boots` as a seed at all —
    `l24_fisher_cooking_rung`'s own `gearcrafting: 5` blocks it, so this is
    raised to 10; and (3) `boots_slot` empty so `iron_boots` is actually
    ASSIGNED as the slot's target (a slot already wearing its tier-appropriate
    item gets no target at all) — `l24_fisher_cooking_rung` wears
    `iron_boots` already, so this clears it. Only those three fields are
    changed; everything else (level, the rest of `_IRON_SET`, the other seven
    skills) is the scenario's own committed loadout, chosen because it is
    already the "fisher on a cooking rung" shape this task's brief describes
    — see the module docstring for why the demanded skill is mining rather
    than fishing.
    """
    base = SCENARIOS["l24_fisher_cooking_rung"]
    sc = dataclasses.replace(
        base,
        skills={**base.skills, "gearcrafting": 10, "mining": mining},
        equipment={**base.equipment, "boots_slot": None})
    return census_state(sc, bundle_game_data)


class TestGatheringDemandPositiveBranch:
    """`resolve_root` end to end, not `_orphan_skill_roots` called directly
    and not with injected `offered` — the coverage the brief's sweep above
    does not provide (Ruling 9): 0 of the 44 committed scenarios demand any
    gathering skill through `resolve_root`, so the positive half of the third
    conjunct had never been driven through the real walk.
    """

    def test_a_genuinely_demanded_skill_is_kept_alongside_the_floor(
            self, bundle_game_data):
        """At mining=5, `iron_boots` (the assigned, UN-blocked target for the
        empty `boots_slot`) needs `iron_bar` -> `iron_ore`, gated at
        mining@10 — genuinely unmet. `resolve_root`'s root-plus-alternatives
        must contain `ReachSkillLevel('mining', 10)`, AT THE DEMANDED LEVEL
        (10), not `current + 1` (6).

        VACUITY: would this still pass with the third conjunct deleted from
        `_orphan_skill_roots`? Yes — an unconditional admission still admits
        mining — so this half alone cannot kill a conjunct-3-deleted mutant.
        It kills the mutant that breaks the SEEDING side instead: e.g. a
        `_seed` that stops handling `ObtainItem` roots, or a `gather_demand`
        that stops walking `requirement_closure` — either would make `demand`
        empty and drop `mining` from the result here even though it is
        genuinely needed. The negative half below is what dies on
        conjunct-3-deleted; see its docstring.
        """
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = _mining_gated_state(gd, mining=5)
        res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
        offered = (res.root, *res.alternatives)
        assert ReachSkillLevel(skill="mining", level=10) in offered
        # Cooking survives alongside it — the floor and a genuine demand are
        # not exclusive.
        assert any(isinstance(g, ReachSkillLevel) and g.skill == "cooking"
                   for g in offered)

    def test_once_satisfied_the_demanded_skill_disappears_while_cooking_survives(
            self, bundle_game_data):
        """The mirror: raise mining to 10 (the gate `iron_boots`'s closure
        demands) and the ONLY thing that changes is that the mining root
        disappears — cooking, the unconditional floor, survives untouched.

        THIS is the half that dies if the third conjunct is deleted from
        `_orphan_skill_roots`: without it, every skill admitted by conjuncts 1
        and 2 is offered regardless of demand, so `ReachSkillLevel('mining',
        11)` (the `current + 1` an unconditional admission would emit) would
        still appear here even though mining is now satisfied. A presence
        assertion alone (this test's predecessor above) cannot die that way;
        this absence assertion can and does.
        """
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = _mining_gated_state(gd, mining=10)
        res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
        offered = (res.root, *res.alternatives)
        assert not any(isinstance(g, ReachSkillLevel) and g.skill == "mining"
                       for g in offered)
        assert any(isinstance(g, ReachSkillLevel) and g.skill == "cooking"
                   for g in offered)


CHAIN_CELL = "l11_band_floor"
"""A COMMITTED scenario — `dataclasses.replace` is used only for the mirror
half, and only on `fishing`. At its declared `cooking=12, fishing=5` the
cooking rung's grind target is `cooked_shrimp`, whose closure bottoms out at
`shrimp`/fishing@10: HAL's live shape (`cooking ->17`, `fishing=8`) at this
cell's own levels. Three other committed cells carry it identically
(`l19_band_edge`, `l21_grey_material_grind`, `l22_grey_rung_grind`) — pinned
as a set in `test_fisher_cooking_rung.test_every_scenario_now_routes_cooking`,
so this suite can stay on one cell and say why."""

CHAIN_RUNG = 10
"""The fishing level `cooked_shrimp`'s closure asks for. NOT `current + 1`
(6): a demanded skill is offered the level that was ASKED FOR, because a
one-rung nudge has no destination and re-emits forever."""


class TestCookingDemandsFishing:
    """THE CANONICAL CHAIN, end to end through the real `resolve_root`:

        cooking rung -> `cooked_shrimp` -> `shrimp` -> fishing@10

    This is the case the one-pass gate could not see, and the reason it could
    not is worth restating where the test lives: `resolve_root` computes
    `offered = [root, *ordered]` and hands it to `_orphan_skill_roots`, so by
    construction `offered` cannot contain an orphan root — and COOKING is an
    orphan. Since `cooked_shrimp` is a `consumable` (no gear sheet, no combat
    deficit) and is the only item in the bundle naming fishing above level 1,
    cooking is fishing's ONLY demand route. One-pass therefore removed fishing
    from every character.

    Both halves run the REAL walk, against a COMMITTED scenario, with no
    injected `offered` and no API call.
    """

    def test_a_cooking_rung_that_needs_a_fish_gets_a_fishing_root(
            self, bundle_game_data):
        """`l11_band_floor` as committed: cooking=12, fishing=5.
        `resolve_root`'s root-plus-alternatives contains
        `ReachSkillLevel('fishing', 10)` — the DEMANDED level, not `current +
        1` (6) — and the cooking rung that demanded it survives alongside.

        WHICH MUTANT THIS HALF KILLS: the two-pass fix itself. Revert
        `_orphan_skill_roots` to computing `demand` from `offered` alone —
        i.e. drop the candidate orphans from the `gather_demand` call — and
        this assertion fails, because cooking's rung is not in `offered` and
        nothing else in the catalogue can ask for fishing. It also kills a
        broken `_seed` (a `ReachSkillLevel` arm that stops calling
        `skill_grind_target`, or a `gather_demand` that stops walking
        `requirement_closure`), and the `demand.get(skill, ...)` level lookup
        collapsing back to `current + 1`.

        WHAT IT CANNOT KILL: deleting the third conjunct. An unconditional
        admission still admits fishing, so a presence assertion survives a
        removed filter — the mirror below is the half that dies.
        """
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        state = census_state(SCENARIOS[CHAIN_CELL], gd)
        # The premise, stated rather than assumed: the gate is genuinely unmet.
        assert state.skills["fishing"] < CHAIN_RUNG
        res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
        offered = (res.root, *res.alternatives)
        assert ReachSkillLevel(skill="fishing", level=CHAIN_RUNG) in offered
        assert any(isinstance(g, ReachSkillLevel) and g.skill == "cooking"
                   for g in offered)

    def test_raising_fishing_to_the_gate_removes_the_root_and_keeps_cooking(
            self, bundle_game_data):
        """The mirror: raise fishing to 10 — the level `cooked_shrimp`'s
        closure asks for — changing nothing else, and the fishing root
        disappears entirely while the cooking rung that demanded it is
        untouched. That is R2D2's and Robby's live line (fishing 14 and 13
        against a cooking rung asking 10) and the outcome the gate exists to
        produce.

        WHICH MUTANT THIS HALF KILLS: the third conjunct. Delete `and (skill
        not in gathering or skill in demand)` and every skill conjuncts 1 and
        2 admit is offered regardless of demand, so `ReachSkillLevel('fishing',
        11)` — the `current + 1` an unconditional admission emits — appears
        here even though fishing is now satisfied. `assert not any(... ==
        "fishing")` is keyed on the SKILL, not on a level, so it dies on that
        mutant whatever level the mutant would have emitted. It also kills an
        inverted unmet test in `gather_demand` (`>` for `<`, or `<=` for `<`),
        which would keep asking for a gate the character has already cleared.

        WHAT IT CANNOT KILL: the two-pass fix. With demand read from `offered`
        alone, fishing is absent here too — which is exactly why the presence
        half above is not redundant with this one.
        """
        gd = bundle_game_data
        objective = CharacterObjective.from_game_data(gd)
        base = SCENARIOS[CHAIN_CELL]
        state = census_state(
            dataclasses.replace(
                base, skills={**base.skills, "fishing": CHAIN_RUNG}), gd)
        res = resolve_root(state, gd, objective, NO_PROFILE_CONTEXT, None)
        offered = (res.root, *res.alternatives)
        assert not any(isinstance(g, ReachSkillLevel) and g.skill == "fishing"
                       for g in offered)
        assert any(isinstance(g, ReachSkillLevel) and g.skill == "cooking"
                   for g in offered)
