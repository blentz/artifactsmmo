#!/bin/bash
set -e

# fetch the spec
curl -s https://api.artifactsmmo.com/openapi.json > openapi.json

# patch non-conformant parts of the spec before generation:
#
# 1. POST /my/{name}/action/fight has an inline request body schema that uses allOf+$ref
#    with a top-level "default" object. openapi-python-client resolves this to a ModelProperty
#    and ModelProperty.convert_value() rejects any non-null default. The default is redundant
#    since FightRequestSchema.participants already declares "default": [] at the property level.
#    Fix: simplify the inline schema to a plain $ref.
python3 - <<'EOF'
import json

with open("openapi.json") as f:
    spec = json.load(f)

# Patch 1: POST /my/{name}/action/fight request body has an inline allOf+$ref schema
# with a top-level "default" object. openapi-python-client rejects defaults on ModelProperty.
# The default is redundant — FightRequestSchema.participants already has default:[].
# Fix: collapse to a plain $ref and drop the invalid default.
fight_post = spec["paths"]["/my/{name}/action/fight"]["post"]
rb_schema = fight_post["requestBody"]["content"]["application/json"]["schema"]
if "allOf" in rb_schema and len(rb_schema["allOf"]) == 1 and "$ref" in rb_schema["allOf"][0]:
    rb_schema["$ref"] = rb_schema["allOf"][0]["$ref"]
    del rb_schema["allOf"]
rb_schema.pop("default", None)

# Patch 2: OpenAPI 3.0 forbids sibling keywords next to $ref, so "nullable: true" beside
# a $ref is ignored by openapi-python-client and produces non-null-safe from_dict code.
# Fix: rewrite every {$ref, nullable:true} property to anyOf:[{$ref},{type:null}], which
# the generator correctly resolves to Optional[T] with a None guard in from_dict.
def fix_nullable_refs(obj):
    if not isinstance(obj, dict):
        return
    for key, val in list(obj.items()):
        if isinstance(val, dict):
            if "$ref" in val and val.get("nullable") is True:
                siblings = {k: v for k, v in val.items() if k not in ("$ref", "nullable")}
                obj[key] = {"anyOf": [{"$ref": val["$ref"]}, {"type": "null"}], **siblings}
            else:
                fix_nullable_refs(val)
        elif isinstance(val, list):
            for item in val:
                fix_nullable_refs(item)

fix_nullable_refs(spec)

with open("openapi.json", "w") as f:
    json.dump(spec, f, indent=2)

print("openapi.json patched OK")
EOF

# generate client
# openapi_templates/ overrides types.py.jinja to use X | Y union syntax instead of
# Union[X, Y], which the upstream template emits and ruff's UP007 rule rejects.
openapi-python-client generate --path openapi.json \
                               --overwrite \
                               --no-fail-on-warning \
                               --custom-template-path openapi_templates \
                               --config openapi_client_config.yml

# Post-process: replace standard HTTPStatus with GameHTTPStatus in all API files.
# HTTPStatus rejects non-IANA codes like 499 (cooldown) that the game API returns.
find artifactsmmo-api-client/artifactsmmo_api_client/api -name "*.py" \
  -exec grep -l "HTTPStatus(response.status_code)" {} \; | \
xargs sed -i \
  -e 's/^from http import HTTPStatus$/from ...types import GameHTTPStatus/' \
  -e 's/HTTPStatus(response\.status_code)/GameHTTPStatus(response.status_code)/g'

echo "Post-processing complete: GameHTTPStatus applied to all API files"
