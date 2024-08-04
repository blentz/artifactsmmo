#!/bin/bash

export access_token=$(cat TOKEN)

/usr/bin/env python3 src/main.py
