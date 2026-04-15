# Deadline Survivor — Project Context for Claude Code

## What is this project?
A lightweight Windows background utility that intercepts the OS clipboard to:
1. **Repair broken text formatting** (e.g., broken line breaks from PDFs) via LLM
2. **Translate text** via LLM
Then instantly pastes the processed text into the active window.

## Current Status: v0.1 shipped
- All core features working, packaged as single-file .exe (44MB) via PyInstaller
- 38 unit tests passing
- Known minor issue: using Ctrl+Shift+C may switch the user's input method (IME)

## Architecture

```
ent2/
├── main.py                  ← Entry point, AppController, Qt signal bridge
├── ai/
│   └── groq_client.py       ← Groq LLM client (singleton `groq_client`)
├── core/
│   ├── clipboard_handler.py ← read() / write() / paste() via ctypes keybd_event
│   ├── hotkey_listener.py   ← RegisterHotKey + hidden window message loop (daemon thread)
│   └── worker.py            ← QThread worker for async API calls
├── ui/
│   ├── tray_icon.py         ← QSystemTrayIcon with dynamic icons (lazy-loaded)
│   └── settings_dialog.py   ← Cyberpunk-styled PyQt5 settings dialog
├── utils/
│   └── logger.py            ← RotatingFileHandler, handles PyInstaller + GBK terminal
├── tests/                   ← unittest suite (38 tests, all mock-based)
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
- API key priority: `settings.json["groq_api_key"]` > `.env GROQ_API_KEY`
- API timeout: 3 seconds default, raises `TimeoutError` → worker pastes original text

## PyInstaller Gotchas (already solved, don't regress)
- `sys.stdout` is `None` when `console=False` → logger must handle this
- `__file__` points to temp extraction dir → use `sys.executable` parent for user files
- `QPixmap` cannot be created before `QApplication` → icons must be lazy-loaded
- Python 3.14 + 64-bit: `GetModuleHandleW` returns 64-bit pointer → must set `restype = c_void_p`
- Batch files with Chinese characters break in GBK cmd → use ASCII-only .bat filenames

## User Workflow
1. Select text → Ctrl+C → Ctrl+Shift+C (repair) or Ctrl+Shift+T (translate)
2. Processed text auto-pastes into active window
3. Right-click tray icon → Settings / Exit

## Running Tests
```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python run_tests.py --verbose
```

## Building .exe
```bash
venv/Scripts/pyinstaller build.spec --clean
# Then copy .env and settings.json to dist/
```

## Communication
- Speak Chinese with the user (跟用户讲中文)
- User prefers concise, direct answers
- User is a developer but not deeply familiar with PyQt5/ctypes internals
