"""Mechanical Python -> Lean 4 extractor (v1) for the pure decision cores.

Per docs/PLAN_mechanical_extraction.md: the Lean models gating the planner are
MECHANICALLY EXTRACTED from the Python pure-core modules, so the generated
definition is a syntactic image of the running code and any drift breaks the
gate (`--check` mode + formal/gate/check_extraction.sh). Hand-written bridge
lemmas in formal/Formal/Extracted/Bridges.lean prove each extracted definition
equal to the pre-existing hand model, transferring the hand theorems.

V1 SUBSET (anything else is REJECTED loudly, naming the construct + line):

  types       int -> Int, bool -> Bool, str -> String, X | None / Optional[X]
              -> Option, tuple[..] -> Prod, list/Sequence -> List,
              dict/Mapping[k, v] -> List (k x v) + emitted lookup helpers,
              frozenset|list unions -> List (set-semantics caveat below),
              Callable[[A..], R] -> plain function argument.
  exprs       int/bool literals, None, + - * (Int), // -> Int.fdiv,
              % -> Int.fmod, comparisons (chained ok) -> decide (..),
              and/or/not -> && || !, max/min(a, b), abs -> _intAbs,
              len -> Int.ofNat (List.length ..), d.get(k, default) ->
              _dictGetD, dict(d) -> identity copy, tuple construction,
              constant tuple indexing -> Prod projections, calls to
              Callable parameters, lambda (only as a min/max key),
              `A if X is not None else B`.
  stmts       assignment (let), annotated assignment, dict-subscript
              assignment -> _dictSet, early return, if/elif with
              always-returning bodies, for-with-single-accumulator ->
              List.foldl, `continue` inside loops.

  REJECTED    while, try/except, with, raise, assert, classes,
              comprehensions/generators, float literals or annotations,
              str methods (any attribute except dict .get), recursion,
              break, return inside a loop, *args/**kwargs/defaults,
              decorators, missing type annotations, iteration over a
              set-typed value (only min/max with an injective total key
              may consume one), bare reads of an Optional variable inside
              an unwrap context, Lean reserved words as identifiers.

EARLY-RETURN STRATEGY: a statement block is translated to ONE Lean
expression by recursing on the statement list. `x = e` becomes
`let x := e; <rest>` (later assignments shadow). An `if` whose body always
returns becomes `(if c then <body> else <rest>)`. Inside a loop body the
same translation applies with `continue`/block-end yielding the current
accumulator binding; an `if` body that only re-assigns the accumulator
becomes `let acc := (if c then e else acc)`. Three Optional patterns get a
`match` translation with a FRESH binder (`x_1`, `x_2`, ...) so the outer
Option binding stays visible in the untaken branch:

  if X is not None: <body>     =>  (match X with
                                    | some X_k => <body, X[i] -> X_k.proj>
                                    | none => <rest>)
  if X is None or COND: <body> =>  (match X with
                                    | none => <body + rest>
                                    | some X_k => (if COND[X[i] -> X_k.proj]
                                                   then <body + rest>
                                                   else <rest>))
  A if X is not None else B    =>  (match X with
                                    | some X_k => A[X[i] -> X_k.proj]
                                    | none => B)

When the declared return type is Optional[T], `return None` emits `none`
and a T-valued `return e` emits `some e`; an expression already typed
Option T (e.g. a _minByKey result) is returned unwrapped.

MIN/MAX WITH KEY: `min(xs, key=lambda t: (k1, .., kn))` (all components
Int) emits a first-wins left fold `_minByKeyN` over an emitted strict
lexicographic Bool comparison `_lexLtN` — exactly Python `min` stability.
The helper is Option-valued (Python raises ValueError on an empty
sequence; the generated model is total and callers guard) and is only
accepted in a return position of an Optional function. When `xs` is
set-typed (frozenset union), the key tuple must contain EVERY projection
of the element, making the key injective and the fold order-independent;
otherwise the call is rejected (unordered-set iteration).

DICTS: `Mapping`/`dict` values become insertion-ordered association lists.
`_dictGetD` returns the first match or the default; `d[k] = v` becomes
`_dictSet` (replace-first-else-append), preserving Python dict update
semantics entry-for-entry.

DETERMINISM: output is a pure function of the registry + source text
(stable statement order, fixed helper ordering, counter-based fresh
names), so regeneration is byte-identical.
"""

import argparse
import ast
import difflib
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent

GENERATED_DIR = "formal/Formal/Extracted"

# Lean reserved words / prelude names an identifier must not collide with.
LEAN_RESERVED = frozenset({
    "fun", "match", "let", "if", "then", "else", "do", "end", "with",
    "theorem", "def", "structure", "abbrev", "instance", "namespace",
    "none", "some", "true", "false", "max", "min", "abs", "open",
    "import", "by", "have", "show", "from", "where", "deriving",
})


class ExtractionError(Exception):
    """A construct outside the v1 subset (or an internal consistency failure)."""


@dataclass(frozen=True)
class LType:
    """A Lean type in the v1 image: Int | Bool | String | Option t | Tuple
    (flat component list, rendered right-nested) | List t | Dict k v
    (rendered List (k x v)) | Fn (args.., ret)."""

    kind: str
    args: tuple["LType", ...] = ()


T_INT = LType("Int")
T_BOOL = LType("Bool")
T_STRING = LType("String")


def t_option(t: LType) -> LType:
    return LType("Option", (t,))


def t_list(t: LType) -> LType:
    return LType("List", (t,))


