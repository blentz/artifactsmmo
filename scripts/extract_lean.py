"""Mechanical Python -> Lean 4 extractor (v6) for the pure decision cores.

Per docs/PLAN_mechanical_extraction.md: the Lean models gating the planner are
MECHANICALLY EXTRACTED from the Python pure-core modules, so the generated
definition is a syntactic image of the running code and any drift breaks the
gate (`--check` mode + formal/gate/check_extraction.sh). Hand-written bridge
lemmas in formal/Formal/Extracted/Bridges.lean prove each extracted definition
equal to the pre-existing hand model, transferring the hand theorems.

V6 SUBSET (anything else is REJECTED loudly, naming the construct + line):

  types       int -> Int, bool -> Bool, str -> String,
              fractions.Fraction -> Rat (exact rationals on both sides),
              X | None / Optional[X] -> Option, tuple[..] -> Prod,
              list/Sequence -> List, dict/Mapping[k, v] -> List (k x v)
              + emitted lookup helpers (str keys, any mapped value type),
              set[X]/frozenset|list unions -> List (set-semantics caveat
              below), Callable[[A..], R] -> plain function argument,
              registry-declared OPAQUE types (e.g. `Goal`, `Action`) ->
              implicit `{X : Type}` binders (payload only: carried,
              passed to Callable params, never inspected),
              registry-declared frozen @dataclass -> Lean `structure`
              (parameterised by the opaque types its fields mention;
              field reads -> projections; construction is out of subset
              until a core needs it).
  exprs       int/bool literals, str literals (printable ASCII without
              quote/backslash), None, {} (only where the dict type is
              pinned: an annotated assignment, a dict.get default, or a
              dict-returning `return {}`),
              + (Int, Rat, or List concatenation -> ++), - (Int),
              * (Int or Rat), / (Rat only -> Rat division), // -> Int.fdiv,
              % -> Int.fmod
              (CAVEAT: Lean's Int.fdiv/fmod AND Rat division are total
              with divisor 0 -> 0 where Python raises ZeroDivisionError;
              cores must keep divisors nonzero by construction, e.g.
              recipe quantities >= 1, gold_per_xp = 100),
              non-empty list literals [a, b, ..] of a uniform element
              type (a starred segment `[*xs, v]` splices -> xs ++ [v],
              the append-copy idiom), xs[i] on a list[int] with an int
              index -> _nthInt
              (CAVEAT: total — out-of-range reads 0 and a negative index
              clamps to 0 where Python raises/wraps; extracted cores keep
              indices in range by construction),
              sorted(xs) on list[int] -> _sortInt (insertion sort;
              sorting an int multiset is order-independent, so it agrees
              with Python's stable Timsort on every input),
              list(reversed(xs)) -> List.reverse,
              Fraction(a) / Fraction(a, b) over ints -> mkRat a 1 /
              mkRat a b (both normalize identically; CAVEAT: mkRat a 0
              = 0 where Python Fraction(a, 0) raises — denominators are
              non-zero literals by construction),
              `x in xs` where xs is a list/frozenset of str or int ->
              List.contains (membership is order-independent, so
              set-typed operands are safe),
              comparisons (chained ok) -> decide (..), and/or/not
              -> && || !, max/min(a, b) (Int or Rat) and n-ary
              max/min(a, b, c, ..) (Int; right-nested two-arg, value-equal
              to Python's first-maximal pick), abs -> _intAbs,
              len -> Int.ofNat (List.length ..), d.get(k, default) ->
              _dictGetD, dict(d) -> identity copy, tuple construction,
              constant tuple indexing -> Prod projections, calls to
              Callable parameters, to PREVIOUSLY-extracted functions of
              the same module, or to registry-declared `imports` from
              EARLIER-registered modules (emitted fully qualified, e.g.
              `Extracted.RecipeClosure._raw_units`, with the matching
              `import Formal.Extracted.<Core>` header lines; a fueled
              callee's Int fuel is bridged with `Int.toNat`),
              registry-declared module-level int CONSTANTS (emitted as
              `def NAME : Int := ..` and readable from every function),
              lambda (only as a min/max key),
              `A if X is not None else B`, `A if c else None` ->
              `if c then some A else none`, a set comprehension
              `{elt for k, v in d.items() if cond}` -> List.map over
              List.filter (dict keys are unique, so the list IS the set),
              a list comprehension `[elt for x in xs if cond]` ->
              List.map over List.filter, `any(expr for x in xs)` ->
              List.any, `next((x for x in xs if cond), None)` -> _find,
              `next((i for i, x in enumerate(xs) if cond), None)` ->
              _findIdx (Int index), struct field access `c.field` ->
              projection, `==`/`!=` between `Optional[T]` and `T`
              (T = int/str) -> `decide (opt = some plain)` (Python:
              `None == t` is False, `some s == t` is `s == t`).
  stmts       assignment (let), annotated assignment (a tuple literal
              value is coerced componentwise into the declared tuple
              type, so `([], None, None)` pins empty-list/None slots),
              dict-subscript assignment -> _dictSet, early return, if/elif with
              always-returning bodies, plain fall-through `if` ->
              `(if c then <body+rest> else <rest>)` (rest duplicated),
              for-with-single-accumulator -> List.foldl (iterable: a
              list value or d.items()), FIRST-MATCH for loops (a body
              whose paths only `continue` or `return`, no cross-
              iteration state; target a name OR a tuple of names) ->
              _findSome with `return e` as `some e`,
              `continue` inside loops.
  recursion   FUEL-BOUNDED self-recursion only: the function's first
              parameter is `fuel: int`, the body opens with
              `if fuel <= 0: return <base>`, and every self-call passes
              `fuel - 1` first (no other read of `fuel` is allowed).
              Emitted as a two-arm `Nat` pattern match (`| 0 ..` /
              `| fuel + 1 ..`) so Lean recursion is STRUCTURAL on the
              fuel — exactly the hand models' fuel idiom. External
              callers' Int fuel is bridged with `Int.toNat` (Python
              `fuel <= 0` <-> Lean fuel 0).

  REJECTED    while, try/except, with, raise, assert, behavioural
              classes (only registered frozen dataclasses), generator /
              dict comprehensions outside the shapes above, float
              literals or annotations, str methods (any attribute except
              dict .get, dict .items and struct fields), recursion
              without the fuel discipline, mutual recursion, break,
              return inside an accumulator loop, *args/**kwargs,
              parameter defaults OTHER than int literals / registered int
              constants (allowed defaults are IGNORED: default application
              happens at Python call sites outside the extraction boundary;
              the Lean def takes every parameter explicitly),
              decorators (except @dataclass on registered structures),
              missing type annotations, iteration over a set-typed value
              (only min/max with an injective total key may consume one),
              bare reads of a TUPLE-typed Optional inside its unwrap
              context (subscript it; non-tuple unwraps read as the
              binder), Lean reserved words as identifiers.

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
  if X is None or Y is None:   =>  (match X with
      <always-exits body>           | none => <body>
                                    | some X_k =>
                                      (match Y with
                                       | none => <body>
                                       | some Y_k => <rest, both unwrapped>))
  if X is None:                =>  (match X with
      <always-exits body>           | none => <body>
                                    | some X_k => <rest, X unwrapped>)
  if X is not None and COND:   =>  (match X with
      <body>                        | some X_k => (if COND[unwrapped]
                                                   then <body + rest>
                                                   else <rest>)
                                    | none => <rest>)

A non-exiting `if X is not None:` body falls into the same `match` with
`<body + rest>` in the `some` arm. A FIRST-MATCH loop body is translated
with `return e` as `some e` and `continue`/fall-off-the-end as `none`;
the loop becomes `match _findSome (fun x => <body>) xs with | some r => r
| none => <rest>` (sound because Python `return` exits the function; the
extractor verifies no loop-assigned name is read before assignment in the
body or anywhere after the loop).

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
    """A Lean type in the extraction image: Int | Bool | String | Rat |
    Option t | Tuple (flat component list, rendered right-nested) | List t |
    Dict k v (rendered List (k x v)) | Fn (args.., ret) | Var (an opaque
    type parameter, `name`) | Struct (a registered dataclass, `name`,
    args = its instantiated type parameters)."""

    kind: str
    args: tuple["LType", ...] = ()
    name: str = ""


T_INT = LType("Int")
T_BOOL = LType("Bool")
T_STRING = LType("String")
T_RAT = LType("Rat")


def t_option(t: LType) -> LType:
    return LType("Option", (t,))


def t_list(t: LType) -> LType:
    return LType("List", (t,))


@dataclass(frozen=True)
class ModuleSpec:
    """Registry entry: one Python source module -> one generated Lean file.

    `opaque_types` are Python class names mapped to implicit `{X : Type}`
    binders (pure payload). `structures` are frozen-dataclass names emitted
    as Lean `structure`s (in declaration order, before the functions).
    `constants` are module-level int constants emitted as `def NAME : Int`.
    `imports` are function names of EARLIER-registered modules this module's
    cores may call (emitted fully qualified, with matching import lines)."""

    source: str
    output: str
    core_name: str
    functions: tuple[str, ...]
    opaque_types: tuple[str, ...] = ()
    structures: tuple[str, ...] = ()
    constants: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()


@dataclass
class TypeEnv:
    """Per-module type environment: the registry-declared opaque type
    parameters and the extracted structures (name -> (fields, type params))."""

    opaque: tuple[str, ...] = ()
    structs: dict[str, tuple[tuple[tuple[str, LType], ...], tuple[str, ...]]] = field(
        default_factory=dict)


# ---------------------------------------------------------------------------
# Registry (P1: the Tier-1 trio; P2a: priority_band + shopping_list; P2b:
# arbiter_select; P3a: the recipe family; P3b: inventory_caps; P3c: the
# exact-Fraction learning cores; P4b: the exact equipment-scoring cores
# unlocked by P4a). `functions`
# order is the emission
# order: a function may only call functions emitted BEFORE it (plus
# fuel-bounded self-recursion); `imports` may only name functions of modules
# registered BEFORE this one.
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
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/priority_band.py",
        output=f"{GENERATED_DIR}/PriorityBand.lean",
        core_name="PriorityBand",
        functions=("clamp_into_band",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/shopping_list.py",
        output=f"{GENERATED_DIR}/ShoppingList.lean",
        core_name="ShoppingList",
        functions=("_expand", "shopping_list", "fully_covered_materials"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/arbiter_select.py",
        output=f"{GENERATED_DIR}/ArbiterSelect.lean",
        core_name="ArbiterSelect",
        functions=("_precedes", "select_pure"),
        opaque_types=("Goal", "Action"),
        structures=("Candidate",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/recipe_closure.py",
        output=f"{GENERATED_DIR}/RecipeClosure.lean",
        core_name="RecipeClosure",
        functions=("_closure_visited", "_raw_units", "_closure_demand",
                   "recipe_closure_pure"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/task_batch.py",
        output=f"{GENERATED_DIR}/TaskBatch.lean",
        core_name="TaskBatch",
        functions=("task_batch_size_pure",),
        constants=("BATCH_CAP", "_MIN_FREE_SLOTS"),
        imports=("_raw_units", "_closure_visited"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/task_reservation.py",
        output=f"{GENERATED_DIR}/TaskReservation.lean",
        core_name="TaskReservation",
        functions=("task_reserved_demand_pure", "consumes_reserved_pure"),
        imports=("_closure_demand",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/inventory_caps.py",
        output=f"{GENERATED_DIR}/InventoryCaps.lean",
        core_name="InventoryCaps",
        functions=("overstock_excess", "_is_dominated_pure",
                   "_task_chain_demand_pure",
                   "useful_quantity_cap_excl_equipped_pure",
                   "useful_quantity_cap_pure"),
        constants=("DISCARD_WATERMARK_NUM", "DISCARD_WATERMARK_DEN",
                   "EQUIPPABLE_KEEP", "CONSUMABLE_KEEP"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/learning/cycles_for_progress_core.py",
        output=f"{GENERATED_DIR}/CyclesForProgress.lean",
        core_name="CyclesForProgress",
        functions=("_strict_step", "_satisfy_step", "_median_exact",
                   "cycles_for_progress_exact"),
        structures=("CycleRow",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/learning/scalar_core.py",
        output=f"{GENERATED_DIR}/ScalarCore.lean",
        core_name="ScalarCore",
        functions=("scalar_yield_exact", "coins_spent_from_delta"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/min_gathers.py",
        output=f"{GENERATED_DIR}/MinGathers.lean",
        core_name="MinGathers",
        functions=("_min_gathers", "min_gathers"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/gather_floor.py",
        output=f"{GENERATED_DIR}/GatherFloor.lean",
        core_name="GatherFloor",
        functions=("ceil_gathers",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/min_crafts.py",
        output=f"{GENERATED_DIR}/MinCrafts.lean",
        core_name="MinCrafts",
        functions=("_min_crafts", "min_crafts"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/min_plan_length.py",
        output=f"{GENERATED_DIR}/MinPlanLength.lean",
        core_name="MinPlanLength",
        functions=("min_plan_length",),
        imports=("ceil_gathers", "min_gathers", "min_crafts"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/equipment/scoring.py",
        output=f"{GENERATED_DIR}/EquipmentScoring.lean",
        core_name="EquipmentScoring",
        functions=("weapon_score_raw_pure", "weapon_score_pure",
                   "gather_score_pure", "armor_score_pure"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/tiers/equip_value.py",
        output=f"{GENERATED_DIR}/EquipValue.lean",
        core_name="EquipValue",
        functions=("equip_value_pure", "tool_value_pure"),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/tiers/skill_target_curve.py",
        output=f"{GENERATED_DIR}/SkillTargetCurve.lean",
        core_name="SkillTargetCurve",
        functions=("skill_curve_target_pure",),
        structures=("SkillItem",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py",
        output=f"{GENERATED_DIR}/SkillGrindSelection.lean",
        core_name="SkillGrindSelection",
        functions=("_beats", "skill_grind_selection_pure"),
        structures=("GrindCandidate",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/tiers/skill_step_dispatch.py",
        output=f"{GENERATED_DIR}/SkillStepDispatch.lean",
        core_name="SkillStepDispatch",
        functions=("combine_dispatch_pure",),
    ),
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/tiers/strategic_value.py",
        output=f"{GENERATED_DIR}/StrategicValue.lean",
        core_name="StrategicValue",
        functions=("strategic_value_pure",),
    ),
)


@dataclass
class Ctx:
    """Per-function translation context (vars/unwraps/setlike/aliases are
    scoped by copying at branch points; helpers, the module signature table
    and the fresh counter are shared)."""

    src: str
    fn_name: str
    ret: LType
    vars: dict[str, LType]
    setlike: set[str]
    unwraps: dict[str, tuple[str, LType]]
    helpers: set[str]
    loop_acc: str | None = None
    # First-match loop mode: `loop_acc` is the literal Lean `none` and
    # `return e` emits `some e` (the loop is a `_findSome`).
    loop_first: bool = False
    fresh: list[int] = field(default_factory=lambda: [0])
    # Fuel-bounded recursion: True inside the `fuel + 1` arm of a fueled
    # function; rec_params are its parameter types EXCLUDING the fuel.
    fueled: bool = False
    rec_params: tuple[LType, ...] = ()
    # Signatures of module functions already emitted: name -> (param types
    # excluding any fuel, return type, fueled?). Shared (read-only) so a later
    # function can call an earlier one.
    module_sigs: dict[str, tuple[tuple[LType, ...], LType, bool]] = field(default_factory=dict)
    # Signatures of registry-declared imports from EARLIER-registered modules:
    # name -> (core name, param types excluding any fuel, return type,
    # fueled?). Shared (read-only); calls render fully qualified.
    import_sigs: dict[str, tuple[str, tuple[LType, ...], LType, bool]] = field(
        default_factory=dict)
    # Comprehension binders: Python name -> (rendered Lean code, type).
    aliases: dict[str, tuple[str, LType]] = field(default_factory=dict)
    # Module type environment (opaque type params + structures). Shared.
    tenv: TypeEnv = field(default_factory=TypeEnv)


def branch(ctx: Ctx, loop_acc: str | None = None,
           loop_first: bool | None = None) -> Ctx:
    """A child scope: copied bindings, SHARED helper set + fresh counter."""
    return Ctx(
        src=ctx.src, fn_name=ctx.fn_name, ret=ctx.ret,
        vars=dict(ctx.vars), setlike=set(ctx.setlike),
        unwraps=dict(ctx.unwraps), helpers=ctx.helpers,
        loop_acc=ctx.loop_acc if loop_acc is None else loop_acc,
        loop_first=ctx.loop_first if loop_first is None else loop_first,
        fresh=ctx.fresh,
        fueled=ctx.fueled, rec_params=ctx.rec_params,
        module_sigs=ctx.module_sigs,
        import_sigs=ctx.import_sigs,
        aliases=dict(ctx.aliases),
        tenv=ctx.tenv,
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
    if t.kind in ("Int", "Bool", "String", "Rat"):
        return t.kind
    if t.kind == "Var":
        return t.name
    if t.kind == "Struct":
        if not t.args:
            return t.name
        return t.name + " " + " ".join(render_atom(a) for a in t.args)
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
    if t.kind in ("Int", "Bool", "String", "Rat", "Tuple", "Fn", "Var"):
        return render_type(t)
    if t.kind == "Struct" and not t.args:
        return render_type(t)
    return f"({render_type(t)})"


def parse_annotation(env: TypeEnv, src: str, node: ast.expr) -> tuple[LType, bool]:
    """Parse an annotation -> (LType, setlike). Rejects anything unmapped."""
    if isinstance(node, ast.Name):
        if node.id == "int":
            return T_INT, False
        if node.id == "bool":
            return T_BOOL, False
        if node.id == "str":
            return T_STRING, False
        if node.id == "Fraction":
            return T_RAT, False
        if node.id == "float":
            reject(src, node, "float annotation")
        if node.id in env.opaque:
            return LType("Var", name=node.id), False
        if node.id in env.structs:
            _, params = env.structs[node.id]
            return LType("Struct", tuple(LType("Var", name=p) for p in params),
                         name=node.id), False
        reject(src, node, f"type annotation {node.id!r}")
    if isinstance(node, ast.Constant) and node.value is None:
        reject(src, node, "bare None annotation outside a union")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        members = _flatten_union(node)
        non_none = [m for m in members if not (isinstance(m, ast.Constant) and m.value is None)]
        has_none = len(non_none) < len(members)
        parsed = [parse_annotation(env, src, m) for m in non_none]
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
            inner, setlike = parse_annotation(env, src, node.slice)
            return t_option(inner), setlike
        if head == "tuple":
            if not isinstance(node.slice, ast.Tuple):
                reject(src, node, "non-tuple subscript on tuple[..]")
            comps = [parse_annotation(env, src, e)[0] for e in node.slice.elts]
            return LType("Tuple", tuple(comps)), False
        if head in ("list", "Sequence"):
            return t_list(parse_annotation(env, src, node.slice)[0]), False
        if head == "frozenset" or head == "set":
            return t_list(parse_annotation(env, src, node.slice)[0]), True
        if head in ("dict", "Mapping"):
            if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2:
                reject(src, node, "dict annotation without key/value pair")
            k = parse_annotation(env, src, node.slice.elts[0])[0]
            v = parse_annotation(env, src, node.slice.elts[1])[0]
            return LType("Dict", (k, v)), False
        if head == "Callable":
            if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2 \
                    or not isinstance(node.slice.elts[0], ast.List):
                reject(src, node, "Callable annotation without [[args], ret]")
            args = [parse_annotation(env, src, a)[0] for a in node.slice.elts[0].elts]
            ret = parse_annotation(env, src, node.slice.elts[1])[0]
            return LType("Fn", (*args, ret)), False
        reject(src, node, f"type annotation {head!r}[..]")
    reject(src, node, f"type annotation node {type(node).__name__}")


def _collect_type_vars(t: LType, acc: list[str]) -> None:
    """Opaque type-parameter names occurring in `t`, first-occurrence order."""
    if t.kind == "Var" and t.name not in acc:
        acc.append(t.name)
    for a in t.args:
        _collect_type_vars(a, acc)


def _subst_type_vars(t: LType, mapping: dict[str, LType]) -> LType:
    """Substitute opaque type parameters (used to instantiate struct fields)."""
    if t.kind == "Var":
        return mapping.get(t.name, t)
    if t.args:
        return LType(t.kind, tuple(_subst_type_vars(a, mapping) for a in t.args), t.name)
    return t


def _flatten_union(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flatten_union(node.left) + _flatten_union(node.right)
    return [node]


# ---------------------------------------------------------------------------
# Emitted helper definitions (fixed bodies, fixed ordering).
# ---------------------------------------------------------------------------
HELPER_ORDER = ("_intAbs", "_dictGetD", "_dictSet", "_find", "_findIdxFrom",
                "_findIdx", "_findSome", "_lexLt3", "_minByKey3",
                "_sortIntInsert", "_sortInt", "_nthIntNat", "_nthInt")

HELPER_DEFS = {
    "_intAbs": (
        "/-- `abs` on `Int` (Python `abs`): non-negative magnitude. -/\n"
        "def _intAbs (i : Int) : Int := Int.ofNat i.natAbs"
    ),
    "_dictGetD": (
        "/-- Python `dict.get(k, default)` over an insertion-ordered association list:\n"
        "first matching value, else the default (value-polymorphic). -/\n"
        "def _dictGetD {α : Type} (m : List (String × α)) (k : String) (d : α) : α :=\n"
        "  match m with\n"
        "  | [] => d\n"
        "  | (k', v) :: rest => if k' == k then v else _dictGetD rest k d"
    ),
    "_dictSet": (
        "/-- Python `d[k] = v` over an insertion-ordered association list: replace the\n"
        "first matching entry in place, else append — every other entry is preserved\n"
        "bit-for-bit, mirroring dict update semantics (value-polymorphic). -/\n"
        "def _dictSet {α : Type} (m : List (String × α)) (k : String) (v : α) : List (String × α) :=\n"
        "  match m with\n"
        "  | [] => [(k, v)]\n"
        "  | (k', v') :: rest => if k' == k then (k', v) :: rest else (k', v') :: _dictSet rest k v"
    ),
    "_find": (
        "/-- Python `next((x for x in xs if p(x)), None)`: the first element\n"
        "satisfying `p`, else `none` (value-polymorphic). -/\n"
        "def _find {α : Type} (p : α → Bool) (xs : List α) : Option α :=\n"
        "  match xs with\n"
        "  | [] => none\n"
        "  | x :: rest => if p x then some x else _find p rest"
    ),
    "_findIdxFrom": (
        "/-- Index search from a running offset — the recursion behind `_findIdx`. -/\n"
        "def _findIdxFrom {α : Type} (p : α → Bool) (i : Int) (xs : List α) : Option Int :=\n"
        "  match xs with\n"
        "  | [] => none\n"
        "  | x :: rest => if p x then some i else _findIdxFrom p (i + 1) rest"
    ),
    "_findIdx": (
        "/-- Python `next((i for i, x in enumerate(xs) if p(x)), None)`: the index of\n"
        "the first element satisfying `p`, else `none` (value-polymorphic). -/\n"
        "def _findIdx {α : Type} (p : α → Bool) (xs : List α) : Option Int :=\n"
        "  _findIdxFrom p 0 xs"
    ),
    "_findSome": (
        "/-- A Python `for` loop whose body only `continue`s or `return`s: the first\n"
        "iteration producing `some` wins; `none` falls through to the code after the\n"
        "loop (value-polymorphic). -/\n"
        "def _findSome {α β : Type} (f : α → Option β) (xs : List α) : Option β :=\n"
        "  match xs with\n"
        "  | [] => none\n"
        "  | x :: rest =>\n"
        "    match f x with\n"
        "    | some r => some r\n"
        "    | none => _findSome f rest"
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
    "_sortIntInsert": (
        "/-- Insert into an ascending-sorted list — the inner step of `_sortInt`. -/\n"
        "def _sortIntInsert (x : Int) : List Int → List Int\n"
        "  | [] => [x]\n"
        "  | y :: ys => if x ≤ y then x :: y :: ys else y :: _sortIntInsert x ys"
    ),
    "_sortInt": (
        "/-- Python `sorted` over ints (insertion sort). Sorting a multiset of ints is\n"
        "order-independent, so this agrees with Python's stable Timsort on every input. -/\n"
        "def _sortInt : List Int → List Int\n"
        "  | [] => []\n"
        "  | x :: xs => _sortIntInsert x (_sortInt xs)"
    ),
    "_nthIntNat": (
        "/-- Element at a Nat index, default 0 past the end (the recursion behind\n"
        "`_nthInt`). -/\n"
        "def _nthIntNat : List Int → Nat → Int\n"
        "  | [], _ => 0\n"
        "  | x :: _, 0 => x\n"
        "  | _ :: xs, n + 1 => _nthIntNat xs n"
    ),
    "_nthInt": (
        "/-- Python `xs[i]` on a list of ints. TOTAL: an out-of-range index reads 0 and\n"
        "a negative index clamps to 0 where Python raises/wraps — extracted cores keep\n"
        "indices in range by construction. -/\n"
        "def _nthInt (xs : List Int) (i : Int) : Int := _nthIntNat xs i.toNat"
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
        if isinstance(e.value, str):
            if any(c in '"\\' or not 32 <= ord(c) < 127 for c in e.value):
                reject(src, e, "string literal outside printable ASCII "
                               "(or containing a quote/backslash)")
            return f'"{e.value}"', T_STRING
        if e.value is None:
            reject(src, e, "None outside a return/annotated-assignment position")
        reject(src, e, f"literal {type(e.value).__name__}")
    if isinstance(e, ast.Name):
        name = check_ident(src, e, e.id)
        if name in ctx.aliases:
            return ctx.aliases[name]
        if name in ctx.unwraps:
            binder, inner = ctx.unwraps[name]
            if inner.kind == "Tuple":
                reject(src, e, f"bare read of Optional {name!r} inside its unwrap context (subscript it)")
            return binder, inner
        if name not in ctx.vars:
            reject(src, e, f"unbound name {name!r}")
        return name, ctx.vars[name]
    if isinstance(e, ast.Tuple):
        elts = [emit_expr(ctx, x) for x in e.elts]
        code = "(" + ", ".join(p[0] for p in elts) + ")"
        return code, LType("Tuple", tuple(p[1] for p in elts))
    if isinstance(e, ast.List):
        # Non-empty list literal; `*xs` splices a list segment, so
        # `[*xs, v]` is Python's append-copy idiom -> `(xs ++ [v])`.
        if not e.elts:
            reject(src, e, "empty list literal outside a pinned position "
                           "(annotated assignment / return slot)")
        parts_l: list[str] = []
        pending: list[str] = []
        elem_t: LType | None = None
        for elt in e.elts:
            if isinstance(elt, ast.Starred):
                val, tv = emit_expr(ctx, elt.value)
                if tv.kind != "List":
                    reject(src, e, "starred non-list inside a list literal")
                if elem_t is None:
                    elem_t = tv.args[0]
                elif tv.args[0] != elem_t:
                    reject(src, e, "list literal with mixed element types")
                if pending:
                    parts_l.append("[" + ", ".join(pending) + "]")
                    pending = []
                parts_l.append(val)
            else:
                val, tv = emit_expr(ctx, elt)
                if elem_t is None:
                    elem_t = tv
                elif tv != elem_t:
                    reject(src, e, "list literal with mixed element types")
                pending.append(val)
        if pending:
            parts_l.append("[" + ", ".join(pending) + "]")
        assert elem_t is not None
        code = parts_l[0] if len(parts_l) == 1 else "(" + " ++ ".join(parts_l) + ")"
        return code, t_list(elem_t)
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
        if isinstance(e.op, ast.Add) and ta == T_RAT and tb == T_RAT:
            return f"({a} + {b})", T_RAT
        if isinstance(e.op, ast.Add) and ta.kind == "List" and tb == ta:
            # Python list concatenation -> List append.
            return f"({a} ++ {b})", ta
        if isinstance(e.op, ast.Mult) and ta == T_RAT and tb == T_RAT:
            return f"({a} * {b})", T_RAT
        if isinstance(e.op, ast.Div):
            # True division is Rat-only (CAVEAT: Lean's Rat division is total
            # with divisor 0 -> 0 where Python raises ZeroDivisionError;
            # divisors stay non-zero by construction).
            if ta != T_RAT or tb != T_RAT:
                reject(src, e, "true division on non-Fraction operands")
            return f"({a} / {b})", T_RAT
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
        if is_none_const(e.orelse):
            # `A if c else None` -> `if c then some A else none`.
            a, ta = emit_expr(ctx, e.body)
            return f"(if {c} then (some {a}) else none)", t_option(ta)
        a, ta = emit_expr(ctx, e.body)
        b, tb = emit_expr(ctx, e.orelse)
        if ta != tb:
            reject(src, e, "conditional-expression branches of distinct types")
        return f"(if {c} then {a} else {b})", ta
    if isinstance(e, ast.SetComp):
        return emit_set_comp(ctx, e)
    if isinstance(e, ast.ListComp):
        return emit_list_comp(ctx, e)
    if isinstance(e, (ast.DictComp, ast.GeneratorExp)):
        reject(src, e, "comprehension/generator expression")
    if isinstance(e, ast.Lambda):
        reject(src, e, "lambda outside a min/max key position")
    if isinstance(e, ast.Attribute):
        if isinstance(e.ctx, ast.Load):
            val, tv = emit_expr(ctx, e.value)
            if tv.kind == "Struct":
                fields, params = ctx.tenv.structs[tv.name]
                mapping = dict(zip(params, tv.args, strict=True))
                for fname, ftype in fields:
                    if fname == e.attr:
                        return f"({val}.{e.attr})", _subst_type_vars(ftype, mapping)
                reject(src, e, f"unknown field .{e.attr} on structure {tv.name!r}")
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
        if isinstance(op, ast.In):
            # Membership is order-independent, so set-typed (frozenset image)
            # operands are safe here.
            if tb.kind != "List" or tb.args[0] != ta or ta not in (T_STRING, T_INT):
                reject(src, e, "`in` outside str/int membership in a list/set")
            parts.append(f"(List.contains {b} {a})")
            continue
        if isinstance(op, ast.NotIn):
            reject(src, e, "`not in` (use `x in xs` under `not`/`else`)")
        if isinstance(op, (ast.Eq, ast.NotEq)) and ta != tb:
            # Python `t == opt` where opt: Optional[T] — False on None,
            # plain equality on some. Lean: `decide (opt = some t)`.
            if ta.kind == "Option" and ta.args[0] == tb and tb in (T_INT, T_STRING):
                core = f"(decide ({a} = some {b}))"
            elif tb.kind == "Option" and tb.args[0] == ta and ta in (T_INT, T_STRING):
                core = f"(decide ({b} = some {a}))"
            else:
                reject(src, e, "comparison between distinct types")
            parts.append(core if isinstance(op, ast.Eq) else f"(!{core})")
            continue
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
    if t.kind == "List" and t.args[0] == T_INT:
        # Python `xs[i]` on a list[int] — emitted total helper (out-of-range
        # reads 0, negative clamps to 0; callers keep indices in range).
        idx, ti = emit_expr(ctx, e.slice)
        if ti != T_INT:
            reject(src, e, "list index is not an int")
        ctx.helpers.add("_nthIntNat")
        ctx.helpers.add("_nthInt")
        return f"(_nthInt {binder} {idx})", T_INT
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
            if td.args[0] != T_STRING:
                reject(src, e, "dict helpers require str keys")
            if len(e.args) != 2 or e.keywords:
                reject(src, e, "dict.get without an explicit default")
            k, tk = emit_expr(ctx, e.args[0])
            if tk != td.args[0]:
                reject(src, e, "dict.get key type mismatch")
            default = e.args[1]
            if isinstance(default, ast.Dict) and not default.keys:
                # `{}` default: the dict's value type pins the empty literal.
                if td.args[1].kind != "Dict":
                    reject(src, e, "empty-dict default on a non-dict-valued dict")
                dflt = "[]"
            else:
                dflt, tdflt = emit_expr(ctx, default)
                if tdflt != td.args[1]:
                    reject(src, e, "dict.get default type mismatch")
            ctx.helpers.add("_dictGetD")
            return f"(_dictGetD {d} {k} {dflt})", td.args[1]
        reject(src, e, f"method call .{e.func.attr}(..)")
    if not isinstance(e.func, ast.Name):
        reject(src, e, "call of a non-name")
    fname = e.func.id
    if fname == ctx.fn_name:
        return emit_recursive_call(ctx, e, fname)
    if fname in ("min", "max"):
        return emit_min_max(ctx, e, fname)
    if fname == "next":
        return emit_next(ctx, e)
    if fname == "any":
        return emit_any(ctx, e)
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
    if fname == "sorted":
        # Sorting an int multiset is order-independent (so a set-typed
        # argument would also be safe): the emitted insertion sort agrees
        # with Python's stable Timsort on every input.
        if len(e.args) != 1 or e.keywords:
            reject(src, e, "sorted with unexpected arguments")
        a, ta = emit_expr(ctx, e.args[0])
        if ta != t_list(T_INT):
            reject(src, e, "sorted over a non-list[int]")
        ctx.helpers.add("_sortIntInsert")
        ctx.helpers.add("_sortInt")
        return f"(_sortInt {a})", ta
    if fname == "list":
        # `list(reversed(xs))` -> List.reverse (Python's reversed sequence,
        # materialized). Anything else under `list(..)` is out of subset.
        if len(e.args) == 1 and not e.keywords and isinstance(e.args[0], ast.Call) \
                and isinstance(e.args[0].func, ast.Name) and e.args[0].func.id == "reversed":
            inner = e.args[0]
            if len(inner.args) != 1 or inner.keywords:
                reject(src, e, "reversed with unexpected arguments")
            if isinstance(inner.args[0], ast.Name) and inner.args[0].id in ctx.setlike:
                reject(src, e, "reversed over a set-typed value (order-dependent)")
            a, ta = emit_expr(ctx, inner.args[0])
            if ta.kind != "List":
                reject(src, e, "reversed over a non-sequence")
            return f"(List.reverse {a})", ta
        reject(src, e, "list(..) outside the `list(reversed(xs))` shape")
    if fname == "Fraction":
        # fractions.Fraction over ints -> mkRat (both normalize identically).
        # CAVEAT: `mkRat a 0 = 0` where Python `Fraction(a, 0)` raises —
        # denominators are non-zero by construction (literal 2 in the median).
        if e.keywords or len(e.args) not in (1, 2):
            reject(src, e, "Fraction(..) outside the 1/2-int-argument shapes")
        rendered_args: list[str] = []
        for arg_node in e.args:
            arg_code, got = emit_expr(ctx, arg_node)
            if got != T_INT:
                reject(src, e, "Fraction(..) argument is not an int")
            rendered_args.append(arg_code)
        if len(rendered_args) == 1:
            return f"(mkRat {rendered_args[0]} 1)", T_RAT
        return f"(mkRat {rendered_args[0]} {rendered_args[1]})", T_RAT
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
    if fname in ctx.module_sigs:
        return emit_module_call(ctx, e, fname)
    if fname in ctx.import_sigs:
        return emit_import_call(ctx, e, fname)
    reject(src, e, f"call to {fname!r}")


def emit_recursive_call(ctx: Ctx, e: ast.Call, fname: str) -> tuple[str, LType]:
    """A fuel-bounded self-call: `f(fuel - 1, args..)` inside the `fuel + 1`
    arm becomes `(f fuel args..)` — structural recursion on the Nat fuel."""
    src = ctx.src
    if not ctx.fueled:
        reject(src, e, "recursion without the fuel discipline (leading `fuel: int` + guard)")
    if e.keywords or len(e.args) != len(ctx.rec_params) + 1:
        reject(src, e, f"recursive call arity mismatch for {fname!r}")
    first = e.args[0]
    if not (isinstance(first, ast.BinOp) and isinstance(first.op, ast.Sub)
            and isinstance(first.left, ast.Name) and first.left.id == "fuel"
            and isinstance(first.right, ast.Constant)
            and not isinstance(first.right.value, bool) and first.right.value == 1):
        reject(src, e, "recursive call whose first argument is not exactly `fuel - 1`")
    rendered = [fname, "fuel"]
    for arg_node, want in zip(e.args[1:], ctx.rec_params, strict=True):
        arg_code, got = emit_expr(ctx, arg_node)
        if got != want:
            reject(src, e, f"argument type mismatch in recursive call to {fname!r}")
        rendered.append(arg_code)
    return "(" + " ".join(rendered) + ")", ctx.ret


def emit_module_call(ctx: Ctx, e: ast.Call, fname: str) -> tuple[str, LType]:
    """A call to a PREVIOUSLY-extracted function of the same module. A fueled
    callee's leading Int fuel is bridged with `Int.toNat` (Python's `fuel <= 0`
    base case is exactly Lean fuel 0)."""
    src = ctx.src
    params, ret, fueled = ctx.module_sigs[fname]
    if e.keywords:
        reject(src, e, f"keyword arguments in call to {fname!r}")
    args = list(e.args)
    rendered = [fname]
    if fueled:
        if len(args) != len(params) + 1:
            reject(src, e, f"call arity mismatch for fueled {fname!r}")
        fuel_code, fuel_t = emit_expr(ctx, args[0])
        if fuel_t != T_INT:
            reject(src, e, f"fuel argument to {fname!r} is not int")
        rendered.append(f"(Int.toNat {fuel_code})")
        args = args[1:]
    elif len(args) != len(params):
        reject(src, e, f"call arity mismatch for {fname!r}")
    for arg_node, want in zip(args, params, strict=True):
        arg_code, got = emit_expr(ctx, arg_node)
        if got != want:
            reject(src, e, f"argument type mismatch in call to {fname!r}")
        rendered.append(arg_code)
    return "(" + " ".join(rendered) + ")", ret


def emit_import_call(ctx: Ctx, e: ast.Call, fname: str) -> tuple[str, LType]:
    """A call to a registry-declared import from an EARLIER-registered module,
    rendered fully qualified (`Extracted.<Core>.<fname>`). A fueled callee's
    leading Int fuel is bridged with `Int.toNat`, like same-module calls."""
    src = ctx.src
    core, params, ret, fueled = ctx.import_sigs[fname]
    if e.keywords:
        reject(src, e, f"keyword arguments in call to {fname!r}")
    args = list(e.args)
    rendered = [f"Extracted.{core}.{fname}"]
    if fueled:
        if len(args) != len(params) + 1:
            reject(src, e, f"call arity mismatch for fueled {fname!r}")
        fuel_code, fuel_t = emit_expr(ctx, args[0])
        if fuel_t != T_INT:
            reject(src, e, f"fuel argument to {fname!r} is not int")
        rendered.append(f"(Int.toNat {fuel_code})")
        args = args[1:]
    elif len(args) != len(params):
        reject(src, e, f"call arity mismatch for {fname!r}")
    for arg_node, want in zip(args, params, strict=True):
        arg_code, got = emit_expr(ctx, arg_node)
        if got != want:
            reject(src, e, f"argument type mismatch in call to {fname!r}")
        rendered.append(arg_code)
    return "(" + " ".join(rendered) + ")", ret


def emit_set_comp(ctx: Ctx, e: ast.SetComp) -> tuple[str, LType]:
    """`{elt for k, v in d.items() if cond}` -> `List.map` over `List.filter`.
    Dict keys are unique and insertion-ordered, so the produced list IS the set
    (set-semantics caveat: consumers must be order-independent)."""
    src = ctx.src
    if len(e.generators) != 1:
        reject(src, e, "set comprehension with multiple generators")
    gen = e.generators[0]
    if gen.is_async:
        reject(src, e, "async comprehension")
    if len(gen.ifs) > 1:
        reject(src, e, "set comprehension with multiple conditions")
    dname, kt, vt = match_dict_items(ctx, e, gen.iter)
    if not (isinstance(gen.target, ast.Tuple) and len(gen.target.elts) == 2
            and all(isinstance(t, ast.Name) for t in gen.target.elts)):
        reject(src, e, "set comprehension target must be a `k, v` pair over d.items()")
    knode, vnode = gen.target.elts
    assert isinstance(knode, ast.Name) and isinstance(vnode, ast.Name)
    if "_kv" in ctx.vars or "_kv" in ctx.aliases:
        reject(src, e, "identifier `_kv` collides with the comprehension binder")
    child = branch(ctx)
    child.aliases[check_ident(src, knode, knode.id)] = ("(_kv.1)", kt)
    child.aliases[check_ident(src, vnode, vnode.id)] = ("(_kv.2)", vt)
    seq = dname
    if gen.ifs:
        cond, tc = emit_expr(child, gen.ifs[0])
        if tc != T_BOOL:
            reject(src, e, "set comprehension condition is not bool")
        seq = f"(List.filter (fun _kv => {cond}) {dname})"
    elt, te = emit_expr(child, e.elt)
    return f"(List.map (fun _kv => {elt}) {seq})", t_list(te)


def _list_generator(ctx: Ctx, where: ast.expr, gen: ast.comprehension,
                    max_ifs: int) -> tuple[str, LType]:
    """Validate a single list-valued comprehension generator; returns the
    rendered sequence + element type (the caller binds the target)."""
    src = ctx.src
    if gen.is_async:
        reject(src, where, "async comprehension")
    if len(gen.ifs) > max_ifs:
        reject(src, where, "comprehension with too many conditions")
    if isinstance(gen.iter, ast.Name) and gen.iter.id in ctx.setlike:
        reject(src, where, "comprehension over a set-typed value (order-dependent)")
    seq, tseq = emit_expr(ctx, gen.iter)
    if tseq.kind != "List":
        reject(src, where, "comprehension over a non-sequence")
    return seq, tseq.args[0]


def emit_list_comp(ctx: Ctx, e: ast.ListComp) -> tuple[str, LType]:
    """`[elt for x in xs if cond]` -> `List.map` over `List.filter`."""
    src = ctx.src
    if len(e.generators) != 1:
        reject(src, e, "list comprehension with multiple generators")
    gen = e.generators[0]
    if not isinstance(gen.target, ast.Name):
        reject(src, e, "list comprehension target must be a single name")
    seq, elem = _list_generator(ctx, e, gen, max_ifs=1)
    binder = check_ident(src, gen.target, gen.target.id)
    child = branch(ctx)
    child.vars[binder] = elem
    bind = f"(fun ({binder} : {render_type(elem)}) =>"
    if gen.ifs:
        cond, tc = emit_expr(child, gen.ifs[0])
        if tc != T_BOOL:
            reject(src, e, "list comprehension condition is not bool")
        seq = f"(List.filter {bind} {cond}) {seq})"
    elt, te = emit_expr(child, e.elt)
    return f"(List.map {bind} {elt}) {seq})", t_list(te)


def emit_next(ctx: Ctx, e: ast.Call) -> tuple[str, LType]:
    """`next((x for x in xs if cond), None)` -> `_find`;
    `next((i for i, x in enumerate(xs) if cond), None)` -> `_findIdx`."""
    src = ctx.src
    if len(e.args) != 2 or e.keywords or not isinstance(e.args[0], ast.GeneratorExp) \
            or not is_none_const(e.args[1]):
        reject(src, e, "next(..) outside the `next((.. for .. in ..), None)` shapes")
    gen_exp = e.args[0]
    if len(gen_exp.generators) != 1:
        reject(src, e, "next(..) generator with multiple `for` clauses")
    gen = gen_exp.generators[0]
    if len(gen.ifs) != 1:
        reject(src, e, "next(..) generator without exactly one condition")
    # Index shape: `next((i for i, x in enumerate(xs) if cond), None)`.
    if isinstance(gen.iter, ast.Call) and isinstance(gen.iter.func, ast.Name) \
            and gen.iter.func.id == "enumerate":
        it = gen.iter
        if len(it.args) != 1 or it.keywords:
            reject(src, e, "enumerate with unexpected arguments")
        if isinstance(it.args[0], ast.Name) and it.args[0].id in ctx.setlike:
            reject(src, e, "enumerate over a set-typed value (order-dependent)")
        seq, tseq = emit_expr(ctx, it.args[0])
        if tseq.kind != "List":
            reject(src, e, "enumerate over a non-sequence")
        elem = tseq.args[0]
        if not (isinstance(gen.target, ast.Tuple) and len(gen.target.elts) == 2
                and all(isinstance(t, ast.Name) for t in gen.target.elts)):
            reject(src, e, "enumerate target must be an `i, x` pair")
        inode, xnode = gen.target.elts
        assert isinstance(inode, ast.Name) and isinstance(xnode, ast.Name)
        if not (isinstance(gen_exp.elt, ast.Name) and gen_exp.elt.id == inode.id):
            reject(src, e, "next(.. enumerate ..) element must be the index")
        binder = check_ident(src, xnode, xnode.id)
        child = branch(ctx)
        child.vars[binder] = elem
        cond, tc = emit_expr(child, gen.ifs[0])
        if tc != T_BOOL:
            reject(src, e, "next(..) condition is not bool")
        ctx.helpers.add("_findIdxFrom")
        ctx.helpers.add("_findIdx")
        return (f"(_findIdx (fun ({binder} : {render_type(elem)}) => {cond}) {seq})",
                t_option(T_INT))
    # Element shape: `next((x for x in xs if cond), None)`.
    if not isinstance(gen.target, ast.Name):
        reject(src, e, "next(..) target must be a single name")
    seq, elem = _list_generator(ctx, e, gen, max_ifs=1)
    if not (isinstance(gen_exp.elt, ast.Name) and gen_exp.elt.id == gen.target.id):
        reject(src, e, "next(..) element must be the iteration variable")
    binder = check_ident(src, gen.target, gen.target.id)
    child = branch(ctx)
    child.vars[binder] = elem
    cond, tc = emit_expr(child, gen.ifs[0])
    if tc != T_BOOL:
        reject(src, e, "next(..) condition is not bool")
    ctx.helpers.add("_find")
    return (f"(_find (fun ({binder} : {render_type(elem)}) => {cond}) {seq})",
            t_option(elem))


def emit_any(ctx: Ctx, e: ast.Call) -> tuple[str, LType]:
    """`any(expr for x in xs)` -> `List.any xs (fun x => expr)`."""
    src = ctx.src
    if len(e.args) != 1 or e.keywords or not isinstance(e.args[0], ast.GeneratorExp):
        reject(src, e, "any(..) outside the `any(expr for x in xs)` shape")
    gen_exp = e.args[0]
    if len(gen_exp.generators) != 1:
        reject(src, e, "any(..) generator with multiple `for` clauses")
    gen = gen_exp.generators[0]
    if not isinstance(gen.target, ast.Name):
        reject(src, e, "any(..) target must be a single name")
    seq, elem = _list_generator(ctx, e, gen, max_ifs=0)
    binder = check_ident(src, gen.target, gen.target.id)
    child = branch(ctx)
    child.vars[binder] = elem
    body, tb = emit_expr(child, gen_exp.elt)
    if tb != T_BOOL:
        reject(src, e, "any(..) element is not bool")
    return (f"(List.any {seq} (fun ({binder} : {render_type(elem)}) => {body}))",
            T_BOOL)


def match_dict_items(ctx: Ctx, where: ast.AST, it: ast.expr) -> tuple[str, LType, LType]:
    """Require `it` to be `<dict-variable>.items()`; return (name, key t, value t)."""
    src = ctx.src
    if not (isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute)
            and it.func.attr == "items" and not it.args and not it.keywords
            and isinstance(it.func.value, ast.Name)):
        reject(src, where, "iteration source must be a list value or `d.items()`")
    dname = it.func.value.id
    if dname not in ctx.vars or ctx.vars[dname].kind != "Dict":
        reject(src, where, f".items() on non-dict {dname!r}")
    dt = ctx.vars[dname]
    return dname, dt.args[0], dt.args[1]


def emit_min_max(ctx: Ctx, e: ast.Call, fname: str) -> tuple[str, LType]:
    src = ctx.src
    if len(e.args) == 2 and not e.keywords:
        a, ta = emit_expr(ctx, e.args[0])
        b, tb = emit_expr(ctx, e.args[1])
        if ta != tb or ta not in (T_INT, T_RAT):
            reject(src, e, f"{fname}(a, b) operands must both be int or both Fraction")
        return f"({fname} {a} {b})", ta
    if len(e.args) >= 3 and not e.keywords:
        parts_n = [emit_expr(ctx, arg) for arg in e.args]
        if any(t != T_INT for _, t in parts_n):
            reject(src, e, f"{fname}(a, b, ..) operands must all be int")
        # Python n-ary min/max over ints == right-nested two-arg (value-equal).
        code = parts_n[-1][0]
        for part, _ in reversed(parts_n[:-1]):
            code = f"({fname} {part} {code})"
        return code, T_INT
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


def match_is_none(test: ast.expr) -> str | None:
    """`X is None` -> X (a plain variable), else None."""
    if isinstance(test, ast.Compare) and len(test.ops) == 1 \
            and isinstance(test.ops[0], ast.Is) and is_none_const(test.comparators[0]) \
            and isinstance(test.left, ast.Name):
        return test.left.id
    return None


def match_is_not_none_and(test: ast.expr) -> tuple[str, ast.expr] | None:
    """`X is not None and COND..` -> (X, COND..), else None."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And) \
            and len(test.values) >= 2:
        x = match_is_not_none(test.values[0])
        if x is not None:
            if len(test.values) == 2:
                return x, test.values[1]
            residual = ast.BoolOp(op=ast.And(), values=test.values[1:])
            ast.copy_location(residual, test)
            return x, residual
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
    if isinstance(value, ast.Dict) and not value.keys:
        # `return {}` — the declared dict return type pins the empty literal.
        if ctx.ret.kind != "Dict":
            reject(ctx.src, node, "empty dict returned from a non-dict function")
        return "[]"
    if isinstance(value, ast.Tuple) and ctx.ret.kind == "Tuple" \
            and len(value.elts) == len(ctx.ret.args):
        comps = [_emit_component(ctx, node, elt, want)
                 for elt, want in zip(value.elts, ctx.ret.args, strict=True)]
        return "(" + ", ".join(comps) + ")"
    code, got = emit_expr(ctx, value)
    if got == ctx.ret:
        return code
    if ctx.ret.kind == "Option" and ctx.ret.args[0] == got:
        return f"(some {code})"
    reject(ctx.src, node, f"return type mismatch ({render_type(got)} vs {render_type(ctx.ret)})")


