"""Stat-projection completeness census — can the objective SEE what an item grants?

The unified objective `J` prices a gear candidate by projecting the character
holding it and asking `cheapest_path_to_level` how the grind changes. That
question reaches gear through exactly one channel:
`ai/equipment/projection.project_loadout_stats`, whose `ProjectedStats` result is
what `is_winnable` and `expected_damage_per_fight` read.

**A stat `ProjectedStats` does not carry is a stat `J` cannot value.** Not
under-value — cannot value at all, because the projected candidate comes back
byte-identical to the trunk and then loses on acquisition cost. Measured on
scenario `l12_deep_chain_grind` at `5a2d1b8d`:

    trunk           reach=17  cost=0
    wisdom_amulet   reach=17  cost=50     <- wisdom 60 = +6% xp on every kill
    iron_sword      reach=18  cost=65     <- attack {earth: 24}

`wisdom 60` multiplies the xp of every kill from here to level 50 and moved the
projection by nothing, because `ProjectedStats` has no `wisdom` field. The sword
won on a stat that happens to have one. That is the whole defect, and it is
invisible to ordinary tests because nothing errors — an absent term reads as
zero, and zero is always a plausible number.

WHAT THIS CENSUS ASSERTS. Every `ItemStats` field is classified into exactly one
bucket, and every WORN-EFFECT field is either projected or carries a written
justification for why it is not. Two directions, both load-bearing:

  * COMPLETENESS — a worn-effect field that is neither projected nor declared
    fails. This is what catches a NEW stat the server adds: it lands in
    `ItemStats` during OpenAPI conformance work, matches no bucket, and the
    census goes red rather than the objective quietly ignoring it.

  * NO STALE EXCLUSIONS — a field declared `UNPRICED` that HAS since become
    projected also fails. The exclusion list is therefore forced to SHRINK as
    the epic lands; it cannot become a permanent parking lot for stats nobody
    got round to. Deleting an entry is part of the increment that fixes it.

The bucket assignment is exhaustive by construction (`_classify` partitions
`dataclasses.fields(ItemStats)`), so a field cannot be silently ignored by being
left out of every list — the failure mode that let five stats go unpriced for
the whole life of the objective.

See `docs/PLAN_unified_acquisition_objective.md`. `wisdom` GRADUATED in increment
3 — the numbers above are history, not the current state. `prospecting` GRADUATED in increment 4, where
it reduces expected kills in the DROP-route cost. `inventory_space` and `lifesteal` are expressible in
actions but have no `WorldState` base total to project a delta from, so they wait
on that. `haste` is a PERMANENT exclusion and is the one entry here that is not a
defect — see its justification.
"""

from dataclasses import dataclass, fields

from artifactsmmo_cli.ai.equipment.projection import ProjectedStats
from artifactsmmo_cli.ai.game_data import ItemStats

METADATA_FIELDS = frozenset({
    "code", "level", "type_", "subtype", "tradeable", "conditions",
    "crafting_skill", "crafting_level",
})
"""Identity and provenance. Describes what an item IS, never what wearing it
does to the character, so projection is not a meaningful question for these."""

CONSUMABLE_FIELDS = frozenset({
    "hp_restore", "combat_buff", "antipoison", "teleport_map_id", "gold_value",
    "skill_effects",
})
"""Effects of USING an item (or of a utility-slot consumable), not of wearing a
piece of gear. They are modelled elsewhere — `predict_win` reads `combat_buff`
and `antipoison` directly from the equipped potion, `hp_restore` drives
consumable selection — and a loadout projection is the wrong instrument for
them. Out of scope for this census by construction, not by oversight."""

WORN_EFFECT_TO_PROJECTED = {
    "attack": "attack",
    "resistance": "resistance",
    "dmg": "dmg",
    "dmg_elements": "dmg_elements",
    "critical_strike": "critical_strike",
    "initiative": "initiative",
    "hp_bonus": "max_hp",
    "wisdom": "wisdom",
    "prospecting": "prospecting",
}
"""Worn-gear effects `ProjectedStats` carries, mapped to the field that carries
them. `hp_bonus` -> `max_hp` is the one rename: the item grants a BONUS, the
projection reports the resulting TOTAL, which is why this is a mapping rather
than a set membership test."""

