# PLAN: group (multi-character) boss fights

USER 2026-10-10: "scope the group fight feature as a plan". Prompted by the
conditions census (docs/PLAN_drop_fight_loadout.md): 7 recipes plan only when
handed duskworm's drops, because duskworm is a `boss` no single character beats
— and the bot only ever fights alone.

## Evidence

- duskworm (`boss`, event `out_of_the_ground`): 25,000 HP, 550 water attack a
  turn, initiative 600, `void_drain` 10 (every 4 turns drains 10% HP from EACH
  enemy), `lifesteal` 25. The best level-60 catalogue loadout (1,935 HP) needs
  39 turns to kill it and dies in 4; no stockable potion closes it.
- Recipes it walls: adamantite_ring, adamantite_sword, dust_amulet, dust_sword,
  eternal_red_ring, heart_amulet, desert_whip (duskworm_skin /
  adventurer_skull).
- Bosses in the catalogue: king_slime 15, lich 30, goblin_priestess 35,
  rosenblood 40, duskworm 48, sandwhisper_empress 55 (`boss`); pixie 40,
  sonnengott 55 (`raid_boss`). Several are beaten solo today; a group widens
  that set and pays the boss XP multiplier (×2).

## Server rules (docs.artifactsmmo.com/concepts/stats_and_fights, changelog 6.0.0)

1. Up to 2 other characters of the SAME account join (`participants` on
   `POST /my/{name}/action/fight`, max 2 names), 3 total, only against `boss`
   and `raid_boss`. All participants must be on the same map.
2. A normal boss fight grants XP, gold and drops to EACH participant
   independently (`CharacterMultiFightResultSchema`: per-character xp, gold,
   drops, final_hp). Raid fights use the raid reward system.
3. XP uses the group's average level (floored) for the base and the level
   penalty; each character's own wisdom applies after.
4. Turn order by initiative (ties: higher HP, then random).
5. Targeting: the monster hits the highest-THREAT character 90% of the time,
   the lowest-HP character 10%; ties by lowest HP, then random.
6. `void_drain` hits each enemy; area effects scale with party size.

Unknown (must be measured, not assumed — Increment 0):
- whether every participant takes the fight cooldown, and how long;
- whether a dead participant leaves the fight (win if any survivor kills it?);
- whether a participant in cooldown, or not on the map, fails the whole request
  (and with which HTTP code);
- how the leader's response reports the others' state.

## What the code assumes today

- `FightAction` sends no `participants`; every fight model (`combat_terms`,
  `fight_terms_core`, `fight_outcome_core`, Lean `Formal.PredictWin` /
  `Formal.FightOutcome`) is one player against one monster.
- `threat` is parsed and deliberately carved out as solo-inert
  (`game_data.py:2139`).
- The drop gate, the band target and the census all judge a fight as solo.
- Characters run as separate players; fleet coordination exists only through
  claim tables in learning.db (supply claims, turn-in claims, role leases).

## Increments

0. **Mechanics, from data.** A supervised live probe (fleet stopped, two
   characters, king_slime — the cheapest boss): one group fight, then record
   each participant's cooldown, final_hp, drops and XP from the response and
   the character reads; one deliberate failure each for "not on the map" and
   "in cooldown". Every unknown above settled with its evidence. Needs your
   go-ahead (live actions on two characters).
1. **Group fight model.** Pure core + Lean: the turn walk generalised to N ≤ 3
   players (initiative order, the monster's hits on its threat target, void
   drain on every player, per-player potions), with targeting modelled
   conservatively (the threat target takes every hit; the 10% lowest-HP hits
   bound separately). Theorems: N = 1 equals today's `fight_outcome` (a
   differential pins it); adding a participant never lowers the win verdict.
   `threat` stops being carved out.
2. **The census names it.** A `party:N@L` rung: N copies of the census
   character (armory, potions). Acceptance: the 7 duskworm recipes plan under
   a party condition instead of a held leaf — or the model says no party of 3
   wins, which is then the named limit.
3. **Obtain and decide.** A boss drop route gated on a winnable PARTY of the
   fleet's available characters (the roster: level, gear, potions); the band
   target may rank a party boss fight (×2 XP, group-average level). One party
   per boss at a time.
4. **Coordination.** A party lease in learning.db (like the supply claims): a
   leader proposes (boss, members, window); members accept when their own
   commitment allows, travel to the tile and hold; the leader fights with
   `participants` when every member is on the map and out of cooldown; the
   lease expires on a timeout, the event's end, or a member's guard (HP,
   bag). The arbiter treats "hold for the party" as the member's step, not a
   Wait (the liveness ladder needs a rung for it).
5. **Execution and learning.** `FightAction.participants`; parse the
   multi-character result into each participant's cycle (xp, gold, drops,
   hp); the fight record keyed on the party for the loss veto and the
   loss-risk price.
6. **Witness.** A duskworm-window group fight live: kills, drops per
   participant, deaths, time held waiting for the party.

## Rulings (USER 2026-10-10)

1. "use groups for boss xp, too. XP velocity matters for leaderboard
   placement." — a party boss fight is ranked by XP per second like any fight.
2. "always" — a party may pull a member off its own objective at any time.
3. "fleet is down, approve probe." — Increment 0 runs.

## Increment 0 — probe (2026-10-11 01:48Z, fleet down; R2D2 leads, Lor joins, king_slime)

Raw responses: `docs/evidence/group_fight_probe_2026-10-11.json`.

- **A, group fight:** HTTP 200, `win` in 17 turns. The response carries
  `data.characters` — one `{character_name, xp, gold, drops, final_hp}` per
  participant — beside the leader's own `cooldown` and `fight`. Gold 5 and 4,
  no drops, XP 0 each (king_slime 15 against the group's average 32: past the
  10-level penalty).
- **Cooldown:** BOTH characters took the SAME fight cooldown, 32 s, expiring
  at the same instant (01:49:28.535). The participant's cooldown is the
  leader's.
- **Damage lands per character:** king_slime hit Lor every time (Lor 705 →
  446) and never R2D2 (785/785) — targeting, not a split.
- **Turns are per actor:** "Turn 1: R2D2 … Turn 2: Lor … Turn 3: King Slime"
  — each actor's action is a numbered turn, so with 3 actors the monster acts
  every third turn. Effects keyed on turn counts (`void_drain` every 4 turns,
  the barrier every 5) must be modelled on that global count.
- **B, participant not on the map:** HTTP **486** "All characters must be on
  the same map location."
- **C, participant in cooldown:** HTTP **499** "The character is in cooldown:
  4.83 seconds remaining."
- **Not settled:** a participant's death mid-fight (none died); whether a
  participant's equipped utility potions are drunk in a group fight (none
  worn). Settle in Increment 5's first live fights.
