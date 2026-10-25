"""Named specialization roles.

A role is a STRATEGY declaration, the same category of thing as
`loadout_profiles` — not a classification derived from API data, so the
"generic over API taxonomy, never hardcoded" rule (which governs item keep/junk
classification) does not apply. What DOES apply is that a role must not name a
skill the server lacks: `validate_catalog` checks every declared skill against
the api-client-derived sets in `tiers/skill_classes.py` and raises rather than
silently no-opping, per "use only API data or fail with an error".

`skill_classes` exports the RAW schema vocabularies `GATHERING_SKILLS` /
`CRAFT_SKILLS` (every value of the `GatheringSkill` / `CraftSkill` enums,
undivided by policy) alongside a separate ranking-prior PARTITION
(`GATHER_SKILLS` / `COMBAT_CRAFT_SKILLS` / `CONSUMABLE_CRAFT_SKILLS`).
`validate_catalog` below checks each role's `gather` against
`GATHERING_SKILLS` and `craft` against `CRAFT_SKILLS` — the raw vocabularies,
not the partition — because the partition reassigns `alchemy`/`cooking` out
of gathering to value them as consumable-craft, so it cannot answer "is this
a real skill the server puts in this slot" for either slot on its own (it
would wrongly accept a role declaring `craft="fishing"`, since the partition
folds `fishing` into `GATHER_SKILLS`). This module's only hand-authored
content is the PAIRING of skills into roles.

Verified against the api-client enums 2026-08-01:
  GatheringSkill = {alchemy, fishing, mining, woodcutting}
  CraftSkill     = {alchemy, cooking, gearcrafting, jewelrycrafting, mining,
                    weaponcrafting, woodcutting}

`mining` and `woodcutting` appear in BOTH enums — they cover extraction and the
first processing step alike — so `miner` owning `mining` covers ore through
bar, and `logger` owning `woodcutting` covers log through plank. `alchemy` also
appears in both, which is what lets `alchemist` declare `gather="alchemy",
craft="alchemy"`.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from artifactsmmo_cli.ai.tiers.skill_classes import CRAFT_SKILLS, GATHERING_SKILLS


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

ROLES_BY_NAME: dict[str, Role] = {role.name: role for role in ROLE_CATALOG}
"""Name lookup over `ROLE_CATALOG`. Names are unique by construction (each of
the eight API skills is owned exactly once), so this loses nothing."""


def role_skills(role: Role) -> frozenset[str]:
    """Every skill this role owns. `gather == craft` (alchemist) collapses."""
    if role.gather is None:
        return frozenset({role.craft})
    return frozenset({role.gather, role.craft})


def role_skill_level(role: Role, skill_levels: Mapping[str, int]) -> int:
    """The character's BEST level among the skills this role owns.

    Max rather than min or mean: a role is served by producing what a sibling
    asked for, and any one of the role's owned skills can be the producer (the
    `miner` role serves a copper_ore request from `mining` alone). A character
    deep in one of a role's skills is genuinely suited to it even if the other
    is untouched.

    A skill absent from `skill_levels` reads as 0, NOT as the API's level-1
    floor: absence means the caller had no reading for it, and treating "no
    data" as "the starting level" would make an unknown skill look equal to a
    genuinely untrained one. `role_skills` is never empty, so the max is always
    over at least one entry."""
    return max(skill_levels.get(skill, 0) for skill in role_skills(role))


def validate_catalog(catalog: tuple[Role, ...]) -> None:
    """Raise ValueError if any role names a skill outside the API-derived sets.

    Validated against the RAW schema vocabularies (`GATHERING_SKILLS` /
    `CRAFT_SKILLS`), not the ranking-prior partition — the partition
    reassigns `alchemy`/`cooking` out of gathering, so it cannot express true
    per-slot membership (e.g. it would wrongly accept `craft="fishing"`).
    """
    for role in catalog:
        if role.gather is not None and role.gather not in GATHERING_SKILLS:
            raise ValueError(
                f"Role {role.name!r} declares gather skill {role.gather!r}, "
                f"which is not an API gathering skill: {sorted(GATHERING_SKILLS)}"
            )
        if role.craft not in CRAFT_SKILLS:
            raise ValueError(
                f"Role {role.name!r} declares craft skill {role.craft!r}, "
                f"which is not an API craft skill: {sorted(CRAFT_SKILLS)}"
            )
