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
    """A target whose crafting skill is too low, and whose materials are ALSO
    unavailable, blocks on the skill: `skill:<name>:<level>`."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    target = objective._classify_target("copper_legs_armor", state)

    assert target.attainable is False
    assert target.blocker == "skill:gearcrafting:5"


def test_unattainable_leaf_item_blocks_on_its_own_code(bundle_game_data):
    """A target with no recipe at all (a leaf item) that is not attainable now
    blocks on itself: `material:<code>`, the fallback blocker."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    target = objective._classify_target("wooden_stick", state)

    assert target.attainable is False
    assert target.blocker == "material:wooden_stick"
