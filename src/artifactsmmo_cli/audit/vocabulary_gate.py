"""The vocabulary gate (spec 2026-10-18 §5 item 4): no source file under `src/`
defines or reads tier, rung, band, ladder or milestone.

The tier ladder was a CONCEPT the planner computed: decade rungs, level bands
around the character, a gear cap per tier, milestone roots. Spec §2.7 lists it
among the things that must emerge and must not be computed (USER 2026-10-18,
"tiers are emergent"). Plan C deleted it. This gate keeps it deleted: a new
identifier whose parts name one of the words fails the build, so the concept
cannot come back under a fresh helper name.

NAME TOKENS ONLY. Every `src/` file goes through Python's `tokenize`, and only
`NAME` tokens are read. A comment or a docstring that says "tier" is prose, not
a definition, and passes. The words are matched against an identifier's PARTS:
its snake_case segments, each split again on camelCase humps. So `gear_tier`,
`IsMyGearBehindMyTier` and `BAND_MARGIN` are caught, while `frontier` and
`husband` are not. A plural part (`tiers`, `rungs`) counts as the word.

ALLOWED BY NAME, NOT BY PATTERN (plan C, Review Focus 5). Some live vocabulary
shares a word without being the deleted concept: the arbiter's priority bands,
the skill grind's recipe rungs, the `content_tiers` audit, and the level windows
the inventory caps and combat targets read. Each is in `ALLOWED` under its exact
identifier, with the reason, and in `HOMES` with the modules it lives in. So a
generic name such as `band` is allowed only where it already means a priority
band or a cap band, and a new `band` anywhere else fails.

Both tables must stay true. An entry whose name no longer appears in one of its
homes is an ORPHAN and fails too, like `liveness_completeness`'s `DORMANT`: an
allowance that outlives its use would quietly reopen the word.
"""

import io
import re
import tokenize
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

WORDS = frozenset({"tier", "rung", "band", "ladder", "milestone"})
"""The deleted concept's vocabulary (spec §5 item 4)."""

PACKAGE_PREFIX = "src/artifactsmmo_cli/"
"""A module's key in `HOMES` is its path below this, without `.py`."""

_PRIORITY_ORDER = ("the arbiter's dispatch order: the priority band a goal clamps into "
                  "(`priority_band`, `arbiter_select`), not a level band")
_GRIND_RECIPE = ("a skill grind's rung: the in-level catalogue recipe the grind crafts "
               "for XP (`grind_rung`, `skill_grind_target`), not a ladder rung")
_CONDITIONS_CENSUS = ("the craft-conditions census's ladder of planning conditions, "
                      "one rung per added condition; an audit dimension")
_CONTENT_AUDIT = ("the `content_tiers` audit's fixed grouping of content by level, a "
                  "census dimension that decides nothing")
_LEVEL_WINDOW = ("a level window a published server rule is read through "
               "(`combat_targets`, `inventory_caps`)")
_INVENTORY_DISTANCE = ("the inventory census's level-distance dimension (`in_band` / "
                   "`far`), realised from `inventory_caps.LEVEL_BAND_*`")
_POTION_SUPPLY = ("`potion_supply`'s supply ladder: held ingredients, then an "
                  "affordable buy mix, then a craft")
_MACRO_REPORT = "the `macro` research report's XP segment bands, an offline tool"