def _emit_component(ctx: Ctx, node: ast.stmt, e: ast.expr, want: LType) -> str:
    """One component of a returned tuple, coerced into its declared slot
    (Python lets `T`/None/`[]` flow into `Optional[T]`/`list[..]` slots)."""
    if is_none_const(e):
        if want.kind != "Option":
            reject(ctx.src, node, "None returned into a non-Optional tuple slot")
        return "none"
    if isinstance(e, ast.List) and not e.elts:
        if want.kind != "List":
            reject(ctx.src, node, "empty list returned into a non-list tuple slot")
        return "[]"
    code, got = emit_expr(ctx, e)
    if got == want:
        return code
    if want.kind == "Option" and want.args[0] == got:
        return f"(some {code})"
    reject(ctx.src, node,
           f"tuple-slot type mismatch ({render_type(got)} into {render_type(want)})")


def emit_block(ctx: Ctx, stmts: list[ast.stmt], indent: int) -> str:
    src = ctx.src
    pad = " " * indent
    if not stmts:
        if ctx.loop_acc is not None:
            return ctx.loop_acc
        raise ExtractionError(f"{src}: in {ctx.fn_name}: control falls off the end without a return")
    s, rest = stmts[0], stmts[1:]

    if isinstance(s, ast.Return):
        if ctx.loop_acc is not None and not ctx.loop_first:
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
                code = (f"(match {x} with\n{pad}| some {binder} => {a}\n{pad}| none => {b})")
                return f"(some {code})" if ctx.loop_first else code
        val = emit_return_value(ctx, s, s.value)
        # First-match loop mode: Python `return e` exits the function; the
        # `_findSome` body signals it as `some e`.
        return f"(some {val})" if ctx.loop_first else val

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
        declared, setlike = parse_annotation(ctx.tenv, src, s.annotation)
        if is_none_const(s.value):
            if declared.kind != "Option":
                reject(src, s, "None assigned into a non-Optional annotation")
            code = "none"
        elif isinstance(s.value, ast.Dict) and not s.value.keys:
            if declared.kind != "Dict":
                reject(src, s, "empty dict literal into a non-dict annotation")
            code = "[]"
        elif isinstance(s.value, ast.Tuple) and declared.kind == "Tuple" \
                and len(s.value.elts) == len(declared.args):
            # A tuple literal coerced componentwise into the declared tuple
            # type (`([], None, None)`: the annotation pins each slot).
            comps = [_emit_component(ctx, s, elt, want)
                     for elt, want in zip(s.value.elts, declared.args, strict=True)]
            code = "(" + ", ".join(comps) + ")"
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
    if dt.args[0] != T_STRING:
        reject(src, s, "dict helpers require str keys")
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
    if isinstance(s.iter, ast.Call):
        # `for k, v in d.items():` — the dict IS its insertion-ordered pair list.
        dname, kt, vt = match_dict_items(ctx, s, s.iter)
        seq = dname
        elem = LType("Tuple", (kt, vt))
    else:
        seq, tseq = emit_expr(ctx, s.iter)
        if tseq.kind != "List":
            reject(src, s, "for over a non-sequence")
        elem = tseq.args[0]
    if any(isinstance(n, ast.Return) for st in s.body for n in ast.walk(st)):
        return emit_for_first_match(ctx, s, rest, indent, seq, elem)
    assigned = sorted({n.id for n in ast.walk(s) if isinstance(n, ast.Name)
                       and isinstance(n.ctx, ast.Store)} - _target_names(s.target))
    if len(assigned) != 1:
        reject(src, s, f"loop must have exactly one accumulator (got {assigned!r})")
    acc = assigned[0]
    if acc not in ctx.vars:
        reject(src, s, f"loop accumulator {acc!r} is not bound before the loop")
    body_ctx = branch(ctx, loop_acc=acc, loop_first=False)
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


