#!/bin/bash

# fetch the spec
curl -s https://api.artifactsmmo.com/openapi.json > openapi.json

# changes=""
# 
# # rewrite the operationId, removing redundant or unnecessary information
# for x in $(jq -r 'path(..) | select(contains(["operationId"])) | map(if type == "string" then ".\(.)" else "[\(.)]" end)| join("")' openapi.json | awk -F "." '{print "."$2".""\042"$3"\042""."$4"."$5}')
# do
#     declare -A words=()
#     index=0
# 
#     for i in $(jq -r $x openapi.json | \
#                 sed 's/__/_/g' | \
#                 sed 's/_code//' | \
#                 sed 's/_get\|_post$//' |\
#                 tr "_" ' ')
#     do
#         if [ ${#words[@]} -gt 0 ] && [ $(echo "${!words[@]}" | grep -c $i) -gt 0 ]; then
#             continue # skip repeats
#         fi
# 
#         if [ "$(echo $i | grep -c -e 's$')" == "1" ] && [ $i != "status" ]; then
#             words[$(echo "$i" | sed 's/s$//g')]=$index
#         else
#             words[$(echo "$i")]=$index
#         fi
#         index=$(echo "${index}+1" | bc)
#     done
# 
#     ordered=()
#     for i in ${!words[@]}; do
#         ordered[${words["$i"]}]=$i
#     done
# 
#     updated_opid=$(echo ${ordered[@]} | tr ' ' '_')
#     if [ "$updated_opid" == "get_status" ]; then
#         # last entry
#         changes+="$x |= \"$updated_opid\""
#     else
#         changes+="$x |= \"$updated_opid\" | "
#     fi
# done
# 
# jq -c -r "$changes" openapi.json > updated_openapi.json
# mv updated_openapi.json openapi.json
# 
# # bugfixes
# sed -i 's/NPCs/NPCS/g' openapi.json

# comment out inconvenient error-handling.
cp .openapi_bugfixes/openapi.py ~/.virtualenvs/artifactsmmo/lib/python3.13/site-packages/openapi_python_client/parser/openapi.py
cp .openapi_bugfixes/init.py ~/.virtualenvs/artifactsmmo/lib/python3.13/site-packages/openapi_python_client/parser/properties/__init__.py

# generate client
openapi-python-client generate --path openapi.json \
                               --overwrite \
                               --no-fail-on-warning \
                               --config openapi_client_config.yml
