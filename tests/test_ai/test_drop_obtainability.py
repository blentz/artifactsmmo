"""The shared drop oracle, and THE test that closes the selection/emission split.

`ai/drop_obtainability` is the single answer to "can this character obtain item
X by killing something?". Two sides consult it:

  * SELECTION — `tiers/skill_grind_target.is_obtainable`,
    `tiers/objective.is_attainable_now`, `tiers/strategy._producible`: pure
    game-data walks that decide WHAT to pursue, with no action list to consult.
  * EMISSION  — `ai/drop_fight_selection.select_drop_fight`: turns the verdict
    into the one `FightAction` a goal plans with.

They used to answer differently on four axes (liveness, grey policy, choice
rule, policy source) and the L21 wool/iron_ring grind livelocked in the gap.
`test_selection_and_emission_never_disagree` is the property that would have
caught it: over EVERY dropped item in the real catalog, in every scenario
state, under both grey policies, the oracle's verdict and the emitted fight
agree — with the oracle's ONE named residual (an action pool carrying no
FightAction for an approved dropper) asserted EMPTY for the production pool.
"""

from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.drop_fight_selection import select_drop_fight
from artifactsmmo_cli.ai.drop_obtainability import drop_obtainable, fightable_droppers
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


def _fighter(**overrides) -> WorldState:
    """A character with real attack, so a low-HP fixture monster is winnable.

    Level 12 so that a level-1 fixture monster is GREY (>= 11 levels below,
    the xpPositive gate's rule) while a level-9 one is still xp-positive."""
    base = dict(level=12, x=0, y=0, hp=200, max_hp=200,
                attack={"fire": 40}, dmg=20, initiative=50)
    base.update(overrides)
    return make_state(**base)


def _gd(**monster_levels: int) -> GameData:
    """A GameData with harmless, spawned monsters at the given levels."""
    gd = GameData()
    gd._monster_level = dict(monster_levels)
    gd._monster_locations = {code: [(1, 1)] for code in monster_levels}
    fill_monster_stat_defaults(gd)
    for code in monster_levels:
        gd._monster_hp[code] = 10
    return gd


# --------------------------------------------------------------------------
# The oracle's three gates, one test each.
# --------------------------------------------------------------------------

def test_no_droppers_is_no_route() -> None:
    """An item nothing drops has no fightable dropper under any policy."""
    gd = _gd(chicken=1)
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    state = _fighter()
    assert fightable_droppers("ash_wood", state, gd, allow_grey=True) == []
    assert drop_obtainable("ash_wood", state, gd, allow_grey=True) is False


def test_spawn_gate_rejects_a_dropper_with_no_routable_tile() -> None:
    """The LIVENESS gate. A catalog monster with no routable spawn is not a
    source however winnable it looks — this is the gate selection always had
    and emission (which asked only "is a FightAction in my list") did not."""
    gd = _gd(chicken=1)
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    gd._monster_locations = {"chicken": []}
    state = _fighter()
    assert gd.monster_spawn_known("chicken") is False
    assert drop_obtainable("feather", state, gd, allow_grey=True) is False


def test_combat_gate_rejects_an_unwinnable_dropper() -> None:
    """The COMBAT gate: never offer a fight the character loses."""
    gd = _gd(dragon=40)
    gd._monster_drops = {"dragon": [("dragon_scale", 8, 1, 1)]}
    gd._monster_hp["dragon"] = 99999
    gd._monster_attack["dragon"] = {"fire": 9999}
    state = _fighter()
    assert drop_obtainable("dragon_scale", state, gd, allow_grey=True) is False


def test_grey_gate_is_the_callers_policy() -> None:
    """The GREY gate. The same grey dropper is a source under `allow_grey` and
    is not without it — the oracle never decides the policy itself."""
    gd = _gd(chicken=1)
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    state = _fighter()
    assert gd.xp_per_kill("chicken", state.level) == 0
    assert drop_obtainable("feather", state, gd, allow_grey=True) is True
    assert drop_obtainable("feather", state, gd, allow_grey=False) is False


