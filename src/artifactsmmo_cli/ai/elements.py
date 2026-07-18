"""The combat element vocabulary, DERIVED from the API schema (not hard-coded).

The server models damage/resistance per element as `attack_<elem>` /
`res_<elem>` fields on every monster and item schema. We read the element names
straight off the generated `MonsterSchema` attribute list, so the vocabulary is
the schema's — a new element the server adds appears here on client regen
instead of being silently ignored by every scoring loop. Previously this tuple
was hand-typed in three places (`equipment/elements.py`, `world_state.py`,
inline in `game_data.py`), which guaranteed drift.

Kept a LEAF module (only `attrs` + the api-client schema) so the base modules
`world_state` and `game_data` can import it without an equipment-package cycle.
The order is the schema's field-definition order — currently
`("fire", "earth", "water", "air")` — and is consumed identically by the impl
and the differential harness, so the element→index mapping stays consistent.
"""

import attrs
from artifactsmmo_api_client.models.monster_schema import MonsterSchema

_ATTACK_PREFIX = "attack_"

ELEMENTS: tuple[str, ...] = tuple(
    field.name[len(_ATTACK_PREFIX):]
    for field in attrs.fields(MonsterSchema)
    if field.name.startswith(_ATTACK_PREFIX)
)
