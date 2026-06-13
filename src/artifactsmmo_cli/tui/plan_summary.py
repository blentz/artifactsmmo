"""Pure builder: render the AI's committed objective as a collapsed plan tree
with have/need progress. Reuses closure_demand/shopping_list; no planning logic."""

import re

from rich.console import Group, RenderableType
from rich.table import Table

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.shopping_list import shopping_list

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")


def _depth(code: str, recipes: dict, memo: dict[str, int]) -> int:
    """Recipe depth: raw item = 0, craftable = 1 + max(input depth). Cycle-safe
    via memo seeded to 0 before recursion."""
    if code in memo:
        return memo[code]
    memo[code] = 0
    recipe = recipes.get(code)
    if recipe:
        memo[code] = 1 + max((_depth(m, recipes, memo) for m in recipe), default=0)
    return memo[code]


def _obtain_chain(code: str, qty: int, inventory: dict[str, int],
                  bank: dict[str, int] | None, game_data: GameData) -> Table:
    recipes = game_data.crafting_recipes
    owned: dict[str, int] = dict(inventory)
    if bank:
        for c, q in bank.items():
            owned[c] = owned.get(c, 0) + q
    total: dict[str, int] = {}
    closure_demand(code, qty, game_data, total, frozenset())
    net = shopping_list(code, qty, recipes, owned)

    memo: dict[str, int] = {}
    items = sorted(total, key=lambda c: (_depth(c, recipes, memo), c))
    # deepest item with remaining work = the leaf being worked now
    pending = [c for c in items if net.get(c, 0) > 0]
    active = max(pending, key=lambda c: (_depth(c, recipes, memo), c)) if pending else None

    t = Table(box=None, padding=(0, 2), show_header=False)
    t.add_column("v")
    t.add_column("item")
    t.add_column("prog")
    t.add_column("note")
    for c in items:
        tot = total[c]
        have = tot - net.get(c, 0)
        verb = "Craft" if recipes.get(c) else "Collect"
        note = "<- now" if c == active else ""
        stats = game_data.item_stats(c)
        if stats is not None and stats.crafting_skill and verb == "Craft":
            note = (note + f"  (needs {stats.crafting_skill} {stats.crafting_level})").strip()
        t.add_row(verb, f"{tot}x {c}", f"[{have}/{tot}]", note)
    stats = game_data.item_stats(code)
    if stats is not None and stats.type_ in ITEM_TYPE_TO_SLOTS:
        t.add_row("Equip", code, "", "")
    return t


def build_plan_summary(
    chosen_root: str | None,
    ranking: list[RootScoreView],
    inventory: dict[str, int],
    bank: dict[str, int] | None,
    game_data: GameData,
    projected_cycles_to_max: float | None,
) -> RenderableType:
    """Render the committed objective's collapsed plan + progress. Task 2 adds
    the non-craftable root branches, header/ETA, and the ALTERNATIVES block."""
    if chosen_root is None:
        return Group(Table(box=None))  # placeholder; Task 2 replaces with empty-state text
    m = _OBTAIN_RE.search(chosen_root)
    if m:
        return _obtain_chain(m.group(1), int(m.group(2)), inventory, bank, game_data)
    return Group(Table(box=None))  # non-craftable roots: Task 2
