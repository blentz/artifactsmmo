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
   differential pins it); see the design below for the rest (a newcomer CAN
   lower the verdict). `threat` stops being carved out.
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
- **Not settled:** whether a participant's equipped utility potions are drunk
  in a group fight (none worn). Settle in Increment 5's first live fights.

## Increment 0b — a member's death (2026-10-11 02:59Z, fleet down; USER approved)

Raw responses: `docs/evidence/group_fight_death_probe_2026-10-11.json`.

- Lowering Lor's HP: a solo king_slime fight from 446 HP was LOST (turn 16,
  king_slime at 333/1000); Lor respawned at (0,0) with 1 HP.
- **D, party fight with a 1-HP member:** R2D2 (785/785) leads, Lor (1/705)
  joins, king_slime. "Turn 3: King Slime used fire attack against Lor ...
  Lor has been defeated!" — and the fight goes on: R2D2 alone wins on turn 24
  with 170/785. `result: win`; Lor's entry `final_hp: 1`, gold 2 (paid
  although dead); after the fight Lor is still on the boss tile at 1 HP — no
  respawn walk.
- **Settled:** a dead member leaves the fight; the rest fight on; the fight is
  lost only when every member is dead. The Increment 1 model ("any death is a
  loss") was wrong; Increment 1b replaces it.

## Increment 1 — design (2026-10-11)

Per-player numbers at the geared census cell (`combat_terms`, no potions),
duskworm: level 55-60 kill 6.5M/round (39 rounds alone, 13 for three), takes
5.0M a hit with 1,910-1,935 HP (4 hits). `void_drain` alone is 1.9M of that
and lands on every member every round. So no honest model lets three of these
characters kill duskworm without potions; the model decides with them.

**Inputs.** Each member: `raw` (its raw hit), `net` (its share of the kill
rate: its damage less the bubble/sun-shield cut and the monster's heal from
draining IT), `hit` (what one monster hit costs it: the attack, berserk,
frenzy, greed terms), `area` (what every round costs it targeted or not:
poison, burn, void drain, mirror, less its own lifesteal), `hp`, `max_hp`,
`first` (initiative ≥ the monster's), `threat` (summed from its gear), the
restore potion and its stock. The monster: effective HP (barrier included),
reconstitution, and `drain` = the kill-rate terms that happen once per
MONSTER turn (its lifesteal on crit, its healing). For one member
`net - drain` is today's `kill_step` and `hit + area` today's `die_step`,
term for term (each floored term kept whole).

**Exits** (today's ladder, over the party): no member deals damage; the
summed kill rate `K = Σ net - drain ≤ 0`; `R = ⌈HP×10000 / K⌉` rounds with
`R × (N+1) > 2 × 100` actor turns (the cap counts actor turns — the probe's
"Turn 3: King Slime"); reconstitution `2 × recon ≤ R × (N+1)`; every member
out-sustains a hit; a member starts dead. For N = 1 each is today's test.

**The round.** Members with initiative drink; in the kill round, if every
member moves first, the party wins before the monster acts. The monster then
hits its target — the highest threat, ties by lowest HP, then lowest index —
for `hit - hit/10`, and the lowest-HP member for `hit/10` (the 90/10 rule,
in expectation like every other term; with equal threat both are the same
member, the focus fire the probe saw). Every member takes `area`; a negative
total (lifesteal) heals, capped at max HP. Members without initiative then
drink; the kill round ends in a win.

**A death is a loss.** Whether a dead member leaves a fight the rest can
still win is not settled (Increment 0). The model calls the fight lost when
ANY member's pool reaches 0: never claims a win the server could refuse, and
a member's death costs its respawn walk anyway. Increment 5 measures it.

**Theorems.** `groupOutcome_single` — one member IS `fightOutcome` on today's
terms (verdict, turns, HP, potions), so every solo theorem holds at N = 1;
`killRounds_antitone` — a member adding damage never delays the kill round;
`used_le_stock` — no member drinks more than it holds; `win_alive` — a walked
win leaves every member alive. "Adding a member never lowers the verdict" is
FALSE in this model and in the game: a high-threat newcomer draws the hits and
may die. The plan's earlier line claiming it is withdrawn.

## Increment 1 — built (2026-10-11)

- `formal/Formal/GroupFight.lean`: `groupOutcome` + `groupOutcome_single`,
  `killRounds_antitone`, `win_alive` (with `win_alive_witness`); oracle
  `group_fight`; differential `formal/diff/test_group_fight_diff.py` (random
  parties of 0-3, the one-member walk against `fight_outcome`, pinned focus
  fire / tank / exact-0 parties); 15 core mutants, all killed.
- `ai/group_fight_core.py` (the walk); `combat.fight_numbers` /
  `party_member` / `party_boss` / `boss_drain` split the solo terms
  (`tests/test_ai/test_party_terms.py`, 5 mutants killed); `ItemStats.threat`
  parsed from the `threat` effect.
- What it says (geared census cell, no potions, N identical members): lich
  loses alone at 50 and 60 and WINS with two (9 rounds) or three (6);
  king_slime is won alone already; goblin_priestess, rosenblood and duskworm
  lose at every N — identical members tie on threat, so the boss focuses one
  and any death is a loss. Potions and a real tank (threat) are the levers
  Increment 2's rung must try.

## Increment 1b — the death rule from data (2026-10-11)

`Formal.GroupFight.walk` now tracks the boss's pool: a dead member stops
acting, drinking, being targeted and paying `area`; a round's damage is each
first mover alive before the boss's turn and each late mover alive after it;
the fight is lost only when every member is dead, or when a death delays the
kill past the turn cap or reconstitution (counted in the full party's actor
turns: conservative). `groupOutcome_single` re-proved over the new walk
(`walk_single`: the boss's pool is `n` kill steps from 0 exactly when the solo
walk has `n` rounds left); `win_alive` becomes `win_survivor` (a win leaves
some member alive; witness: one dies, the other wins). 21 core mutants, all
killed (two needed pinned parties: a dead member's lifesteal must not revive
it; a death that delays the kill past reconstitution).

Duskworm (geared census cell L60, three members, each the same potion pair,
production `party_member`): see Increment 2.
