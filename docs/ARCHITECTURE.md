# ArtifactsMMO AI Player - Architecture Document

## Executive Summary

This document defines the comprehensive architecture for an intelligent AI player system for ArtifactsMMO, designed with modularity, testability, and scalability as core principles. The architecture employs a layered approach with clear separation of concerns, supporting 100% test coverage and modern Python development practices.

## System Overview

The ArtifactsMMO AI Player is an autonomous agent that plays the ArtifactsMMO game through its REST API, making intelligent decisions about character actions, resource management, combat, crafting, and economic activities. The system uses Goal-Oriented Action Planning (GOAP) for decision-making and maintains comprehensive knowledge of the game world.

## Technology Stack

- **Language**: Python 3.13
- **Dependency Management**: uv
- **Linting**: ruff
- **Testing**: pytest with pytest-cov
- **API Client**: ArtifactsMMO OpenAPI-generated client (`./artifactsmmo-api-client/`)
- **Data Validation**: Pydantic
- **Game API Data Caching**: JSON file-based
- **CLI Framework**: Click or Typer for command-line interface
- **Async Framework**: asyncio
