"""Skill classification for ranking priors — the single source.

The base vocabulary is the API schema's `CraftSkill` / `GatheringSkill` enums.
The craft skills split into gear-producing ("combat craft": weapon/armor/jewelry)
and consumable-producing (the kitchen skills cooking/alchemy). That split sets
ranking-prior TIERS (see `tiers/strategy.py` PRIOR_* constants) and is a value
POLICY, not derivable from the enum names alone — but it reduces to ONE policy
seed, `_CONSUMABLE_KITCHEN` (which craft skills make consumables); the combat
and gather sets then fall out by set algebra against the enums, so they cannot
drift from the schema vocabulary and are defined in exactly one place.

This module exports two kinds of set, and callers must pick the right kind:

- `CRAFT_SKILLS` / `GATHERING_SKILLS` are the RAW schema vocabularies — every
  value the `CraftSkill` / `GatheringSkill` enums contain, with no policy
  applied. Use these when the question is "is this a real skill the server
  puts in this slot" (e.g. per-slot membership validation), since the three
  partitioned sets below reassign `alchemy`/`cooking` away from
  `GATHER_SKILLS`/into `CONSUMABLE_CRAFT_SKILLS` and so cannot answer that
  question for either slot on their own.
- `COMBAT_CRAFT_SKILLS` / `CONSUMABLE_CRAFT_SKILLS` / `GATHER_SKILLS` are the
  ranking-prior PARTITION described above — each of the eight skills belongs
  to exactly one of the three, valued by policy rather than raw enum
  membership. Use these for ranking priors and tier logic.

Leaf module (imports only the api-client enums) so both `strategy.py` and
`prerequisite_graph.py` import it without a tiers-package cycle.
"""

from artifactsmmo_api_client.models.craft_skill import CraftSkill
from artifactsmmo_api_client.models.gathering_skill import GatheringSkill

# Raw schema vocabularies: every value the API enums contain, undivided by
# policy. `mining`, `woodcutting`, and `alchemy` are members of BOTH sets
# (they cover extraction/gathering and a craft step alike) — that overlap is
# a real property of the schema, not an error.
CRAFT_SKILLS: frozenset[str] = frozenset(s.value for s in CraftSkill)
GATHERING_SKILLS: frozenset[str] = frozenset(s.value for s in GatheringSkill)

# POLICY SEED: the craft skills whose output is consumables (food/potions),
# valued as consumable-craft rather than combat-craft or raw gathering. The only
# hand-set member list; everything below is derived from it and the enums.
_CONSUMABLE_KITCHEN: frozenset[str] = frozenset({"alchemy", "cooking"})

# Craft skills that produce consumables (intersect the seed with real craft
# skills so a typo or a kitchen skill the schema lacks drops out).
CONSUMABLE_CRAFT_SKILLS: frozenset[str] = _CONSUMABLE_KITCHEN & CRAFT_SKILLS
# Craft skills that produce equippable combat gear (weapon/armor/jewelry): the
# craft skills that are neither gathering/processing skills nor the kitchen.
COMBAT_CRAFT_SKILLS: frozenset[str] = (
    CRAFT_SKILLS - GATHERING_SKILLS - CONSUMABLE_CRAFT_SKILLS
)
# Pure gather skills for ranking: gathering skills not valued as consumable-craft
# (alchemy both gathers and brews, and is valued as the latter).
GATHER_SKILLS: frozenset[str] = GATHERING_SKILLS - CONSUMABLE_CRAFT_SKILLS
