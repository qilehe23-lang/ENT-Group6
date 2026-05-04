Deadline Survivor v1.2
======================

A lightweight Windows tray utility that intercepts your clipboard to:
  • Repair broken text formatting via LLM (Ctrl+Shift+C)
  • Translate text via LLM (Ctrl+Shift+T)
  • Open the command palette (Ctrl+Shift+Space)

The processed text is auto-pasted into the active window.


Quick start
-----------
1. Double-click DeadlineSurvivor.exe.
2. On first launch, paste your Groq API key when prompted.
   (Get a free key from https://console.groq.com/keys)
   Or skip — the app runs in DEMO MODE with mocked output.
3. Look for the DS icon in your system tray.
4. Select text anywhere → press Ctrl+Shift+C or Ctrl+Shift+T.
5. Done. The repaired/translated text replaces your selection.


Customizing
-----------
Right-click the tray icon → Settings to:
  • Change your API key, model, or timeout
  • Pick a translation target language (Chinese / English / Japanese / …)
  • Edit the built-in tasks or add your own from the Preset Library
  • Bind global hotkeys to any task
  • Live-test prompt edits before saving


Files in this folder
--------------------
  DeadlineSurvivor.exe   — the app (no install needed)
  settings.json          — your config; edited via Settings or by hand
  README.txt             — this file


Tray menu
---------
  ↶ Restore Last Original  — undo the most recent AI replacement
                              (clipboard history of last 10 dispatches)
  Settings                  — open the settings window
  Exit                      — quit


What's new in v1.2
------------------
  • Command palette: Ctrl+Shift+Space brings up a fuzzy task launcher
  • Custom tasks: define your own prompts beyond Repair / Translate
  • Preset Library: 6 ready-made tasks (Polish, Formula → LaTeX, etc.)
  • Hero startup toast with live telemetry
  • Glass-style v2 toasts for each operation
  • Settings dialog redesign: tabs for Engine / Tasks / Translation / About


Notes
-----
  • Clipboard history is in-memory only — never written to disk.
  • Your API key is stored locally in settings.json next to the .exe.
  • No telemetry leaves your machine. The only network call is to Groq's
    /chat/completions endpoint when you trigger a task.
  • If the API call exceeds the timeout (default 3s), your original text
    is pasted back automatically — your flow is never blocked.

Running from source / development build:
  See CLAUDE.md / CHANGELOG.md in the project repo.
