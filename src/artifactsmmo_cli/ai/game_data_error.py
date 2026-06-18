"""Game-data parser-coverage failure."""


class GameDataCoverageError(RuntimeError):
    """A loaded game-data record carries an effect code the parser neither maps
    to a modeled stat nor explicitly carves out.

    Raising here — instead of silently dropping the code — is the parser-coverage
    guard from ``docs/PLAN_game_modeling_roadmap.md``: the effect parser is an
    allowlist, and an unlisted code used to vanish, silently corrupting
    predict_win / valuation (the wisdom/prospecting/haste/lifesteal class of
    bugs). With the guard, a new server-side effect can no longer slip through
    unmodeled — it fails loudly at load, naming the record and the code, so it is
    either mapped or added to a documented carve-out before the bot trusts it.
    """
