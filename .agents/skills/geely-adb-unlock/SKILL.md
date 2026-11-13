---
name: geely-adb-unlock
description: >-
  Expert guide and runbook for maintaining, troubleshooting, and extending the Geely ADB Unlock Master
  application. Use this skill whenever working on Geely multimedia head unit (HU) unlock workflows,
  modifying core/engine.py, editing the native TUI in core/tui.py, building launchers, or debugging ADB and VHAL connections.
---

# Geely ADB Unlock Master — Knowledge base and developer guide

This skill contains a full description of the design, build procedures, debugging, and modification of the **Geely ADB Unlock Master** project.

---

## 1. Application architecture

The application is built as a **Zero-Dependency Native TUI/CLI Application**:

```text
               ┌────────────────────────────────────────────────────────┐
               │       Console window (cmd / PowerShell / Terminal)     │
               │        Strict retro TUI interface (core/tui.py)        │
               └──────────────────────────┬─────────────────────────────┘
                                          │  Direct Python function calls
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │         Business-logic engine (core/engine.py)         │
               │    or the standalone binary core/geely_unlock.exe      │
               └──────────────────────────┬─────────────────────────────┘
                                          │
                                          │  ADB commands (subprocesses)
                                          ▼
   ┌────────────────────────────────────────────────────────────────────────────┐
   │           Bundled Google ADB (core/bin/adb.exe / -darwin / -linux)         │
   └──────────────────────────────────────┬─────────────────────────────────────┘
                                          │  USB cable
                                          ▼
   ┌────────────────────────────────────────────────────────────────────────────┐
   │                      Geely car (head unit)                                 │
   │   - VHAL: lshal ... --set 557872680 i 0 a 0 (USB_SWITCH=0)                 │
   │   - Script: unlock-hu.sh (disables Parrot & AutoInstallVerifier)          │
   │   - Package: Geely-ADB-Toggle-1.1.0.apk (--user 10)                        │
   └────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Key components

### 1. `core/engine.py`
* Pure business logic with no ties to the interface.
* Background `threading.Thread` threads for long operations (VHAL capture, head unit reboot polling, running `unlock-hu.sh`).
* Cleanup of stuck ADB processes.
* The `get_resource_path()` function for correctly handling resources from `sys._MEIPASS` when built into a single `.exe`.

### 2. `core/tui.py`
* Zero-Dependency interface rendering via pure ANSI codes.
* Automatic activation of ANSI VT100 on Windows (`SetConsoleMode`).
* A status panel for the head unit connection and the Parrot and AutoInstallVerifier locks.
* An interactive menu with digits [0-8], a live terminal logger with an animated spinner.

### 3. `core/main.py`
* The main entry point of the console application.

### 4. Binaries in `core/bin/`
* `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll` — for Windows.
* `adb-darwin` — for macOS (Universal x86_64 / arm64).
* `adb-linux` — for Linux (x86_64).

---

## 3. Maintenance and build procedures

### How to rebuild `core/geely_unlock.exe` (for Windows)
The standalone executable is rebuilt with the resources packed inside:

```cmd
cd /d d:\ADB_Unlock\core
python -m PyInstaller --clean --onefile --name "geely_unlock" --distpath "d:\ADB_Unlock\core" --workpath "d:\ADB_Unlock\core\build" --specpath "d:\ADB_Unlock\core" --add-data "d:\ADB_Unlock\core\bin\adb.exe;bin" --add-data "d:\ADB_Unlock\core\bin\AdbWinApi.dll;bin" --add-data "d:\ADB_Unlock\core\bin\AdbWinUsbApi.dll;bin" --add-data "d:\ADB_Unlock\core\unlock-hu.sh;." --add-data "d:\ADB_Unlock\core\Geely-ADB-Toggle-1.1.0.apk;." "d:\ADB_Unlock\core\main.py"
```

After building, remove the temporary files:
```powershell
Remove-Item -Recurse -Force 'd:\ADB_Unlock\core\build', 'd:\ADB_Unlock\core\geely_unlock.spec'
```

### How to test macOS and Linux on Windows
1. **Syntax check of the launcher scripts:**
   ```bash
   "C:\Program Files\Git\bin\bash.exe" -n d:/ADB_Unlock/START_Linux.sh
   "C:\Program Files\Git\bin\bash.exe" -n d:/ADB_Unlock/START_Mac.command
   ```
2. **Checking macOS emulation in Python:**
   ```cmd
   python -c "import platform; platform.system = lambda: 'Darwin'; exec(open('d:/ADB_Unlock/core/main.py', encoding='utf-8').read())"
   ```

---

## 4. Common problems and solutions

### Problem: The batch file throws strange command errors on Windows
* **Cause:** `LF` line endings instead of `CRLF`, or Cyrillic characters in the batch file code.
* **Solution:** The file `START_Windows.bat` must contain strictly `\r\n` (CRLF) line endings and pure ASCII command text.

### Problem: "Must be root" error or missing the 20-second window
* **Cause:** The head unit booted too fast, or the reset was started before the script launched.
* **Solution:** Repeat the factory reset on the head unit screen. The engine sits in an infinite polling loop and will automatically catch the next attempt.

### Problem: A stuck ADB process in the system
* **Solution:** Choose item 6 in the application's main menu ("Restart the ADB service") or run `taskkill /F /IM adb.exe` (Windows) / `killall -9 adb` (macOS/Linux) in the terminal.
