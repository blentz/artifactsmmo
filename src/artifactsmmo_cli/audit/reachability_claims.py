"""Census of REACHABILITY CLAIMS: comments in production Python that assert a
named thing has no caller. Every claim is resolved to a subject and verified
against the real import/reference graph; a FALSE claim fails the gate.

WHY THIS EXISTS. The wave-3b deletion pass found three comments asserting that
LIVE code was dead. `ai/obtain_sources.py` opened "INERT — nothing calls this
yet" while ELEVEN production modules imported it and both plan producers ran
through it; acting on that comment takes out the planner. `ai/acquisition_cost
_core.py` said "INERT ON ARRIVAL. Nothing consumes this yet" while
`acquisition_cost.py:30` imported it. Both were TRUE the day they were written
and were never revisited. That is a defect class, not two incidents: the claim
is a fact about the import graph, the import graph changes underneath it, and
nothing re-checks it.

SCOPE IS DELIBERATELY NARROW, on the precedent of `formal/gate/
check_proof_citations.sh`, which refused to gate on `proved|proven|provably`
because a broad rule "would be almost all noise and would rot into an
allowlist". `grep -i inert` over src/ returns ~20 hits and most are legitimate
CONDITIONAL claims — "inert while `bank_items` is None", "solo-inert",
"arithmetically INERT" — none of which is decidable. Only a REACHABILITY claim
is: it says a subject has no caller, and the caller either exists or does not.
So the phrase set matches that assertion and nothing else.

TENSE IS PART OF THE CLAIM. This repo writes a great deal of true history —
"the flat-ranking search it fed was deleted, leaving zero callers", "as of this
commit they had zero callers", "it landed with no consumer on purpose". Those
describe a past state, usually of something now deleted, and gating on them
would be pure noise. A claim is therefore skipped when the phrase is directly
governed by a past-tense frame (`had`/`was`/`were`/`leaving`/`left`/`used to`/
`until`/`no longer`), and — since only a subject that still exists can be
checked at all — when an explicitly named subject is no longer defined.

SUBJECT RESOLUTION is by CONTAINMENT, which is what makes it mechanical:

  * an explicitly named subject — "nothing calls `foo`" — is that symbol;
  * otherwise the innermost `def`/`class` whose body CONTAINS the claim line
    (so a claim in a method's docstring is a claim about that method);
  * otherwise — a module docstring, or a comment between definitions — the
    MODULE. This is why the two live failures resolve: both were module
    docstrings, so the subject is the module and the verdict is "does any
    other production module import it".

A claim in a `#` comment sitting ABOVE a definition therefore resolves to the
module, not to that definition. That is the honest reading: such comments in
this repo are almost always about something just deleted, and attributing them
to the next definition down would invent a subject the author never named.

VERIFICATION asks the real graph, built from `ast` over all of src/:

  * MODULE subject — reached if any OTHER production module imports it.
  * SYMBOL subject — reached if the name is referenced anywhere in src/
    outside the subject's own definition body. A module-level name counts a
    bare `Name` reference, an `import`, or `module.name` where `module` is an
    imported module in that file; it deliberately does NOT count a bare
    `obj.name` attribute, because attribute names collide across classes
    (`RequirementGraph.is_obtainable` must not be read as a caller of
    `tiers/skill_grind_target.is_obtainable`). A METHOD counts attribute
    references, which is the only way a method is ever called.

A TRUE claim passes and is meant to: `player.py`'s `_tree_band_adequate` says
"nothing calls this method any more — a deliberate deferral", which is true,
and `tiers/progression_tree_core.potion_type_weight` is retained with no caller
on purpose. Recording that truthfully is the behaviour this census rewards.
"""

import ast
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# A sweep that finds nothing must FAIL, not pass: this repo has shipped a
# census that reported total success over an empty reference set, and "0 false
# claims" reads identically whether the matcher is working or broken.
#
# The bound is TIGHT ON PURPOSE — it is exactly the population carried on
# 2026-08-24: `player._tree_band_adequate`, `tiers/skill_grind_target
# .is_obtainable` and `tiers/progression_tree_core.potion_type_weight`, all
# three verified true. The decidable population in this repo is small (~20
# `inert` hits, nearly all CONDITIONAL and undecidable, are deliberately out of
# scope), so a slack bound would not fail until the matcher was completely
# dead. Rewording one of the three costs a deliberate edit here, which is the
# point: the register is meant to be small enough to read.
MIN_CLAIMS = 3

_SUBJECT = r"(?:this|it|them)"
_ROLE = r"(?:caller|consumer|importer|reader)s?"