def emit_for_first_match(ctx: Ctx, s: ast.For, rest: list[ast.stmt], indent: int,
                         seq: str, elem: LType) -> str:
    """A loop whose body `return`s: translated to `_findSome` (first `some`
    wins; `continue`/fall-off-the-end is `none`). Sound iff the body carries no
    cross-iteration state and nothing after the loop reads its locals — both
    verified below."""
    src = ctx.src
    pad = " " * indent
    if ctx.loop_acc is not None:
        reject(src, s, "return-exiting loop nested inside another loop")
    is_tuple_target = isinstance(s.target, ast.Tuple) \
        and all(isinstance(t, ast.Name) for t in s.target.elts)
    if not isinstance(s.target, ast.Name) and not is_tuple_target:
        reject(src, s, "first-match loop target must be a name or a tuple of names")
    for st0 in s.body:
        for n0 in ast.walk(st0):
            if isinstance(n0, ast.Subscript) and isinstance(n0.ctx, ast.Store):
                reject(src, st0, "dict mutation inside a return-exiting loop "
                                 "(cross-iteration state)")
    stored = {n.id for st in s.body for n in ast.walk(st)
              if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)} \
        - _target_names(s.target)
    _check_no_carry(src, s.body, stored, set())
    for st in rest:
        for n in ast.walk(st):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in stored:
                reject(src, st, f"loop-local {n.id!r} read after a return-exiting loop")
    body_ctx = branch(ctx, loop_acc="none", loop_first=True)
    if isinstance(s.target, ast.Name):
        binder = check_ident(src, s, s.target.id)
        body_ctx.vars[binder] = elem
        body = emit_block(body_ctx, s.body, indent + 4)
        lam = (f"(fun ({binder} : {render_type(elem)}) =>\n"
               f"{pad}      {body})")
    else:
        assert isinstance(s.target, ast.Tuple)
        if elem.kind != "Tuple" or len(elem.args) != len(s.target.elts):
            reject(src, s, "loop target arity mismatch with element tuple")
        names = [check_ident(src, s, t.id) for t in s.target.elts
                 if isinstance(t, ast.Name)]
        body_ctx.vars["_x"] = elem
        unpack = ""
        for i, (nm, ft) in enumerate(zip(names, elem.args, strict=True)):
            body_ctx.vars[nm] = ft
            unpack += f"let {nm} := ({proj('_x', i, len(elem.args))})\n{pad}      "
        body = emit_block(body_ctx, s.body, indent + 4)
        lam = (f"(fun (_x : {render_type(elem)}) =>\n"
               f"{pad}      {unpack}{body})")
    ctx.helpers.add("_findSome")
    res = fresh_binder(ctx, "_r")
    cont = emit_block(branch(ctx), rest, indent + 2)
    return (f"(match (_findSome\n"
            f"{pad}    {lam}\n"
            f"{pad}    {seq}) with\n"
            f"{pad}| some {res} => {res}\n"
            f"{pad}| none =>\n{pad}  {cont})")


