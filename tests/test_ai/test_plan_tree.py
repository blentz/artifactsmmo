from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, PlanTreeNode
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.plan_tree import build_plan_tree
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.strategy import RootScore, StrategyDecision
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "life_amulet": ItemStats(code="life_amulet", level=5, type_="amulet",
                                 crafting_skill="jewelrycrafting", crafting_level=5),
        "golden_ring": ItemStats(code="golden_ring", level=3, type_="ring",
                                 crafting_skill="jewelrycrafting", crafting_level=3),
        "topaz": ItemStats(code="topaz", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "life_amulet": {"golden_ring": 1, "topaz": 2},
        "golden_ring": {"topaz": 4},
    }
    gd._resource_drops = {}
    gd._resource_skill = {}
    return gd


def _decision(chosen, step, ranking):
    return StrategyDecision(interrupt=None, chosen_root=chosen, chosen_step=step,
                            desired_state={}, ranking=ranking)


def _rs(node, score, category="gear"):
    return RootScore(root_repr=repr(node), category=category,
                     contribution=Fraction(0), cost=0, score=Fraction(score), step_repr="")


def test_chosen_expands_materials():
    # P3b: the crafting-skill gate is no longer a prerequisite node; the chosen
    # root expands directly into its material ObtainItems.
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1}, equipment={"amulet_slot": None})
    chosen = ObtainItem("life_amulet")
    step = ObtainItem("golden_ring", 1)
    tree = build_plan_tree(_decision(chosen, step, [_rs(chosen, 2)]), state, gd, None)

    assert len(tree) == 1                      # only the chosen root (no other ranked roots)
    root = tree[0]
    assert root.kind == "obtain" and root.label == "life_amulet" and root.status == "unmet"
    kinds = {c.label: c for c in root.children}
    assert kinds["golden_ring"].status == "current"     # == chosen_step
    assert kinds["topaz ×2"].status == "unmet"


def test_current_step_gets_synthetic_serve_child():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    step = ObtainItem("golden_ring", 1)
    tree = build_plan_tree(_decision(chosen, step, [_rs(chosen, 2)]), state, gd,
                           "LevelSkill: craft copper_ring")
    ring = next(c for c in tree[0].children if c.label == "golden_ring")
    steps = [c for c in ring.children if c.kind == "step"]
    assert len(steps) == 1
    assert steps[0].label == "LevelSkill: craft copper_ring"
    assert steps[0].status == "current"


def test_serve_child_carries_grind_children():
    # The runtime skill-grind legs (captured by the player) graft onto the
    # current step's synthetic serve child so the plan tree shows the whole
    # action chain below a LevelSkill step.
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    step = ObtainItem("golden_ring", 1)
    legs = (PlanTreeNode(key="leg0", label="GatherAsh()", kind="obtain", status="current"),
            PlanTreeNode(key="leg1", label="CraftPlank()", kind="obtain", status="unmet"))
    tree = build_plan_tree(_decision(chosen, step, [_rs(chosen, 2)]), state, gd,
                           "UpgradeEquipment: LevelSkill(woodcutting)", grind_children=legs)
    ring = next(c for c in tree[0].children if c.label == "golden_ring")
    serve = next(c for c in ring.children if c.kind == "step")
    assert serve.children == legs


def test_grind_children_default_empty_leaves_serve_child_a_leaf():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    step = ObtainItem("golden_ring", 1)
    tree = build_plan_tree(_decision(chosen, step, [_rs(chosen, 2)]), state, gd,
                           "UpgradeEquipment: LevelSkill(woodcutting)")
    ring = next(c for c in tree[0].children if c.label == "golden_ring")
    serve = next(c for c in ring.children if c.kind == "step")
    assert serve.children == ()


def test_no_serve_child_when_serve_step_none():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    step = ObtainItem("golden_ring", 1)
    tree = build_plan_tree(_decision(chosen, step, [_rs(chosen, 2)]), state, gd, None)
    ring = next(c for c in tree[0].children if c.label == "golden_ring")
    assert [c for c in ring.children if c.kind == "step"] == []


