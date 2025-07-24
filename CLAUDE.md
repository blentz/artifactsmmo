# Claude.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **artifactsmmo AI player** project - an AI player for operating a character in a role-playing game through an API. Uses Python 3.13.

## Reasoning Guidelines

- Always use @sentient-agi-reasoning when thinking about complex problems.

## Programming Guidelines

- DO use `uv` to manage virtualenvs and dependencies.
- ALWAYS prefix Python commands with `uv run` to ensure virtualenv is active (e.g., `uv run python`, `uv run pytest`, `uv run mypy`).

- DO NOT use inline imports for any reason.

## Testing Guidelines

- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.

## Antipatterns to avoid
- DO NOT use print statements to fake success. Fix the errors you see.
- DO NOT simplify problems. Ask the user for clarification or directions instead.
- DO NOT prioritize speed or time. Stop working when your context is 95% full and request user intervention.