def _check_no_carry(src: str, stmts: list[ast.stmt], stored: set[str],
                    assigned: set[str]) -> None:
    """Reject any read of a loop-assigned name before its assignment on the
    same path — such a read would carry state across iterations in Python but
    see the OUTER binding in the `_findSome` lambda."""
    def check_loads(node: ast.AST) -> None:
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) \
                    and n.id in stored and n.id not in assigned:
                reject(src, n, f"loop-local {n.id!r} read before assignment "
                               "(cross-iteration state in a return-exiting loop)")
    for st in stmts:
        if isinstance(st, ast.If):
            check_loads(st.test)
            _check_no_carry(src, st.body, stored, set(assigned))
            _check_no_carry(src, st.orelse, stored, set(assigned))
            continue
        if isinstance(st, ast.Assign):
            check_loads(st.value)
            for t in st.targets:
                assigned |= _target_names(t)
            continue
        if isinstance(st, ast.AnnAssign):
            if st.value is not None:
                check_loads(st.value)
            assigned |= _target_names(st.target)
            continue
        check_loads(st)


def emit_if(ctx: Ctx, s: ast.If, rest: list[ast.stmt], indent: int) -> str:
    src = ctx.src
    pad = " " * indent

    # Pattern A: `if X is not None: <body>`. An always-exiting body keeps the
    # `some`-arm to itself; a fall-through body carries the continuation into
    # the `some` arm (the unwrap is still sound there: X IS some).
    x = match_is_not_none(s.test)
    if x is not None and not s.orelse:
        binder, child = unwrap_var(ctx, s, x)
        body_stmts = s.body if always_exits(ctx, s.body) else s.body + rest
        body = emit_block(child, body_stmts, indent + 2)
        cont = emit_block(branch(ctx), rest, indent + 2)
        return (f"(match {x} with\n{pad}| some {binder} =>\n{pad}  {body}\n"
                f"{pad}| none =>\n{pad}  {cont})")

    # Pattern F: `if X is None: <always-exits body>` — the continuation runs
    # with X unwrapped (it IS some there).
    xn = match_is_none(s.test)
    if xn is not None and not s.orelse and always_exits(ctx, s.body):
        binder, child = unwrap_var(ctx, s, xn)
        body = emit_block(branch(ctx), s.body, indent + 2)
        cont = emit_block(child, rest, indent + 2)
        return (f"(match {xn} with\n{pad}| none =>\n{pad}  {body}\n"
                f"{pad}| some {binder} =>\n{pad}  {cont})")

    # Pattern D: `if X is None or Y is None: <always-exits body>` — a nested
    # double-unwrap; the continuation runs with BOTH variables unwrapped.
    none_or = match_is_none_or(s.test)
    if none_or is not None and not s.orelse:
        xname, cond = none_or
        y = match_is_none(cond)
        if y is not None and always_exits(ctx, s.body):
            body1 = emit_block(branch(ctx), s.body, indent + 2)
            binder_x, child_x = unwrap_var(ctx, s, xname)
            body2 = emit_block(branch(child_x), s.body, indent + 4)
            binder_y, child_xy = unwrap_var(child_x, s, y)
            cont = emit_block(child_xy, rest, indent + 4)
            return (f"(match {xname} with\n"
                    f"{pad}| none =>\n{pad}  {body1}\n"
                    f"{pad}| some {binder_x} =>\n"
                    f"{pad}  (match {y} with\n"
                    f"{pad}  | none =>\n{pad}    {body2}\n"
                    f"{pad}  | some {binder_y} =>\n{pad}    {cont}))")

    # Pattern B: `if X is None or COND: <body>` (body + continuation in both arms).
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

    # Pattern E: `if X is not None and COND: <body>` — unwrap X, test COND in
    # the unwrap scope; the taken arm carries the continuation (still under
    # the unwrap) unless the body always exits.
    nn_and = match_is_not_none_and(s.test)
    if nn_and is not None and not s.orelse:
        xname, residual = nn_and
        binder, child = unwrap_var(ctx, s, xname)
        cond_code, tc = emit_expr(child, residual)
        if tc != T_BOOL:
            reject(src, s, "Optional-guard residual condition is not bool")
        taken_stmts = s.body if always_exits(ctx, s.body) else s.body + rest
        taken = emit_block(branch(child), taken_stmts, indent + 4)
        skipped = emit_block(branch(ctx), rest, indent + 4)
        skipped2 = emit_block(branch(ctx), rest, indent + 4)
        return (f"(match {xname} with\n"
                f"{pad}| some {binder} =>\n"
                f"{pad}  (if {cond_code}\n{pad}   then\n{pad}    {taken}\n"
                f"{pad}   else\n{pad}    {skipped})\n"
                f"{pad}| none =>\n{pad}    {skipped2})")

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
    if ctx.loop_acc is not None and not ctx.loop_first and not s.orelse \
            and len(s.body) == 1 and isinstance(s.body[0], ast.Assign):
        a = s.body[0]
        if len(a.targets) == 1 and isinstance(a.targets[0], ast.Name) \
                and a.targets[0].id == ctx.loop_acc:
            val, got = emit_expr(ctx, a.value)
            code = coerce_assign(ctx, a, ctx.vars[ctx.loop_acc], val, got)
            return (f"let {ctx.loop_acc} := (if {cond_code} then {code} else {ctx.loop_acc})\n"
                    f"{pad}" + emit_block(ctx, rest, indent))

    # General fall-through `if c: <body>`: both arms re-emit the continuation.
    if not s.orelse:
        taken = emit_block(branch(ctx), s.body + rest, indent + 2)
        skipped = emit_block(branch(ctx), rest, indent + 2)
        return (f"(if {cond_code}\n{pad} then\n{pad}  {taken}\n"
                f"{pad} else\n{pad}  {skipped})")

    reject(src, s, "if statement outside the supported translation patterns")


