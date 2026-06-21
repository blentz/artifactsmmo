#!/usr/bin/env python
"""One-shot EMPIRICAL haste-rate probe (PLAN_acquisition_timing.md Phase 1b).

The ArtifactsMMO openapi documents haste only as "reduces the cooldown of a
fight" — there is NO published %-per-point rate. CLAUDE.md forbids inventing a
default ("use only API data or fail"), so the rate for the #16 efficiency model
must be MEASURED on the live server. This script does that measurement and
nothing else; it does NOT plan or play the character.

Method (mirrors the plan):
  1. Fight a fixed monster R times with the haste item EQUIPPED  -> mean cdN.
  2. Fight the same monster R times with it UNEQUIPPED           -> mean cd0.
  3. rate per point = (cd0 - cdN) / (cd0 * N)   where N = item haste value.
Averaging over R rounds cancels per-fight turn-count variance.

SAFETY / SCOPE — this PERTURBS a real character (equips/unequips, fights, rests):
  * Run it only when the bot is NOT playing this character (serialize: it imports
    src and mutates live state).
  * Position the character ON a monster tile it can BEAT first; the probe refuses
    to start otherwise and aborts immediately if any fight is lost.
  * It restores the original loadout (re-equips the item) before exiting.

Usage:
    uv run python scripts/probe_haste.py <character_name> [--rounds R]
"""

import argparse
import sys
import time

from artifactsmmo_api_client.models.equip_schema import EquipSchema
from artifactsmmo_api_client.models.fight_result import FightResult
from artifactsmmo_api_client.models.item_slot import ItemSlot
from artifactsmmo_api_client.models.unequip_schema import UnequipSchema

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

# Stats that change combat turn-count and therefore confound a fight-cooldown
# measurement. A clean probe wants a PURE-haste item (these all zero).
_COMBAT_CONFOUND_FIELDS = (
    "attack", "resistance", "dmg", "dmg_elements", "critical_strike",
    "initiative", "hp_bonus", "lifesteal", "combat_buff", "antipoison",
)

_COOLDOWN_EPSILON = 0.5  # small slack so we never act a hair before expiry


def _slot_enum(slot_field: str) -> ItemSlot:
    """`rune_slot` -> ItemSlot.RUNE (the API body wants the slot without suffix)."""
    return ItemSlot(slot_field.replace("_slot", ""))


def _confounding_stats(stats) -> list[str]:
    """Combat-affecting stats on the item that would bias the cooldown reading."""
    out = []
    for fname in _COMBAT_CONFOUND_FIELDS:
        val = getattr(stats, fname)
        if val:  # non-zero scalar or non-empty dict
            out.append(f"{fname}={val}")
    return out


