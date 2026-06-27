# Graceful Server-Down Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the game API returns an HTML maintenance page instead of JSON, the app shows the user a readable version of that page and exits cleanly (exit code 3) instead of crashing with a `json.JSONDecodeError` traceback — for every CLI command and the bot.

**Architecture:** A single httpx **response event-hook** (installed via the `httpx_args` the generated `AuthenticatedClient` already forwards) detects a `text/html` body and raises a typed `ServerUnavailableError` carrying the extracted page text, before the generated client ever calls `.json()`. One top-level boundary (`run()`, the new console entrypoint) catches it, renders the page, exits 3. The bot's TUI worker-thread supervisor re-raises it cleanly to that boundary.

**Tech Stack:** Python 3.13 (`uv`), httpx, Typer/click, Rich, stdlib `html.parser`.

## Global Constraints

- Run every Python command via `uv run` (e.g. `uv run pytest`, `uv run python`).
- All imports at the top of the file. No inline imports. No `if TYPE_CHECKING`. No `except Exception`. No multiple implementations.
- One behavioral class per file (the HTML parser helper is a private class cohesive with its single module — allowed).
- Test-suite success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage (`--cov-fail-under` enforced).
- **No formal/Lean** for this feature — it is I/O glue + text extraction, no decision logic. Do NOT add Lean modules or run `formal/gate.sh`.
- Detection trigger is narrow: only `content-type` starting with `text/html` is treated as unavailability. A JSON error body is untouched.
- Exit code for server-unavailable is `3` (distinct from `play`'s `2` and `status`'s `1`).
- `ServerUnavailableError` is a `RuntimeError` subclass (NOT a `ValueError`), so existing per-command `except (ValueError, UnexpectedStatus, httpx.HTTPError)` handlers do not swallow it.

---

### Task 1: Foundation — `ServerUnavailableError` + `extract_readable_text`

**Files:**
- Create: `src/artifactsmmo_cli/server_unavailable_error.py`
- Create: `src/artifactsmmo_cli/maintenance_page.py`
- Test: `tests/test_maintenance_page.py`

**Interfaces:**
- Consumes: nothing (leaf modules; stdlib only).
- Produces:
  - `ServerUnavailableError(message: str, url: str)` with attributes `.page_text: str`, `.url: str`.
  - `extract_readable_text(html: str) -> str` — title + visible text, script/style dropped, entities decoded, whitespace collapsed; empty/no-text input → `""`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_maintenance_page.py`:

```python
from artifactsmmo_cli.maintenance_page import extract_readable_text
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError


def test_extracts_title_and_body():
    html = "<html><head><title>Maintenance</title></head><body><p>Back at 5pm</p></body></html>"
    assert extract_readable_text(html) == "Maintenance\nBack at 5pm"


def test_strips_script_and_style():
    html = (
        "<html><head><style>body{color:red}</style></head>"
        "<body><script>var x=1;</script><p>Down for upkeep</p></body></html>"
    )
    assert extract_readable_text(html) == "Down for upkeep"


def test_decodes_entities_and_collapses_whitespace():
    html = "<body><p>Tom   &amp;\n\n  Jerry</p></body>"
    assert extract_readable_text(html) == "Tom & Jerry"


def test_empty_input_returns_empty():
    assert extract_readable_text("") == ""


def test_body_with_only_script_returns_empty():
    assert extract_readable_text("<body><script>noise()</script></body>") == ""


def test_server_unavailable_error_carries_text_and_url():
    err = ServerUnavailableError("Maintenance", url="https://api.example.com/")
    assert err.page_text == "Maintenance"
    assert err.url == "https://api.example.com/"
    assert str(err) == "Maintenance"
    assert isinstance(err, RuntimeError)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_maintenance_page.py -v`
Expected: FAIL — `ModuleNotFoundError` for `artifactsmmo_cli.maintenance_page` / `server_unavailable_error`.

- [ ] **Step 3: Write `server_unavailable_error.py`**

```python
"""Raised when the API returns a non-JSON HTML page (server down / maintenance)."""


