#!/bin/bash
uv run python -m src.cli.main --token-file=TOKEN $@ 2>&1 | tee session.log