def test_recurses_material_subtree_to_raw_leaf():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    tree = build_plan_tree(_decision(chosen, None, [_rs(chosen, 2)]), state, gd, None)
    ring = next(c for c in tree[0].children if c.label == "golden_ring")
    topaz = next(c for c in ring.children if c.label == "topaz ×4")
    assert topaz.children == ()                                           # raw resource → leaf


def test_met_material_marked_met():
    gd = _gd()
    # topaz owned enough at the amulet level: 2 needed, hold 2 -> met leaf
    state = make_state(skills={"jewelrycrafting": 1}, inventory={"topaz": 2})
    chosen = ObtainItem("life_amulet")
    tree = build_plan_tree(_decision(chosen, None, [_rs(chosen, 2)]), state, gd, None)
    topaz = next(c for c in tree[0].children if c.label == "topaz ×2")
    assert topaz.status == "met"


def test_non_chosen_roots_are_leaf_stubs():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    other = ObtainItem("golden_ring")
    ranking = [_rs(chosen, 2, "gear"), _rs(other, 1, "gear")]
    tree = build_plan_tree(_decision(chosen, None, ranking), state, gd, None)
    assert len(tree) == 2
    stub = tree[1]
    assert stub.kind == "root_stub" and stub.children == ()
    assert stub.label == "golden_ring" and "1.00" in stub.detail


def test_chosen_root_none_returns_empty():
    gd = _gd()
    tree = build_plan_tree(_decision(None, None, []), make_state(), gd, None)
    assert tree == ()


def test_cycle_and_depth_bounded():
    # A self-referential recipe would recurse forever without the visited-set.
    gd = _gd()
    gd._crafting_recipes = {"loop_item": {"loop_item": 1}}
    gd._item_stats = {"loop_item": ItemStats(code="loop_item", level=1, type_="resource")}
    state = make_state()
    chosen = ObtainItem("loop_item")
    tree = build_plan_tree(_decision(chosen, None, [_rs(chosen, 1)]), state, gd, None)
    # terminates; the repeated node becomes a leaf via the visited-set
    assert tree[0].label == "loop_item"


def test_reach_char_level_root_labelled_and_leaf():
    # Empty monster table -> combat_capable's any() short-circuits False without
    # calling predict_win; no attainable weapon -> prerequisites() returns [] (leaf).
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._monster_level = {}
    gd._resource_drops = {}
    gd._resource_skill = {}
    chosen = ReachCharLevel(5)
    tree = build_plan_tree(_decision(chosen, None, [_rs(chosen, 1)]), make_state(), gd, None)
    assert tree[0].label == "character → 5" and tree[0].kind == "charlevel"
    assert tree[0].children == ()


@dataclass(frozen=True)
class _UnknownGoal:
    def is_satisfied(self, state, game_data) -> bool:
        return False


def test_unknown_metagoal_falls_back_to_short_root_label():
    gd = _gd()
    dummy = _UnknownGoal()
    tree = build_plan_tree(_decision(dummy, None, [_rs(dummy, 1)]), make_state(), gd, None)
    assert tree[0].kind == "obtain"        # fallback branch
    assert tree[0].children == ()          # prerequisites(unknown) -> []


def test_snapshot_carries_plan_tree():
    node = PlanTreeNode(key="k", label="life_amulet", kind="obtain", status="unmet")
    snap = CycleSnapshot(cycle_index=1, timestamp="t", character="hero",
                         x=0, y=0, level=1, xp=0, max_xp=1, hp=1, max_hp=1, gold=0,
                         selected_goal="g", action="a", outcome="ok",
                         plan_tree=(node,))
    assert snap.plan_tree[0].label == "life_amulet"
    assert snap.plan_tree[0].children == ()


def test_snapshot_carries_grind_expansion():
    leg = PlanTreeNode(key="leg0", label="GatherAsh()", kind="obtain", status="current")
    snap = CycleSnapshot(cycle_index=1, timestamp="t", character="hero",
                         x=0, y=0, level=1, xp=0, max_xp=1, hp=1, max_hp=1, gold=0,
                         selected_goal="g", action="LevelSkill(woodcutting)", outcome="ok",
                         grind_expansion=(leg,))
    assert snap.grind_expansion[0].label == "GatherAsh()"
