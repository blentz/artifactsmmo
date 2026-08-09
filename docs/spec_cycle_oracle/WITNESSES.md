# Witness ledger — <project>

Every resolved distinguishing pair, in the order they were ratified.

**This file is the acceptance suite.** Not a log, not a record of what happened — the
source the harness harvests from. Each witness already carries a concrete input, two
candidate outputs, and the answer the spec author chose. That *is* a test:

```gherkin
Given  <distinguishing_input>
When   the system runs
Then   <ratified>            # and NOT <rejected>, which an uncertified impl would do
```

You do not author the acceptance suite. You harvest it. So write these entries as
**executable facts**, not as prose about a discussion. If a reader cannot turn an
entry into a passing test without asking a question, the entry is not done.

Two rules that keep the ledger honest:

- **Ids are permanent.** `W-004` is cited by a clause, by a scenario, and by the grid.
  Never renumber, never reuse.
- **A witness is never deleted.** A witness the author decided is a *don't-care* is
  resolved as `DON'T-CARE` and stays in the ledger — it is a carve-out, and carve-outs
  go on the record. Deleting it would hide a decision that was actually made.
