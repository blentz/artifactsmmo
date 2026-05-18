"""Tests for the generic BlockerRegistry."""

import time

from artifactsmmo_cli.ai.blockers import BlockerRegistry, BlockerState
from artifactsmmo_cli.ai.learning.store import LearningStore


class TestBlockerRegistryInMemory:
    def test_empty_by_default(self):
        reg = BlockerRegistry()
        assert reg.is_blocked("bank") is False
        assert reg.get("bank") is None

    def test_mark_blocked_records_state(self):
        reg = BlockerRegistry()
        before = time.monotonic()
        reg.mark_blocked("bank", char_level=2, unlock_monster="sea_marauder", required_level=44)
        b = reg.get("bank")
        assert b is not None
        assert b.unlock_monster == "sea_marauder"
        assert b.required_level == 44
        assert b.blocked_at_char_level == 2
        assert b.blocked_since_monotonic is not None
        assert b.blocked_since_monotonic >= before

    def test_clear_removes(self):
        reg = BlockerRegistry()
        reg.mark_blocked("bank", char_level=2)
        reg.clear("bank")
        assert not reg.is_blocked("bank")

    def test_supports_multiple_codes(self):
        """The registry's purpose: more than one gate, no special-casing."""
        reg = BlockerRegistry()
        reg.mark_blocked("bank", char_level=2)
        reg.mark_blocked("workshop:weaponcrafting", char_level=2, required_level=5)
        assert reg.is_blocked("bank")
        assert reg.is_blocked("workshop:weaponcrafting")
        assert not reg.is_blocked("nonexistent")


class TestBlockerRegistryPersistence:
    def test_mark_blocked_persists_via_store(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        reg = BlockerRegistry()
        reg.mark_blocked("bank", char_level=2, unlock_monster="sea_marauder",
                          required_level=44, store=store)
        # Reload from store
        reg2 = BlockerRegistry.load(store, known_codes=["bank"])
        store.close()
        b = reg2.get("bank")
        assert b is not None
        assert b.unlock_monster == "sea_marauder"
        assert b.required_level == 44

    def test_load_ignores_codes_without_required_level(self, tmp_path):
        """A persisted blocker with required_level=0 is effectively no info —
        don't add it to the in-memory registry."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        store.set_blocker("bank", unlock_monster=None, required_level=0)
        reg = BlockerRegistry.load(store, known_codes=["bank"])
        store.close()
        assert not reg.is_blocked("bank")

    def test_mark_blocked_without_store_just_holds_in_memory(self):
        """No store wired: behaviour is purely in-process."""
        reg = BlockerRegistry()
        reg.mark_blocked("bank", char_level=2, required_level=44)
        assert reg.is_blocked("bank")


class TestBlockerStateConstruction:
    def test_required_fields_default(self):
        b = BlockerState(code="bank")
        assert b.code == "bank"
        assert b.unlock_monster is None
        assert b.required_level == 0
        assert b.blocked_since_monotonic is None
        assert b.blocked_at_char_level == 0