# ---------------------------------------------------------------------------
# Function / module extraction.
# ---------------------------------------------------------------------------
def extract_function(env: TypeEnv, src: str, fd: ast.FunctionDef, helpers: set[str],
                     module_sigs: dict[str, tuple[tuple[LType, ...], LType, bool]],
                     import_sigs: dict[str, tuple[str, tuple[LType, ...], LType, bool]],
                     consts: dict[str, LType]) -> str:
    if fd.decorator_list:
        reject(src, fd, "decorated function")
    a = fd.args
    if a.vararg or a.kwarg or a.kwonlyargs or a.posonlyargs or a.kw_defaults:
        reject(src, fd, "*args/**kwargs/keyword-only parameters")
    # Parameter defaults are allowed only for int literals / registered int
    # constants, and are IGNORED: default application happens at Python call
    # sites outside the extraction boundary, so the Lean def takes every
    # parameter explicitly (extracted call sites must pass full arity).
    for default in a.defaults:
        if isinstance(default, ast.Constant) and isinstance(default.value, int) \
                and not isinstance(default.value, bool):
            continue
        if isinstance(default, ast.Name) and default.id in consts:
            continue
        reject(src, default,
               "parameter default outside int literals / registered constants")
    if fd.returns is None:
        reject(src, fd, "missing return annotation")
    ret, _ = parse_annotation(env, src, fd.returns)
    params: list[tuple[str, LType, bool]] = []
    for arg in a.args:
        if arg.annotation is None:
            reject(src, arg, f"missing annotation on parameter {arg.arg!r}")
        t, setlike = parse_annotation(env, src, arg.annotation)
        params.append((check_ident(src, arg, arg.arg), t, setlike))
    body = list(fd.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]  # docstring
    if _is_recursive(fd):
        return extract_fueled_function(env, src, fd, ret, params, body, helpers,
                                       module_sigs, import_sigs, consts)
    ctx = Ctx(src=src, fn_name=fd.name, ret=ret, vars=dict(consts), setlike=set(),
              unwraps={}, helpers=helpers, module_sigs=module_sigs,
              import_sigs=import_sigs, tenv=env)
    for name, t, setlike in params:
        ctx.vars[name] = t
        if setlike:
            ctx.setlike.add(name)
    expr = emit_block(ctx, body, 2)
    tvars: list[str] = []
    for _, t, _ in params:
        _collect_type_vars(t, tvars)
    _collect_type_vars(ret, tvars)
    binders = "".join(f"{{{v} : Type}} " for v in env.opaque if v in tvars)
    sig = " ".join(f"({n} : {render_type(t)})" for n, t, _ in params)
    module_sigs[fd.name] = (tuple(t for _, t, _ in params), ret, False)
    return (f"/-- Extracted from `{fd.name}` (line {fd.lineno}). -/\n"
            f"def {fd.name} {binders}{sig} :\n    {render_type(ret)} :=\n  {expr}")


