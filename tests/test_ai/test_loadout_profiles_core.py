from artifactsmmo_cli.ai.loadout_profiles_core import bank_space_cost, gear_demand


def test_shared_gear_held_once():
    p1 = {"weapon_slot": "copper_dagger", "ring1_slot": "copper_ring"}
    p2 = {"weapon_slot": "copper_dagger", "helmet_slot": "iron_helmet"}
    d = gear_demand([p1, p2])
    assert d["copper_dagger"] == 1          # shared -> held once
    assert d["copper_ring"] == 1
    assert d["iron_helmet"] == 1


def test_ring_counts_two_within_one_profile():
    p = {"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"}
    assert gear_demand([p])["copper_ring"] == 2


def test_demand_is_max_not_sum():
    p1 = {"ring1_slot": "copper_ring", "ring2_slot": "copper_ring"}  # 2
    p2 = {"ring1_slot": "copper_ring"}                                # 1
    assert gear_demand([p1, p2])["copper_ring"] == 2                  # max, not 3


def test_bank_space_cost_excludes_equipped():
    p1 = {"weapon_slot": "copper_dagger", "helmet_slot": "iron_helmet"}
    p2 = {"weapon_slot": "copper_dagger", "boots_slot": "leather_boots"}
    # distinct gear = {copper_dagger, iron_helmet, leather_boots}; equipped copper_dagger
    assert bank_space_cost([p1, p2], {"copper_dagger"}) == 2
