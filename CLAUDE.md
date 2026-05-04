# Deadline Survivor — Project Context for Claude Code

## What is this project?
A lightweight Windows background utility that intercepts the OS clipboard to:
1. **Repair broken text formatting** (e.g., broken line breaks from PDFs) via LLM
2. **Translate text** via LLM
Then instantly pastes the processed text into the active window.

## Current Status: v1.1 — "Bulletproof" Update
- All core features working, packaged as single-file .exe via PyInstaller
- 50 unit tests passing
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
├── main.py                  ← Entry point, AppController, Qt signal bridge
├── ai/
│   └── groq_client.py       ← Groq LLM client (singleton `groq_client`)
├── core/
│   ├── clipboard_handler.py ← read() / write() / paste() / copy_selection() via SendInput + scan codes
│   ├── history.py           ← ClipboardHistory: in-memory deque(10) of pre-AI snapshots (v1.1)
│   ├── hotkey_listener.py   ← RegisterHotKey + hidden window message loop (daemon thread)
│   └── worker.py            ← QThread worker for async API calls
├── ui/
│   ├── tray_icon.py         ← QSystemTrayIcon with dynamic icons (lazy-loaded), Restore menu (v1.1)
│   ├── settings_dialog.py   ← Cyberpunk-styled PyQt5 settings dialog
│   └── first_run_dialog.py  ← BYOK welcome dialog (v1.0, first launch only)
├── utils/
│   └── logger.py            ← RotatingFileHandler, handles PyInstaller + GBK terminal
├── tests/                   ← unittest suite (50 tests, all mock-based)
├── settings.json            ← Runtime config (user-editable)
├── .env                     ← GROQ_API_KEY (fallback if settings.json key is empty)
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
- **Groq API** (`groq` package) with `llama-3.1-8b-instant` model
- **pyperclip** for clipboard read/write
- API key priority:
  - Frozen/shipped exe: `settings.json["groq_api_key"]` **only** (.env is never read, never bundled)
  - Dev mode: `settings.json["groq_api_key"]` > local `.env GROQ_API_KEY` (for convenience)
- API timeout: 3 seconds default, raises `TimeoutError` → worker pastes original text

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