CLAIM_RE = re.compile(
    r"nothing\s+(?:calls|consumes|reads|imports|uses|invokes)\s+"
    # `\b` belongs INSIDE the pronoun arm: after a closing backtick the next
    # character is usually "." or ",", so a trailing \b would reject every
    # explicitly named subject.
    r"(?:`(?P<sym>[A-Za-z_][A-Za-z0-9_]*)`|" + _SUBJECT + r"\b)"
    r"|(?:has|have)\s+no\s+(?:production\s+)?" + _ROLE + r"\b"
    r"|no\s+production\s+" + _ROLE + r"\b"
    r"|no\s+" + _ROLE + r"\s+(?:yet|today|any\s?more)\b"
    r"|zero[-\s]" + _ROLE + r"\b"
    r"|not\s+called\s+(?:yet|any\s?more|today)\b",
    re.IGNORECASE,
)

# A past-tense frame governing the phrase, within two words of it.
HISTORICAL_RE = re.compile(
    r"\b(?:had|has\s+been|was|were|leaving|left|used\s+to|until|no\s+longer)\s+"
    r"(?:\w+\s+){0,2}$",
    re.IGNORECASE,
)

# The same frame TRAILING the phrase. Both live cases are about something
# already deleted: "NO production caller ever passed one — it was dead code"
# (the `reserved` argument of `skill_grind_target`) and "why each one has no
# reader left" (six parameters removed in THE FLIP). Neither subject still
# exists to be resolved, so neither is decidable.
TRAILING_HISTORICAL_RE = re.compile(r"^\s*(?:ever|left|before|originally)\b", re.IGNORECASE)

# The census must name the phrasings it matches, so its own source is the one
# file whose prose is guaranteed to trip it. Excluded from the SWEEP only — it
# stays in the index as an importer and a reference site like any other module.
SELF_MODULE = "artifactsmmo_cli.audit.reachability_claims"


@dataclass(frozen=True)
class Definition:
    """One `def`/`class` and the line range its body occupies."""

    name: str
    kind: str  # "function" | "class" | "method"
    module: str
    start: int
    end: int


@dataclass(frozen=True)
class Reference:
    """One use of a name, and how it was written."""

    name: str
    module: str
    lineno: int
    kind: str  # "name" | "import" | "module_attr" | "attr"


@dataclass(frozen=True)
class Claim:
    """A reachability assertion and the subject it resolves to."""

    module: str
    lineno: int
    phrase: str
    subject: str
    kind: str  # "module" | "symbol"


@dataclass(frozen=True)
class Verdict:
    """A claim plus the call sites that contradict it (empty means TRUE)."""

    claim: Claim
    reached_by: tuple[str, ...]

    @property
    def is_false(self) -> bool:
        return bool(self.reached_by)


def module_name(path: str) -> str:
    """`src/artifactsmmo_cli/ai/x.py` -> `artifactsmmo_cli.ai.x`."""
    trimmed = path[len("src/") :] if path.startswith("src/") else path
    dotted = trimmed[: -len(".py")].replace("/", ".")
    return dotted[: -len(".__init__")] if dotted.endswith(".__init__") else dotted


def _definitions(tree: ast.Module, module: str) -> list[Definition]:
    """Every def/class in the file, tagged `method` when class-nested."""
    found: list[Definition] = []
    stack: list[tuple[ast.AST, bool]] = [(tree, False)]
    while stack:
        node, in_class = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                is_class = isinstance(child, ast.ClassDef)
                kind = "class" if is_class else ("method" if in_class else "function")
                end = child.end_lineno or child.lineno
                found.append(Definition(child.name, kind, module, child.lineno, end))
                stack.append((child, is_class))
            else:
                stack.append((child, in_class))
    return found


def _imported_modules(tree: ast.Module, module: str) -> tuple[set[str], set[str]]:
    """(dotted modules this file imports, names bound to a module by import)."""
    modules: set[str] = set()
    aliases: set[str] = set()
    package = module.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                aliases.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                root = ".".join(parts[: len(parts) - node.level + 1])
                base = f"{root}.{base}" if base else root
            modules.add(base)
            for alias in node.names:
                modules.add(f"{base}.{alias.name}")
                aliases.add(alias.asname or alias.name)
    return modules, aliases


