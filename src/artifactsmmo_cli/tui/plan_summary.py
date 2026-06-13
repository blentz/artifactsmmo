"""Pure builder: render the AI's committed objective as a collapsed plan tree
with have/need progress. Reuses closure_demand/shopping_list; no planning logic."""

import re
from collections.abc import Mapping

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.shopping_list import shopping_list

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")
_CHARLVL_RE = re.compile(r"ReachCharLevel\(level=(\d+)\)")
_SKILL_RE = re.compile(r"ReachSkillLevel\(skill='([^']+)', level=(\d+)\)")


def _depth(code: str, recipes: Mapping[str, dict[str, int]], memo: dict[str, int]) -> int:
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
    # SHALLOWEST item with remaining work = what's being acquired NOW (work
    # proceeds raw -> up the recipe; you gather the leaf before crafting above it).
    pending = [c for c in items if net.get(c, 0) > 0]
    active = min(pending, key=lambda c: (_depth(c, recipes, memo), c)) if pending else None

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


def _category_of(root_repr: str, ranking: list[RootScoreView]) -> tuple[str, float | None]:
    for r in ranking:
        if r.root_repr == root_repr:
            return r.category, r.score
    return "?", None


def _body(chosen_root: str, inventory: dict[str, int], bank: dict[str, int] | None,
          game_data: GameData,
          path_next_action: str | None, snap_xp: tuple[int, int],
          skill_xp: dict[str, int], task: tuple[str | None, int, int]) -> RenderableType:
    m = _OBTAIN_RE.search(chosen_root)
    if m:
        return _obtain_chain(m.group(1), int(m.group(2)), inventory, bank, game_data)
    m = _CHARLVL_RE.search(chosen_root)
    if m:
        xp, mx = snap_xp
        mon = path_next_action or "monster"
        return Text(f"Grind {mon} for char XP  [{xp}/{mx}]  -> L{m.group(1)}")
    m = _SKILL_RE.search(chosen_root)
    if m:
        sk = m.group(1)
        return Text(f"Grind {sk}  [skill xp {skill_xp.get(sk, 0)}]  -> L{m.group(2)}")
    code, prog, tot = task
    if code is not None and ("Task" in chosen_root or "task" in chosen_root):
        return Text(f"Task {code}  [{prog}/{tot}]")
    return Text(f"Plan: {chosen_root}")


def build_plan_summary(
    chosen_root: str | None,
    ranking: list[RootScoreView],
    inventory: dict[str, int],
    bank: dict[str, int] | None,
    game_data: GameData,
    projected_cycles_to_max: float | None,
    *,
    xp: int = 0, max_xp: int = 0,
    skill_xp: dict[str, int] | None = None,
    task_code: str | None = None, task_progress: int = 0, task_total: int = 0,
    path_next_action: str | None = None,
) -> RenderableType:
    """Render the committed objective's collapsed plan + progress: a COMMITTED
    header, the per-root body (ObtainItem chain / char-level / skill-level / task),
    an ETA footer, and the ranked ALTERNATIVES block."""
    if chosen_root is None:
        return Text("No committed objective this cycle.")
    cat, score = _category_of(chosen_root, ranking)
    parts: list[RenderableType] = []
    short = chosen_root.replace("ObtainItem(code=", "").replace(", quantity=1)", "")
    head = f"COMMITTED: {short}  ({cat}" + (f", score {score:.2f}" if score is not None else "") + ")"
    parts.append(Text(head, style="bold"))
    parts.append(_body(chosen_root, inventory, bank, game_data, path_next_action,
                       (xp, max_xp), skill_xp or {}, (task_code, task_progress, task_total)))
    if projected_cycles_to_max is not None:
        parts.append(Text(f"ETA ~{projected_cycles_to_max:.0f} cycles (estimate)", style="dim"))
    alts = [r for r in ranking if r.root_repr != chosen_root][:6]
    if alts:
        parts.append(Text("ALTERNATIVES (not chosen):", style="bold"))
        for r in alts:
            parts.append(Text(f"  {r.score:.2f}  {r.root_repr}  ({r.category})", style="dim"))
    return Group(*parts)
