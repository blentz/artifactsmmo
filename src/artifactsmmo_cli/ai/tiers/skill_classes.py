"""Skill classification for ranking priors — the single source.

The base vocabulary is the API schema's `CraftSkill` / `GatheringSkill` enums.
The craft skills split into gear-producing ("combat craft": weapon/armor/jewelry)
and consumable-producing (the kitchen skills cooking/alchemy). That split sets
ranking-prior TIERS (see `tiers/strategy.py` PRIOR_* constants) and is a value
POLICY, not derivable from the enum names alone — but it reduces to ONE policy
seed, `_CONSUMABLE_KITCHEN` (which craft skills make consumables); the combat
and gather sets then fall out by set algebra against the enums, so they cannot
drift from the schema vocabulary and are defined in exactly one place.

Leaf module (imports only the api-client enums) so both `strategy.py` and
`prerequisite_graph.py` import it without a tiers-package cycle.
"""

from artifactsmmo_api_client.models.craft_skill import CraftSkill
from artifactsmmo_api_client.models.gathering_skill import GatheringSkill

_CRAFT: frozenset[str] = frozenset(s.value for s in CraftSkill)
_GATHER: frozenset[str] = frozenset(s.value for s in GatheringSkill)

# POLICY SEED: the craft skills whose output is consumables (food/potions),
# valued as consumable-craft rather than combat-craft or raw gathering. The only
# hand-set member list; everything below is derived from it and the enums.
_CONSUMABLE_KITCHEN: frozenset[str] = frozenset({"alchemy", "cooking"})

# Craft skills that produce consumables (intersect the seed with real craft
# skills so a typo or a kitchen skill the schema lacks drops out).
CONSUMABLE_CRAFT_SKILLS: frozenset[str] = _CONSUMABLE_KITCHEN & _CRAFT
# Craft skills that produce equippable combat gear (weapon/armor/jewelry): the
# craft skills that are neither gathering/processing skills nor the kitchen.
COMBAT_CRAFT_SKILLS: frozenset[str] = _CRAFT - _GATHER - CONSUMABLE_CRAFT_SKILLS
# Pure gather skills for ranking: gathering skills not valued as consumable-craft
# (alchemy both gathers and brews, and is valued as the latter).
GATHER_SKILLS: frozenset[str] = _GATHER - CONSUMABLE_CRAFT_SKILLS
