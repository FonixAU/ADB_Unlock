# Development rules for the Geely ADB Unlock Master project

## 1. Concept and goal of the project
The project is a universal, cross-platform "one-click" solution for permanently unlocking ADB debugging, disabling third-party app install restrictions (Parrot certificates, AutoInstallVerifier), and integrating with the GeelyTune web installer on Geely cars (in particular the Geely EX5 EM-i with 2.1.4.5+ / Flyme Auto / Ecarx firmware).

The target audience is ordinary users and older people, so the interface must be extremely simple, friendly, and self-contained ("press one button and it does everything itself").

---

## 2. Directory structure and file-placement rules

### Project root (`/`)
The root folder must contain **ONLY** the 3 user-facing launcher files that are easy to understand, plus the service directories:
* `START_Windows.bat` — launcher for Windows.
* `START_Mac.command` — launcher for macOS.
* `START_Linux.sh` — launcher for Linux.
* `core/` — all the internals (hidden from the user's eyes).
* `.agents/` — system rules and skills for the AI assistant.

> ⚠️ **CRITICAL RULE:** Never add temporary files, helper scripts, `.apk`, `.exe`, or logs to the project root. All internal content must live inside `core/`.

### The `core/` folder
* `main.py` — the main entry point of the standalone CLI/TUI application.
* `engine.py` — the independent business-logic engine (ADB, VHAL, Parrot, AutoInstallVerifier, head unit checks).
* `tui.py` — the lightweight Zero-Dependency terminal interface (ASCII frames, ANSI palette, interactive menu).
* `geely_unlock.exe` — the compiled standalone Windows binary with embedded ADB and resources.
* `bin/` — bundled Android Debug Bridge binaries:
  * `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll` — for Windows.
  * `adb-darwin` — for macOS.
  * `adb-linux` — for Linux.
* `unlock-hu.sh` — the script that removes Parrot and AutoInstallVerifier protection, run inside the head unit.
* `Geely-ADB-Toggle-1.1.0.apk` — the helper ADB toggle app.

---

## 3. System and platform requirements

1. **Windows batch files (`.bat`):**
   * Always save strictly with **CRLF (`\r\n`)** line endings.
   * The command and `echo` syntax inside the `.bat` must be pure **ASCII** (Latin), to avoid `cmd.exe` parser bugs in the CP866 system code page.
2. **Shell scripts (`.sh`, `.command`):**
   * Always save strictly with **LF (`\n`)** line endings.
   * Always include the shebang `#!/usr/bin/env bash`.
   * Include auto-granting of `chmod +x` on the ADB binaries and scripts.
3. **Python engine and TUI (`core/engine.py`, `core/tui.py`, `core/main.py`):**
   * Strictly **Zero-Dependency**: no external `pip` dependencies (only the Python standard library: `subprocess`, `threading`, `time`, `os`, `sys`, `ctypes`, `platform`, `webbrowser`, `urllib`).
   * For the Windows console, always enable ANSI VT100 via `ctypes.windll.kernel32.SetConsoleMode` and use safe output with `sys.stdout.reconfigure(encoding='utf-8')`.
   * When compiling with PyInstaller: resources (ADB, script, APK) are embedded inside the binary and extracted via `get_resource_path()` (`sys._MEIPASS`).
4. **Processes:**
   * Before starting work, the engine automatically clears old stuck ADB processes (`taskkill /F /IM adb.exe` / `killall -9 adb`).

---

## 4. The Geely unlock algorithm

1. **Step 1: Hardware jumper:**
   * Install the jumper in the head unit connector to temporarily activate service ADB at boot time.
2. **Step 2: Factory reset and catching the 20-second window:**
   * Poll `adb get-state` in a loop.
   * Request `adb root`, `adb wait-for-device`, `adb remount`.
   * Send the VHAL command to lock in persistent ADB:
     `/system/bin/lshal debug android.hardware.automotive.vehicle@2.0::IVehicle/default --set 557872680 i 0 a 0`
   * Check the response: the presence of `Set property` confirms success.
3. **Step 3: Remove the jumper and reboot:**
   * Pull out the jumper, run `adb reboot`, wait for `sys.boot_completed=1`.
4. **Step 4: Remove install restrictions:**
   * Push `unlock-hu.sh` to `/data/local/tmp/gt-unlock.sh`.
   * Disable `com.ecarx.xsfinstallverifier` and the system verifiers.
   * Set `ro.vendor.ecarx.app_verify=false` in `/product/build.prop`.
   * Install `Geely-ADB-Toggle-1.1.0.apk` via `adb install -r --user 10 ...`.
5. **Step 5: Move on to GeelyTune:**
   * Open the official web installer `https://geelytune.github.io` in the default browser.
