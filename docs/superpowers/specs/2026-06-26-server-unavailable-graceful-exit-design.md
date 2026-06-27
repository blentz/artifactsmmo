# Graceful Server-Down Handling — Design

**Status:** approved (brainstorm 2026-06-26)
**Trigger:** The live game API (`https://api.artifactsmmo.com`) began returning an
HTML maintenance/landing page (HTTP 200, `content-type: text/html`) on its
endpoints. The generated API client parses every body as JSON, so any live call
raises a raw `json.JSONDecodeError` ("Expecting value: line 1 column 1") that
escapes to the terminal as an unhandled traceback (seen from CLI commands and the
`play` bot). Group A already hardened the *test* for this; this work hardens the
*application*.

## Goal

When the server returns a non-JSON HTML page, the app shows the user a readable
version of that page and exits cleanly (non-zero), instead of crashing with a
`JSONDecodeError` traceback. Covers every CLI command AND the long-running bot.

## Approach (chosen)

**One detection point, one catch boundary.**

- **Detect** at the transport: a single httpx **response event-hook** attached to
  the client the `ClientManager` builds. The generated `AuthenticatedClient`
  accepts `httpx_args` (a dict forwarded verbatim to the `httpx.Client`
  constructor — confirmed in `artifactsmmo-api-client/.../client.py`), so
  `httpx_args={"event_hooks": {"response": [detect_maintenance_response]}}` installs
  the hook for every request. The hook fires when the response is received,
  *before* the generated client's `_parse_response` calls `.json()`, so the raw
  `JSONDecodeError` is preempted.
- **Catch** at one boundary: a new `run()` entrypoint wrapping the Typer `app()`.

Rejected alternatives: wrapping each `APIWrapper` method (per-method churn);
catching `JSONDecodeError` in each command (multiple levels of error handling —
violates CLAUDE.md "Multiple levels of error handling is always a bug").

## Components (one responsibility per file)

### 1. `src/artifactsmmo_cli/server_unavailable_error.py`
```python
class ServerUnavailableError(RuntimeError):
    """The API returned a non-JSON HTML page (server down / maintenance).

    Carries the human-readable text extracted from that page and the request URL.
    """
    def __init__(self, message: str, url: str) -> None:
        super().__init__(message)
        self.page_text = message
        self.url = url
```
A `RuntimeError` subclass (NOT a `ValueError`), so it is NOT swallowed by the
existing per-command `except (ValueError, UnexpectedStatus, httpx.HTTPError)`
handlers — it propagates to the single boundary.

### 2. `src/artifactsmmo_cli/maintenance_page.py`
Pure, dependency-free text extraction (stdlib `html.parser` only):
```python
def extract_readable_text(html: str) -> str:
    """Extract human-readable text from an HTML page.

    Drops <script>/<style> content, captures the <title> and visible text,
    decodes entities, collapses runs of whitespace/blank lines. Returns a
    compact multi-line string. Empty input or a body with no visible text
    returns "" (the caller supplies a fallback line)."""
```
Implementation: an `HTMLParser` subclass that tracks whether it is inside
`script`/`style` (skip their data), collects the `<title>` separately, and
accumulates `handle_data` text elsewhere; whitespace is collapsed and blank lines
de-duplicated at the end. No new behavioral class escapes the module — the parser
subclass is a private helper of this function's module (one cohesive unit).

### 3. `src/artifactsmmo_cli/maintenance_detector.py`
```python
def detect_maintenance_response(response: httpx.Response) -> None:
    """httpx response event-hook: raise ServerUnavailableError on an HTML body."""
```
- Reads `response.headers.get("content-type", "")`. If it does NOT start with
  `text/html` (case-insensitive, ignoring any `; charset=...`), return (no-op —
  normal `application/json` responses cost only a header read).
- Otherwise `response.read()` (sync hook; body not yet consumed by the caller),
  extract text, and `raise ServerUnavailableError(extract_readable_text(text) or "",
  url=str(response.request.url))`.

### 4. `src/artifactsmmo_cli/client_manager.py` (modify)
Add the hook to the client construction:
```python
self._client = AuthenticatedClient(
    base_url=config.api_base_url,
    token=config.token,
    timeout=httpx.Timeout(config.timeout),
    raise_on_unexpected_status=False,
    httpx_args={"event_hooks": {"response": [detect_maintenance_response]}},
)
```

