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

## Increment 2 — design (2026-10-11)

Increments 2 and 3 meet here: the census can only name a party condition the
PLANNER plans under, so the drop route's WINNABLE gate gains a party arm.

- `WorldState.party`: the characters able to join this one's boss fight (their
  states). Empty by default, so production is unchanged until Increment 4
  fills it from the fleet; the census fills it with copies of the census
  character.
- `party_win.wins_as_a_party(state, game_data, monster)`: only for a `boss` or
  `raid_boss` with a non-empty `party`. For each utility-potion loadout the
  character can stock (`fight_walk.loadouts`, as the solo gate) and each set of
  one or two of `party` (the server's limit), every member wears that loadout
  if it can stock it (else none), at full HP, and `group_fight_core.
  group_outcome` decides. Memoized per catalogue on what it reads (as
  `loadout_win`).
- WINNABLE = bare `is_winnable` OR a potion loadout OR a party. One function
  (`drop_routes.drop_fight_winnable`) serves the gate and the census
  classifier, which mirrored it by hand.
- Census: `CraftCell.party` = siblings granted (2 = a party of three); rungs
  `party` and `party@L<n>` after the grey rungs, before `held:`. Acceptance:
  the 7 duskworm recipes plan under a party rung.
- Not here: execution (`FightAction.participants`, Increment 5) — under a
  non-empty `party` the planner may plan a fight the executor still fights
  alone; production never sets `party` before Increment 4/5.

## Increment 2 — built (2026-10-11)

As designed. `WorldState.party`; `party_win.winning_party` /
`wins_as_a_party`; `drop_routes.drop_fight_winnable` (bare, potion loadout or
party) serves the WINNABLE gate and the census classifier; `fight_walk.wear`
projects a utility loadout for both arms; census `CraftCell.party`, rungs
`party` / `party@L<n>`, and `fight_needs` names a party win
`party<size>:<loadout>`.

Conditions census: still **321/321**, and the seven duskworm recipes
(adamantite_ring, adamantite_sword, dust_amulet, dust_sword, eternal_red_ring,
heart_amulet, desert_whip) move from `held:duskworm_skin` /
`held:adventurer_skull` to `party`: duskworm falls to
`party3:water_res_potion+enhanced_health_potion`. The held last resort now
names only enchanted_fabric (raid reward, 9) and wooden_stick (starter, 1).

Production is unchanged: `party` is empty until Increment 4 fills it from the
fleet; Increment 5 makes the executor fight with `participants`.

## Increment 3 — built (2026-10-11)

USER ruling 1: a party boss fight is ranked by XP per second like any fight.

- `party_loop.best_party_loop`: the best party loop against a `boss` (a
  `raid_boss` pays through the raid reward system, so it is no XP loop):
  every stockable loadout × every set of one or two of `state.party`, walked
  by `group_outcome`; this character's own XP per second — XP at the party's
  AVERAGE level (floored, rule 3) with its own wisdom, its own drinks priced
  as `loop_rate` prices them, its own recovery over its food menu. The fight
  takes `SECONDS_PER_TURN` (2) per actor turn, `rounds × (N + 1)` turns: the
  probes' cooldowns (29 s / 16 turns, 32 s / 17, 45 s / 24) are 2 s a turn
  less haste, left uncredited. A loop paying no XP (the boss grey to the
  party's average) is no loop.
- `band_target.band_combat_target(..., party_of)`: party bosses
  (`party_candidates`: spawning, under the executor's level ceiling) compete
  with the band's normal monsters on one key; a party pick carries its
  `joiners` (`BandTarget.joiners`). A cleared ladder still farms a party boss.
  `GamePlayer._band_party` prices a party as `_band_loadout` prices a loop.
- What it says (census L45, three members): duskworm 7.2 XP/s on
  water_res + enhanced_health; rosenblood 4.2; goblin_priestess 1.9; a level-40
  and a level-50 member earn rosenblood's XP at 45 (473, not the 680 a level-40
  character earns alone).

**Ordering constraint for what follows.** With a non-empty `party` the band may
name a boss that `GrindCharacterXP` would fight ALONE: the executor does not
send `participants` until increment 5. So increment 5 (execution) must land
before increment 4 fills `party` from the live fleet, or increment 4 must ship
behind the executor.

## Increment 5 — built (2026-10-11), ahead of increment 4

- `FightAction.participants`: sent as `participants` on the fight request;
  the new state is read from this character's own entry in
  `data.characters` (a party fight returns every participant's); part of the
  action's identity and repr (`Fight(duskworm+R2D2+Lor)`), so a party fight's
  learned cost and success rate are its own.
- `party_win.party_participants`: the action factory takes a party to a boss
  ONLY where the solo arms of the drop gate lose (bare stats and every
  stockable potion loadout, at full HP) and a party wins; the joiners are the
  first winning party's (`winning_party` now returns their indices). A boss
  one character beats is fought alone.
- The leader records a party fight under `party_combat_key`
  (`combat-party:<monster>`), never the solo `combat:<monster>` key the
  learned-loss veto reads.
- HTTP 486 (a participant off the tile) and 499 (one in cooldown) fall to the
  TRANSPORT class (a short retry) until increment 4 coordinates positions and
  cooldowns.
- Not here: a JOINER's own cycle. Its process sees the fight's XP, gold,
  drops and HP on its next state read; attributing them to its "hold for the
  party" step is increment 4's.

Still inert in production: `party` is empty until increment 4.

## Increment 4 — design (2026-10-11)

What production has today (survey 2026-10-11): sibling coordination lives in
`CoordinationStore` (learning.db, `--coordination-db`, one store per
character, every call takes `now`, TTL rows: `LEASE_TTL_SECONDS` 600 for
snapshots, one-row claims unique on their key, renewed by re-claiming each
cycle, released by the owner only). Fleet WORK (supply, turn-in) is a root
alternative (`ReachFleetOutcome`), served on its rotation turn. A party hold
cannot be that: rotation demotes a served goal, so a member on the tile would
leave it after one turn. USER ruling 2 ("always") makes it an INTERRUPT.

**4a — the data (inert).**
- `PartyCard` (table `party_cards`, unique on character): each character
  publishes, every cycle, the WorldState fields a party fight reads
  (`fight_key`'s fields, hp, position, cooldown, skills, gold, bag/bank
  potions), JSON, `LEASE_TTL_SECONDS` expiry. `sibling_cards(now)` returns the
  live siblings' as WorldStates.
- `PartyLease` (table `party_leases`, unique on boss: one party per boss):
  leader, members, tile, claimed/expires. `claim_party(boss, members, tile,
  now)` (refused while a live lease names any of them or another leader holds
  the boss), `party_lease_for(character, now)` (the live lease naming a
  character as leader or member), `release_party(boss)` (the leader only).
  Expiry `PARTY_LEASE_TTL_SECONDS` = 300 (a hold costs the members their own
  work; the leader renews while it still wants the fight).
- `party_lease_core.py` (pure, proved if it decides anything): `assembled`
  — every member's card fresh, on the lease tile, out of cooldown at `now`.

**4b — the behaviour.**
- The roster: `state.party` = the live siblings' cards NOT named by another
  live lease (each a WorldState). The band (increment 3) ranks party bosses
  over it; the drop gate (increment 2) admits them.
- Leader: NOT a guard. Rotation would walk a guard-held leader off the fight
  while its members wait, and a party fight is wanted by two producers (the
  band's XP target and a drop route's plan). So the leader acts at EXECUTION:
  when the plan's head is a party `FightAction` (`participants`, set by the
  factory), `GamePlayer._lead_party` claims or renews the lease (boss, the
  participants, the fight's nearest tile) and runs the fight only when the
  party is `assembled`; otherwise it runs a `HoldForPartyAction` on that tile
  instead. The fight — won, lost or refused — releases the lease. A leader
  whose plan stops heading the fight stops renewing; the lease expires on its
  TTL.
- Member: a live lease naming it fires the `PARTY_JOIN` guard — the LAST
  guard, after `CRAFT_POTIONS` (survival, bag and the fight's potions first;
  the potion guard's fight is the lease's boss). Its goal `JoinPartyGoal`
  plans `Move` to the tile then `HoldForPartyAction` (one short no-API pause,
  a productive step: not Wait, which the arbiter filters and the census
  alarms on). A member's cycle that holds records the fight's XP/gold/drops
  when its next state read shows them.
- Lean: `PARTY_JOIN` is a new guard rung: `GuardKind`, `allInLadderOrder`,
  `DecideKey`, the oracle's ladder vector (appended index), the F/D/E measure
  slot (distance to the tile, then a hold flag cleared fire-and-lose — the
  `currencyTurnInFlag` shape: the lease's end is the world's answer, bounded
  by its TTL), the cycle-step dispatch and its progress lemma, the sim
  mirrors, the ladder diff tests, the census `DORMANT` entries for the new
  goal and action, and mutants.
- Only after 4b's Lean lands does `state.party` get filled from the cards.

## Increment 4a — built (2026-10-11)

`party_card.card_json` / `card_state` (a sibling's fight state, round-trip
tested); tables `party_cards` (`PartyCard`, unique per character, the
snapshot clock) and `party_leases` (`PartyLeaseRow`, unique per boss,
`PARTY_LEASE_TTL_SECONDS` 300); `CoordinationStore.publish_party_card`,
`sibling_party_cards`, `claim_party` (refused while another leader holds the
boss or a live lease on another boss names any of the party; renews its own;
an insert race reports False), `party_lease_for` (leader or member, read-only),
`release_party` (the leader's own row only); `party_lease_core.PartyLease`,
`on_tile`, `ready`, `assembled`. Inert: nothing publishes or reads them yet.

## Increment 4b — built (2026-10-11)

- `GuardKind.PARTY_JOIN` (LAST guard, after CRAFT_POTIONS) fires on
  `ctx.party_hold` — the live lease naming this character as a member —
  and maps to `JoinPartyGoal`: one `HoldForPartyAction` (move to the tile, else
  pause `HOLD_SECONDS` 20 and read the character back, so the cycle records
  what the leader's fight paid this member). `WorldState.party_held` is the
  planning-only marker the hold sets.
- Leader at execution (`GamePlayer._lead_party`): a party `FightAction` at the
  plan's head claims/renews the lease and fights only when `assembled`, else
  holds on the tile; the fight releases the lease. Past
  `PARTY_ASSEMBLY_SECONDS` (300, the lease TTL) unassembled, the leader frees
  the members and blocks the fight as a TRANSPORT failure, so its plan moves
  on.
- `GamePlayer._refresh_party` each cycle (before the actions are built, and in
  `plan_from_state`): sibling cards, the lease, and `state.party` (the lease's
  members for its leader; none for a member; else every sibling no live lease
  names). `_update_coordination` publishes this character's card.
- Lean (`Formal.Liveness`): `MeansKind.partyJoin` after `.craftPotions`;
  `State.partyJoinActive`; `ActionKind.holdForParty` clears it (fire-and-lose:
  the model collapses the hold, bounded in production by the lease TTL, into
  one step — the `GE_CANCEL` shape); F/D/E slot `partyJoinFlag` (F: bottom,
  slot 17; D/E: directly above `objectiveStepFlag`, which the refresh can
  raise); `descends*_partyJoin`; ladder oracle index [41], decide-key guard
  index 13; the ladder diff (PARTY_JOIN selected when every higher rung is
  quiet, preempted by HP_CRITICAL, quiet without a lease); sim mirrors.
- Census: `JoinPartyGoal` / `HoldForPartyAction` declared `conditional:`.

THIS IS THE FIRST LIVE INCREMENT: with the fleet running under
`--coordination-db`, cards are published, rosters fill, the band and the drop
gate weigh parties, and a boss only a party wins is fought by a lease.

Known limits (residuals), and how each closed:
- R1. A member joins only on the lease tile's own layer (`HoldForPartyAction` is
  inapplicable elsewhere); a cross-region approach is not planned.
  CLOSED (2026-10-13, verified, test-pinned): the hold carries the tile's
  `travel_region`, so the search admits the region edges and an interior member
  plans `Transition` then `HoldForParty`.
- R2. A member fights in the utility potions it already wears; nothing stocks the
  party loadout for it (the CRAFT_POTIONS guard sizes for its own fight).
  CLOSED (2026-10-13): the fight carries the winning party's loadout
  (`party_win.party_loadout`), the lease stores it, and leader and members
  take the lease's boss as the fight ahead in `party_chosen_loadout` (what the
  party walk drinks for each), so the CRAFT_POTIONS guard stocks and equips
  it. The leader fights only once every fighter that can stock it wears it
  (`wears_party_loadout`). A member that cannot stock it fights bare, as the
  model judged it. Bounded by the 300 s assembly deadline.
- R3. A leader whose plan stops heading the fight stops renewing: its members
  hold until the lease's TTL (300 s). CLOSED by f1bd902a for a commitment
  change (the lease is released); a leader process that dies still leaves
  the TTL as the bound.

## Increment 6 — first live data (2026-10-11 13:55-14:03Z)

The fleet ran 4b within the hour. C3P0 (`GatherMaterials(king_slimeball)`)
led `Fight(king_slime+HAL)`: 26 attempts, 24 HTTP 499 (a participant in
cooldown) and 2 HTTP 486 (off the tile), 0 fights; HAL held only 3 times.
Cause: the leader released the lease after EVERY attempt, refusals included
— HAL's PARTY_JOIN guard went quiet between attempts and HAL walked back to
its task (TaskTrade, TaskCancel at the taskmaster). Fixed: a party fight
releases its lease only when it RESOLVED (won, or `fight_lost`); a 486/499
refusal keeps it, so the members keep holding. `JoinPartyGoal` /
`HoldForPartyAction` left the census's dormant table (live).

## Increment 6 — second live data (after the 9585e542 restart, 14:30-15:10Z)

The lease now held across refusals, yet still 0 fights: C3P0 held 55 times
and fired `Fight(king_slime+HAL)` 48 times (45 HTTP 499, 3 HTTP 486); HAL
held 9 times. HAL's PARTY_JOIN guard fired only BETWEEN its cached sunflower
gather batches (14:39:51, 14:42:44, 14:48:38): an interrupt is consulted only
on a re-decide, and the plan cache had no trigger for a party call. C3P0
read HAL's card from that one hold — on the tile, out of cooldown — fired,
and met HAL gathering again. Fixed: `should_replan` trigger 7 — a party
lease calling this member re-decides unless the cached plan IS that lease's
hold (`JoinParty(<boss>)`); a call is never a mere staleness refresh.

## Increment 6 — why no party formed (2026-10-11 ~21:50Z)

C3P0's root `ObtainItem(slime_shield)` (king_slimeball for the party fight)
was never served after its turn 41: `GrindCharacterXP(vampire)` and its food
`GatherMaterials(cooked_trout, carry)` swapped the commitment every 1-3
cycles, and the intention budget counted cycles per COMMITMENT, resetting on
every switch — neither ever filled `BUDGET_CYCLES`, neither recorded a turn,
and rotation kept them ahead of king_slimeball (most recently served) for
hours. Not a party bug: a rotation starvation any alternating pair causes.
Fixed: the budget is summed per goal across commitments (`_budget_spent`).
Also seen on the way: C3P0 lost 8 straight `Fight(rat)` (19:43-19:58,
`SupplyBank(cooked_rat_meat)` / slime_shield chain, predicted loss, no
utility potion worn) — the drop gate's potion-loadout arm admitted a fight
fought without its potions. Residual, not fixed here.
A third fix on the way (the local gate's liveness alarm — retired 2026-10-19
for the liveness census's stall report — HAL 21:35Z): 12 Wait
cycles with every plan declined `bag_overflow` at 61/164 items, 17/20 slots,
far below DEPOSIT_FULL. An overflowing plan now banks the bag's surplus in
front of itself when that makes it fit (`craft_plan_gen._bank_first`).

## Increment 6 — first party wins (2026-10-12)

Four faults between the first formed party and the first wins, each fixed:

- `fe19dcbb`: the planner's state key left out `party_held`, so a member
  already on the tile planned no hold and its commitment ran instead (HAL
  back to trout with the lease live).
- `323f6c16`: the drop gate and `party_participants` were cold — C3P0 lost
  king_slime alone 41 of 44 at level 31 and the party arm never fired. The
  learned-loss veto now reaches both as `WorldState.lost_fights`, which voids
  the solo arms only. Also: the run loop recorded the PLAN's fight, so every
  leader hold was logged as a party win (134 rows, 0 fights); it now records
  `executed_action`.
- 19:31Z and 19:33Z: `Fight(king_slime+HAL)` won twice (grey: 0 XP; HAL paid
  gold). Between the wins the lease was released, HAL went to iron, and the
  leader drew 13 HTTP 499 four seconds apart; its 100-cycle turn ran out and
  HAL held an orphan lease for 5 minutes.
- Fixed together: a WON party fight keeps its lease (only a loss, the
  assembly deadline, the TTL, or a new leader commitment end it); a refused
  party fight makes the leader hold one cycle; each character republishes
  its party card after its action (the cycle-start card predates the action's
  cooldown, and the next publish waits it out).
