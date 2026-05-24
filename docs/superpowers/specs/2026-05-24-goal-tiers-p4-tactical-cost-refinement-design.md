# Goal Tiers — P4: Tactical Cost Refinement

Date: 2026-05-24
Status: Draft (for review)

The Tier-4 tactical layer from the goal-architecture vision. Rather than a new
decision tier, P4 sharpens the planner's *existing* emergent tactical choices —
which already arise from action `cost()` and goal `desired_state` — so the bot
fights with its best loadout and heals without wasting consumables.

Prior phases: P1 objective/gap/personality, P2 prerequisite graph, P3a–P3c the
strategy arbiter (sole goal selector). P4 changes no selection logic; it refines
combat-stat projection, the combat goal's prerequisites, and one action cost.

## Goal

1. **Loadout-swap before fights.** The bot equips its best on-hand loadout for a
   target before grinding it, and winnability (`predict_win`) reflects that best
   loadout — not whatever is currently equipped. Today `OptimizeLoadoutAction`
   exists and is in the action list, but the planner never picks it (`Fight` is a
   flat-cost single action, so a swap only *adds* cost), and `predict_win` reads
   current equipped stats — so the bot fights winnable-but-close monsters with
   suboptimal gear and mis-judges winnability.
2. **Consumable-vs-rest overheal avoidance.** Replace the static
   `UseConsumable=2.0` vs `Rest=10.0` costs so the bot rests for trivial heals
   instead of burning a potion, and uses a consumable only when the HP deficit
   justifies it.

Out of scope: craft-vs-buy (NPCs sell only consumables, already gold-cost-modeled);
any new tactical tier; bank gear in loadout selection; learned heal-value models.

## Design

### Part 1 — Loadout-swap before fights + winnability on best loadout

#### 1a. Extend `ItemStats` (`game_data.py`)

`ItemStats` currently captures `attack` (element→value), `resistance`
(element→%), `hp_restore` (consumable heal), and `skill_effects`. The item
loader (`_load_items`) parses effect codes `heal`, `attack_*`, `res_*`, and
gather-skill effects, and **ignores** the combat effects gear actually provides.
Add fields:

```python
dmg: int = 0                                          # global damage % bonus
dmg_elements: dict[str, int] = field(default_factory=dict)  # element -> dmg % bonus
critical_strike: int = 0                              # crit chance % bonus
initiative: int = 0                                   # initiative bonus
hp_bonus: int = 0                                     # flat max-HP bonus (gear)
```

In `_load_items`, extend the effect-parsing loop to also handle:
- `effect.code == "dmg"` → `stats.dmg = effect.value`
- `effect.code.startswith("dmg_")` → `stats.dmg_elements[elem] = effect.value`
- `effect.code == "critical_strike"` → `stats.critical_strike = effect.value`
- `effect.code == "initiative"` → `stats.initiative = effect.value`
- `effect.code == "hp"` → `stats.hp_bonus = effect.value`

(`ELEMENTS = ("fire","earth","water","air")`.) Existing `heal`/`attack_*`/`res_*`/
gather-skill handling is unchanged.

#### 1b. Loadout stat projection — `ai/equipment/projection.py` (new)

A pure function projecting a hypothetical loadout's combat stats as a **delta**
from the character's current totals (the server gives only totals, never base):

```python
@dataclass(frozen=True)
class ProjectedStats:
    attack: dict[str, int]
    dmg: int
    dmg_elements: dict[str, int]
    resistance: dict[str, int]
    critical_strike: int
    initiative: int
    max_hp: int

def project_loadout_stats(state, loadout, game_data) -> ProjectedStats:
    """Project combat stats if `loadout` (slot -> item_code | None) were equipped.

    projected = current totals + Σ_slot (picked_item_contribution
                                         − currently_equipped_item_contribution).
    Contributions come from ItemStats; a None/empty slot contributes nothing.
    Covers attack, dmg (global + per-element), resistance, critical_strike,
    initiative, and max_hp (via hp_bonus)."""
```