class HasteProbe:
    """Drives the equip/fight/unequip/fight measurement against the live server."""

    def __init__(self, name: str, rounds: int):
        self.name = name
        self.rounds = rounds
        cm = ClientManager()
        cm.initialize(Config.from_token_file())
        self.api = cm.api
        self.game_data = GameData.load(cm.client)

    def _state(self) -> WorldState:
        """Fresh WorldState from the live character."""
        char = self.api.get_character(self.name).data
        return WorldState.from_character_schema(char)

    def _wait_cooldown(self) -> None:
        char = self.api.get_character(self.name).data
        if char.cooldown > 0:
            time.sleep(char.cooldown + _COOLDOWN_EPSILON)

    def _rest_to_full(self) -> None:
        """Rest until HP is full so each fight starts from the same condition."""
        while True:
            self._wait_cooldown()
            state = self._state()
            if state.hp >= state.max_hp:
                return
            self.api.action_rest(self.name)

    def _one_fight(self, monster: str) -> float:
        """Fight once at full HP; return the fight cooldown in seconds. Abort the
        whole probe if the fight is lost (the monster is not safely beatable)."""
        self._rest_to_full()
        self._wait_cooldown()
        resp = self.api.action_fight(self.name).data
        if resp.fight.result != FightResult.WIN:
            sys.exit(
                f"ABORT: lost a fight vs '{monster}' (result={resp.fight.result.value}). "
                f"Move the character onto a monster it reliably beats and re-run."
            )
        return resp.cooldown.total_seconds

    def _find_haste_item(self, state: WorldState) -> tuple[str, str, int]:
        """Locate a haste item to test. Prefer one ALREADY equipped (no swap);
        else an inventory item with a free slot of its type. Returns
        (code, slot_field, haste_value). Exits with guidance if none is usable."""
        # Already-equipped haste item -> measure it in place.
        for slot_field, code in state.equipment.items():
            if not code:
                continue
            stats = self.game_data.item_stats(code)
            if stats and stats.haste > 0:
                return code, slot_field, stats.haste

        # Inventory haste item -> needs a free slot of its type to equip into.
        for code, qty in state.inventory.items():
            if qty <= 0:
                continue
            stats = self.game_data.item_stats(code)
            if not stats or stats.haste <= 0:
                continue
            for slot_field in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                if state.equipment.get(slot_field) is None:
                    return code, slot_field, stats.haste
            sys.exit(
                f"Haste item '{code}' is in inventory but every {stats.type_} slot is "
                f"occupied. Free a slot (or equip it manually) and re-run."
            )

        sys.exit(
            "No haste item found equipped or in inventory. Acquire one (e.g. a haste "
            "rune/utility) and put it on this character, then re-run the probe."
        )

    def _current_monster(self, state: WorldState) -> str:
        """The monster spawning on the character's current tile, or exit."""
        for code in self.game_data.monsters.locations:
            if (state.x, state.y) in self.game_data.monster_locations(code):
                return code
        sys.exit(
            f"No monster on the current tile ({state.x},{state.y}). Move the character "
            f"onto a monster tile it can beat, then re-run."
        )

    def _equip(self, code: str, slot_field: str) -> None:
        self._wait_cooldown()
        self.api.action_equip_item(
            self.name, EquipSchema(code=code, slot=_slot_enum(slot_field))
        )

    def _unequip(self, slot_field: str) -> None:
        self._wait_cooldown()
        self.api.action_unequip_item(
            self.name, UnequipSchema(slot=_slot_enum(slot_field))
        )

    def _run_phase(self, label: str, monster: str) -> list[float]:
        cooldowns = []
        for i in range(1, self.rounds + 1):
            cd = self._one_fight(monster)
            cooldowns.append(cd)
            print(f"  [{label}] fight {i}/{self.rounds}: cooldown {cd:.1f}s")
        return cooldowns

    def run(self) -> None:
        state = self._state()
        code, slot_field, haste_n = self._find_haste_item(state)
        monster = self._current_monster(state)

        stats = self.game_data.item_stats(code)
        confounds = _confounding_stats(stats)

        print(f"Haste probe — character '{self.name}'")
        print(f"  item     : {code}  (haste={haste_n}, slot={slot_field})")
        print(f"  monster  : {monster}  at ({state.x},{state.y})")
        print(f"  rounds   : {self.rounds} per phase")
        if confounds:
            print(
                f"  WARNING  : item also carries combat stats {confounds} — these "
                f"change turn count and bias the reading. A pure-haste item is "
                f"cleaner; treat the result as approximate."
            )

        # Safety: refuse to start unless the documented formula says we win.
        if not predict_win(state, self.game_data, monster):
            sys.exit(
                f"predict_win says '{monster}' is NOT a safe win for the current "
                f"loadout. Move to a weaker monster and re-run (the probe must not "
                f"risk repeated deaths)."
            )

        # Phase ON: ensure equipped, then measure.
        if state.equipment.get(slot_field) != code:
            self._equip(code, slot_field)
        on = self._run_phase("haste-ON", monster)

        # Phase OFF: remove it, measure, then restore.
        self._unequip(slot_field)
        off = self._run_phase("haste-OFF", monster)
        self._equip(code, slot_field)
        print(f"Restored: re-equipped {code} into {slot_field}.")

        cd_n = sum(on) / len(on)
        cd_0 = sum(off) / len(off)
        print("\n=== RESULT ===")
        print(f"  mean cooldown  haste-ON  (cdN) : {cd_n:.3f}s")
        print(f"  mean cooldown  haste-OFF (cd0) : {cd_0:.3f}s")
        print(f"  reduction              (cd0-cdN): {cd_0 - cd_n:.3f}s")
        if cd_0 <= 0 or haste_n <= 0:
            sys.exit("Cannot derive a rate (cd0 or N is zero).")
        frac_per_pt = (cd_0 - cd_n) / (cd_0 * haste_n)
        secs_per_pt = (cd_0 - cd_n) / haste_n
        print(f"  N (haste points)               : {haste_n}")
        print(f"  RATE: fractional cooldown reduction per haste point = {frac_per_pt:.5f}")
        print(f"        (= {frac_per_pt * 100:.3f}% per point;  {secs_per_pt:.4f}s per point)")
        print(
            "\nFeed `frac_per_pt` into strategic_value as the haste efficiency rate "
            "(replace the deferred weight 1). Re-run a few times to confirm stability."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Empirical haste-rate probe.")
    parser.add_argument("character", help="character name to probe")
    parser.add_argument(
        "--rounds", type=int, default=8,
        help="fights per phase (more = less turn-count noise; default 8)",
    )
    args = parser.parse_args()
    HasteProbe(args.character, args.rounds).run()


if __name__ == "__main__":
    main()
