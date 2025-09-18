# Current Status - ArtifactsMMO CLI

## Character Progress
- **Character**: IglxCnzc
- **Level**: 4 (112/450 XP)
- **Equipment**: wooden_stick (severe bottleneck)
- **Issue**: Death loop due to poor equipment causing 58-second cooldowns

## Proposed CLI Features to Improve Gameplay

### 1. Combat Prediction Commands
```bash
# Simulate fight outcome BEFORE engaging
uv run python -m artifactsmmo_cli.main combat simulate IglxCnzc chicken
> Win Probability: 95%
> Expected HP Loss: 56 (36%)
> Time to Kill: 8 rounds
> Expected XP/minute: 72
> Death Risk: LOW

# Compare multiple monsters at once
uv run python -m artifactsmmo_cli.main combat compare IglxCnzc
> Chicken: 95% win, 72 XP/min, LOW risk
> Slime: 45% win, 120 XP/min, HIGH risk ⚠️
> Wolf: 5% win, 180 XP/min, EXTREME risk ❌
```

### 2. Equipment Upgrade Advisor
```bash
# Show what equipment to get next
uv run python -m artifactsmmo_cli.main equipment suggest IglxCnzc
> Current: wooden_stick (4 attack)
> Recommended: copper_dagger (12 attack) - 3x damage!
> How to get:
>   - Craft: Need 8 copper_ore (you have 15 ✓)
>   - Buy: 250g on Grand Exchange
>   - Location: Weaponcraft Workshop (1, 3)
> Impact: Reduce chicken fight time by 65%
```

### 3. Optimal Path Calculator
```bash
# Multi-step planning with efficiency metrics
uv run python -m artifactsmmo_cli.main plan level10 IglxCnzc
> Optimal Path to Level 10:
> 1. Craft copper_dagger at (1,3) [20 min]
> 2. Farm chickens to level 5 [2 hours]
> 3. Craft iron_sword at (2,3) [30 min]
> 4. Farm wolves to level 8 [3 hours]
> 5. Complete grand_quest [1 hour]
> Total time: 6.8 hours
> Current approach time: 48+ hours ⚠️
```

### 4. Auto-Recovery System
```bash
# Automatically handle deaths and recovery
uv run python -m artifactsmmo_cli.main auto farm IglxCnzc chickens \
  --auto-rest-at 30% \
  --auto-bank-when-full \
  --stop-on-death false \
  --target-level 10
```

### 5. Efficiency Dashboard
```bash
# Real-time efficiency metrics
uv run python -m artifactsmmo_cli.main stats efficiency IglxCnzc --last 1h
> === Last Hour Performance ===
> XP Gained: 450 (7.5 XP/min)
> Deaths: 4 (3.9 min cooldown penalty)
> Efficiency: 23% (death penalties costing 77% of time!)
> Bottleneck: Poor equipment causing deaths
> Recommendation: STOP! Upgrade equipment first!
```

### 6. Smart Task Selection
```bash
# Evaluate task efficiency before accepting
uv run python -m artifactsmmo_cli.main task evaluate IglxCnzc
> Available Tasks:
> 1. Kill 153 chickens
>    Time: 4.2 hours
>    XP/hour: 95
>    Rating: ⭐⭐ (POOR - too many for low XP)
>
> 2. Gather 20 copper
>    Time: 20 min
>    XP/hour: 450
>    Rating: ⭐⭐⭐⭐⭐ (EXCELLENT)
```

### 7. Market Intelligence
```bash
# Find equipment upgrade opportunities
uv run python -m artifactsmmo_cli.main market scout IglxCnzc
> Your gold: 143
> Affordable upgrades:
> - leather_helmet: 89g (↑5 defense) - BUY NOW
> - copper_ring: 134g (↑2 attack) - WORTH IT
> Items to sell:
> - ruby_stone: 45g each (not needed until level 15)
```

### 8. Batch Operation Planner
```bash
# Queue up actions to minimize clicking
uv run python -m artifactsmmo_cli.main batch create
  goto 2 0
  gather --count 10
  goto 1 3
  craft copper_dagger 1
  equip copper_dagger weapon
  goto 0 1
  fight --until-level 5
> Estimated time: 3.5 hours
> Execute? [y/n]
```

### 9. Death Prevention Warnings
```bash
# Alert BEFORE engaging in risky combat
uv run python -m artifactsmmo_cli.main action fight IglxCnzc
> ⚠️ WARNING: High death risk!
> Monster: chicken
> Your HP: 94/150 (63%)
> Expected damage: 56
> Survival chance: 45%
> Recommendation: Rest first or skip
> Proceed anyway? [y/n]
```

### 10. Progress Tracking
```bash
# See realistic time estimates
uv run python -m artifactsmmo_cli.main progress IglxCnzc
> Level 4 (112/450) → Level 10
> At current rate (4.2 XP/min with 23% uptime):
> - Time to level 5: 1.3 hours
> - Time to level 10: 47 hours ⚠️
>
> With copper_dagger (projected):
> - Time to level 10: 8 hours ✓
```

### 11. Smart Cooldown Handler
```bash
# Use cooldowns productively
uv run python -m artifactsmmo_cli.main smart wait IglxCnzc
> Cooldown: 52s remaining (death penalty)
> Meanwhile, I'll:
> - Check market prices
> - Calculate optimal next moves
> - Update efficiency stats
> Ready in: 47s...
```

### 12. Equipment Comparison Matrix
```bash
uv run python -m artifactsmmo_cli.main equipment compare IglxCnzc
> Current vs Available:
>                  Now → Copper → Iron
> Weapon Attack:    4  →   12  →  22
> Kill Speed:      8s →    3s →   2s
> Deaths/hour:      4 →     1 →   0
> XP/hour (real):  95 →   380 → 620
```

## Core Issue
The current CLI requires too much game knowledge and manual calculation. These features would provide the intelligence layer needed to make optimal decisions, especially for equipment progression which is the critical bottleneck in early game efficiency.

## Key Insights from Testing
1. **Equipment > Levels** - Better gear prevents death loops
2. **Death penalty kills efficiency** - 58s cooldowns are devastating
3. **Task rewards matter** - Bonus XP can double progression
4. **Market shortcuts exist** - Buying gear can save hours
5. **Combat math is critical** - Need to predict fight outcomes