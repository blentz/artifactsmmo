# ArtifactsMMO AI Player

An intelligent AI player for [ArtifactsMMO](https://artifactsmmo.com) that uses Goal-Oriented Action Planning (GOAP) to autonomously play the game through the API.

This project is being generated almost entirely by Claude Code. INcluding this README.md. AI-generated hallucinations
will be removed over the course of development, but may exist in the documentation while this project is under heavy
development.

## Overview

This project implements a sophisticated AI system that can:
- 🎯 **Autonomously plan and execute goals** using GOAP (Goal-Oriented Action Planning)
- ⚔️ **Combat intelligently** by learning from battles and selecting appropriate targets
- 🛠️ **Craft equipment** by analyzing recipes and gathering required materials
- 🗺️ **Explore the world** and build a knowledge base of discovered locations
- 📈 **Progress skills** through dynamic goal selection and task prioritization
- 🧠 **Learn from experience** and persist knowledge between sessions

## Features

### Intelligent Planning System
- **GOAP-based decision making** - The AI creates action plans to achieve goals
- **Dynamic replanning** - Adapts plans based on discoveries and failures
- **Priority-based goal selection** - Chooses appropriate goals based on character state

### Learning & Knowledge Management
- **Combat learning** - Tracks win rates and adapts target selection
- **Map exploration** - Remembers discovered locations and resources
- **Crafting knowledge** - Learns recipes and material requirements
- **Persistent storage** - All knowledge saved between sessions

### Modular Architecture
- **YAML-driven configuration** - Behavior defined through configuration files
- **Action-based system** - Modular actions that can be combined into complex behaviors
- **No hardcoded logic** - All game mechanics discovered through API

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/artifactsmmo.git
cd artifactsmmo
```

2. Set up Python environment (requires Python 3.13+):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Generate the API client:
```bash
./generate_openapi_client.sh
```

4. Configure your API token:
```bash
echo "YOUR_API_TOKEN" > TOKEN
```

## Usage

### Basic Usage

Run the AI player:
```bash
./run.sh
```

### Example Output

Here's what the AI player looks like in action:

```json
{"timestamp": "2025-07-01T04:23:10.252Z", "level": "INFO", "message": "🎯 Executing goal: bootstrap_character (priority: 90)"}
{"timestamp": "2025-07-01T04:23:10.253Z", "level": "INFO", "message": "📋 Created GOAP plan with 5 actions: evaluate_weapon_recipes → find_resources → gather_resources → craft_item → equip_item"}
{"timestamp": "2025-07-01T04:23:10.255Z", "level": "INFO", "message": "🔨 Evaluating 12 weapon recipes for character level 2"}
{"timestamp": "2025-07-01T04:23:10.256Z", "level": "INFO", "message": "Top weapon recipe candidates:"}
{"timestamp": "2025-07-01T04:23:10.256Z", "level": "INFO", "message": "1. Wooden Staff (score: 1250.0, completion: 90.0%) - [ash_wood: 9/6 ✓]"}
{"timestamp": "2025-07-01T04:23:10.257Z", "level": "INFO", "message": "2. Apprentice Gloves (score: 666.7, completion: 16.7%) - [feather: 1/6]"}
{"timestamp": "2025-07-01T04:23:10.258Z", "level": "INFO", "message": "🧠 Learned: Selected weapon wooden_staff for crafting"}
{"timestamp": "2025-07-01T04:23:15.432Z", "level": "INFO", "message": "🎯 Moving to workshop at (2, 1)"}
{"timestamp": "2025-07-01T04:23:18.765Z", "level": "INFO", "message": "🔨 Crafting wooden_staff..."}
{"timestamp": "2025-07-01T04:23:22.123Z", "level": "INFO", "message": "✅ Successfully crafted wooden_staff!"}
{"timestamp": "2025-07-01T04:23:25.456Z", "level": "INFO", "message": "🗡️ Equipped wooden_staff - Attack increased from 4 to 10"}
```

### Command Line Options

```bash
# Run with specific character
python -m src.main --character "YourCharacterName"

# Enable debug logging
python -m src.main --log-level DEBUG

# Run tests
python -m pytest
```

## Architecture

The AI player uses a modular, configuration-driven architecture:

```
artifactsmmo/
├── config/                 # YAML configuration files
│   ├── goal_templates.yaml # Goal definitions
│   ├── actions.yaml       # GOAP action configurations
│   └── state_engine.yaml  # State calculation rules
├── src/
│   ├── controller/        # Core AI logic
│   │   ├── actions/       # Modular action implementations
│   │   ├── ai_player_controller.py
│   │   └── goap_execution_manager.py
│   ├── game/              # Game state management
│   └── lib/               # Utilities and GOAP implementation
└── data/                  # Persistent knowledge storage
    ├── knowledge.yaml     # Combat and crafting data
    ├── map.yaml          # Explored locations
    └── world.yaml        # GOAP world state
```

## Key Concepts

### GOAP (Goal-Oriented Action Planning)
The AI uses GOAP to dynamically create action sequences:
1. **Current State** - Where the character is now
2. **Goal State** - What the AI wants to achieve
3. **Actions** - Available actions with preconditions and effects
4. **Planning** - Finding the optimal sequence of actions

### Action Context
Actions communicate through a shared context that persists throughout plan execution:
```python
# Actions can set results for subsequent actions
self._context.set_result('target_item', 'wooden_staff')
```

### Learning System
The AI learns from every action:
- **Combat results** → Adjusts monster targeting
- **Map exploration** → Remembers resource locations
- **Crafting attempts** → Tracks material requirements

## Configuration

### Goal Templates (`config/goal_templates.yaml`)
Define what the AI should achieve:
```yaml
bootstrap_character:
  description: "Equip basic gear and prepare for combat"
  target_state:
    has_better_weapon: true
    character_level: 3
    character_safe: true
  priority: 90
```

### Action Configurations (`config/action_configurations.yaml`)
Define available actions:
```yaml
evaluate_weapon_recipes:
  type: "builtin"
  description: "Analyze craftable weapons and select the best option"
  max_weapons_to_evaluate: 50
  weapon_stat_weights:
    attack: 10.0
    defense: 5.0
```

## Development

### Running Tests
```bash
# Run all tests
python -m unittest

# Run specific test module
python -m unittest test.controller.test_ai_player_controller -v
```

### Adding New Actions
1. Create action class in `src/controller/actions/`
2. Register in `config/action_configurations.yaml`
3. Define GOAP properties (conditions, reactions, weights)
4. Write tests

### Debugging
Monitor the AI's decision-making:
```bash
# Watch the session log
tail -f session.log | jq -r '"\(.timestamp) [\(.level)] \(.message)"'

# Check specific actions
cat session.log | jq 'select(.message | contains("craft"))'
```

## Contributing

See [CLAUDE.md](CLAUDE.md) for detailed development guidelines and architecture documentation.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [ArtifactsMMO](https://artifactsmmo.com) for the game and API
- The GOAP algorithm for intelligent action planning
- The Python community for excellent libraries