UNPRICED: dict[str, str] = {
    "inventory_space": (
        "+bag slots. Pays in avoided bank round-trips, which are actions — so "
        "this IS expressible in J's currency, unlike haste. Needs a model of "
        "how often a full bag forces a deposit trip; not yet built. Scheduled: "
        "no increment assigned."
    ),
    "lifesteal": (
        "Heals a share of attack on a crit, so it reduces the damage taken per "
        "fight and therefore `rest_cycles_per_fight` — the same channel armour "
        "already pays through. Expressible in actions today; blocked only on "
        "`expected_damage_per_fight` modelling crits. Scheduled: no increment "
        "assigned."
    ),
    "haste": (
        "PERMANENT EXCLUSION — not a defect. Haste reduces action COOLDOWN, "
        "which is measured in SECONDS. `J` is denominated in ACTIONS. A hasted "
        "character performs the same number of actions, faster. Admitting haste "
        "would mix seconds into an action count, which is the exact confusion "
        "that has produced four separate bugs here (`mats_missing` as cost, "
        "`DEFAULT_FIGHT_CYCLES` as cycles, `cycles_to_fifty` as whole-loop "
        "cycles, `cheapest_path_to_level` in seconds). Wall-clock deserves its "
        "own objective with an explicit conversion, never a term smuggled into "
        "this one. Travel distance is excluded for the identical reason — see "
        "decision 2 in the plan."
    ),
}
"""Worn-gear effects `ProjectedStats` does NOT carry, each with the reason and,
where one exists, the increment that removes it. An entry here is a DECLARED
blind spot, which is a different thing from an unnoticed one — and the census
below fails if an entry ever becomes stale, so the list can only shrink."""


@dataclass(frozen=True)
class StatProjectionCensus:
    """Verdict of one census run.

    `unclassified` and `stale_exclusions` must BOTH be empty. `unpriced` is
    expected to be non-empty until the epic lands and is reported for visibility
    rather than as a failure — it is exactly `UNPRICED`'s key set, re-derived
    from the live dataclasses so it cannot drift from what the code does."""

    projected: frozenset[str]
    unpriced: frozenset[str]
    unclassified: frozenset[str]
    stale_exclusions: frozenset[str]

    @property
    def ok(self) -> bool:
        return not self.unclassified and not self.stale_exclusions


def _item_stats_fields() -> frozenset[str]:
    return frozenset(f.name for f in fields(ItemStats))


def _projected_fields() -> frozenset[str]:
    return frozenset(f.name for f in fields(ProjectedStats))


def run_census() -> StatProjectionCensus:
    """Partition `ItemStats`' fields and check both directions.

    Reads the live dataclasses via `dataclasses.fields` rather than a
    hand-copied roster, so adding a field to either one is what triggers the
    census — a roster restated here could drift from the type it describes, and
    a census that describes a stale type proves nothing."""
    all_fields = _item_stats_fields()
    projected_fields = _projected_fields()

    worn = all_fields - METADATA_FIELDS - CONSUMABLE_FIELDS
    unclassified = worn - frozenset(WORN_EFFECT_TO_PROJECTED) - frozenset(UNPRICED)

    # A declared exclusion is STALE once the projection carries it — either
    # under its own name, or under the name `WORN_EFFECT_TO_PROJECTED` would
    # give it if it graduated.
    stale = frozenset(name for name in UNPRICED if name in projected_fields)

    return StatProjectionCensus(
        projected=frozenset(WORN_EFFECT_TO_PROJECTED),
        unpriced=frozenset(UNPRICED),
        unclassified=unclassified,
        stale_exclusions=stale,
    )


def format_census(census: StatProjectionCensus) -> str:
    """Human-readable report — the shape the other censuses in this package
    print, so a failure reads the same way wherever it comes from."""
    lines = [
        "STAT PROJECTION COMPLETENESS",
        f"  priced by J   ({len(census.projected):2d}): "
        f"{', '.join(sorted(census.projected))}",
        f"  UNPRICED      ({len(census.unpriced):2d}): "
        f"{', '.join(sorted(census.unpriced))}",
    ]
    if census.unclassified:
        lines.append(
            f"  UNCLASSIFIED  ({len(census.unclassified):2d}): "
            f"{', '.join(sorted(census.unclassified))}"
            "  <- a new ItemStats field matches no bucket; classify it")
    if census.stale_exclusions:
        lines.append(
            f"  STALE         ({len(census.stale_exclusions):2d}): "
            f"{', '.join(sorted(census.stale_exclusions))}"
            "  <- now projected; delete the UNPRICED entry")
    lines.append(f"  verdict: {'OK' if census.ok else 'FAIL'}")
    return "\n".join(lines)
