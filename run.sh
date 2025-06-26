#!/bin/bash

export TOKEN=$(cat TOKEN)

# Activate the virtual environment
source $(which virtualenvwrapper.sh)
workon artifactsmmo

/usr/bin/env python3 -m src.main 2>&1 | tee session.log