ALLOWED: dict[str, str] = {
    "BAND_DISCRETIONARY": _PRIORITY_ORDER,
    "BAND_FALLBACK_STEP": _PRIORITY_ORDER,
    "BAND_GAIN": _PRIORITY_ORDER,
    "BAND_GUARD": _PRIORITY_ORDER,
    "BAND_RAID": _PRIORITY_ORDER,
    "BAND_STEP": _PRIORITY_ORDER,
    "clamp_into_band": _PRIORITY_ORDER,
    "lower_band_precedes": _PRIORITY_ORDER,
    "priority_band": _PRIORITY_ORDER,
    "band": (f"{_PRIORITY_ORDER}; {_MACRO_REPORT}; {_CONTENT_AUDIT}; {_INVENTORY_DISTANCE}"),
    "craft_rung": _GRIND_RECIPE,
    "grind_rung": _GRIND_RECIPE,
    "grind_rung_goal": _GRIND_RECIPE,
    "rung": _GRIND_RECIPE,
    "rung_item": _GRIND_RECIPE,
    "rung_level": _GRIND_RECIPE,
    "rung_mats": _GRIND_RECIPE,
    "rung_resources": _GRIND_RECIPE,
    "rung_state_core": _GRIND_RECIPE,
    "_rung_below": _GRIND_RECIPE,
    "_EXPECTED_RUNG": _GRIND_RECIPE,
    "by_rung": _CONDITIONS_CENSUS,
    "ladder": _CONDITIONS_CENSUS,
    "rungs": _CONDITIONS_CENSUS,
    "ContentTier": _CONTENT_AUDIT,
    "derive_content_tiers": _CONTENT_AUDIT,
    "tiers": _CONTENT_AUDIT,
    "_tier": _CONTENT_AUDIT,
    "_band_index": _CONTENT_AUDIT,
    "LEVEL_BAND_BELOW": _LEVEL_WINDOW,
    "LEVEL_BAND_FAR": _LEVEL_WINDOW,
    "LEVEL_BAND_NEAR": _LEVEL_WINDOW,
    "BANDS": _INVENTORY_DISTANCE,
    "band_level": _INVENTORY_DISTANCE,
    "band_summary": _INVENTORY_DISTANCE,
    "bands": f"{_MACRO_REPORT}; {_INVENTORY_DISTANCE}",
    "_ladder_runs": _POTION_SUPPLY,
    "ladder_supplies": _POTION_SUPPLY,
    "Band": _MACRO_REPORT,
    "segment_bands": _MACRO_REPORT,
}

HOMES: dict[str, tuple[str, ...]] = {
    "BAND_DISCRETIONARY": ("ai/arbiter_select", "ai/strategy_driver"),
    "BAND_FALLBACK_STEP": ("ai/arbiter_select", "ai/intention_progress", "ai/strategy_driver"),
    "BAND_GAIN": ("ai/scalar_priority",),
    "BAND_GUARD": ("ai/arbiter_select", "ai/strategy_driver"),
    "BAND_RAID": ("ai/arbiter_select", "ai/strategy_driver"),
    "BAND_STEP": ("ai/arbiter_select", "ai/intention_progress", "ai/strategy_driver"),
    "clamp_into_band": ("ai/goals/gathering", "ai/goals/grind_character_xp",
                        "ai/goals/pursue_task", "ai/goals/supply_bank", "ai/priority_band"),
    "lower_band_precedes": ("ai/arbiter_select",),
    "priority_band": ("ai/goals/gathering", "ai/goals/grind_character_xp",
                      "ai/goals/pursue_task", "ai/goals/supply_bank"),
    "band": ("ai/arbiter_select", "ai/intention_progress", "ai/macro/scoring",
             "ai/strategy_driver", "audit/content_tiers", "audit/inventory_census",
             "audit/inventory_completeness", "audit/inventory_report"),
    "craft_rung": ("ai/grind_rung",),
    "grind_rung": ("ai/craft_plan_gen", "audit/craft_completeness"),
    "grind_rung_goal": ("ai/craft_plan_gen", "ai/grind_rung", "audit/craft_completeness"),
    "rung": ("ai/craft_plan_gen", "ai/grind_probe_state", "ai/grind_rung",
             "ai/progression/skill_grind_target", "audit/craft_completeness",
             "audit/craft_conditions", "audit/shed_reachability_completeness"),
    "rung_item": ("audit/craft_completeness",),
    "rung_level": ("ai/learning/rung_state_core",),
    "rung_mats": ("audit/craft_completeness",),
    "rung_resources": ("audit/craft_completeness",),
    "rung_state_core": ("ai/task_horizon",),
    "_rung_below": ("audit/craft_completeness",),
    "_EXPECTED_RUNG": ("audit/shed_reachability_completeness",),
    "by_rung": ("audit/craft_conditions",),
    "ladder": ("audit/craft_conditions",),
    "rungs": ("audit/craft_conditions",),
    "ContentTier": ("audit/content_tiers",),
    "derive_content_tiers": ("audit/content_tiers",),
    "tiers": ("audit/content_tiers",),
    "_tier": ("audit/content_tiers",),
    "_band_index": ("audit/content_tiers",),
    "LEVEL_BAND_BELOW": ("ai/combat_targets",),
    "LEVEL_BAND_FAR": ("ai/inventory_caps",),
    "LEVEL_BAND_NEAR": ("ai/inventory_caps",),
    "BANDS": ("audit/inventory_completeness",),
    "band_level": ("audit/inventory_completeness",),
    "band_summary": ("audit/inventory_report",),
    "bands": ("ai/macro/scoring", "ai/macro/segmentation", "audit/inventory_report",
              "commands/macro_research"),
    "_ladder_runs": ("ai/potion_supply",),
    "ladder_supplies": ("ai/grind_heal_prep", "ai/potion_supply"),
    "Band": ("ai/macro/scoring", "ai/macro/segmentation"),
    "segment_bands": ("ai/macro/segmentation", "commands/macro_research"),
}


