"""Score equipment against a monster's element profile and pick the best loadout."""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState


def weapon_score(weapon: ItemStats, monster_resistance: dict[str, int]) -> float:
    """Estimated damage-per-hit a weapon deals against a monster.

    Uses the simple model: per-element damage = attack * (1 - resistance%).
    Sums across elements (monsters/weapons typically have only one).
    """
    score = 0.0
    for elem in ELEMENTS:
        atk = weapon.attack.get(elem, 0)
        res_pct = monster_resistance.get(elem, 0)
        score += atk * max(0.0, 1.0 - res_pct / 100.0)
    return score


def armor_score(armor: ItemStats, monster_attack: dict[str, int]) -> float:
    """Estimated damage REDUCED per hit by an armor piece. Higher = better defense."""
    score = 0.0
    for elem in ELEMENTS:
        mon_atk = monster_attack.get(elem, 0)
        armor_res_pct = armor.resistance.get(elem, 0)
        score += mon_atk * armor_res_pct / 100.0
    return score


def _candidates_for_slot(
    slot: str, state: WorldState, game_data: GameData,
) -> list[ItemStats]:
    """Items the char owns (inventory + currently-equipped) that fit `slot`."""
    pool: set[str] = set()
    for code in state.inventory:
        if state.inventory[code] > 0:
            pool.add(code)
    for equipped_code in state.equipment.values():
        if equipped_code:
            pool.add(equipped_code)

    result: list[ItemStats] = []
    for code in pool:
        stats = game_data.item_stats(code)
        if stats is None or state.level < stats.level:
            continue
        if slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
            result.append(stats)
    return result


def pick_loadout(
    monster_code: str, state: WorldState, game_data: GameData,
) -> dict[str, str | None]:
    """Best {slot: item_code | None} loadout from owned items against `monster_code`.

    Considers only slots whose candidate items beat what's currently equipped
    on that slot. Returns the slot map; unchanged slots map to their current
    value. Caller compares with `state.equipment` to find the swap delta.
    """
    monster_atk = game_data.monster_attack(monster_code)
    monster_res = game_data.monster_resistance(monster_code)

    result: dict[str, str | None] = dict(state.equipment)
    # Each known equipment slot is independently optimized.
    all_slots: set[str] = set()
    for slots in ITEM_TYPE_TO_SLOTS.values():
        all_slots.update(slots)

    for slot in all_slots:
        candidates = _candidates_for_slot(slot, state, game_data)
        if not candidates:
            continue

        if slot == "weapon_slot":
            best = max(candidates, key=lambda s: weapon_score(s, monster_res))
        else:
            best = max(candidates, key=lambda s: armor_score(s, monster_atk))
        # Don't downgrade: only swap if the candidate beats the current item.
        current_code = state.equipment.get(slot)
        if current_code == best.code:
            continue
        current_stats = game_data.item_stats(current_code) if current_code else None
        if current_stats is None:
            result[slot] = best.code
            continue
        if slot == "weapon_slot":
            if weapon_score(best, monster_res) > weapon_score(current_stats, monster_res):
                result[slot] = best.code
        else:
            if armor_score(best, monster_atk) > armor_score(current_stats, monster_atk):
                result[slot] = best.code
    return result
