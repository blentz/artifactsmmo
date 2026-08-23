"""A gear target that cannot be built today is a target WITH A BLOCKER, never a
target that was deleted."""
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.tier_progress import gear_target_tier
from tests.test_ai.fixtures import make_state


def test_an_unattainable_target_is_kept_and_carries_its_blocker(bundle_game_data):
    """near_term_gear drops these. Live 2026-08-22 that left Robby with the
    battlestaff he was already wearing as his best weapon target, so no weapon
    root existed and weaponcrafting had no demand path at all."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    targets = objective.gear_targets_with_blockers(state, None)

    assert "weapon_slot" in targets, "the weapon slot must produce a target"
    weapon = targets["weapon_slot"]
    assert weapon.attainable is False
    assert weapon.blocking_skill is None, \
        "this target is material-blocked, not skill-blocked"
    assert weapon.blocker == "wooden_stick", \
        "unattainable target must name its exact blocking material"


def test_tier_cap_bounds_the_candidate_set(bundle_game_data):
    """I2: every prior test in this file builds its state from `make_state()`,
    whose `attack={}` makes `predict_win` False against every monster, so
    `next_uncleared_tier` is always 1 and `gear_target_tier`'s cap is only
    ever exercised in its degenerate corner (tier 1). `l10_gearcrafting_gap`
    has real derived combat stats and clears through tier 10 -- pins that the
    cap actually EXCLUDES higher-tier items rather than merely defaulting to
    the lowest possible one. `artifact1_slot` is the witness: uncapped
    (`target_gear`, the perfect sheet) it is `sandwhisper_codex` (level 50);
    capped to tier 10 it must be `novice_guide` (level 10), never the
    level-50 item."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = scenario_state(SCENARIOS["l10_gearcrafting_gap"], gd)

    tier = gear_target_tier(state, gd, None)
    assert tier == 10, "scenario fixture drifted; re-derive the expected tier"

    targets = objective.gear_targets_with_blockers(state, None)
    assert "artifact1_slot" in targets
    capped = targets["artifact1_slot"]
    assert capped.code == "novice_guide"
    capped_stats = gd.item_stats(capped.code)
    assert capped_stats is not None and capped_stats.level <= tier

    perfect_code = objective.target_gear.get("artifact1_slot")
    assert perfect_code == "sandwhisper_codex"
    perfect_stats = gd.item_stats(perfect_code)
    assert perfect_stats is not None and perfect_stats.level > tier, (
        "the perfect-sheet target must be ABOVE the tier cap for this "
        "assertion to prove the cap excludes it")


def test_attainable_target_is_reported_attainable_with_no_blocker(bundle_game_data):
    """Fix-round-2 (2026-08-23): the happy-path return in `_classify_target`
    (`attainable=True, blocker=None`) had ZERO assertion coverage — a mutant
    that replaced it with `attainable=False, blocker="MUTATION_PROBE"` (every
    attainable target reported as blocked) still passed every existing test,
    because they only assert inside `if not target.attainable:` branches.
    `copper_helmet` is verified attainable under this fixture state (level 30,
    weaponcrafting 10 — gearcrafting defaults to 1, but copper_helmet's
    materials/skill are within reach): pin that `helmet_slot` reports it as
    attainable with no blocker."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    targets = objective.gear_targets_with_blockers(state, None)

    assert "helmet_slot" in targets
    helmet = targets["helmet_slot"]
    assert helmet.code == "copper_helmet"
    assert helmet.attainable is True
    assert helmet.blocker is None
    assert helmet.blocking_skill is None


def test_every_unattainable_target_names_a_blocker(bundle_game_data):
    """The invariant whose absence caused the freeze: nothing is dropped for
    unattainability without saying what would unblock it."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    examined_unattainable = 0
    for slot, target in objective.gear_targets_with_blockers(state, None).items():
        if not target.attainable:
            examined_unattainable += 1
            assert target.blocker is not None or target.blocking_skill is not None, \
                f"{slot}/{target.code} has no blocker"
    # Guard against vacuous success: at level 30 with weaponcrafting 10 the
    # weapon_slot target (wooden_staff, materials from an unwinnable monster)
    # is unattainable, so this loop must actually examine it at least once.
    assert examined_unattainable > 0, "no unattainable target was examined"


def test_already_equipped_best_item_is_dropped_not_reoffered(bundle_game_data):
    """A slot whose current item already matches the best candidate's value
    produces no target at all — it is not re-offered as its own blocker."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10},
                       equipment={"helmet_slot": "copper_helmet"})

    targets = objective.gear_targets_with_blockers(state, None)

    assert "helmet_slot" not in targets


def test_skill_blocked_target_names_skill_and_level(bundle_game_data):
    """A target whose crafting skill is too low, and whose materials also
    happen to be unavailable, blocks on the skill: `skill:<name>:<level>`.
    (This case alone does not prove the skill check runs BEFORE
    `is_attainable_now` — both blockers would apply either way. See
    `test_skill_gate_blocks_even_when_materials_are_reachable` for the case
    that pins the ordering.)"""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    target = objective._classify_target("copper_legs_armor", state)

    assert target.attainable is False
    assert target.blocker is None, \
        "a skill-blocked target must not also carry a material blocker"
    assert target.blocking_skill == "gearcrafting"
    assert target.blocking_skill_level == 5


def test_skill_gate_blocks_even_when_materials_are_reachable(bundle_game_data):
    """Fix-round-1 (2026-08-23): `_classify_target` consulted
    `is_attainable_now` FIRST, and that function is materials-only — it never
    inspects `crafting_skill`/`crafting_level`. So the skill-gate branch was
    unreachable for any target whose materials happened to be reachable: 17
    live-bundle items (e.g. `maple_plank`, woodcutting@40 with the character
    at woodcutting 30) reported `attainable=True, blocker=None` although the
    character cannot perform that craft at all — an earlier check masking a
    later one, the same shape Task 5 fixed in `objective_step_goal`.

    `maple_plank` needs only `maple_wood` (a gatherable raw, always
    attainable-now) so `is_attainable_now("maple_plank", ...)` is True on its
    own — this pins that the skill gate still wins."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"woodcutting": 30})

    target = objective._classify_target("maple_plank", state)

    assert target.attainable is False
    assert target.blocker is None, \
        "a skill-blocked target must not also carry a material blocker"
    assert target.blocking_skill == "woodcutting"
    assert target.blocking_skill_level == 40


def test_unattainable_leaf_item_blocks_on_its_own_code(bundle_game_data):
    """A target with no recipe at all (a leaf item) that is not attainable now
    blocks on itself: the fallback material blocker is the target's own
    code, with no skill involved."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    target = objective._classify_target("wooden_stick", state)

    assert target.attainable is False
    assert target.blocking_skill is None
    assert target.blocker == "wooden_stick"
