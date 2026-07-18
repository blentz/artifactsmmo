import pytest
from textual.app import App, ComposeResult

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.tui.widgets.plan_tree import PlanTree, default_expanded


def _sample() -> tuple[PlanTreeNode, ...]:
    step = PlanTreeNode(key="step:sk", label="grind copper_ring", kind="step", status="current")
    skill = PlanTreeNode(key="sk", label="jewelrycrafting → 5", kind="skill",
                         status="current", children=(step,))
    ring = PlanTreeNode(key="ring", label="golden_ring", kind="obtain", status="met")
    chosen = PlanTreeNode(key="amulet", label="life_amulet", kind="obtain",
                          status="unmet", children=(skill, ring))
    stub = PlanTreeNode(key="boots", label="steel_boots", kind="root_stub",
                        status="unmet", detail="root 2 · gear · 3.10")
    return (chosen, stub)


def test_default_expanded_opens_chosen_and_path_to_current():
    keys = default_expanded(_sample())
    assert "amulet" in keys and "sk" in keys      # chosen root + path to current
    assert "boots" not in keys                     # stub stays collapsed


class _Harness(App):
    def __init__(self, roots):
        super().__init__()
        self._roots = roots

    def compose(self) -> ComposeResult:
        yield PlanTree(id="pt")

    def on_mount(self) -> None:
        self.query_one("#pt", PlanTree).set_nodes(self._roots)


@pytest.mark.asyncio
async def test_set_nodes_builds_structure_and_stub_is_leaf():
    app = _Harness(_sample())
    async with app.run_test():
        tree = app.query_one("#pt", PlanTree)
        top = tree.root.children
        assert [n.data.label for n in top] == ["life_amulet", "steel_boots"]
        stub = top[1]
        assert stub.allow_expand is False          # root_stub is a leaf
        assert top[0].is_expanded                   # chosen auto-expanded


@pytest.mark.asyncio
async def test_expansion_memory_reapplied_on_rebuild():
    app = _Harness(_sample())
    async with app.run_test():
        tree = app.query_one("#pt", PlanTree)
        # simulate the user having opened the 'golden_ring' branch's parent chain
        tree._expanded_keys.add("ring")
        tree.set_nodes(_sample())
        _ring = next(n for n in tree.root.children[0].children if n.data.key == "ring")
        # 'ring' has no children so it cannot expand, but its key is retained
        assert "ring" in tree._expanded_keys


def _sample_with_unmet_child() -> tuple[PlanTreeNode, ...]:
    # A non-chosen, non-root_stub/step node with status "unmet" exercises the
    # _glyph fallback branch ("unmet" -> "○"), which the brief's sample never
    # reaches (its only unmet nodes are the chosen root and the root_stub).
    leaf = PlanTreeNode(key="leaf", label="raw_iron", kind="obtain", status="unmet")
    skill = PlanTreeNode(key="sk2", label="mining -> 3", kind="skill",
                         status="current", children=(leaf,))
    root = PlanTreeNode(key="pick", label="iron_pick", kind="obtain",
                        status="unmet", children=(skill,))
    return (root,)


def _sample_with_grind_legs() -> tuple[PlanTreeNode, ...]:
    # The current step's synthetic serve child now carries the runtime grind
    # legs (a leaf gather + a nested cross-skill grind wrapper) so the tree
    # shows the whole action chain below a LevelSkill step.
    inner = PlanTreeNode(key="inner0", label="GatherOak()", kind="obtain", status="current")
    nested = PlanTreeNode(key="grind:fishing", label="grind fishing", kind="step",
                          status="current", children=(inner,))
    leg = PlanTreeNode(key="leg0", label="GatherAsh()", kind="obtain", status="current")
    step = PlanTreeNode(key="step:sk", label="Upgrade: LevelSkill(gearcrafting)",
                        kind="step", status="current", children=(leg, nested))
    root = PlanTreeNode(key="bow", label="fire_bow", kind="obtain",
                        status="current", children=(step,))
    return (root,)


@pytest.mark.asyncio
async def test_grind_legs_render_and_autoexpand_below_step():
    app = _Harness(_sample_with_grind_legs())
    async with app.run_test():
        tree = app.query_one("#pt", PlanTree)
        root_node = tree.root.children[0]
        step_node = root_node.children[0]
        assert step_node.allow_expand is True          # step now has children
        assert step_node.is_expanded                    # path-to-current auto-opens
        labels = [n.data.label for n in step_node.children]
        assert labels == ["GatherAsh()", "grind fishing"]
        # the nested cross-skill grind wrapper carries its own leg
        nested_node = step_node.children[1]
        assert nested_node.children[0].data.label == "GatherOak()"


@pytest.mark.asyncio
async def test_unmet_child_glyph_fallback_and_collapse_updates_memory():
    app = _Harness(_sample_with_unmet_child())
    async with app.run_test() as pilot:
        tree = app.query_one("#pt", PlanTree)
        root_node = tree.root.children[0]
        skill_node = root_node.children[0]
        leaf_node = skill_node.children[0]

        # fallback glyph for a plain unmet, non-chosen, non-stub/step node
        assert "○" in leaf_node.label.plain

        # "sk2" is on the path to the current node, so it starts expanded
        assert "sk2" in tree._expanded_keys
        assert skill_node.is_expanded

        skill_node.collapse()
        await pilot.pause()
        assert "sk2" not in tree._expanded_keys
