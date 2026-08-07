# Witness ledger

Each entry is an ACCEPTANCE CASE, not a log line: a concrete input, both candidate
behaviours, and the ratified answer. The implementation's test suite is harvested
from here.

---

### W-001 · s009-guard-vs-j-order-precedence

| | |
|---|---|
| **cell** | E. Finite-band ordering (J-minimisation) / normal |
| **Σ dimension** | value semantics, ordering |
| **severity** | 5 |
| **provenance** | Surfaced by Phase 2 round 0, which was subsequently VOIDED for blindness (one of 73 agents read implementation source). The finding is retained because it is **independently verifiable by reading S-009 and S-014 side by side** — it rests on no agent evidence. Everything else that round produced was discarded. |

**Distinguishing input**

```
current_level = 30
candidates (in input order):
  trunk_xp   kind=TRUNK  cost=0   outcome=(level 50, cycles_to_50=900)  -> J = 900
  iron_sword kind=GEAR   cost=40  outcome=(level 50, cycles_to_50=300)  -> J = 340

Both are in the FINITE band: S-014 says unreachable ⟺ level < 50, and both
report 50. The gear costs 40 actions and saves 600 cycles — gear that pays off.
```

| | behaviour |
|---|---|
| **A** | `ranking = [iron_sword, trunk_xp]`, `chosen = iron_sword` — S-003/S-005 govern; S-009 treated as a corollary that only bites for non-improving gear |
| **B** | `ranking = [trunk_xp, iron_sword]`, `chosen = trunk_xp` — S-009 read as a hard ordering constraint. In the finite band **every** candidate reports level 50, so its antecedent holds for **every** positive-cost gear, pinning all of it behind the trunk |

Both readings satisfied every clause as written. That is the gap.

**Resolution:** `RATIFIED → C` — neither A nor B as stated. **S-009 is WITHDRAWN.**

**Because:** S-009 was self-defeating *and* redundant.

*Self-defeating:* S-014 collapses the finite band's level field to the constant 50,
so a clause that compares levels within that band compares a constant against
itself. Read literally S-009 destroyed gear selection outright; read charitably it
never fired. The spec did not say which.

*Redundant:* its intent — a gear buying no progression must not beat plain XP
grinding — is already forced in both bands.
* FINITE: a no-value gear shares the trunk's outcome, so `J = cost + C` against the
  trunk's `0 + C`. S-005 already prefers the trunk, and when the gear *does* pay for
  itself S-005 correctly prefers the gear — the case S-009 wrongly forbade.
* UNREACHABLE: same reachable level, so S-006's second key (acquisition cost)
  already prefers the trunk's zero.

S-005 and S-006 are strictly stronger, so this is not a mutually-redundant pair:
deleting S-009 alone forbids everything it forbade and nothing it should not have.

**Became:** no new clause. A withdrawal, recorded in `CERTIFICATE.md` RESIDUALS.
The `kind` field left S-002 with it, since no remaining clause reads it.

**Scenarios the implementation must satisfy** (harvest these directly):

1. *Paying gear beats the trunk.* Input above → `chosen = iron_sword`,
   `ranking = [iron_sword, trunk_xp]`. This is behaviour **A**, and it is the case
   S-009 would have broken.
2. *Worthless gear loses to the trunk, with no special clause.*
   `trunk (cost 0, level 50, cycles 900)` and `gear (cost 40, level 50, cycles 900)`
   → `chosen = trunk`, because `J` is 900 against 940. No trunk guard is consulted.
3. *Worthless gear loses in the unreachable band too.*
   `trunk (cost 0, level 17, …)` and `gear (cost 40, level 17, …)` → `chosen = trunk`
   by S-006's acquisition-cost key.
4. *Ceiling-raising gear wins in the unreachable band.*
   `trunk (cost 0, level 17)` and `gear (cost 40, level 25)` → `chosen = gear`,
   by S-006's first key, whatever the costs.