### 5. `src/artifactsmmo_cli/main.py` (modify) + `pyproject.toml` (modify)
New entrypoint wrapping the app — the single CLI boundary:
```python
def run() -> None:
    try:
        app()
    except ServerUnavailableError as exc:
        _render_server_unavailable(exc)   # console.print of the extracted page
        sys.exit(SERVER_UNAVAILABLE_EXIT_CODE)  # = 3
```
`_render_server_unavailable` prints a short header (e.g. "ArtifactsMMO server is
unavailable — it returned a maintenance page:") followed by `exc.page_text` (or a
fixed fallback line if the page had no extractable text), then the URL.
`pyproject.toml`: `[project.scripts] artifactsmmo = "artifactsmmo_cli.main:run"`
(was `:app`). The Typer callback already named `main` (main.py:44) is unaffected —
the new function is `run`.

### 6. `src/artifactsmmo_cli/commands/play.py` (modify)
The bot must also exit clean (user decision: exit, do not retry).
- Non-TUI path (`player.run()`): `ServerUnavailableError` already propagates out of
  `play()` (its `except` only catches `StuckExit`/`KeyboardInterrupt`) up to
  `run()`. No change needed beyond ensuring `play()` does not relabel it.
- TUI path: the worker-thread `_bot_excepthook` records the exception in `crashes`
  and re-raises it on the main thread after Textual teardown. Special-case
  `ServerUnavailableError` like `StuckExit` (a deliberate, non-"crash" stop): clean
  teardown message, set `exit_reason` to `"server_unavailable"` (not `"crash"`),
  and re-raise so it reaches `run()`. The rendering still happens once, at `run()`.

## Data flow

```
any API call → httpx receives HTTP 200 text/html
  → response hook detect_maintenance_response fires (before .json())
  → raises ServerUnavailableError(extracted_text, url)
  → propagates up through the generated client + APIWrapper + command/bot
  → caught once at run()  (TUI bot: via the worker re-raise → run())
  → _render_server_unavailable prints the page → sys.exit(3)
```

## Error handling / safety (CLAUDE.md)

- **One level of error handling:** the hook RAISES (does not handle); exactly one
  boundary (`run()`) handles. The bot's TUI re-raise is plumbing, not a second
  handler — it forwards to `run()`.
- **No `except Exception`:** the boundary catches the specific
  `ServerUnavailableError`. The hook catches nothing.
- **Narrow trigger:** only `content-type: text/html` is treated as
  unavailability. A JSON error body (5xx with `application/json`) is untouched and
  still flows through `UnexpectedStatus`/existing handling.
- **Behavior change to note:** the `status` command previously caught the
  `JSONDecodeError` (a `ValueError`) and printed "API connection failed: Expecting
  value…". With the hook, that branch no longer fires for the HTML case; `status`
  now renders the maintenance page and exits 3 via `run()`. This is the desired
  uniform behavior. The `status` `except (ValueError, …)` stays (still catches
  other value errors) — not dead in general.

## Testing

Unit tests, 100% coverage, no formal/Lean (I/O glue + text extraction, no decision
logic — no provable core):
- `tests/.../test_maintenance_page.py`: `extract_readable_text` — title+body, script
  & style stripped, HTML entities decoded, whitespace/blank-line collapse, empty
  input → "", body with only script/style → "".
- `tests/.../test_maintenance_detector.py`: hook with a `text/html` `httpx.Response`
  → raises `ServerUnavailableError` with the extracted text and URL; with
  `application/json` → no raise, body untouched; with `text/html; charset=utf-8`
  → raises (charset suffix tolerated); missing content-type → no raise.
- `tests/.../test_server_unavailable_boundary.py`: `run()` with `app()` patched to
  raise `ServerUnavailableError` → renders the page text and `sys.exit(3)`; normal
  `app()` return → exit 0, no render.
- `play.py` bot path: `_bot_excepthook` / crashes re-raise classifies
  `ServerUnavailableError` as `server_unavailable` (clean), not `crash`.
- Update existing `client_manager` construction test to expect the new `httpx_args`.

## Known limits / non-goals

- No retry/back-off — the bot exits on maintenance (user decision); restart when the
  server returns.
- Detection is content-type based. A server returning malformed JSON with an
  `application/json` content-type is out of scope (still surfaces as today's
  `JSONDecodeError`/`UnexpectedStatus`) — that is a server contract violation, not a
  maintenance page, and is not what this addresses.
- Exit code `3` is the dedicated "server unavailable" code (play=2, status=1).
