# Deadline Survivor — Project Context for Claude Code

## What is this project?
A lightweight Windows background utility that intercepts the OS clipboard to:
1. **Repair broken text formatting** (e.g., broken line breaks from PDFs) via LLM
2. **Translate text** via LLM
Then instantly pastes the processed text into the active window.

## Current Status: v1.3 — "Multi-Engine" (feature-complete)
- Multi-provider LLM layer + Engine UI + Tray pulse + Token cost +
  Streaming output all shipped. All originally-planned v1.3 items
  done; remaining backlog explicitly deferred to v1.4+.
- 140 unit tests passing.
- v1.3 changelog (this release):
  - **Provider abstraction**: `ai/providers/` package — `LLMProvider` ABC +
    concrete `GroqProvider` (uses `groq` SDK) + `OpenAICompatProvider` (raw
    httpx → `/v1/chat/completions`, one impl serves OpenAI / DeepSeek / Kimi /
    GLM / Qwen / SiliconFlow / any custom OpenAI-compatible host).
    Selectable via `settings.json["active_provider"]`; per-provider config
    lives under `settings.json["providers"][<id>]`. Adding a host = one
    entry in `ai/providers/registry.py:PROVIDERS`.
  - **Unified errors** (`ai/providers/errors.py`): `AuthError` /
    `RateLimitError` / `ServerError` / `ConnectionError` /
    `ProviderTimeoutError`. The last subclasses built-in `TimeoutError` so
    `core/worker.py`'s `except TimeoutError:` fallback path keeps working
    unchanged.
  - **`ai/llm_client.py`** is the new singleton entry. Old
    `from ai.groq_client import groq_client` still works — `groq_client.py`
    is now a thin shim re-exporting `groq_client = llm_client`. New code
    should `from ai.llm_client import llm_client`. Old `_call_api` private
    method is now `chat_raw` (public, used by Tasks page LIVE TEST).
  - **Test Connection**: each provider has `test_connection(model, timeout)`
    returning `TestConnectionResult(ok, rtt_ms, model, error_kind, detail,
    prompt_tokens, completion_tokens)`. Wired via
    `llm_client.test_connection(...)` and used by Engine page TEST button.
  - **Schema migration**: `core/tasks.migrate_settings()` auto-upgrades v1.2
    settings — top-level `groq_api_key` / `groq_model` /
    `api_timeout_seconds` lifted into `providers.groq.*`; 8 provider stubs
    seeded so every host appears in the picker on fresh installs. Legacy
    keys NOT deleted (v1.2 downgrade safety).
  - **Engine page UI** (`ui/engine_page.py`, ~870 LOC) per Claude Design v3:
    `ProviderTile` (4×2 frosted-glass picker, 4 visual states, all-paintEvent
    to dodge ghost-shadow paths) + `ConfigCard` (API Key + Base URL + Model
    + Timeout) + `TestPanel` "diagnostic theatre" (idle / probing /
    success / error × 4 codes — auth / rate_limit / network / timeout /
    server) + `_TestConnectionWorker(QThread)`. Tile width is fluid via
    `setColumnStretch + setMinimumWidth(140) + Expanding` so the 4-tile
    row fits inside the 900px settings dialog without horizontal overflow.
    Custom `_ChevronComboBox` (paintEvent-drawn arrow) replaces Qt's
    default down-arrow, which renders as a black square under our QSS.
  - **Tray pulse status strip** (`ui/tray_icon.py`): new `_PulseStrip`
    (320×38, `[●] Provider [sparkline×15] 87ms`) inserted at the very top
    of the tray menu via `QWidgetAction`. Below it: existing
    `_TelemetryHeader` for cumulative `OPS TODAY / AVG / $ TODAY` (the
    third column was `SAVED` chars in v1.2 — replaced by `$ TODAY` cost
    since cost is more actionable than chars-saved vanity metric).
    `menu.aboutToShow` refreshes both. Pulse strip pulls provider name
    from `llm_client.effective_config()` and sparkline from
    `telemetry.snapshot()['samples']`. Defensive against upstream
    exceptions (tray must never crash — it's the only re-entry point).
  - **Token / cost estimation** (`ai/pricing.py`, ~190 LOC): per-provider /
    per-model price table (USD per million tokens, with `_cny()` for CNY-
    quoted providers using a single 7.30 RMB/USD constant). `estimate_cost()`
    uses longest-substring matching (`"llama-3.1-8b"` catches every
    `-instant`/`-instruct` variant). Format helpers split between tray
    (`format_cost_short`: `$0.08`/`<$0.01`), TestPanel per-probe
    (`format_cost_per_probe`: `≈ $0.000016`), and TestPanel projection
    (`project_cost_per_1k`: `≈ $0.016`). Data flow: provider chat already
    returns `prompt_tokens`/`completion_tokens` → `llm_client._call_provider`
    computes cost → side-channel `llm_client.last_usage` (new
    `LastUsage` dataclass, doesn't change `run_task` return signature →
    no caller/shim breaks) → `main.py._on_worker_success` reads it →
    `telemetry.record_op(..., cost_usd, prompt_tokens, ...)` → snapshot
    exposes `today_cost`/`total_cost`/`total_tokens`. **Unknown models
    (custom endpoints) are excluded from cumulative totals** so unknown-
    price use never silently inflates the dollar figure. UI distinguishes
    "free" (`is_estimate=True` + price 0, e.g. GLM-4-flash) from "unknown"
    (`is_estimate=False` → `—` + "(model not in pricing table)").
  - **`supports_vision` metadata**: `ProviderSpec.supports_vision: bool`
    True for OpenAI / GLM / Qwen / SiliconFlow / Custom. **No code reads
    it yet** — pure forward-prep for v1.4 vision mode (model dropdown
    filter / 📷 badge / image clipboard handling).
  - **Real-machine bug fixes** (2026-05-11):
    - Multiple v1.2 string leftovers (About page version, hero toast
      defaults, startup log, pitch text) all bumped to v1.3.
    - First-run dialog now writes the v1.3 multi-provider schema (was
      writing v1.2 flat schema). Welcome blurb provider-agnostic.
    - Engine page horizontal scrollbar disabled + vertical re-styled.
    - QComboBox model dropdown arrow re-painted via subclass.
    - **Duplicate BUILTIN badge bug**: `QListWidget.setItemWidget(item,
      new)` doesn't reliably delete the old widget across all Qt /
      Windows / DPI combos — leaked old `_TaskRow` widgets eventually
      bled their BUILTIN labels around the new widget on user machines.
      `tasks_page._refresh_row` and `reload()` now explicitly
      `removeItemWidget` + `setParent(None)` + `deleteLater()` before
      registering the new row widget.
  - **Streaming output** (opt-in via `STREAM OUTPUT` Engine-page checkbox;
    persisted as `settings.streaming_enabled`). New
    `LLMProvider.chat_stream(..., on_chunk: StreamCallback) -> ChatResult`
    interface — `StreamCallback` returns True to keep going, False to
    cancel. GroqProvider uses the SDK's `stream=True`; OpenAICompatProvider
    parses raw httpx SSE (`iter_lines` over `data: <json>` events with
    `data: [DONE]` terminator). Token usage piggybacks on the final chunk
    via `stream_options.include_usage` so cost telemetry still works.
    `ClipboardWorker` accepts a `streaming` flag + emits a `chunk` signal
    (queued connection → main thread). Default fallback: base class
    `chat_stream` calls `chat()` once and emits the whole text — providers
    without real streaming still satisfy the contract.
    Cancellation: `worker.request_cancel()` flips a flag → next on_chunk
    returns False → provider closes the stream → worker pastes original
    text (same as timeout path; the clipboard never receives a half-formed
    response — that's a hard invariant).
  - **v4 streaming UI — phrase cycler** (design v4 handoff, supersedes the
    initial "tail-truncated 240-char body" approach): the streaming Toast
    now owns the buffer + commit rules. main.py's `_dispatch` snapshots
    `llm_client.streaming_enabled` and `_on_worker_chunk` forwards each
    raw fragment via `toast_manager().feed_chunk(fragment)` — NO string
    concat in main.py. The Toast (with `streaming=True`) wraps a
    `_PhraseStack` widget that vertically cycles committed phrases, a
    `_GhostLine` showing the un-committed buffer tail, and a telemetry
    row (`{phrases} phrase · {tokens} tok · {rate} t/s`, refreshed by a
    200ms timer). Commit rules live in **`ui/phrase_commit.py`**
    (Qt-free, unit-testable): R1 Latin sentence terminator + whitespace,
    R2 ≥6 whole words, R3 CJK fallback at last CJK punct or 24-char mark.
    `end_streaming(cancelled=False)` flushes the trailing buffer as one
    final phrase (RACE edge case); `cancelled=True` drops it (timeout /
    error / user cancel). `update_streaming(text)` kept as back-compat
    shim that just calls `feed_chunk(text)`.
- Explicitly deferred to v1.4+: Anthropic / Claude, Ollama, keyring /
  encrypted key storage, per-task model override, settings export/import,
  command-palette provider switch, quota bar (per-provider rate-limit
  signals not unified), Tasks-page per-task audit column, toast cost
  threshold alerts.

## v1.1 — "Bulletproof" Update (carried forward)
- All core features working, packaged as single-file .exe via PyInstaller
- v1.1 changelog (this release):
  - **Clipboard history & restore**: pre-AI snapshot pushed to a 10-slot in-memory deque on every dispatch. Tray menu adds `↶ Restore Last Original (N)` — pop semantics, repeated clicks walk back through history. Never persisted to disk (clipboard may hold secrets). See `core/history.py`.
  - **Atomic SendInput paste**: `core/clipboard_handler.paste()` now uses `SendInput` + `KEYEVENTF_SCANCODE` instead of `keybd_event`. Bypasses IME hooks (scan codes are processed below the VK translation layer) and fixes the long-standing "Ctrl+Shift+C accidentally toggles input method" bug. Includes `GetAsyncKeyState`-based stuck-modifier cleanup before injection (Shift/Alt/Win force-released to prevent the Ctrl+V from being misread as Ctrl+Shift+V). UIPI failures fall back to legacy `keybd_event`.
  - **Auto Ctrl+C**: `_dispatch()` now calls `core.clipboard_handler.copy_selection()` before `read()`. Users can press Ctrl+Shift+C/T directly on a text selection without first doing Ctrl+C. Reuses the same chord-injection helper as paste, with the same modifier cleanup so it can't trigger our own hotkey.
  - **Settings feedback fixes**:
    - `_mock_translate` now embeds the current target language in its label (e.g. `[Mock · target=French]`). Previously hardcoded `[已翻译·演示模式]` made language switches invisible in DEBUG_MODE.
    - `groq_client.effective_config()` exposes a runtime config snapshot (key prefix, model, target lang, debug state).
    - "Settings applied" toast shows the effective config (`key=gsk_xxx…ABC`, model, target). Closes the "I changed the API key but it didn't work" feedback gap.
    - `reload_settings()` logs key prefix + length so users can confirm from logs that a new key actually loaded.
- v1.0 baseline (still in effect): **Bring Your Own Key** — shipped exe no longer contains `.env`. First launch shows BYOK welcome dialog with link to console.groq.com/keys, or skip into DEBUG_MODE.
- Known limitation (deferred): no support for non-Groq providers. Acceptable for the school demo.

## Architecture

```
ent2/
├── main.py                  ← Entry point, AppController, Qt signal bridge.
│                              _on_worker_success reads llm_client.last_usage
│                              and pipes cost into telemetry.
├── ai/
│   ├── llm_client.py        ← v1.3 unified singleton `llm_client`. Picks
│   │                          active provider; tracks `last_usage` after
│   │                          every chat for cost telemetry.
│   │                          Exposes `run_task_streaming(task, text, on_chunk)`
│   │                          when `streaming_enabled`.
│   ├── groq_client.py       ← v1.3 compat shim (re-exports `groq_client = llm_client`)
│   ├── pricing.py           ← v1.3 per-provider/model price table + estimate_cost()
│   └── providers/
│       ├── base.py          ← LLMProvider ABC, ChatResult, TestConnectionResult
│       │                      (TestConnectionResult carries token counts)
│       ├── errors.py        ← AuthError / RateLimitError / ServerError / ProviderTimeoutError
│       ├── registry.py      ← PROVIDERS spec list + build_provider().
│       │                      ProviderSpec.supports_vision (forward-prep, no readers yet)
│       ├── groq.py          ← GroqProvider (groq SDK)
│       └── openai_compat.py ← OpenAICompatProvider (httpx → /v1/chat/completions)
├── core/
│   ├── clipboard_handler.py ← read() / write() / paste() / copy_selection() via SendInput + scan codes
│   ├── history.py           ← ClipboardHistory: in-memory deque(10) of pre-AI snapshots (v1.1)
│   ├── hotkey_listener.py   ← RegisterHotKey + hidden window message loop (daemon thread)
│   ├── tasks.py             ← Task dataclass + migrate_settings (v1.1→v1.3 schema migration)
│   └── worker.py            ← QThread worker for async API calls;
│                              v1.3 streaming mode + chunk signal + request_cancel()
├── ui/
│   ├── engine_page.py       ← v1.3 Engine page (provider grid + ConfigCard + TestPanel + worker)
│   ├── tray_icon.py         ← QSystemTrayIcon. v1.3 _PulseStrip + _TelemetryHeader (with $ TODAY)
│   ├── settings_dialog.py   ← Settings dialog shell — hosts engine_page / tasks_page / about
│   ├── tasks_page.py        ← Tasks page (with v1.3 widget-leak fix in _refresh_row / reload)
│   ├── toast.py             ← Toast system. v1.3 streaming mode: _PhraseStack + _GhostLine
│   │                          + telemetry row + 200ms t/s timer. feed_chunk(fragment) is the
│   │                          new streaming contract (toast owns buffer + commit rules).
│   ├── phrase_commit.py     ← v1.3 v4 phrase-cycler commit rules (R1/R2/R3). Qt-free,
│   │                          unit-tested. No PyQt5 dep so test_streaming.py can import it.
│   └── first_run_dialog.py  ← BYOK welcome dialog (v1.3: writes providers schema)
├── utils/
│   ├── logger.py            ← RotatingFileHandler, handles PyInstaller + GBK terminal
│   └── telemetry.py         ← Per-op rolling log; v1.3 records cost_usd + tokens
├── tests/                   ← unittest suite (140 tests as of v1.3 v4)
├── settings.json            ← Runtime config (v1.3 schema: active_provider + providers block)
├── telemetry.json           ← Rolling op log (auto-written; not user-edited)
├── .env                     ← GROQ_API_KEY (dev-mode fallback for groq provider only)
├── build.spec               ← PyInstaller onefile config
├── start.bat                ← Double-click launcher for development
└── dist/                    ← Packaged exe + README + .env + settings.json
```

## Threading Model (CRITICAL — do not break this)
```
Main Thread (Qt event loop)
├── QApplication.exec_()
├── TrayIcon (system tray, menus, toast notifications)
├── SettingsDialog (modal dialog)
└── ClipboardWorker (QThread — API calls here, NOT on main thread)

Daemon Thread
└── HotkeyListener (Win32 message loop via ctypes, NOT keyboard library)
```
- Hotkey fires in daemon thread → Qt signal (thread-safe) → main thread
- Main thread reads clipboard → starts QThread worker
- Worker calls Groq API → writes clipboard → simulates Ctrl+V → signals done

## Tech Stack & Constraints
- **Python 3.14** (user's environment)
- **PyQt5** for UI (main thread only, all UI ops)
- **ctypes + RegisterHotKey** for global shortcuts (no admin needed, no `keyboard` lib)
- **LLM**: pluggable via `ai/providers/`. Default = Groq (`llama-3.1-8b-instant`).
  Other supported: OpenAI / DeepSeek / Kimi / GLM / Qwen / SiliconFlow / Custom
  (any OpenAI-compatible host). Selectable via `settings.json["active_provider"]`.
- **Dependencies**: `groq` SDK (Groq path) + `httpx` (already a Groq dep, used by
  OpenAICompatProvider) — **no new SDK dependency was added in v1.3**.
- **pyperclip** for clipboard read/write
- API key location (per-provider, v1.3):
  - `settings.json["providers"][<id>]["api_key"]`
  - Dev-mode fallback (only when active_provider=="groq" AND not frozen):
    `.env GROQ_API_KEY`. Frozen builds NEVER read `.env`.
- API timeout: per-provider default (Groq=3s, OpenAI/DeepSeek/Kimi/GLM=8s,
  Qwen/SiliconFlow=10s). Override via `settings["providers"][<id>]["timeout_s"]`.
  Raises `ProviderTimeoutError` (subclasses `TimeoutError`) → worker pastes
  original text.

## PyInstaller Gotchas (already solved, don't regress)
- `sys.stdout` is `None` when `console=False` → logger must handle this
- `__file__` points to temp extraction dir → use `sys.executable` parent for user files
- `QPixmap` cannot be created before `QApplication` → icons must be lazy-loaded
- Python 3.14 + 64-bit: `GetModuleHandleW` returns 64-bit pointer → must set `restype = c_void_p`
- Batch files with Chinese characters break in GBK cmd → use ASCII-only .bat filenames

## User Workflow
1. **First launch**: welcome dialog prompts for Groq API key (or Skip → demo mode)
2. Select text → Ctrl+C → Ctrl+Shift+C (repair) or Ctrl+Shift+T (translate)
3. Processed text auto-pastes into active window
4. Right-click tray icon → Settings / Exit

## Running Tests
```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python run_tests.py --verbose
```

## Building .exe (v1.1)
```bash
venv/Scripts/pyinstaller build.spec --clean
# settings.json with empty key is already bundled via build.spec's datas.
# Do NOT copy .env into dist/ — that's the whole point of BYOK.
# First run on the user's machine shows FirstRunDialog automatically.
```
Before shipping a build, double-check `dist/settings.json` has an empty
`groq_api_key` and that there is no `dist/.env` left over from old builds.

## Communication
- Speak Chinese with the user (跟用户讲中文)
- User prefers concise, direct answers
- User is a developer but not deeply familiar with PyQt5/ctypes internals