@dataclass(frozen=True)
class ModuleSpec:
    """Registry entry: one Python source module -> one generated Lean file."""

    source: str
    output: str
    core_name: str
    functions: tuple[str, ...]


# ---------------------------------------------------------------------------
# Registry (v1: the Tier-1 pure cores).
# ---------------------------------------------------------------------------
MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/combat_picker.py",
        output=f"{GENERATED_DIR}/CombatPicker.lean",
        core_name="CombatPicker",
        functions=("pick_winnable_monster_pure",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/nearest_tile.py",
        output=f"{GENERATED_DIR}/NearestTile.lean",
        core_name="NearestTile",
        functions=("nearest_tile",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/actions/npc_buy_core.py",
        output=f"{GENERATED_DIR}/NpcBuyCore.lean",
        core_name="NpcBuyCore",
        functions=("npc_buy_is_applicable_pure", "npc_buy_apply_pure"),
    ),
)


@dataclass
class Ctx:
    """Per-function translation context (vars/unwraps/setlike are scoped by
    copying at branch points; helpers and the fresh counter are shared)."""

    src: str
    fn_name: str
    ret: LType
    vars: dict[str, LType]
    setlike: set[str]
    unwraps: dict[str, tuple[str, LType]]
    helpers: set[str]
    loop_acc: str | None = None
    fresh: list[int] = field(default_factory=lambda: [0])


def branch(ctx: Ctx, loop_acc: str | None = None) -> Ctx:
    """A child scope: copied bindings, SHARED helper set + fresh counter."""
    return Ctx(
        src=ctx.src, fn_name=ctx.fn_name, ret=ctx.ret,
        vars=dict(ctx.vars), setlike=set(ctx.setlike),
        unwraps=dict(ctx.unwraps), helpers=ctx.helpers,
        loop_acc=ctx.loop_acc if loop_acc is None else loop_acc,
        fresh=ctx.fresh,
    )


def reject(src: str, node: ast.AST, what: str) -> NoReturn:
    line = getattr(node, "lineno", "?")
    raise ExtractionError(f"{src}:{line}: unsupported construct outside the v1 subset: {what}")


def check_ident(src: str, node: ast.AST, name: str) -> str:
    if name in LEAN_RESERVED:
        reject(src, node, f"identifier {name!r} collides with a Lean reserved word")
    return name


# ---------------------------------------------------------------------------
# Type rendering / annotation parsing.
# ---------------------------------------------------------------------------
def render_type(t: LType) -> str:
    if t.kind in ("Int", "Bool", "String"):
        return t.kind
    if t.kind == "Option":
        return f"Option {render_atom(t.args[0])}"
    if t.kind == "List":
        return f"List {render_atom(t.args[0])}"
    if t.kind == "Dict":
        return f"List ({render_type(t.args[0])} × {render_type(t.args[1])})"
    if t.kind == "Tuple":
        return "(" + " × ".join(render_atom(a) for a in t.args) + ")"
    if t.kind == "Fn":
        parts = [render_atom(a) for a in t.args]
        return "(" + " → ".join(parts) + ")"
    raise ExtractionError(f"internal: unrenderable type kind {t.kind!r}")


def render_atom(t: LType) -> str:
    if t.kind in ("Int", "Bool", "String", "Tuple", "Fn"):
        return render_type(t)
    return f"({render_type(t)})"


def parse_annotation(src: str, node: ast.expr) -> tuple[LType, bool]:
    """Parse an annotation -> (LType, setlike). Rejects anything unmapped."""
    if isinstance(node, ast.Name):
        if node.id == "int":
            return T_INT, False
        if node.id == "bool":
            return T_BOOL, False
        if node.id == "str":
            return T_STRING, False
        if node.id == "float":
            reject(src, node, "float annotation")
        reject(src, node, f"type annotation {node.id!r}")
    if isinstance(node, ast.Constant) and node.value is None:
        reject(src, node, "bare None annotation outside a union")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        members = _flatten_union(node)
        non_none = [m for m in members if not (isinstance(m, ast.Constant) and m.value is None)]
        has_none = len(non_none) < len(members)
        parsed = [parse_annotation(src, m) for m in non_none]
        base, setlike = parsed[0]
        for other, oset in parsed[1:]:
            if other != base:
                reject(src, node, "union of distinct types (only X | None and frozenset|list unions)")
            setlike = setlike or oset
        if has_none:
            return t_option(base), setlike
        return base, setlike
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        head = node.value.id
        if head == "Optional":
            inner, setlike = parse_annotation(src, node.slice)
            return t_option(inner), setlike
        if head == "tuple":
            if not isinstance(node.slice, ast.Tuple):
                reject(src, node, "non-tuple subscript on tuple[..]")
            comps = [parse_annotation(src, e)[0] for e in node.slice.elts]
            return LType("Tuple", tuple(comps)), False
        if head in ("list", "Sequence"):
            return t_list(parse_annotation(src, node.slice)[0]), False
        if head == "frozenset" or head == "set":
            return t_list(parse_annotation(src, node.slice)[0]), True
        if head in ("dict", "Mapping"):
            if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2:
                reject(src, node, "dict annotation without key/value pair")
            k = parse_annotation(src, node.slice.elts[0])[0]
            v = parse_annotation(src, node.slice.elts[1])[0]
            return LType("Dict", (k, v)), False
        if head == "Callable":
            if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2 \
                    or not isinstance(node.slice.elts[0], ast.List):
                reject(src, node, "Callable annotation without [[args], ret]")
            args = [parse_annotation(src, a)[0] for a in node.slice.elts[0].elts]
            ret = parse_annotation(src, node.slice.elts[1])[0]
            return LType("Fn", (*args, ret)), False
        reject(src, node, f"type annotation {head!r}[..]")
    reject(src, node, f"type annotation node {type(node).__name__}")