Per slot: look up the picked item's `ItemStats` and the currently-equipped item's
`ItemStats`; add the picked contribution and subtract the equipped one from the
running totals seeded with `state.attack`/`state.dmg`/`state.dmg_elements`/
`state.resistance`/`state.critical_strike`/`state.initiative`/`state.max_hp`.
Drop zero entries from dicts (consistent with `WorldState`). A slot whose picked
code equals the equipped code is a net-zero delta. Element/dict stats merge
key-by-key; scalars add.

#### 1c. Winnability on the optimal loadout (`combat.py`)

`predict_win(state, game_data, monster_code)` currently reads
`state.attack/dmg/dmg_elements/resistance/critical_strike/initiative` and
`state.max_hp`. Change it to evaluate the **best on-hand loadout**:

```python
loadout = pick_loadout(monster_code, state, game_data)      # inventory + equipped
projected = project_loadout_stats(state, loadout, game_data)
# use projected.* in place of state.* for the player side of the fight
```

The monster side is unchanged. `combat.py` imports `pick_loadout`
(`ai/equipment/scoring.py`) and `project_loadout_stats`
(`ai/equipment/projection.py`) — both pure, importing only `world_state`/
`game_data`, so no import cycle. `_round_half_up`/`_element_damage`/`_expected_hit`/
MAX_TURNS/initiative logic are unchanged; only the player's stat source becomes
the projected loadout.

Consequence: `_is_winnable` / `_pick_winnable_monster` / `_winnable_farm_target`
(player.py) now mean "winnable with my best available loadout." No signature
change — the projection happens inside `predict_win`.

#### 1d. Equip the optimal loadout before grinding (`goals/grind_character_xp.py`)

The GOAP planner terminates on `goal.is_satisfied(state)` (not `desired_state`),
and `is_satisfied` takes only `state` — no `game_data`. So the loadout
prerequisite is expressed through `is_satisfied` with the goal holding the
context it needs:

- `GrindCharacterXPGoal` gains a `game_data` constructor argument (so it can
  compute `pick_loadout(target, state, game_data)` inside `is_satisfied`). The
  construction site — the driver's `objective_step_goal` — passes it:
  `GrindCharacterXPGoal(target_monster=..., initial_xp=..., game_data=game_data)`.
  (Confirm during implementation this is the only live construction site; the
  P3c cutover removed the player-side fallback grind. Update any others found.)
- `is_satisfied(state)` becomes: **xp increased this cycle AND the loadout is
  already optimal for the target** —
  `state.xp > self._initial_xp and _loadout_optimal(state)`, where
  `_loadout_optimal(state)` is True when `pick_loadout(self._target, state,
  self._game_data)` matches `state.equipment` on every slot it would change (i.e.
  the swap plan is empty). Reuse `OptimizeLoadoutAction`'s own swap-plan logic so
  "optimal" is defined identically across the goal, the action, and `predict_win`.
