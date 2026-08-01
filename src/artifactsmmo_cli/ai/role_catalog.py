"""Named specialization roles.

A role is a STRATEGY declaration, the same category of thing as
`loadout_profiles` — not a classification derived from API data, so the
"generic over API taxonomy, never hardcoded" rule (which governs item keep/junk
classification) does not apply. What DOES apply is that a role must not name a
skill the server lacks: `validate_catalog` checks every declared skill against
the api-client-derived sets in `tiers/skill_classes.py` and raises rather than
silently no-opping, per "use only API data or fail with an error".

`skill_classes` derives GATHER_SKILLS / COMBAT_CRAFT_SKILLS /
CONSUMABLE_CRAFT_SKILLS from the `CraftSkill` / `GatheringSkill` enums by set
algebra over a single policy seed, specifically so they cannot drift from the
schema. This module's only hand-authored content is the PAIRING of those
skills into roles.

Verified against the api-client enums 2026-08-01:
  GatheringSkill = {alchemy, fishing, mining, woodcutting}
  CraftSkill     = {alchemy, cooking, gearcrafting, jewelrycrafting, mining,
                    weaponcrafting, woodcutting}
so GATHER_SKILLS = {fishing, mining, woodcutting} (alchemy both gathers and
brews and is valued as consumable-craft), COMBAT_CRAFT_SKILLS =
{gearcrafting, jewelrycrafting, weaponcrafting}, CONSUMABLE_CRAFT_SKILLS =
{alchemy, cooking}.

`mining` and `woodcutting` appear in BOTH enums — they cover extraction and the
first processing step alike — so `miner` owning `mining` covers ore through
bar, and `logger` owning `woodcutting` covers log through plank.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.tiers.skill_classes import (
    COMBAT_CRAFT_SKILLS,
    CONSUMABLE_CRAFT_SKILLS,
    GATHER_SKILLS,
)


@dataclass(frozen=True)
class Role:
    """One specialization. `gather` is None for a pure-consumer role. Pure data;
    exempt from one-class-per-file."""

    name: str
    gather: str | None
    craft: str


ROLE_CATALOG: tuple[Role, ...] = (
    Role(name="miner", gather="mining", craft="weaponcrafting"),
    Role(name="logger", gather="woodcutting", craft="gearcrafting"),
    Role(name="fisher", gather="fishing", craft="cooking"),
    # No gather skill: a pure consumer of banked bars. This role is the
    # clearest single signal that collusion is working — it CANNOT progress
    # without a sibling's deposit.
    Role(name="jeweler", gather=None, craft="jewelrycrafting"),
    Role(name="alchemist", gather="alchemy", craft="alchemy"),
)
"""Five roles covering all eight API skills, each owned exactly once."""


def role_skills(role: Role) -> frozenset[str]:
    """Every skill this role owns. `gather == craft` (alchemist) collapses."""
    if role.gather is None:
        return frozenset({role.craft})
    return frozenset({role.gather, role.craft})


def validate_catalog(catalog: tuple[Role, ...]) -> None:
    """Raise ValueError if any role names a skill outside the API-derived sets."""
    valid_gather = GATHER_SKILLS | CONSUMABLE_CRAFT_SKILLS
    valid_craft = COMBAT_CRAFT_SKILLS | CONSUMABLE_CRAFT_SKILLS | GATHER_SKILLS
    for role in catalog:
        if role.gather is not None and role.gather not in valid_gather:
            raise ValueError(
                f"Role {role.name!r} declares gather skill {role.gather!r}, "
                f"which is not an API gathering skill: {sorted(valid_gather)}"
            )
        if role.craft not in valid_craft:
            raise ValueError(
                f"Role {role.name!r} declares craft skill {role.craft!r}, "
                f"which is not an API craft skill: {sorted(valid_craft)}"
            )