def _is_recursive(fd: ast.FunctionDef) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == fd.name for n in ast.walk(fd))


def _is_fuel_guard(s: ast.stmt) -> bool:
    """`if fuel <= 0: return <expr>` (no else) — the mandatory base case."""
    return (isinstance(s, ast.If) and not s.orelse
            and isinstance(s.test, ast.Compare)
            and isinstance(s.test.left, ast.Name) and s.test.left.id == "fuel"
            and len(s.test.ops) == 1 and isinstance(s.test.ops[0], ast.LtE)
            and isinstance(s.test.comparators[0], ast.Constant)
            and not isinstance(s.test.comparators[0].value, bool)
            and s.test.comparators[0].value == 0
            and len(s.body) == 1 and isinstance(s.body[0], ast.Return))


def extract_fueled_function(env: TypeEnv, src: str, fd: ast.FunctionDef, ret: LType,
                            params: list[tuple[str, LType, bool]], body: list[ast.stmt],
                            helpers: set[str],
                            module_sigs: dict[str, tuple[tuple[LType, ...], LType, bool]],
                            import_sigs: dict[str, tuple[str, tuple[LType, ...], LType, bool]],
                            consts: dict[str, LType]) -> str:
    """A fuel-bounded recursive function -> a two-arm `Nat` pattern match.

    The Python `fuel <= 0` guard IS the `| 0` arm; the rest of the body is the
    `| fuel + 1` arm in which the binder `fuel` already denotes the decremented
    value, so every self-call `f(fuel - 1, ..)` renders as `f fuel ..` —
    STRUCTURAL recursion the Lean termination checker accepts, exactly the
    hand models' fuel idiom. `fuel` is not otherwise bound: any stray read is
    rejected as an unbound name.
    """
    if not params or params[0][0] != "fuel" or params[0][1] != T_INT:
        reject(src, fd, "recursive function without a leading `fuel: int` parameter")
    tvars: list[str] = []
    for _, t, _ in params:
        _collect_type_vars(t, tvars)
    _collect_type_vars(ret, tvars)
    if tvars:
        reject(src, fd, "opaque type parameters in a fuel-recursive function")
    rest = params[1:]
    if not body or not _is_fuel_guard(body[0]):
        reject(src, fd, "recursive function must open with `if fuel <= 0: return <base>`")
    guard = body[0]
    assert isinstance(guard, ast.If)
    base_ret = guard.body[0]
    base_ctx = Ctx(src=src, fn_name=fd.name, ret=ret,
                   vars={**consts, **{n: t for n, t, _ in rest}},
                   setlike={n for n, _, s in rest if s},
                   unwraps={}, helpers=helpers, module_sigs=module_sigs,
                   import_sigs=import_sigs, tenv=env)
    base_expr = emit_block(base_ctx, [base_ret], 4)
    base_reads = {n.id for n in ast.walk(base_ret)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    binders0 = ", ".join(n if n in base_reads else "_" for n, _, _ in rest)
    succ_ctx = Ctx(src=src, fn_name=fd.name, ret=ret,
                   vars={**consts, **{n: t for n, t, _ in rest}},
                   setlike={n for n, _, s in rest if s},
                   unwraps={}, helpers=helpers, module_sigs=module_sigs,
                   import_sigs=import_sigs, tenv=env,
                   fueled=True, rec_params=tuple(t for _, t, _ in rest))
    succ_ctx.fresh = base_ctx.fresh  # one counter per function
    succ_expr = emit_block(succ_ctx, body[1:], 4)
    binders1 = ", ".join(n for n, _, _ in rest)
    arrow = " → ".join(["Nat", *(render_atom(t) for _, t, _ in rest), render_atom(ret)])
    module_sigs[fd.name] = (tuple(t for _, t, _ in rest), ret, True)
    return (f"/-- Extracted from `{fd.name}` (line {fd.lineno}; the Python `fuel <= 0` guard\n"
            f"is the `Nat` fuel-zero arm — recursion is structural on the fuel). -/\n"
            f"def {fd.name} :\n    {arrow}\n"
            f"  | 0, {binders0} =>\n    {base_expr}\n"
            f"  | fuel + 1, {binders1} =>\n    {succ_expr}")


def extract_structure(env: TypeEnv, src: str, cd: ast.ClassDef) -> str:
    """A registered frozen @dataclass -> a Lean `structure`, parameterised by
    the opaque type parameters its fields mention (declaration order)."""
    is_dataclass = any(
        (isinstance(d, ast.Name) and d.id == "dataclass")
        or (isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
            and d.func.id == "dataclass")
        for d in cd.decorator_list)
    if not is_dataclass:
        reject(src, cd, f"registered structure {cd.name!r} without @dataclass")
    if cd.bases or cd.keywords:
        reject(src, cd, "dataclass with base classes")
    name = check_ident(src, cd, cd.name)
    body = list(cd.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]  # docstring
    fields: list[tuple[str, LType]] = []
    for st in body:
        if not (isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)
                and st.value is None):
            reject(src, st, "non-field statement in a registered dataclass")
        t, setlike = parse_annotation(env, src, st.annotation)
        if setlike:
            reject(src, st, "set-typed dataclass field")
        fields.append((check_ident(src, st.target, st.target.id), t))
    tvars: list[str] = []
    for _, t in fields:
        _collect_type_vars(t, tvars)
    params = tuple(p for p in env.opaque if p in tvars)
    env.structs[name] = (tuple(fields), params)
    param_str = "".join(f" ({p} : Type)" for p in params)
    lines = [f"/-- Extracted from `@dataclass {name}` (line {cd.lineno}). -/",
             f"structure {name}{param_str} where"]
    lines.extend(f"  {fname} : {render_type(ftype)}" for fname, ftype in fields)
    return "\n".join(lines)