def _flatten_union(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flatten_union(node.left) + _flatten_union(node.right)
    return [node]


# ---------------------------------------------------------------------------
# Emitted helper definitions (fixed bodies, fixed ordering).
# ---------------------------------------------------------------------------
HELPER_ORDER = ("_intAbs", "_dictGetD", "_dictSet", "_lexLt3", "_minByKey3")

HELPER_DEFS = {
    "_intAbs": (
        "/-- `abs` on `Int` (Python `abs`): non-negative magnitude. -/\n"
        "def _intAbs (i : Int) : Int := Int.ofNat i.natAbs"
    ),
    "_dictGetD": (
        "/-- Python `dict.get(k, default)` over an insertion-ordered association list:\n"
        "first matching value, else the default. -/\n"
        "def _dictGetD (m : List (String × Int)) (k : String) (d : Int) : Int :=\n"
        "  match m with\n"
        "  | [] => d\n"
        "  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d"
    ),
    "_dictSet": (
        "/-- Python `d[k] = v` over an insertion-ordered association list: replace the\n"
        "first matching entry in place, else append — every other entry is preserved\n"
        "bit-for-bit, mirroring dict update semantics. -/\n"
        "def _dictSet (m : List (String × Int)) (k : String) (v : Int) : List (String × Int) :=\n"
        "  match m with\n"
        "  | [] => [(k, v)]\n"
        "  | (k', v') :: rest => if k' == k then (k', v) :: rest else (k', v') :: _dictSet rest k v"
    ),
    "_lexLt3": (
        "/-- Strict lexicographic `<` on a 3-component Int key — the order Python's\n"
        "tuple comparison gives `min(.., key=lambda t: (a, b, c))`. -/\n"
        "def _lexLt3 (a b : (Int × Int × Int)) : Bool :=\n"
        "  (decide (a.1 < b.1)) ||\n"
        "    ((decide (a.1 = b.1)) && ((decide (a.2.1 < b.2.1)) ||\n"
        "      ((decide (a.2.1 = b.2.1)) && (decide (a.2.2 < b.2.2)))))"
    ),
    "_minByKey3": (
        "/-- Python `min(xs, key=..)` as a first-wins left fold (Python `min` keeps the\n"
        "EARLIEST minimum). Option-valued: `none` on `[]` where Python raises — callers\n"
        "guard emptiness, so the two agree on every reachable input. -/\n"
        "def _minByKey3 (key : (Int × Int) → (Int × Int × Int)) (xs : List (Int × Int)) :\n"
        "    Option (Int × Int) :=\n"
        "  match xs with\n"
        "  | [] => none\n"
        "  | h :: t =>\n"
        "    some (List.foldl (fun best x => if _lexLt3 (key x) (key best) then x else best) h t)"
    ),
}


# ---------------------------------------------------------------------------
# Expression translation.
# ---------------------------------------------------------------------------
def proj(prefix: str, i: int, arity: int) -> str:
    """Lean projection chain for component i of a flat arity-n tuple."""
    path = ".2" * i if i == arity - 1 else ".2" * i + ".1"
    return f"{prefix}{path}"


def emit_expr(ctx: Ctx, e: ast.expr) -> tuple[str, LType]:
    src = ctx.src
    if isinstance(e, ast.Constant):
        if isinstance(e.value, bool):
            return ("true" if e.value else "false"), T_BOOL
        if isinstance(e.value, int):
            return (f"({e.value})" if e.value < 0 else str(e.value)), T_INT
        if isinstance(e.value, float):
            reject(src, e, "float literal")
        if e.value is None:
            reject(src, e, "None outside a return/annotated-assignment position")
        reject(src, e, f"literal {type(e.value).__name__}")
    if isinstance(e, ast.Name):
        name = check_ident(src, e, e.id)
        if name in ctx.unwraps:
            reject(src, e, f"bare read of Optional {name!r} inside its unwrap context (subscript it)")
        if name not in ctx.vars:
            reject(src, e, f"unbound name {name!r}")
        return name, ctx.vars[name]
    if isinstance(e, ast.Tuple):
        elts = [emit_expr(ctx, x) for x in e.elts]
        code = "(" + ", ".join(p[0] for p in elts) + ")"
        return code, LType("Tuple", tuple(p[1] for p in elts))
    if isinstance(e, ast.UnaryOp):
        if isinstance(e.op, ast.Not):
            a, t = emit_expr(ctx, e.operand)
            if t != T_BOOL:
                reject(src, e, "`not` on a non-bool (truthiness)")
            return f"(!{a})", T_BOOL
        if isinstance(e.op, ast.USub):
            a, t = emit_expr(ctx, e.operand)
            if t != T_INT:
                reject(src, e, "unary minus on a non-int")
            return f"(-{a})", T_INT
        reject(src, e, f"unary operator {type(e.op).__name__}")
    if isinstance(e, ast.BinOp):
        a, ta = emit_expr(ctx, e.left)
        b, tb = emit_expr(ctx, e.right)
        if ta != T_INT or tb != T_INT:
            reject(src, e, "arithmetic on non-int operands")
        if isinstance(e.op, ast.Add):
            return f"({a} + {b})", T_INT
        if isinstance(e.op, ast.Sub):
            return f"({a} - {b})", T_INT
        if isinstance(e.op, ast.Mult):
            return f"({a} * {b})", T_INT
        if isinstance(e.op, ast.FloorDiv):
            return f"(Int.fdiv {a} {b})", T_INT
        if isinstance(e.op, ast.Mod):
            return f"(Int.fmod {a} {b})", T_INT
        reject(src, e, f"binary operator {type(e.op).__name__}")
    if isinstance(e, ast.BoolOp):
        sep = " && " if isinstance(e.op, ast.And) else " || "
        parts: list[str] = []
        for v in e.values:
            code, t = emit_expr(ctx, v)
            if t != T_BOOL:
                reject(src, e, "and/or on a non-bool operand (truthiness)")
            parts.append(code)
        return "(" + sep.join(parts) + ")", T_BOOL
    if isinstance(e, ast.Compare):
        return emit_compare(ctx, e)
    if isinstance(e, ast.Subscript):
        return emit_subscript(ctx, e)
    if isinstance(e, ast.Call):
        return emit_call(ctx, e)
    if isinstance(e, ast.IfExp):
        # General IfExp (the `X is not None` form is handled at statement level).
        c, tc = emit_expr(ctx, e.test)
        if tc != T_BOOL:
            reject(src, e, "conditional-expression test is not bool")
        a, ta = emit_expr(ctx, e.body)
        b, tb = emit_expr(ctx, e.orelse)
        if ta != tb:
            reject(src, e, "conditional-expression branches of distinct types")
        return f"(if {c} then {a} else {b})", ta
    if isinstance(e, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        reject(src, e, "comprehension/generator expression")
    if isinstance(e, ast.Lambda):
        reject(src, e, "lambda outside a min/max key position")
    if isinstance(e, ast.Attribute):
        reject(src, e, f"attribute access .{e.attr} (str/list methods are out of subset)")
    reject(src, e, f"expression node {type(e).__name__}")


def emit_compare(ctx: Ctx, e: ast.Compare) -> tuple[str, LType]:
    src = ctx.src
    # `is None` / `is not None` are only legal inside the recognized guard
    # patterns, which are intercepted before reaching here.
    for op, comp in zip(e.ops, e.comparators, strict=True):
        if isinstance(op, (ast.Is, ast.IsNot)):
            reject(src, e, "`is (not) None` outside a recognized Optional guard pattern")
        if isinstance(comp, ast.Constant) and comp.value is None:
            reject(src, e, "comparison against None with ==/!=")
    operands = [e.left, *e.comparators]
    parts: list[str] = []
    for i, op in enumerate(e.ops):
        a, ta = emit_expr(ctx, operands[i])
        b, tb = emit_expr(ctx, operands[i + 1])
        if ta != tb:
            reject(src, e, "comparison between distinct types")
        if isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
            if ta != T_INT:
                reject(src, e, "ordered comparison on a non-int")
            sym = {ast.Lt: "<", ast.LtE: "≤", ast.Gt: ">", ast.GtE: "≥"}[type(op)]
            parts.append(f"(decide ({a} {sym} {b}))")
        elif isinstance(op, ast.Eq):
            if ta not in (T_INT, T_STRING):
                reject(src, e, "equality on an unsupported type")
            parts.append(f"(decide ({a} = {b}))")
        elif isinstance(op, ast.NotEq):
            if ta not in (T_INT, T_STRING):
                reject(src, e, "inequality on an unsupported type")
            parts.append(f"(!(decide ({a} = {b})))")
        else:
            reject(src, e, f"comparison operator {type(op).__name__}")
    if len(parts) == 1:
        return parts[0], T_BOOL
    return "(" + " && ".join(parts) + ")", T_BOOL


def emit_subscript(ctx: Ctx, e: ast.Subscript) -> tuple[str, LType]:
    src = ctx.src
    if not isinstance(e.value, ast.Name):
        reject(src, e, "subscript of a non-variable")
    base = e.value.id
    if base in ctx.unwraps:
        binder, t = ctx.unwraps[base]
    elif base in ctx.vars:
        binder, t = base, ctx.vars[base]
    else:
        reject(src, e, f"subscript of unbound name {base!r}")
    if t.kind != "Tuple":
        reject(src, e, f"subscript of non-tuple {base!r} ({t.kind}; dict reads use .get)")
    if not isinstance(e.slice, ast.Constant) or not isinstance(e.slice.value, int):
        reject(src, e, "non-constant tuple index")
    i = e.slice.value
    if not 0 <= i < len(t.args):
        reject(src, e, f"tuple index {i} out of range")
    return f"({proj(binder, i, len(t.args))})", t.args[i]


def emit_call(ctx: Ctx, e: ast.Call) -> tuple[str, LType]:
    src = ctx.src
    # dict.get(k, default)
    if isinstance(e.func, ast.Attribute):
        if e.func.attr == "get" and isinstance(e.func.value, ast.Name):
            d, td = emit_expr(ctx, e.func.value)
            if td.kind != "Dict":
                reject(src, e, ".get on a non-dict value")
            if td.args != (T_STRING, T_INT):
                reject(src, e, "dict helpers are monomorphic over (str, int) in v1")
            if len(e.args) != 2 or e.keywords:
                reject(src, e, "dict.get without an explicit default")
            k, tk = emit_expr(ctx, e.args[0])
            dflt, tdflt = emit_expr(ctx, e.args[1])
            if tk != td.args[0] or tdflt != td.args[1]:
                reject(src, e, "dict.get key/default type mismatch")
            ctx.helpers.add("_dictGetD")
            return f"(_dictGetD {d} {k} {dflt})", td.args[1]
        reject(src, e, f"method call .{e.func.attr}(..)")
    if not isinstance(e.func, ast.Name):
        reject(src, e, "call of a non-name")
    fname = e.func.id
    if fname == ctx.fn_name:
        reject(src, e, "recursion (v2)")
    if fname in ("min", "max"):
        return emit_min_max(ctx, e, fname)
    if fname == "abs":
        if len(e.args) != 1 or e.keywords:
            reject(src, e, "abs with unexpected arguments")
        a, ta = emit_expr(ctx, e.args[0])
        if ta != T_INT:
            reject(src, e, "abs on a non-int")
        ctx.helpers.add("_intAbs")
        return f"(_intAbs {a})", T_INT
    if fname == "len":
        if len(e.args) != 1 or e.keywords:
            reject(src, e, "len with unexpected arguments")
        a, ta = emit_expr(ctx, e.args[0])
        if ta.kind not in ("List", "Dict"):
            reject(src, e, "len on a non-sequence")
        return f"(Int.ofNat (List.length {a}))", T_INT
    if fname == "dict":
        if len(e.args) != 1 or e.keywords:
            reject(src, e, "dict(..) with unexpected arguments")
        a, ta = emit_expr(ctx, e.args[0])
        if ta.kind != "Dict":
            reject(src, e, "dict(..) copy of a non-dict")
        return a, ta
    if fname in ctx.vars and ctx.vars[fname].kind == "Fn":
        ft = ctx.vars[fname]
        params, ret = ft.args[:-1], ft.args[-1]
        if len(e.args) != len(params) or e.keywords:
            reject(src, e, f"call arity mismatch for {fname!r}")
        rendered: list[str] = []
        for arg_node, want in zip(e.args, params, strict=True):
            arg_code, got = emit_expr(ctx, arg_node)
            if got != want:
                reject(src, e, f"argument type mismatch in call to {fname!r}")
            rendered.append(arg_code)
        return "(" + " ".join([fname, *rendered]) + ")", ret
    reject(src, e, f"call to {fname!r}")


def emit_min_max(ctx: Ctx, e: ast.Call, fname: str) -> tuple[str, LType]:
    src = ctx.src
    if len(e.args) == 2 and not e.keywords:
        a, ta = emit_expr(ctx, e.args[0])
        b, tb = emit_expr(ctx, e.args[1])
        if ta != T_INT or tb != T_INT:
            reject(src, e, f"{fname}(a, b) on non-int operands")
        return f"({fname} {a} {b})", T_INT
    if len(e.args) == 1 and len(e.keywords) == 1 and e.keywords[0].arg == "key":
        if fname != "min":
            reject(src, e, "max(.., key=..) is not used by any v1 core; only min is emitted")
        seq, tseq = emit_expr(ctx, e.args[0])
        if tseq.kind != "List":
            reject(src, e, "min(.., key=..) over a non-sequence")
        elem = tseq.args[0]
        if elem != LType("Tuple", (T_INT, T_INT)):
            reject(src, e, "min(.., key=..) is monomorphic over (int, int) elements in v1")
        lam = e.keywords[0].value
        if not isinstance(lam, ast.Lambda) or len(lam.args.args) != 1:
            reject(src, e, "min key must be a single-parameter lambda")
        param = check_ident(src, lam, lam.args.args[0].arg)
        body = lam.body
        if not isinstance(body, ast.Tuple):
            reject(src, e, "min key lambda must return a tuple")
        lam_ctx = branch(ctx)
        lam_ctx.vars[param] = elem
        comps: list[tuple[str, LType]] = [emit_expr(lam_ctx, c) for c in body.elts]
        if len(comps) != 3 or any(t != T_INT for _, t in comps):
            reject(src, e, "min key helpers are monomorphic over 3 Int components in v1")
        if isinstance(e.args[0], ast.Name) and e.args[0].id in ctx.setlike:
            _require_injective_key(src, e, body, param, len(elem.args))
        ctx.helpers.add("_lexLt3")
        ctx.helpers.add("_minByKey3")
        key = "(fun " + param + " => (" + ", ".join(c for c, _ in comps) + "))"
        return f"(_minByKey3 {key} {seq})", t_option(elem)
    reject(src, e, f"{fname} with unsupported arguments")


def _require_injective_key(src: str, e: ast.Call, body: ast.Tuple, param: str, arity: int) -> None:
    """A set-typed sequence may only be reduced through a key containing every
    element projection (total + injective key => order-independent fold)."""
    seen = set()
    for comp in body.elts:
        if isinstance(comp, ast.Subscript) and isinstance(comp.value, ast.Name) \
                and comp.value.id == param and isinstance(comp.slice, ast.Constant) \
                and isinstance(comp.slice.value, int):
            seen.add(comp.slice.value)
    if seen < set(range(arity)):
        reject(src, e, "min over a set-typed value whose key omits element projections "
                       "(unordered-set iteration would be order-dependent)")


# ---------------------------------------------------------------------------
# Statement-block translation.
# ---------------------------------------------------------------------------
def always_exits(ctx: Ctx, stmts: list[ast.stmt]) -> bool:
    """True when every control path through `stmts` returns (or, in loop mode,
    hits `continue`)."""
    for s in stmts:
        if isinstance(s, ast.Return):
            return True
        if isinstance(s, ast.Continue) and ctx.loop_acc is not None:
            return True
        if isinstance(s, ast.If) and s.orelse \
                and always_exits(ctx, s.body) and always_exits(ctx, s.orelse):
            return True
    return False


def fresh_binder(ctx: Ctx, base: str) -> str:
    ctx.fresh[0] += 1
    return f"{base}_{ctx.fresh[0]}"


def is_none_const(e: ast.expr) -> bool:
    return isinstance(e, ast.Constant) and e.value is None


def match_is_not_none(test: ast.expr) -> str | None:
    """`X is not None` -> X (a plain variable), else None."""
    if isinstance(test, ast.Compare) and len(test.ops) == 1 \
            and isinstance(test.ops[0], ast.IsNot) and is_none_const(test.comparators[0]) \
            and isinstance(test.left, ast.Name):
        return test.left.id
    return None


def match_is_none_or(test: ast.expr) -> tuple[str, ast.expr] | None:
    """`X is None or COND` -> (X, COND), else None."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or) and len(test.values) == 2:
        first = test.values[0]
        if isinstance(first, ast.Compare) and len(first.ops) == 1 \
                and isinstance(first.ops[0], ast.Is) and is_none_const(first.comparators[0]) \
                and isinstance(first.left, ast.Name):
            return first.left.id, test.values[1]
    return None


def unwrap_var(ctx: Ctx, node: ast.stmt, name: str) -> tuple[str, Ctx]:
    """Open an unwrap scope for Optional variable `name`; returns the fresh
    binder and a child ctx in which X[i] resolves through the binder."""
    if name not in ctx.vars or ctx.vars[name].kind != "Option":
        reject(ctx.src, node, f"Optional guard on non-Optional variable {name!r}")
    inner = ctx.vars[name].args[0]
    binder = fresh_binder(ctx, name)
    child = branch(ctx)
    child.unwraps[name] = (binder, inner)
    return binder, child


def coerce_assign(ctx: Ctx, node: ast.stmt, declared: LType, code: str, got: LType) -> str:
    """Python lets a T flow into an Optional[T] slot; Lean needs `some`."""
    if declared == got:
        return code
    if declared.kind == "Option" and declared.args[0] == got:
        return f"(some {code})"
    reject(ctx.src, node, f"assignment type mismatch ({render_type(got)} into {render_type(declared)})")


def emit_return_value(ctx: Ctx, node: ast.stmt, value: ast.expr | None) -> str:
    if value is None or is_none_const(value):
        if ctx.ret.kind != "Option":
            reject(ctx.src, node, "return None from a non-Optional function")
        return "none"
    code, got = emit_expr(ctx, value)
    if got == ctx.ret:
        return code
    if ctx.ret.kind == "Option" and ctx.ret.args[0] == got:
        return f"(some {code})"
    reject(ctx.src, node, f"return type mismatch ({render_type(got)} vs {render_type(ctx.ret)})")


def emit_block(ctx: Ctx, stmts: list[ast.stmt], indent: int) -> str:
    src = ctx.src
    pad = " " * indent
    if not stmts:
        if ctx.loop_acc is not None:
            return ctx.loop_acc
        raise ExtractionError(f"{src}: in {ctx.fn_name}: control falls off the end without a return")
    s, rest = stmts[0], stmts[1:]

    if isinstance(s, ast.Return):
        if ctx.loop_acc is not None:
            reject(src, s, "return inside a loop body")
        if rest:
            reject(src, s, "unreachable statements after return")
        # `return A if X is not None else B` gets the match translation.
        if isinstance(s.value, ast.IfExp):
            x = match_is_not_none(s.value.test)
            if x is not None:
                binder, child = unwrap_var(ctx, s, x)
                a = emit_return_value(child, s, s.value.body)
                b = emit_return_value(ctx, s, s.value.orelse)
                return (f"(match {x} with\n{pad}| some {binder} => {a}\n{pad}| none => {b})")
        return emit_return_value(ctx, s, s.value)

    if isinstance(s, ast.Continue):
        if ctx.loop_acc is None:
            reject(src, s, "continue outside a loop")
        if rest:
            reject(src, s, "unreachable statements after continue")
        return ctx.loop_acc

    if isinstance(s, ast.AnnAssign):
        if not isinstance(s.target, ast.Name) or s.value is None:
            reject(src, s, "annotated assignment without a simple target/value")
        name = check_ident(src, s.target, s.target.id)
        declared, setlike = parse_annotation(src, s.annotation)
        if is_none_const(s.value):
            if declared.kind != "Option":
                reject(src, s, "None assigned into a non-Optional annotation")
            code = "none"
        else:
            val, got = emit_expr(ctx, s.value)
            code = coerce_assign(ctx, s, declared, val, got)
        ctx.vars[name] = declared
        if setlike:
            ctx.setlike.add(name)
        return (f"let {name} : {render_type(declared)} := {code}\n{pad}"
                + emit_block(ctx, rest, indent))

    if isinstance(s, ast.Assign):
        if len(s.targets) != 1:
            reject(src, s, "multiple assignment targets")
        target = s.targets[0]
        if isinstance(target, ast.Subscript):
            return emit_dict_set(ctx, s, target, rest, indent)
        if not isinstance(target, ast.Name):
            reject(src, s, f"assignment target {type(target).__name__}")
        name = check_ident(src, target, target.id)
        val, got = emit_expr(ctx, s.value)
        if name in ctx.vars:
            code = coerce_assign(ctx, s, ctx.vars[name], val, got)
            declared = ctx.vars[name]
        else:
            code, declared = val, got
            ctx.vars[name] = declared
        return f"let {name} := {code}\n{pad}" + emit_block(ctx, rest, indent)

    if isinstance(s, ast.For):
        return emit_for(ctx, s, rest, indent)

    if isinstance(s, ast.If):
        return emit_if(ctx, s, rest, indent)

    if isinstance(s, ast.While):
        reject(src, s, "while loop")
    if isinstance(s, ast.Try):
        reject(src, s, "try/except")
    if isinstance(s, (ast.With, ast.Raise, ast.Assert, ast.ClassDef,
                      ast.FunctionDef, ast.AsyncFunctionDef)):
        reject(src, s, type(s).__name__.lower())
    if isinstance(s, ast.Break):
        reject(src, s, "break")
    if isinstance(s, ast.Expr):
        reject(src, s, "expression statement (no effects in the pure subset)")
    reject(src, s, f"statement node {type(s).__name__}")


def emit_dict_set(ctx: Ctx, s: ast.Assign, target: ast.Subscript,
                  rest: list[ast.stmt], indent: int) -> str:
    src = ctx.src
    pad = " " * indent
    if not isinstance(target.value, ast.Name):
        reject(src, s, "subscript assignment to a non-variable")
    name = target.value.id
    if name not in ctx.vars or ctx.vars[name].kind != "Dict":
        reject(src, s, "subscript assignment to a non-dict")
    dt = ctx.vars[name]
    if dt.args != (T_STRING, T_INT):
        reject(src, s, "dict helpers are monomorphic over (str, int) in v1")
    k, tk = emit_expr(ctx, target.slice)
    v, tv = emit_expr(ctx, s.value)
    if tk != dt.args[0] or tv != dt.args[1]:
        reject(src, s, "dict assignment key/value type mismatch")
    ctx.helpers.add("_dictSet")
    return (f"let {name} := (_dictSet {name} {k} {v})\n{pad}"
            + emit_block(ctx, rest, indent))


def emit_for(ctx: Ctx, s: ast.For, rest: list[ast.stmt], indent: int) -> str:
    src = ctx.src
    pad = " " * indent
    if s.orelse:
        reject(src, s, "for/else")
    if isinstance(s.iter, ast.Name) and s.iter.id in ctx.setlike:
        reject(src, s, "iteration over a set-typed value (order-dependent)")
    seq, tseq = emit_expr(ctx, s.iter)
    if tseq.kind != "List":
        reject(src, s, "for over a non-sequence")
    elem = tseq.args[0]
    assigned = sorted({n.id for n in ast.walk(s) if isinstance(n, ast.Name)
                       and isinstance(n.ctx, ast.Store)} - _target_names(s.target))
    if len(assigned) != 1:
        reject(src, s, f"loop must have exactly one accumulator (got {assigned!r})")
    acc = assigned[0]
    if acc not in ctx.vars:
        reject(src, s, f"loop accumulator {acc!r} is not bound before the loop")
    body_ctx = branch(ctx, loop_acc=acc)
    if isinstance(s.target, ast.Name):
        binder = check_ident(src, s, s.target.id)
        body_ctx.vars[binder] = elem
        body = emit_block(body_ctx, s.body, indent + 4)
        fn = f"(fun {acc} {binder} =>\n{pad}    {body})"
    elif isinstance(s.target, ast.Tuple) and all(isinstance(t, ast.Name) for t in s.target.elts):
        if elem.kind != "Tuple" or len(elem.args) != len(s.target.elts):
            reject(src, s, "loop target arity mismatch with element tuple")
        names = [check_ident(src, s, t.id) for t in s.target.elts
                 if isinstance(t, ast.Name)]
        body_ctx.vars["_x"] = elem
        unpack = ""
        for i, (n, t) in enumerate(zip(names, elem.args, strict=True)):
            body_ctx.vars[n] = t
            unpack += f"let {n} := ({proj('_x', i, len(elem.args))})\n{pad}    "
        body = emit_block(body_ctx, s.body, indent + 4)
        fn = f"(fun {acc} _x =>\n{pad}    {unpack}{body})"
    else:
        reject(src, s, "loop target must be a name or a tuple of names")
    return (f"let {acc} := List.foldl\n{pad}  {fn}\n{pad}  {acc} {seq}\n{pad}"
            + emit_block(ctx, rest, indent))


def _target_names(target: ast.expr) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def emit_if(ctx: Ctx, s: ast.If, rest: list[ast.stmt], indent: int) -> str:
    src = ctx.src
    pad = " " * indent

    # Pattern A: `if X is not None: <always-exits body>`.
    x = match_is_not_none(s.test)
    if x is not None and not s.orelse:
        if not always_exits(ctx, s.body):
            reject(src, s, "`if X is not None` body that does not always return")
        binder, child = unwrap_var(ctx, s, x)
        body = emit_block(child, s.body, indent + 2)
        cont = emit_block(branch(ctx), rest, indent + 2)
        return (f"(match {x} with\n{pad}| some {binder} =>\n{pad}  {body}\n"
                f"{pad}| none =>\n{pad}  {cont})")

    # Pattern B: `if X is None or COND: <body>` (body + continuation in both arms).
    none_or = match_is_none_or(s.test)
    if none_or is not None and not s.orelse:
        xname, cond = none_or
        binder, child = unwrap_var(ctx, s, xname)
        cond_code, tc = emit_expr(child, cond)
        if tc != T_BOOL:
            reject(src, s, "Optional-guard residual condition is not bool")
        taken = emit_block(branch(ctx), s.body + rest, indent + 4)
        taken2 = emit_block(branch(ctx), s.body + rest, indent + 4)
        skipped = emit_block(branch(ctx), rest, indent + 4)
        return (f"(match {xname} with\n{pad}| none =>\n{pad}    {taken}\n"
                f"{pad}| some {binder} =>\n"
                f"{pad}  (if {cond_code}\n{pad}   then\n{pad}    {taken2}\n"
                f"{pad}   else\n{pad}    {skipped}))")

    cond_code, tc = emit_expr(ctx, s.test)
    if tc != T_BOOL:
        reject(src, s, "if condition is not bool (truthiness)")

    # Always-exiting body: `(if c then body else rest)` (elif chains recurse).
    if always_exits(ctx, s.body):
        body = emit_block(branch(ctx), s.body, indent + 2)
        if s.orelse:
            if rest:
                reject(src, s, "statements after an if/else where both branches return")
            alt = emit_block(branch(ctx), s.orelse, indent + 2)
        else:
            alt = emit_block(branch(ctx), rest, indent + 2)
        return f"(if {cond_code}\n{pad} then\n{pad}  {body}\n{pad} else\n{pad}  {alt})"

    # Accumulator-update body: `if c: acc = e` (loop mode only).
    if ctx.loop_acc is not None and not s.orelse and len(s.body) == 1 \
            and isinstance(s.body[0], ast.Assign):
        a = s.body[0]
        if len(a.targets) == 1 and isinstance(a.targets[0], ast.Name) \
                and a.targets[0].id == ctx.loop_acc:
            val, got = emit_expr(ctx, a.value)
            code = coerce_assign(ctx, a, ctx.vars[ctx.loop_acc], val, got)
            return (f"let {ctx.loop_acc} := (if {cond_code} then {code} else {ctx.loop_acc})\n"
                    f"{pad}" + emit_block(ctx, rest, indent))

    reject(src, s, "if statement outside the supported translation patterns")


# ---------------------------------------------------------------------------
# Function / module extraction.
# ---------------------------------------------------------------------------
def extract_function(src: str, fd: ast.FunctionDef, helpers: set[str]) -> str:
    if fd.decorator_list:
        reject(src, fd, "decorated function")
    a = fd.args
    if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs or a.defaults or a.kw_defaults:
        reject(src, fd, "defaults/*args/**kwargs/keyword-only parameters")
    if fd.returns is None:
        reject(src, fd, "missing return annotation")
    ret, _ = parse_annotation(src, fd.returns)
    params: list[tuple[str, LType]] = []
    ctx = Ctx(src=src, fn_name=fd.name, ret=ret, vars={}, setlike=set(),
              unwraps={}, helpers=helpers)
    for arg in a.args:
        if arg.annotation is None:
            reject(src, arg, f"missing annotation on parameter {arg.arg!r}")
        t, setlike = parse_annotation(src, arg.annotation)
        name = check_ident(src, arg, arg.arg)
        params.append((name, t))
        ctx.vars[name] = t
        if setlike:
            ctx.setlike.add(name)
    body = list(fd.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]  # docstring
    expr = emit_block(ctx, body, 2)
    sig = " ".join(f"({n} : {render_type(t)})" for n, t in params)
    return (f"/-- Extracted from `{fd.name}` (line {fd.lineno}). -/\n"
            f"def {fd.name} {sig} :\n    {render_type(ret)} :=\n  {expr}")


def extract_module(spec: ModuleSpec) -> str:
    path = ROOT / spec.source
    text = path.read_text()
    digest = hashlib.sha256(text.encode()).hexdigest()
    tree = ast.parse(text, filename=spec.source)
    by_name = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    missing = [f for f in spec.functions if f not in by_name]
    if missing:
        raise ExtractionError(f"{spec.source}: registered functions not found: {missing}")
    helpers: set[str] = set()
    defs = [extract_function(spec.source, by_name[f], helpers) for f in spec.functions]
    helper_blocks = [HELPER_DEFS[h] for h in HELPER_ORDER if h in helpers]
    parts = [
        f"-- GENERATED from {spec.source} (sha256: {digest}) — DO NOT EDIT",
        "-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).",
        "",
        f"namespace Extracted.{spec.core_name}",
        "",
        "\n\n".join(helper_blocks + defs),
        "",
        f"end Extracted.{spec.core_name}",
        "",
    ]
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=
                                     "Mechanically extract Lean 4 models from the Python pure cores.")
    parser.add_argument("--check", action="store_true",
                        help="regenerate in memory and fail (exit 1) on any drift from disk")
    args = parser.parse_args(argv)
    drift = False
    for spec in MODULES:
        generated = extract_module(spec)
        out = ROOT / spec.output
        if args.check:
            on_disk = out.read_text() if out.exists() else ""
            if on_disk != generated:
                drift = True
                print(f"DRIFT: {spec.output} does not match extraction from {spec.source}")
                sys.stdout.writelines(difflib.unified_diff(
                    on_disk.splitlines(keepends=True), generated.splitlines(keepends=True),
                    fromfile=f"on-disk/{spec.output}", tofile=f"extracted/{spec.output}"))
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(generated)
            print(f"wrote {spec.output}")
    if args.check:
        if drift:
            return 1
        print(f"extraction check OK ({len(MODULES)} modules byte-identical)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ExtractionError as err:
        print(f"EXTRACTION FAILED: {err}", file=sys.stderr)
        sys.exit(1)
