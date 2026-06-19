"""Pure builder: render the AI's committed objective as a flowchart — objective
root, the chosen branch expanded (step / GOAP / have-need body), every non-chosen
root as a one-line stub, and a suppressed-goals footer. No planning logic."""

import re
from collections.abc import Mapping

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.shopping_list import shopping_list
from artifactsmmo_cli.tui.plan_format import short_root

CHOSEN_GLYPH = "●"
STUB_GLYPH = "○"
ALT_PAGE_SIZE = 6

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")
_CHARLVL_RE = re.compile(r"ReachCharLevel\(level=(\d+)\)")
_SKILL_RE = re.compile(r"ReachSkillLevel\(skill='([^']+)', level=(\d+)\)")


def _depth(code: str, recipes: Mapping[str, dict[str, int]], memo: dict[str, int]) -> int:
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


def _chosen_entry(chosen_root: str, ranking: list[RootScoreView]) -> RootScoreView | None:
    return next((r for r in ranking if r.root_repr == chosen_root), None)


def _stub_line(r: RootScoreView, game_data: GameData) -> Text:
    """One-line 'would ...' for a non-chosen root (no closure expansion)."""
    m = _OBTAIN_RE.fullmatch(r.root_repr)
    if m:
        code, qty = m.group(1), m.group(2)
        verb = "Craft" if game_data.crafting_recipes.get(code) else "Collect"
        recipe = game_data.crafting_recipes.get(code)
        needs = ""
        if recipe:
            needs = "  (needs " + ", ".join(f"{q}x {c}" for c, q in recipe.items()) + ")"
        return Text(f"│    would  {verb} {qty}x {code}{needs}", style="dim")
    detail = r.step_repr or short_root(r.root_repr)
    return Text(f"│    would  {detail}", style="dim")


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
    plan_len: int = 0,
    suppressed_goals: list[str] | None = None,
    alt_page: int = 0,
    alt_page_size: int = ALT_PAGE_SIZE,
) -> RenderableType:
    """Render the committed objective as a flowchart: an OBJECTIVE root, the
    chosen branch expanded (step / GOAP / have-need body), the non-chosen roots
    as stub branches, then an ETA and suppressed-goals footer."""
    if chosen_root is None:
        return Text("No committed objective this cycle.")

    parts: list[RenderableType] = []
    max_level = game_data.max_character_level if game_data is not None else 0
    parts.append(Text(f"OBJECTIVE  reach level {max_level}", style="bold"))
    parts.append(Text("│"))

    chosen = _chosen_entry(chosen_root, ranking)
    cat = chosen.category if chosen is not None else "?"
    score_txt = f"  {chosen.score:.2f}" if chosen is not None else ""
    step_txt = chosen.step_repr if chosen is not None and chosen.step_repr else "-"
    parts.append(Text(f"├─{CHOSEN_GLYPH} {short_root(chosen_root)}  {cat}{score_txt}   ◄ CHOSEN",
                      style="bold"))
    parts.append(Text(f"│    step  {step_txt}", style="dim"))
    parts.append(Text(f"│    plan  {plan_len} actions   next {path_next_action or '?'}",
                      style="dim"))
    parts.append(Padding(_body(chosen_root, inventory, bank, game_data, path_next_action,
                               (xp, max_xp), skill_xp or {},
                               (task_code, task_progress, task_total)), (0, 0, 0, 5)))

    stubs = [x for x in ranking if x.root_repr != chosen_root]
    total = len(stubs)
    pages = max(1, (total + alt_page_size - 1) // alt_page_size)
    page = min(max(alt_page, 0), pages - 1)
    lo = page * alt_page_size
    hi = min(lo + alt_page_size, total)
    for r in stubs[lo:hi]:
        parts.append(Text(f"├─{STUB_GLYPH} {short_root(r.root_repr)}  {r.category}  {r.score:.2f}"))
        parts.append(_stub_line(r, game_data))

    if projected_cycles_to_max is not None:
        parts.append(Text(f"ETA ~{projected_cycles_to_max:.0f} cycles (estimate)", style="dim"))
    if suppressed_goals:
        parts.append(Text(f"└─ suppressed  {' · '.join(suppressed_goals)}", style="dim"))
    if pages > 1:
        parts.append(Text(f"   alternatives {lo + 1}–{hi} of {total}    "
                          f"[ prev   ] next", style="dim"))
    return Group(*parts)