def _extract_constants(spec: ModuleSpec, tree: ast.Module) -> tuple[list[str], dict[str, LType]]:
    """Registry-declared module-level int constants -> Lean `def NAME : Int`
    blocks (in registry order) + the constant type environment."""
    assigns: dict[str, ast.Assign] = {}
    for stmt_node in tree.body:
        if isinstance(stmt_node, ast.Assign) and len(stmt_node.targets) == 1 \
                and isinstance(stmt_node.targets[0], ast.Name):
            assigns[stmt_node.targets[0].id] = stmt_node
    blocks: list[str] = []
    consts: dict[str, LType] = {}
    for name in spec.constants:
        cnode = assigns.get(name)
        if cnode is None:
            raise ExtractionError(f"{spec.source}: registered constant {name!r} not found")
        value = cnode.value
        if not (isinstance(value, ast.Constant) and isinstance(value.value, int)
                and not isinstance(value.value, bool)):
            reject(spec.source, cnode, f"registered constant {name!r} without an int literal value")
        check_ident(spec.source, cnode, name)
        rendered = f"({value.value})" if value.value < 0 else str(value.value)
        blocks.append(f"/-- Extracted module constant `{name}` (line {cnode.lineno}). -/\n"
                      f"def {name} : Int := {rendered}")
        consts[name] = T_INT
    return blocks, consts


