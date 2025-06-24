# Claude.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **artifactsmmo AI player** project. This project is an AI player used for operating a character in a role-playing game played through an API. This is a python v3.13 project.

## Development Commands

### Build & Development
- `workon artifactsmmo` - Enable python virtualenv.
- `deactivate artifactsmmo` - Disable python virtualenv
- `generate_openapi_client.sh` - Generate API Client files

### Testing
- `python -m unittest` - Run basic unit tests

### Code Quality
- `pylint` - Run Pylint

### Execution
- `run.sh` - Run application. This command can only be used after all unit tests pass with no errors.

## Architecture

### Core Components

**Core application** (`src/`):
- `main.py` - Application entrypoint

**Controller** (`src/controller/`):
- `actions/` - Actions related to GOAP
- `states/` - States related to GOAP
- `world/` - World classes related to GOAP
- `ai_player_controller.py` - AI Player controller

**Game state** (`src/game/`):
- `character/` - Character state
- `map/` - Map state

**Libraries** (`src/lib/`):
- `goap.py` - Goal-oriented Action Planner base library ("GOAP")
- `goap_data.py` - YAML-backed state storage for Goal-oriented Action Planner base library
- `httpstatus.py` - Custom HTTP status codes used by the ArtifactsMMO API
- `log.py` - Logging facilities
- `yaml_data.py` - YAML-backed file storage

**ArtifactsMMO API Client Library** (`artifactsmmo-api-client/`):
- `artifactsmmo-api-client/` - API Client library files for connecting to the ArtifactsMMO API

### Key Design Patterns

1. **MVC Architecture**: All capabilities are implemented using the Model-View-Controller pattern

## Development Notes

- The system uses Python 3 with type checking. 
- The virtualenv must be enabled before running any python commands.

## Testing Philosophy

- Tests should validate functional correctness based on APIs presented by client library.
- There should be at least one test for every code path.
- All tests should be created under the `test/` directory. 