def test_grey_gate_filters_candidates_rather_than_vetoing_the_item() -> None:
    """The CHOICE-RULE unification. A grey dropper must not mask a fightable
    xp-positive one: with `allow_grey=False` the grey candidate is dropped from
    the SET and the xp-positive dropper survives.

    Emission used to run the expected-kills argmin FIRST and then veto the
    whole item when the winner happened to be grey — so `chicken` (rate 1, the
    argmin) suppressed `wolf` entirely, while every selection walk (a plain
    `any(...)`) still called the item obtainable."""
    gd = _gd(chicken=1, wolf=9)
    gd._monster_drops = {
        "chicken": [("feather", 1, 1, 1)],   # grey at L10, and the argmin
        "wolf": [("feather", 50, 1, 1)],     # xp-positive, far worse rate
    }
    state = _fighter()
    assert gd.xp_per_kill("chicken", state.level) == 0
    assert gd.xp_per_kill("wolf", state.level) > 0
    permissive = [row[0] for row in fightable_droppers("feather", state, gd,
                                                       allow_grey=True)]
    assert permissive == ["chicken", "wolf"]
    strict = [row[0] for row in fightable_droppers("feather", state, gd,
                                                    allow_grey=False)]
    assert strict == ["wolf"]
    # And emission agrees with each verdict rather than refusing outright.
    actions = [FightAction(monster_code="chicken", locations=frozenset({(1, 1)})),
               FightAction(monster_code="wolf", locations=frozenset({(1, 1)}))]
    greedy = select_drop_fight("feather", actions, state, gd, allow_grey=True)
    assert greedy is not None and greedy.monster_code == "chicken"
    assert greedy.drop_farm is True
    careful = select_drop_fight("feather", actions, state, gd, allow_grey=False)
    assert careful is not None and careful.monster_code == "wolf"
    assert careful.drop_farm is False


def test_rows_carry_the_drop_table_payload_in_table_order() -> None:
    """The oracle returns the drop-table rows themselves so the caller's argmin
    ranks the SAME candidates in the same order every cycle."""
    gd = _gd(chicken=1, wolf=9)
    gd._monster_drops = {
        "chicken": [("feather", 4, 1, 3)],
        "wolf": [("feather", 7, 2, 5)],
    }
    state = _fighter()
    assert fightable_droppers("feather", state, gd, allow_grey=True) == [
        ("chicken", 4, 1, 3), ("wolf", 7, 2, 5)]


def test_emission_residual_is_the_missing_action_and_only_that() -> None:
    """The NAMED RESIDUAL. With an approved dropper but no FightAction for it in
    the pool, emission returns None while the oracle says True. That is the one
    gap the oracle cannot see, and a caller handing in a filtered pool must read
    the None as 'not with THIS pool', never as 'not obtainable'."""
    gd = _gd(chicken=1)
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    state = _fighter()
    assert drop_obtainable("feather", state, gd, allow_grey=True) is True
    assert select_drop_fight("feather", [], state, gd, allow_grey=True) is None


# --------------------------------------------------------------------------
# THE divergence-closure property, over the real catalog.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def game_data() -> GameData:
    return load_bundle_game_data(BUNDLE)


@pytest.fixture(scope="module")
def dropped_items(game_data: GameData) -> list[str]:
    """Every catalog item some monster drops — the whole domain of the question."""
    items = sorted({code for code in game_data.all_item_stats
                    if game_data.monsters_dropping(code)})
    assert len(items) > 50, "bundle lost its drop tables; the property is vacuous"
    return items


def _pool(scenario: str, state: WorldState, game_data: GameData) -> list:
    player = GamePlayer(character=scenario, history=None)
    player.seed_offline(state, game_data)
    return player._build_actions()


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
@pytest.mark.parametrize("allow_grey", [True, False])
def test_selection_and_emission_never_disagree(scenario: str, allow_grey: bool,
                                               game_data: GameData,
                                               dropped_items: list[str]) -> None:
    """THE TEST THAT WOULD HAVE CAUGHT THE WOOL LIVELOCK.

    For every dropped item in the real catalog, in every scenario state, under
    both grey policies: the oracle's verdict and the production emission agree
    EXACTLY. No item is ever called obtainable while the planner has no edge to
    obtain it (the livelock), and no fight is ever emitted for an item the
    reachability walks call unreachable (the mirror bug).

    The oracle's named residual is asserted EMPTY here: the production action
    pool carries a FightAction for every dropper the oracle approves, by
    `actions/factory` construction. If this ever fails on the residual arm, the
    factory's emission and `monster_spawn_known` have drifted apart."""
    state = scenario_state(SCENARIOS[scenario], game_data)
    actions = _pool(scenario, state, game_data)
    fight_codes = {a.monster_code for a in actions if isinstance(a, FightAction)}

    for item in dropped_items:
        approved = fightable_droppers(item, state, game_data, allow_grey=allow_grey)
        fight = select_drop_fight(item, actions, state, game_data,
                                  allow_grey=allow_grey)
        if not approved:
            assert fight is None, (
                f"{scenario}/{item}: emission built a fight the oracle refused")
            continue
        approved_codes = {row[0] for row in approved}
        assert approved_codes <= fight_codes, (
            f"{scenario}/{item}: the residual is NON-EMPTY — oracle approved "
            f"{sorted(approved_codes - fight_codes)} with no FightAction in the "
            "production pool; factory emission and monster_spawn_known drifted")
        assert fight is not None, (
            f"{scenario}/{item}: oracle says obtainable, emission refused")
        assert fight.monster_code in approved_codes, (
            f"{scenario}/{item}: emission chose a dropper the oracle never approved")
        assert fight.drop_farm == (
            game_data.xp_per_kill(fight.monster_code, state.level) == 0), (
            f"{scenario}/{item}: drop_farm does not match the dropper's greyness")


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_boolean_face_matches_the_row_list(scenario: str, game_data: GameData,
                                           dropped_items: list[str]) -> None:
    """`drop_obtainable` is never a second implementation: it is exactly
    `fightable_droppers` reduced to a bool, in every state and both policies."""
    state = scenario_state(SCENARIOS[scenario], game_data)
    for allow_grey in (True, False):
        for item in dropped_items:
            assert drop_obtainable(item, state, game_data,
                                   allow_grey=allow_grey) is bool(
                fightable_droppers(item, state, game_data, allow_grey=allow_grey))