def _references(tree: ast.Module, module: str, aliases: set[str]) -> list[Reference]:
    """Every name use in the file, classified so collisions can be excluded."""
    refs: list[Reference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            refs.append(Reference(node.id, module, node.lineno, "name"))
        elif isinstance(node, ast.Attribute):
            through_module = isinstance(node.value, ast.Name) and node.value.id in aliases
            kind = "module_attr" if through_module else "attr"
            refs.append(Reference(node.attr, module, node.lineno, kind))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                refs.append(Reference(alias.name, module, node.lineno, "import"))
    return refs


def _innermost(defs: Iterable[Definition], lineno: int) -> Definition | None:
    """The definition whose body contains `lineno`, deepest first."""
    holding = [d for d in defs if d.start <= lineno <= d.end]
    return max(holding, key=lambda d: d.start) if holding else None


def _claims_in(
    text: str, module: str, defs: list[Definition], defined: set[str]
) -> list[Claim]:
    for_module: list[Claim] = []
    for match in CLAIM_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        if HISTORICAL_RE.search(text[line_start : match.start()]):
            continue
        if TRAILING_HISTORICAL_RE.match(text[match.end() : match.end() + 40]):
            continue
        lineno = text.count("\n", 0, match.start()) + 1
        named = match.groupdict().get("sym")
        if named is not None:
            # A named subject that no longer exists is a note about a deletion,
            # not a claim about live code — there is nothing left to verify.
            if named in defined:
                for_module.append(Claim(module, lineno, match.group(0), named, "symbol"))
            continue
        holder = _innermost(defs, lineno)
        if holder is None:
            for_module.append(Claim(module, lineno, match.group(0), module, "module"))
        else:
            for_module.append(Claim(module, lineno, match.group(0), holder.name, "symbol"))
    return for_module


@dataclass(frozen=True)
class SourceIndex:
    """The whole production import/reference graph, built once."""

    definitions: dict[str, list[Definition]]
    imports: dict[str, set[str]]
    references: dict[str, list[Reference]]


def build_index(sources: Mapping[str, str]) -> SourceIndex:
    """Parse every production file into the graph the verdicts are read from."""
    definitions: dict[str, list[Definition]] = {}
    imports: dict[str, set[str]] = {}
    references: dict[str, list[Reference]] = {}
    for path, text in sources.items():
        module = module_name(path)
        tree = ast.parse(text)
        definitions[module] = _definitions(tree, module)
        modules, aliases = _imported_modules(tree, module)
        imports[module] = modules
        references[module] = _references(tree, module, aliases)
    return SourceIndex(definitions, imports, references)


def find_claims(sources: Mapping[str, str], index: SourceIndex) -> list[Claim]:
    """Every reachability claim in production Python, subject resolved."""
    claims: list[Claim] = []
    for path, text in sorted(sources.items()):
        module = module_name(path)
        if module == SELF_MODULE:
            continue
        defs = index.definitions[module]
        claims.extend(_claims_in(text, module, defs, {d.name for d in defs}))
    return claims


def _reached_module(subject: str, index: SourceIndex) -> tuple[str, ...]:
    return tuple(
        sorted(mod for mod, imported in index.imports.items()
               if mod != subject and subject in imported)
    )


def _reached_symbol(claim: Claim, index: SourceIndex) -> tuple[str, ...]:
    owner = next(
        (d for d in index.definitions[claim.module] if d.name == claim.subject),
        None,
    )
    allowed = {"name", "import", "module_attr"}
    if owner is not None and owner.kind == "method":
        allowed = allowed | {"attr"}
    hits: set[str] = set()
    for module, refs in index.references.items():
        for ref in refs:
            if ref.name != claim.subject or ref.kind not in allowed:
                continue
            own_body = (
                owner is not None
                and module == owner.module
                and owner.start <= ref.lineno <= owner.end
            )
            if own_body:
                continue
            hits.add(f"{module}:{ref.lineno}")
    return tuple(sorted(hits))


def run_census(sources: Mapping[str, str]) -> list[Verdict]:
    """Verify every reachability claim against the real graph."""
    index = build_index(sources)
    verdicts: list[Verdict] = []
    for claim in find_claims(sources, index):
        reached = (
            _reached_module(claim.subject, index)
            if claim.kind == "module"
            else _reached_symbol(claim, index)
        )
        verdicts.append(Verdict(claim, reached))
    return verdicts


def render_register(verdicts: Iterable[Verdict]) -> str:
    """One line per claim: where it is, what it claims about, and the verdict."""
    lines = []
    for verdict in verdicts:
        claim = verdict.claim
        if verdict.is_false:
            shown = ", ".join(verdict.reached_by[:3])
            more = f" (+{len(verdict.reached_by) - 3} more)" if len(verdict.reached_by) > 3 else ""
            status = f"FALSE — reached by {shown}{more}"
        else:
            status = "true — no production caller"
        lines.append(
            f"{claim.module}:{claim.lineno}: {claim.kind} `{claim.subject}` "
            f'claims "{claim.phrase}" -> {status}'
        )
    return "\n".join(lines)


def summary_line(verdicts: list[Verdict]) -> str:
    false_count = sum(1 for v in verdicts if v.is_false)
    return (
        f"reachability-claim census: {len(verdicts)} claims swept, "
        f"{len(verdicts) - false_count} verified true, {false_count} FALSE"
    )