class ServerUnavailableError(RuntimeError):
    """The game API returned an HTML page where JSON was expected.

    Carries the human-readable text extracted from that page and the request
    URL so a single top-level handler can show the user what the server said
    and exit cleanly. A RuntimeError (not a ValueError) so the per-command
    ``except (ValueError, ...)`` handlers do not swallow it.
    """

    def __init__(self, message: str, url: str) -> None:
        super().__init__(message)
        self.page_text = message
        self.url = url
```

- [ ] **Step 4: Write `maintenance_page.py`**

```python
"""Extract human-readable text from an HTML page (e.g. a server maintenance page)."""

import re
from html.parser import HTMLParser


class _ReadableTextParser(HTMLParser):
    """Collect the <title> and visible text, skipping <script>/<style> data."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_title:
            self._title_parts.append(data)
        else:
            self._text_parts.append(data)

    def get_text(self) -> str:
        title = re.sub(r"\s+", " ", "".join(self._title_parts)).strip()
        body = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
        return "\n".join(part for part in (title, body) if part)


def extract_readable_text(html: str) -> str:
    """Return title + visible text from `html`; "" when there is none."""
    parser = _ReadableTextParser()
    parser.feed(html)
    parser.close()
    return parser.get_text()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_maintenance_page.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/server_unavailable_error.py src/artifactsmmo_cli/maintenance_page.py tests/test_maintenance_page.py
git commit -m "feat(server-down): ServerUnavailableError + HTML readable-text extraction"
```

---

### Task 2: Response hook — `detect_maintenance_response`

**Files:**
- Create: `src/artifactsmmo_cli/maintenance_detector.py`
- Test: `tests/test_maintenance_detector.py`

**Interfaces:**
- Consumes: `ServerUnavailableError`, `extract_readable_text` (Task 1).
- Produces: `detect_maintenance_response(response: httpx.Response) -> None` — an httpx response event-hook. Raises `ServerUnavailableError` on a `text/html` body; no-op otherwise.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_maintenance_detector.py`:

```python
import httpx
import pytest

from artifactsmmo_cli.maintenance_detector import detect_maintenance_response
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError

_REQ = httpx.Request("GET", "https://api.example.com/")


def _resp(content_type: str, body: bytes) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": content_type}, content=body, request=_REQ)


def test_html_body_raises_with_extracted_text():
    resp = _resp("text/html", b"<title>Maintenance</title><body>Back soon</body>")
    with pytest.raises(ServerUnavailableError) as exc:
        detect_maintenance_response(resp)
    assert exc.value.page_text == "Maintenance\nBack soon"
    assert exc.value.url == "https://api.example.com/"


def test_html_with_charset_suffix_raises():
    resp = _resp("text/html; charset=utf-8", b"<body>Down</body>")
    with pytest.raises(ServerUnavailableError):
        detect_maintenance_response(resp)


def test_json_body_is_noop():
    resp = _resp("application/json", b'{"data": {"max_level": 50}}')
    assert detect_maintenance_response(resp) is None


def test_missing_content_type_is_noop():
    resp = httpx.Response(200, content=b'{"ok": true}', request=_REQ)
    assert detect_maintenance_response(resp) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_maintenance_detector.py -v`
Expected: FAIL — `ModuleNotFoundError` for `artifactsmmo_cli.maintenance_detector`.

- [ ] **Step 3: Write `maintenance_detector.py`**

```python
"""httpx response event-hook: detect a server maintenance HTML page."""

import httpx

from artifactsmmo_cli.maintenance_page import extract_readable_text
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError


def detect_maintenance_response(response: httpx.Response) -> None:
    """Raise ServerUnavailableError when the API returns a text/html body.

    Installed as an httpx ``response`` event-hook, this fires before the
    generated client parses the body as JSON, so a non-JSON maintenance page
    surfaces as a clean typed error instead of a raw JSONDecodeError.
    """
    content_type = response.headers.get("content-type", "")
    if not content_type.lower().startswith("text/html"):
        return
    response.read()
    raise ServerUnavailableError(
        extract_readable_text(response.text), url=str(response.request.url)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_maintenance_detector.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/maintenance_detector.py tests/test_maintenance_detector.py
git commit -m "feat(server-down): httpx response hook detecting HTML maintenance pages"
```

---

### Task 3: Install the hook in `ClientManager`

**Files:**
- Modify: `src/artifactsmmo_cli/client_manager.py:33-40` (the `AuthenticatedClient(...)` construction)
- Test: `tests/test_client_manager.py`

**Interfaces:**
- Consumes: `detect_maintenance_response` (Task 2).
- Produces: every client built by `ClientManager` carries the response hook.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_client_manager.py` (import `detect_maintenance_response` at the top of the test file):

```python
def test_client_has_maintenance_response_hook():
    from artifactsmmo_cli.client_manager import ClientManager
    from artifactsmmo_cli.config import Config
    from artifactsmmo_cli.maintenance_detector import detect_maintenance_response

    manager = ClientManager()
    manager.initialize(Config(token="t", api_base_url="https://api.example.com", timeout=5))
    hooks = manager.client.get_httpx_client().event_hooks["response"]
    assert detect_maintenance_response in hooks
```

(If `Config`'s constructor signature differs, mirror the construction the existing tests in this file already use — keep the test's Config build consistent with its neighbours.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client_manager.py::test_client_has_maintenance_response_hook -v`
Expected: FAIL — `KeyError: 'response'` or the hook missing.

- [ ] **Step 3: Add the hook to the client construction**

In `src/artifactsmmo_cli/client_manager.py`, add the import at the top:

```python
from artifactsmmo_cli.maintenance_detector import detect_maintenance_response
```

Change the `AuthenticatedClient(...)` call to pass `httpx_args`:

```python
self._client = AuthenticatedClient(
    base_url=config.api_base_url,
    token=config.token,
    # AuthenticatedClient declares `Timeout | None`; wrap the int config
    # value explicitly (httpx.Timeout(int) is the canonical form).
    timeout=httpx.Timeout(config.timeout),
    raise_on_unexpected_status=False,
    httpx_args={"event_hooks": {"response": [detect_maintenance_response]}},
)
```

- [ ] **Step 4: Run the test + the full client-manager suite**

Run: `uv run pytest tests/test_client_manager.py -v`
Expected: PASS (the new test + all existing tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/client_manager.py tests/test_client_manager.py
git commit -m "feat(server-down): install maintenance-detection hook on the API client"
```

---

### Task 4: CLI boundary — `run()` entrypoint renders + exits 3

**Files:**
- Modify: `src/artifactsmmo_cli/main.py` (add imports, `SERVER_UNAVAILABLE_EXIT_CODE`, `_render_server_unavailable`, `run`; update `__main__`)
- Modify: `pyproject.toml:30` (script target `main:app` → `main:run`)
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `ServerUnavailableError` (Task 1), the existing module-level `console` and `format_error_message`.
- Produces: `run() -> None` — the console entrypoint; `SERVER_UNAVAILABLE_EXIT_CODE = 3`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_main.py`:

```python
def test_run_renders_and_exits_on_server_unavailable(monkeypatch, capsys):
    import pytest
    from artifactsmmo_cli import main as main_mod
    from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError

    def _boom():
        raise ServerUnavailableError("Down for maintenance", url="https://api.example.com/")

    monkeypatch.setattr(main_mod, "app", _boom)
    with pytest.raises(SystemExit) as exc:
        main_mod.run()
    assert exc.value.code == main_mod.SERVER_UNAVAILABLE_EXIT_CODE == 3
    out = capsys.readouterr().out
    assert "Down for maintenance" in out
    assert "https://api.example.com/" in out


def test_run_passes_through_on_normal_exit(monkeypatch):
    from artifactsmmo_cli import main as main_mod

    monkeypatch.setattr(main_mod, "app", lambda: None)
    main_mod.run()  # no exception, no SystemExit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main.py::test_run_renders_and_exits_on_server_unavailable tests/test_main.py::test_run_passes_through_on_normal_exit -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'run'`.

- [ ] **Step 3: Add the boundary to `main.py`**

Add imports at the top of `src/artifactsmmo_cli/main.py` (with the existing imports):

```python
import sys
```
and:
```python
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError
```

Add near the top-level definitions (after `console = Console()`):

```python
SERVER_UNAVAILABLE_EXIT_CODE = 3


def _render_server_unavailable(exc: ServerUnavailableError) -> None:
    console.print(format_error_message(
        "ArtifactsMMO server is unavailable — it returned a maintenance page:"))
    page = exc.page_text.strip()
    console.print(page if page else "(the server returned an HTML page with no readable text)")
    console.print(f"[dim]{exc.url}[/dim]")


def run() -> None:
    """Console entrypoint: the single boundary that turns a server maintenance
    page into a clean rendered message + non-zero exit instead of a traceback."""
    try:
        app()
    except ServerUnavailableError as exc:
        _render_server_unavailable(exc)
        sys.exit(SERVER_UNAVAILABLE_EXIT_CODE)
```

Update the bottom of the file:

```python
if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Repoint the console script**

In `pyproject.toml`, change line 30:

```toml
artifactsmmo = "artifactsmmo_cli.main:run"
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS (new tests + existing).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/main.py pyproject.toml tests/test_main.py
git commit -m "feat(server-down): run() boundary renders maintenance page, exits 3"
```

---

### Task 5: Bot path — `play` exits clean on `ServerUnavailableError`

**Files:**
- Modify: `src/artifactsmmo_cli/commands/play.py` (add import; `except ServerUnavailableError` in `play()`; classify it in the TUI `_bot_excepthook` and the `if crashes:` block)
- Test: `tests/test_commands/test_play.py` (the existing play tests; if absent, create it)

**Interfaces:**
- Consumes: `ServerUnavailableError` (Task 1). Relies on `run()` (Task 4) to do the actual rendering — `play()` only classifies the exit and re-raises so it reaches `run()`.
- Produces: bot exits cleanly (no "crashed"/traceback framing) on a maintenance page; session `exit_reason="server_unavailable"`.

- [ ] **Step 1: Write the failing test (non-TUI path)**

Add to `tests/test_commands/test_play.py` (create the file with the standard test header if it does not exist). This test drives `play()` with the bot raising `ServerUnavailableError` and asserts it propagates with the honest exit reason:

```python
def test_play_propagates_server_unavailable_with_reason(monkeypatch):
    import pytest
    from artifactsmmo_cli.commands import play as play_mod
    from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError

    recorded = {}

    class _FakeStore:
        def start_session(self): ...
        def end_session(self, exit_reason): recorded["reason"] = exit_reason
        def close(self): ...

    class _FakePlayer:
        def __init__(self, *a, **k): ...
        def run(self): raise ServerUnavailableError("Down", url="https://api.example.com/")

    monkeypatch.setattr(play_mod, "GamePlayer", _FakePlayer)
    monkeypatch.setattr(play_mod, "LearningStore", lambda *a, **k: _FakeStore())
    monkeypatch.setattr(play_mod.Config, "from_token_file", classmethod(lambda cls: _cfg()))

    with pytest.raises(ServerUnavailableError):
        play_mod.play(character="Robby", tui=False)
    assert recorded["reason"] == "server_unavailable"
```

Where `_cfg()` returns a minimal config object with the attributes `play()` reads (`game_data_ttl_minutes`, etc.). Mirror whatever construction the existing `test_play.py` tests already use for `Config`; if none exist, build a `types.SimpleNamespace(game_data_ttl_minutes=30)` and pass the `play()` arguments that avoid the learn/trace branches (`learn=False`, `trace=False`, `dry_run=True`).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_commands/test_play.py::test_play_propagates_server_unavailable_with_reason -v`
Expected: FAIL — `exit_reason` recorded as `"crash"`, not `"server_unavailable"`.

- [ ] **Step 3: Add the classification to `play.py`**

Add the import at the top of `src/artifactsmmo_cli/commands/play.py`:

```python
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError
```

In `play()`, add an `except` clause BEFORE the `except StuckExit` clause (so the more specific clean-stop classification runs); it re-raises so `run()` renders and exits 3:

```python
    except ServerUnavailableError:
        # Server returned a maintenance page. run() (the console entrypoint)
        # renders it and exits 3; here we only record the honest exit reason.
        exit_reason = "server_unavailable"
        raise
```

In `_run_with_tui`'s `_bot_excepthook`, extend the clean-stop message branch:

```python
        if isinstance(hook_args.exc_value, StuckExit):
            message = f"Bot stopped: {hook_args.exc_value}"
        elif isinstance(hook_args.exc_value, ServerUnavailableError):
            message = "Server unavailable — stopping bot."
        else:
            message = f"Bot worker thread crashed: {hook_args.exc_value!r}"
```

In `_run_with_tui`'s `if crashes:` block, add a clean branch (no traceback dump — `run()` renders):

```python
    if crashes:
        if isinstance(crashes[0], StuckExit):
            print(f"Bot for {character!r} stopped: {crashes[0]}")
        elif isinstance(crashes[0], ServerUnavailableError):
            # Clean stop: run() renders the maintenance page and exits 3.
            pass
        else:
            print(f"Bot worker thread for {character!r} crashed; traceback:")
            traceback.print_exception(crashes[0])
        raise crashes[0]
```

- [ ] **Step 4: Write the TUI-classification test**

Add a test covering the two new TUI branches. Mirror the existing `_run_with_tui` crash test in `test_play.py` (it simulates a worker exception). If the file has such a helper, reuse it with a `ServerUnavailableError`; assert the `_bot_excepthook` records it and the `if crashes:` branch re-raises WITHOUT calling `traceback.print_exception`. Concretely, drive the supervisor by invoking `_bot_excepthook` with a fabricated `threading.ExceptHookArgs` whose `exc_value` is a `ServerUnavailableError` and `thread is bot_thread`, then assert the recorded `crashes[0]` is that error. (Follow the construction the neighbouring crash test already uses; do not invent a new harness if one exists.)

- [ ] **Step 5: Run the play tests**

Run: `uv run pytest tests/test_commands/test_play.py -v`
Expected: PASS (new tests + existing).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/commands/play.py tests/test_commands/test_play.py
git commit -m "feat(server-down): bot exits clean on maintenance page (exit_reason=server_unavailable)"
```

---

### Task 6: Whole-feature verification

**Files:** none (verification; commit only if a coverage gap needs a test)

- [ ] **Step 1: Full suite with coverage**

Run: `uv run pytest`
Expected: 0 failures, 0 warnings, 0 skipped, 100% coverage — including the 3 new modules and every new branch in `main.py`/`play.py`. If a new branch is uncovered, add a focused test (mirror the patterns in Tasks 4–5) and commit as `test(server-down): cover <branch>`.

- [ ] **Step 2: Confirm the entrypoint resolves**

Run: `uv run artifactsmmo --help`
Expected: the CLI help prints (confirms `main:run` is a valid entrypoint and `run` does not break normal invocation — `app()` runs, `--help` exits 0 via click's own SystemExit, which `run()` does not catch).

- [ ] **Step 3: Live smoke test (server currently returning HTML)**

Run: `uv run artifactsmmo status; echo "exit=$?"`
Expected (while the server serves the HTML page): a rendered maintenance message (the extracted page text) + the URL, then `exit=3` — NO `JSONDecodeError` traceback. (When the server is healthy again this prints the normal status instead; either way, no traceback.)

---

## Self-Review

**Spec coverage:**
- `ServerUnavailableError` (spec §Components 1) → Task 1. ✅
- `extract_readable_text` (§2) → Task 1. ✅
- `detect_maintenance_response` hook (§3) → Task 2. ✅
- `client_manager` `httpx_args` wiring (§4) → Task 3. ✅
- `run()` boundary + render + pyproject + exit 3 (§5) → Task 4. ✅
- Bot path / TUI re-raise / `exit_reason` (§6) → Task 5. ✅
- Narrow `text/html` trigger, charset suffix tolerated → Task 2 tests. ✅
- `status` behavior-change note → covered by the uniform boundary (Task 4); no separate task needed. ✅
- 100% coverage, no formal → Task 6 + Global Constraints. ✅

**Placeholder scan:** No TBD/TODO/"add error handling". Every code step shows complete code. The two places that say "mirror the existing test construction" (Config build in Tasks 3/5) are deliberate — they defer to real fixtures the implementer can read, not vague placeholders; exact attribute names depend on the existing `Config`/test helpers in the repo.

**Type consistency:** `ServerUnavailableError(message, url)` with `.page_text`/`.url`; `extract_readable_text(html)->str`; `detect_maintenance_response(response)->None`; `run()->None`; `SERVER_UNAVAILABLE_EXIT_CODE=3`; `exit_reason="server_unavailable"` — names identical across Tasks 1–5.