def extract_module(spec: ModuleSpec,
                   global_sigs: dict[str, tuple[str, tuple[LType, ...], LType, bool]]) -> str:
    path = ROOT / spec.source
    text = path.read_text()
    digest = hashlib.sha256(text.encode()).hexdigest()
    tree = ast.parse(text, filename=spec.source)
    env = TypeEnv(opaque=spec.opaque_types)
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    missing_structs = [s for s in spec.structures if s not in classes]
    if missing_structs:
        raise ExtractionError(
            f"{spec.source}: registered structures not found: {missing_structs}")
    struct_blocks = [extract_structure(env, spec.source, classes[s])
                     for s in spec.structures]
    const_blocks, consts = _extract_constants(spec, tree)
    by_name = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    missing = [f for f in spec.functions if f not in by_name]
    if missing:
        raise ExtractionError(f"{spec.source}: registered functions not found: {missing}")
    missing_imports = [f for f in spec.imports if f not in global_sigs]
    if missing_imports:
        raise ExtractionError(
            f"{spec.source}: registered imports not extracted by an earlier module: "
            f"{missing_imports}")
    import_sigs = {f: global_sigs[f] for f in spec.imports}
    helpers: set[str] = set()
    module_sigs: dict[str, tuple[tuple[LType, ...], LType, bool]] = {}
    defs = [extract_function(env, spec.source, by_name[f], helpers, module_sigs,
                             import_sigs, consts)
            for f in spec.functions]
    for fname, (fparams, fret, ffueled) in module_sigs.items():
        if fname in global_sigs:
            raise ExtractionError(
                f"{spec.source}: extracted function name {fname!r} collides with "
                f"module {global_sigs[fname][0]}")
        global_sigs[fname] = (spec.core_name, fparams, fret, ffueled)
    helper_blocks = [HELPER_DEFS[h] for h in HELPER_ORDER if h in helpers]
    import_cores = sorted({global_sigs[f][0] for f in spec.imports})
    import_lines = [f"import Formal.Extracted.{core}" for core in import_cores]
    parts = [
        f"-- GENERATED from {spec.source} (sha256: {digest}) — DO NOT EDIT",
        "-- Regenerate: `uv run python scripts/extract_lean.py` (drift gate: --check).",
        *import_lines,
        "",
        f"namespace Extracted.{spec.core_name}",
        "",
        "\n\n".join(helper_blocks + struct_blocks + const_blocks + defs),
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
    global_sigs: dict[str, tuple[str, tuple[LType, ...], LType, bool]] = {}
    for spec in MODULES:
        generated = extract_module(spec, global_sigs)
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
