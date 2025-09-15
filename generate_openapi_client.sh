#!/bin/bash

# fetch the spec
curl -s https://api.artifactsmmo.com/openapi.json > openapi.json

# comment out inconvenient error-handling in openapi-python-client. the artifactsmmo openapi.json isn't fully
# conformant to the spec, so we have to remove a few safety checks to generate the client library
# cp .openapi_bugfixes/openapi.py ~/.virtualenvs/artifactsmmo/lib/python3.13/site-packages/openapi_python_client/parser/openapi.py
# cp .openapi_bugfixes/init.py ~/.virtualenvs/artifactsmmo/lib/python3.13/site-packages/openapi_python_client/parser/properties/__init__.py

# generate client
openapi-python-client generate --path openapi.json \
                               --overwrite \
                               --no-fail-on-warning \
                               --config openapi_client_config.yml
