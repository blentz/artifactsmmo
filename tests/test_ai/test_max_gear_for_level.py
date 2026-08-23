"""A gear target that cannot be built today is a target WITH A BLOCKER, never a
target that was deleted."""
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
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
    if not weapon.attainable:
        assert weapon.blocker is not None, "unattainable target must name a blocker"


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
            assert target.blocker is not None, f"{slot}/{target.code} has no blocker"
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
    assert target.blocker == "skill:gearcrafting:5"


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
    assert target.blocker == "skill:woodcutting:40"


def test_unattainable_leaf_item_blocks_on_its_own_code(bundle_game_data):
    """A target with no recipe at all (a leaf item) that is not attainable now
    blocks on itself: `material:<code>`, the fallback blocker."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    target = objective._classify_target("wooden_stick", state)

    assert target.attainable is False
    assert target.blocker == "material:wooden_stick"
