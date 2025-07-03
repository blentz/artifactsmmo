# ArtifactsMMO AI Player

A sophisticated AI that plays [ArtifactsMMO](https://artifactsmmo.com) autonomously using advanced planning algorithms and machine learning techniques. Watch as it explores, fights, crafts, and grows stronger - all while learning from every experience.

> **What makes this special?** Unlike simple bots that follow scripts, this AI actually *thinks* about what to do next. It uses Goal-Oriented Action Planning (GOAP) to create dynamic strategies, learns from successes and failures, and adapts its behavior over time.

## What This AI Can Do

Imagine an AI that doesn't just follow pre-written instructions, but actually makes decisions like a player would:

### 🎯 **Intelligent Planning**
The AI doesn't just randomly pick actions - it creates multi-step plans to achieve goals. Need better equipment? It will analyze available recipes, figure out what materials to gather, find the right workshop, and execute the entire crafting chain.

### ⚔️ **Adaptive Combat**
It learns which monsters it can defeat and which ones to avoid. After each battle, it updates its knowledge and gets better at choosing fights it can win.

### 🗺️ **Smart Exploration**
The AI remembers everywhere it's been and what it found there. It builds a mental map of the world and uses that knowledge to find resources and avoid wasting time.

### 🛠️ **Strategic Crafting**
When it needs equipment, the AI evaluates all possible recipes, considers what materials it has, and picks the most efficient path to upgrade its gear.

### 🧠 **Persistent Learning**
Every session builds on the last. The AI saves what it learns about monster locations, combat effectiveness, resource spots, and crafting chains.

## How It Works

### 🤖 **Goal-Oriented Action Planning (GOAP)**
Instead of following rigid scripts, the AI uses GOAP - the same technique used in advanced video game NPCs. It:
1. Looks at its current situation
2. Decides what it wants to achieve
3. Figures out the best sequence of actions to get there
4. Adapts when things don't go as planned

### 📊 **Real-Time Learning**
Every action teaches the AI something new:
- **Combat outcomes** help it choose better targets
- **Resource discoveries** improve exploration efficiency 
- **Crafting attempts** refine material planning
- **Failed plans** lead to smarter strategies

### ⚙️ **Configuration-Driven Behavior**
No hardcoded behaviors - everything is defined in human-readable YAML files:
- Goals and priorities
- Action definitions
- Learning parameters
- Combat strategies

## Quick Start

### Prerequisites
- Python 3.13 or newer
- An [ArtifactsMMO](https://artifactsmmo.com) account and API token
- Git (for cloning the repository)

### Setup (5 minutes)

1. **Get the code:**
```bash
git clone https://github.com/yourusername/artifactsmmo.git
cd artifactsmmo
```

2. **Set up Python environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Generate the API client:**
```bash
./generate_openapi_client.sh
```

4. **Add your API token:**
```bash
echo "YOUR_API_TOKEN" > TOKEN
```

5. **Start the AI:**
```bash
./run.sh
```

That's it! The AI will start playing immediately, beginning with basic character setup and equipment crafting.

## Watching the AI in Action

### Basic Operation

Just run the AI and watch it work:
```bash
./run.sh
```

The AI will automatically:
1. Assess its character's current state
2. Set appropriate goals (like "get better equipment")
3. Create and execute plans to achieve those goals
4. Learn from the results and adapt its strategies

### Example: Watching the AI Think

Here's what you'll see as the AI plans and executes a goal:

```
🎯 Goal selected: bootstrap_character (priority: 90)
📋 Planning: evaluate_weapon_recipes → find_resources → gather_resources → craft_item → equip_item

🔨 Analyzing 12 weapon recipes for level 2 character...
   1. Wooden Staff (score: 1250.0, feasibility: 90%) ✓ [ash_wood: 9/6 available]
   2. Apprentice Gloves (score: 666.7, feasibility: 17%) [feather: 1/6 needed]

🧠 Decision: Crafting wooden_staff (best combination of power and feasibility)
🎯 Moving to workshop at (2, 1)
🔨 Crafting wooden_staff...
✅ Success! Equipped wooden_staff - Attack: 4 → 10
```

Notice how the AI:
- Evaluated multiple options objectively
- Chose based on both effectiveness and feasibility
- Executed a multi-step plan
- Learned from the outcome

### Customization Options

```bash
# See detailed AI decision-making
python -m src.main --log-level DEBUG

# Start fresh (clear learned knowledge)
python -m src.main --clean

# Test a specific goal strategy
python -m src.main --goal-planner "level_10"

# Validate an action sequence
python -m src.main --evaluate-plan "find_monsters→attack→rest"

# Run system tests
python -m pytest
```

## Understanding the AI's Mind

### 🧠 **Knowledge Files** (`data/`)
The AI's "memory" - everything it learns is saved here:
- **`knowledge.yaml`** - Combat results, crafting discoveries, monster locations
- **`map.yaml`** - Explored areas and what was found there
- **`world.yaml`** - Current understanding of the game world

### ⚙️ **Configuration** (`config/`)
The AI's "personality" and behavior rules:
- **`goal_templates.yaml`** - What the AI wants to achieve and how
- **`action_configurations.yaml`** - Available actions and their parameters  
- **`actions.yaml`** - GOAP rules for when actions can be used

### 🤖 **AI Brain** (`src/controller/`)
- **`ai_player_controller.py`** - Main AI coordination
- **`goap_execution_manager.py`** - Planning and strategy
- **`actions/`** - Individual skills (fighting, crafting, exploring)

### 📊 **Progress Tracking**
Watch the AI learn in real-time:
```bash
# See what the AI has discovered
cat data/knowledge.yaml | head -20

# Check its exploration progress  
cat data/map.yaml | grep -c "content"

# Monitor decision-making
tail -f session.log
```

## What Makes This AI Special?

### 🎯 **Genuine Intelligence**
Most game bots follow pre-written scripts. This AI actually *plans*:

**Example:** Need better equipment?
- **Simple bot:** "Go to location X, kill monster Y, repeat"
- **This AI:** "I need better gear. Let me check what I can craft with my current materials. Wooden staff looks good - I have most materials. I need 3 more ash wood. I remember seeing ash trees near (5,7). Let me go there, gather what I need, find a workshop, and craft it."

### 🧠 **Continuous Learning**
The AI gets smarter over time:
- Remembers which monsters it can beat at each level
- Learns optimal resource gathering routes
- Discovers the most efficient crafting chains
- Builds a mental map of the entire game world

### ⚡ **Dynamic Adaptation**
No situation is exactly the same:
- Plans change when resources aren't where expected
- Strategies adapt when combat doesn't go as planned
- New goals emerge based on discoveries and opportunities

## Customizing the AI

### 🎯 **Changing Goals**
Edit `config/goal_templates.yaml` to modify what the AI prioritizes:
```yaml
# Make the AI focus on combat
combat_focused:
  description: "Become a fighting machine"
  target_state:
    character_level: 20
    has_better_weapon: true
  priority: 95

# Or make it a crafting specialist
crafting_focused:
  description: "Master all crafting skills"
  target_state:
    weaponcrafting_skill: 15
    gearcrafting_skill: 15
  priority: 90
```

### ⚙️ **Tuning Behavior**
Adjust `config/action_configurations.yaml` to change how the AI acts:
```yaml
# Make the AI more aggressive in combat
fight:
  min_hp_percentage: 30  # Fight even when lower on health
  level_range: 3         # Fight monsters up to 3 levels higher

# Or make it more cautious
fight:
  min_hp_percentage: 80  # Only fight when nearly full health
  level_range: 1         # Only fight monsters at similar level
```

## For Developers

### 🔍 **Understanding the Code**
Start with these key files:
- `CLAUDE.md` - Complete architecture documentation
- `src/controller/ai_player_controller.py` - Main AI logic
- `src/lib/goap.py` - Planning algorithm implementation

### 🧪 **Testing**
```bash
# Run all tests (must pass before changes)
python -m pytest

# Test specific functionality  
python -m pytest test/controller/test_ai_player_controller.py -v

# Integration test (run AI for 30 seconds)
./run.sh
```

### 🐛 **Debugging AI Decisions**
```bash
# See detailed planning process
python -m src.main --log-level DEBUG

# Test planning without execution
python -m src.main --goal-planner "bootstrap_character"

# Validate action sequences
python -m src.main --evaluate-plan "scan→move→gather_resources"

# Monitor real-time decisions
tail -f session.log | jq -r '.message'
```

### ➕ **Adding New Capabilities**
1. **Create the action** in `src/controller/actions/`
2. **Register it** in `config/action_configurations.yaml`
3. **Define GOAP rules** in `config/actions.yaml`
4. **Write tests** to ensure it works
5. **Test integration** with existing behaviors

## Get Involved

### 🤝 **Contributing**
Want to make the AI smarter? Check out [CLAUDE.md](CLAUDE.md) for:
- Complete architecture documentation
- Development guidelines and patterns
- How to add new AI behaviors
- Testing and debugging strategies

### 📞 **Support & Community**
- **Issues:** Found a bug or have a feature request? [Open an issue](../../issues)
- **Documentation:** Everything you need is in [CLAUDE.md](CLAUDE.md)
- **Examples:** Check the `test/` directory for usage examples

### 🎮 **Try ArtifactsMMO**
New to the game? [ArtifactsMMO](https://artifactsmmo.com) is a fascinating MMO designed for automation and AI experimentation. Create an account and get your API token to start experimenting!

---

## License

This project is licensed under the **GNU Affero General Public License v3** (AGPL-3.0) - see [LICENSE](LICENSE) for details.

The AGPL ensures that any modifications to this AI, including those used to provide network services, remain open source and available to the community.

## Credits

- **[ArtifactsMMO](https://artifactsmmo.com)** - The game that makes this AI possible
- **GOAP Algorithm** - Enabling truly intelligent behavior
- **Python Community** - For the excellent tools and libraries
- **Contributors** - Everyone who helps make this AI smarter

---

*Watch an AI learn to play a game, one decision at a time.* 🤖