- `relevant_actions`: include the existing `OptimizeLoadoutAction(target_monster)`
  (already constructed per-monster in the player's action list) in the goal's
  relevant subset alongside Fight/Rest/UseConsumable/Move.
- `value` (A* heuristic): when the loadout is not yet optimal, the goal is
  "further" — keep `value` finite and let `relevant_actions` + `is_satisfied`
  drive the swap; no negative costs.

`OptimizeLoadoutAction.apply` already swaps `state.equipment` toward the optimal
loadout in simulation (verify; if it does not update `equipment`, fix `apply` to
set it so the planner can see the post-swap state). The planner then plans
`OptimizeLoadout → Fight`: after the swap, `_loadout_optimal` is True and a fresh
`Fight` satisfies the goal. When the loadout is already optimal at cycle start,
`is_satisfied` needs only xp progress → the plan is just `Fight` (the swap action
yields an empty plan / is not chosen).

**Cross-check with P3b.1:** winnability now projects the optimal loadout, and the
grind goal equips it before fighting — so the stats `predict_win` assumed are the
stats the bot actually fights with. This closes the gap where winnability over- or
under-rated a monster relative to the gear the bot brought.

### Part 2 — Consumable-vs-rest overheal avoidance (`actions/consumable.py`)

Replace `UseConsumableAction`'s static `cost = 2.0` with an overheal-aware cost.
Let `deficit = state.max_hp − state.hp` and `restore = hp_restore of the best
consumable in inventory` (the one `_best_consumable` would use):

- `deficit >= restore` → the heal is not wasted → `cost = 2.0` (cheap, beats
  `Rest`'s 10.0 → planner uses the consumable).
- `deficit < restore` → using the potion overheals/wastes it → `cost` returns a
  value **above** `Rest`'s 10.0 (e.g. `100.0`) so the planner rests for the small
  top-up instead.

`RestAction.cost` stays flat (`10.0`). `RestoreHPGoal` still heals to full; with
this cost the planner picks `Rest` for trivial deficits and `UseConsumable` for
substantial ones. No reserve-count or value model (out of scope). When no
consumable is in inventory, `UseConsumable` is already not applicable, so only
`Rest` is available — unchanged.

## Error handling

- `project_loadout_stats`: an item code with no `ItemStats` contributes nothing
  (treated as empty) — never raises; unknown gear is rare and low-stakes.
- `predict_win`: if `pick_loadout` returns the current equipment (nothing better
  on hand), the projection equals current stats → behavior identical to today.
- `UseConsumable.cost`: when `_best_consumable` is None (no consumable), the
  action is not applicable and cost is not consulted; guard against a None restore
  by treating it as "not applicable" rather than dividing/comparing.
- Pure logic throughout; no API, no `except Exception`.

## Testing

Per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`ItemStats` parsing:** a gear item with `dmg`, `dmg_fire`, `critical_strike`,
  `initiative`, `hp` effects populates the new fields; a consumable still
  populates `hp_restore`; an attack/res weapon/armor unchanged.
- **`project_loadout_stats`:** swapping a higher-attack weapon raises projected
  attack by the delta; swapping in hp_bonus armor raises projected max_hp;
  picking the already-equipped item is a net-zero projection (equals current);
  an unknown item code contributes nothing; per-element and scalar stats combine
  correctly.
- **`predict_win` on optimal loadout:** a monster unwinnable with current gear but
  winnable after equipping a better in-inventory weapon → `predict_win` True; with
  no better gear on hand → identical to the current-stats result.
- **`GrindCharacterXPGoal`:** `is_satisfied` is False when xp increased but the
  loadout is not optimal, True only when both hold; with a suboptimal loadout the
  planner's plan begins with `OptimizeLoadout(target)` then `Fight`; with the
  optimal loadout already equipped the plan is just `Fight` (no redundant swap).
- **`OptimizeLoadoutAction.apply`:** updates simulated `state.equipment` to the
  optimal loadout so the planner sees the swap take effect (and `_loadout_optimal`
  flips True after it).
- **`UseConsumable.cost`:** `deficit >= restore` → 2.0 (chosen over Rest);
  `deficit < restore` → > 10.0 (Rest chosen); integration: a near-full character
  with a big potion rests; a badly-hurt character with a matching potion drinks it.

## Files

- Modify `src/artifactsmmo_cli/ai/game_data.py` — `ItemStats` fields +
  `_load_items` effect parsing.
- Create `src/artifactsmmo_cli/ai/equipment/projection.py` — `ProjectedStats` +
  `project_loadout_stats`.
- Modify `src/artifactsmmo_cli/ai/combat.py` — `predict_win` projects the optimal
  loadout's stats for the player side.
- Modify `src/artifactsmmo_cli/ai/goals/grind_character_xp.py` — `game_data` ctor
  arg + loadout prerequisite in `is_satisfied`/`relevant_actions`.
- Modify `src/artifactsmmo_cli/ai/strategy_driver.py` — `objective_step_goal`
  passes `game_data` to `GrindCharacterXPGoal`.
- Modify `src/artifactsmmo_cli/ai/actions/optimize_loadout.py` — ensure `apply`
  updates simulated `state.equipment` to the optimal loadout (only if it does not
  already).
- Modify `src/artifactsmmo_cli/ai/actions/consumable.py` — overheal-aware `cost`.
- Tests: `tests/test_ai/test_game_data.py`, new `test_equipment_projection.py`,
  `test_combat.py`, `test_grind_character_xp.py`, `test_actions*` (optimize_loadout,
  consumable).

## Out of scope (later phases)

- P5 pluggable AI personalities (weight skill/level/balanced).
- Craft-vs-buy refinement; bank gear in loadout selection; reserve-count or
  learned consumable-value heal policy.
