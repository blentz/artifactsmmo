# PLAN #6: low-value modeling bundle

**Priority:** 6 (per user ordering, before #5/#4/#2). **Status:** planned.
Three small, independent items. Each cheap; none touches the proven combat core.

## 6a. Strategic consumable supply (cooking/alchemy)

**Now:** the bot EATS food if present (UseConsumable for sustain) and levels
cooking/alchemy as skills, but does not STRATEGICALLY cook/brew to keep a heal
stockpile — it falls back to Rest (slow; the trace showed ~50% combat overhead is
rest). **Fix:** a goal/heuristic to maintain a minimum heal-consumable inventory
(cook food / brew potions) when below a threshold and combat is the active means, so
the bot rests less. Scope: a `MaintainConsumables`-style discretionary goal gated on
(combat-active ∧ heal-stock < floor ∧ cooking-skill-can-make-a-better-heal). Reuses
crafting + consumable_selection. No proven-core change. Verify it doesn't loop with
DiscardOverstock (heal items must be in the keep-set — they are, CONSUMABLE_KEEP=999).

## 6b. Teleport / fast-travel consumables

`teleport` (forest_bank_potion → map 955) is a consumable that warps. The bot walks
maps (movement/transition). **Fix:** when a teleport item targets a useful
destination (a bank, a needed resource/monster map) and is cheaper (in cooldown/
distance) than walking, prefer using it. Scope: a movement-cost comparison in the
path/transition layer (calculate_path is proven; teleport is an alternative edge).
Low value (only one teleport item seen; saves a few cooldowns). Likely DEFER unless
travel time proves a real bottleneck in a trace.

## 6c. `threat` stat

Aggro/taunt (amulet_of_the_grand_master +10). Irrelevant for a SOLO bot (no allies to
pull aggro from). **Decision: do not model.** Record as a deliberate carve-out so the
parser-coverage guard (see roadmap) doesn't flag it. If multi-character/party play is
ever added, revisit.

## Sequencing
6a (consumable supply — real throughput win, cheap) → 6b (teleport, likely defer) →
6c (threat — carve-out only). Only 6a is worth building now; 6b/6c are
record-and-defer.
