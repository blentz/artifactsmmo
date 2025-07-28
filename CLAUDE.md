# Claude.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **artifactsmmo AI player** project - an AI player for operating a character in a role-playing game through an API. Uses Python 3.13.

## Reasoning Guidelines

- Always use @sentient-agi-reasoning when thinking about complex problems.
- For large or complex tasks, use an iterative approach across multiple sessions. Break complex tasks up into smaller tasks. Write your plans to `docs/plans/PLAN_{feature_name}.md` for future sessions to iterate on.

## Programming Guidelines

- DO use `uv` to manage virtualenvs and dependencies.
- ALWAYS prefix Python commands with `uv run` to ensure virtualenv is active (e.g., `uv run python`, `uv run pytest`, `uv run mypy`).

- DO NOT use inline imports. Always put imports at the top of the file.
- DO NOT create "simple" tests; use the test suite.
- **ONE CLASS PER FILE**: Each Python file should contain only one class definition. This improves code organization, makes imports cleaner, and follows standard Python conventions.

## Testing Guidelines

- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- Put all tests in the tests/ directory.

## Antipatterns to avoid
- DO NOT use print statements to report fake success. Fix the errors you see.
- DO NOT simplify problems. Stop working and ask the user for clarification or directions instead.