# --------------------------------------------------------------------------
# Route EXISTENCE is asked at restorable hp, not at current hp.
# --------------------------------------------------------------------------

def test_a_damaged_character_has_the_same_droppers_as_a_healthy_one() -> None:
    """THE LIVE DEFECT, pinned.

    `combat.predict_win` reads CURRENT hp by design — a damaged character really
    does lose fights a healthy one wins, and the runtime target picker must see
    that. But this oracle answers a route-EXISTENCE question, and Rest is an
    action the planner has. Asking it at current hp made the answer swing on how
    beaten up the character happened to be when `J` ran.

    Measured live 2026-08-17: C3P0 at 63/315 hp reported sheep, cow and
    blue_slime all unwinnable, so `wool` had no route and `iron_shield` priced at
    3,000,926; the same character at 315/315 priced it at 926. A factor of ~7,000
    in a RANKING key, driven by combat noise."""
    gd = _gd(bruiser=9)
    gd._monster_drops = {"bruiser": [("hide", 8, 1, 1)]}
    # Tuned so CURRENT hp is what decides: 200 monster hp takes several turns,
    # and 30 damage a turn kills a near-dead character long before it kills a
    # healthy one. A harmless fixture monster would make this test pass without
    # the fix and prove nothing.
    gd._monster_hp["bruiser"] = 200
    gd._monster_attack["bruiser"] = {"fire": 30}
    healthy = _fighter(hp=200, max_hp=200)
    hurt = _fighter(hp=1, max_hp=200)
    assert fightable_droppers("hide", healthy, gd, allow_grey=True) != [], \
        "fixture is not winnable even when healthy — it can prove nothing"
    assert fightable_droppers("hide", hurt, gd, allow_grey=True) == \
        fightable_droppers("hide", healthy, gd, allow_grey=True)
    assert drop_obtainable("hide", hurt, gd, allow_grey=True) is True


def test_the_gate_is_moved_not_removed() -> None:
    """A monster the character loses to even at FULL hp is still not a route.
    Without this the change would hand the planner a fight it can never take,
    which is the livelock the winnability gate exists to prevent."""
    gd = _gd(dragon=9)
    gd._monster_drops = {"dragon": [("scale", 8, 1, 1)]}
    gd._monster_hp["dragon"] = 10_000
    gd._monster_attack["dragon"] = {"fire": 5_000}
    hopeless = _fighter(hp=200, max_hp=200)
    assert fightable_droppers("scale", hopeless, gd, allow_grey=True) == []


def test_the_level_gates_still_read_the_real_level_not_a_rested_one() -> None:
    """Resting restores hp and NOTHING else. The grey gate reads `state.level`,
    which a rested copy shares, so moving the hp basis must not silently move
    the xp verdict with it — a level-1 dropper stays grey for a level-12
    character however healthy it is."""
    gd = _gd(chick=1)
    gd._monster_drops = {"chick": [("down", 8, 1, 1)]}
    hurt = _fighter(hp=1, max_hp=200)
    assert fightable_droppers("down", hurt, gd, allow_grey=True) != []
    assert fightable_droppers("down", hurt, gd, allow_grey=False) == []