@dataclass(frozen=True)
class Hit:
    """One identifier that names the concept: `name` at `module:lineno`."""

    module: str
    lineno: int
    name: str


@dataclass(frozen=True)
class GateResult:
    """`violations`: hits no allowance covers. `orphans`: `(name, module)`
    allowances the tree no longer uses. The gate passes iff both are empty."""

    violations: tuple[Hit, ...]
    orphans: tuple[tuple[str, str], ...]

    @property
    def passed(self) -> bool:
        return not self.violations and not self.orphans


def module_key(path: str) -> str:
    """`src/artifactsmmo_cli/ai/x.py` -> `ai/x`, the key `HOMES` uses."""
    key = path.replace("\\", "/").removesuffix(".py")
    return key.removeprefix(PACKAGE_PREFIX)


def parts(name: str) -> list[str]:
    """`name`'s lower-cased words: snake_case segments, each split on camelCase
    humps and digit runs (`CanICraftThisAtAll` -> can, i, craft, this, at, all)."""
    found: list[str] = []
    for segment in name.split("_"):
        found.extend(p.lower() for p in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", segment))
    return found


def names_the_concept(name: str) -> bool:
    """Whether a part of `name` is one of `WORDS`, or its plural."""
    return any(p in WORDS or (p.endswith("s") and p[:-1] in WORDS) for p in parts(name))


def scan(module: str, text: str) -> list[Hit]:
    """Every NAME token of `text` that names the concept. Comments and strings
    (docstrings included) are other token types, and are never read."""
    return [Hit(module, token.start[0], token.string)
            for token in tokenize.generate_tokens(io.StringIO(text).readline)
            if token.type == tokenize.NAME and names_the_concept(token.string)]


def violations(hits: Iterable[Hit], homes: Mapping[str, tuple[str, ...]]) -> tuple[Hit, ...]:
    """The hits no allowance covers: a name not allowed, or allowed elsewhere."""
    return tuple(hit for hit in hits if hit.module not in homes.get(hit.name, ()))


def orphans(hits: Iterable[Hit], homes: Mapping[str, tuple[str, ...]]
            ) -> tuple[tuple[str, str], ...]:
    """`(name, module)` for every allowance the tree no longer uses there."""
    seen = {(hit.name, hit.module) for hit in hits}
    return tuple((name, module) for name, modules in homes.items() for module in modules
                 if (name, module) not in seen)


def run_gate(sources: Mapping[str, str],
             homes: Mapping[str, tuple[str, ...]] = HOMES) -> GateResult:
    """The gate over `sources` (path -> text)."""
    hits = [hit for path, text in sorted(sources.items())
            for hit in scan(module_key(path), text)]
    return GateResult(violations(hits, homes), orphans(hits, homes))


def render(result: GateResult) -> str:
    """One line per violation and per orphan, then the verdict."""
    lines = [f"  {hit.module}:{hit.lineno}: `{hit.name}` names tier/rung/band/ladder/"
             "milestone and is not allowed there" for hit in result.violations]
    lines += [f"  orphan allowance: `{name}` no longer appears in {module}"
              for name, module in result.orphans]
    verdict = "PASS" if result.passed else (
        f"FAIL: {len(result.violations)} violation(s), {len(result.orphans)} orphan(s)")
    return "\n".join([*lines, f"vocabulary gate: {verdict}"])
