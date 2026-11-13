"""
Geely ADB Unlock Master - Core Engine
Handles all device discovery, ADB communication, VHAL interactions,
and unlock workflows across Windows, macOS, and Linux without external dependencies.
"""

import sys
import os
import platform
import subprocess
import threading
import time
from sound import play_sound

# Base directories
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ROOT_DIR = os.path.dirname(BASE_DIR)
BIN_DIR = os.path.join(BASE_DIR, 'bin')

def get_resource_path(relative_path):
    """Returns absolute path to a bundled or local resource."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_path = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(bundle_path):
            return bundle_path

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        exe_path = os.path.join(exe_dir, relative_path)
        if os.path.exists(exe_path):
            return exe_path

    base_path = os.path.join(BASE_DIR, relative_path)
    if os.path.exists(base_path):
        return base_path

    return base_path


def humanize_adb_error(raw_err, context=""):
    """
    Translates raw low-level ADB errors, OS socket errors, and Android status messages
    into clear, respectful, and actionable diagnostic explanations with step-by-step guidance.
    """
    raw_str = str(raw_err or "").strip()
    raw_lower = raw_str.lower()

    if any(k in raw_lower for k in ["no devices/emulators found", "device not found", "device offline"]):
        title = "Car (head unit) not detected over USB"
        reason = "The ADB service did not find an active multimedia device on the computer's USB ports."
        steps = [
            "Check that the USB-A cable between the laptop and the head unit's service port is firmly seated.",
            "Make sure the car's multimedia screen is on and in a working state.",
            "If ADB debugging on the head unit is being set up for the first time (or is closed), use \"[2] Open ADB from scratch\" with the jumper. Item [1] does not open a closed ADB; it only removes install protection on cars with an already-active port (after a dealer update)."
        ]
        return title, reason, steps

    if "unauthorized" in raw_lower:
        title = "Access must be confirmed on the head unit screen"
        reason = "The head unit is waiting for the USB debugging security key to be confirmed."
        steps = [
            "Look at the car's central multimedia screen.",
            "In the \"Allow USB debugging?\" popup, check \"Always allow from this computer\" and tap \"OK\"."
        ]
        return title, reason, steps

    if "more than one device" in raw_lower:
        title = "Multiple connected Android devices detected"
        reason = "Several devices in ADB mode are connected to the computer (phone, tablet, or emulator)."
        steps = [
            "Disconnect any other phones and external gadgets from the laptop.",
            "Leave only the USB cable that goes to the car connected."
        ]
        return title, reason, steps

    if any(k in raw_lower for k in ["must be root", "adbd cannot run as root", "not in root mode", "uid is not 0"]):
        title = "No system root privileges on the head unit"
        reason = "The command requires superuser privileges, but the adbd service is running in restricted user mode."
        steps = [
            "During the initial unlock, make sure the jumper is installed and the factory reset is running during the interception.",
            "During express removal, make sure persistent ADB mode (VHAL) was previously enabled on the head unit."
        ]
        return title, reason, steps

    if any(k in raw_lower for k in ["build.prop", "could not modify", "read-only file system", "remount failed"]):
        title = "Head unit system partitions are locked for writing"
        reason = "The /product or /system partition is protected from changes (read-only overlayfs)."
        steps = [
            "Make sure root access to the head unit was granted (adb root).",
            "Repeat the operation: the program will remount the filesystem and apply the changes."
        ]
        return title, reason, steps

    if any(k in raw_lower for k in ["install_parse_failed_no_certificates", "install_failed_no_certificates"]):
        title = "Installation blocked by Parrot certificate protection"
        reason = "The Geely firmware rejects installing apps without the factory Parrot digital signature."
        steps = [
            "Run \"Scenario 1: Express protection removal\" to disable the ro.vendor.ecarx.app_verify flag.",
            "Wait for the normal head unit reboot so the system changes take effect."
        ]
        return title, reason, steps

    if any(k in raw_lower for k in ["autoinstallverifier did not turn off", "xsfinstallverifier", "install_failed_verification"]):
        title = "Installation blocked by the Geely verifier"
        reason = "The system service com.ecarx.xsfinstallverifier rejects installing third-party APK packages."
        steps = [
            "Run the protection-removal procedure: the program will forcibly disable the verifier service."
        ]
        return title, reason, steps

    if any(k in raw_lower for k in ["timeout", "timeoutexpired", "timed out"]):
        title = "Timed out waiting for a response from the head unit"
        reason = "The head unit did not answer the system request within the configured timeout."
        steps = [
            "Check that the USB cable is firmly seated - a contact may have come loose from vibration.",
            "Make sure the multimedia screen has not frozen (if needed, reboot the screen by holding the volume knob)."
        ]
        return title, reason, steps

    if any(k in raw_lower for k in ["cannot connect to daemon", "connection refused", "failed to start daemon"]):
        title = "Local ADB service failure on the computer"
        reason = "The ADB server could not bind to port 5037 on your computer (the port is taken by another process)."
        steps = [
            "Close any third-party phone-sync utilities or Android emulators.",
            "In the main menu choose \"[6] Restart the ADB service\" to clean up processes automatically."
        ]
        return title, reason, steps

    # Fallback with context
    title = context or "Operation failed"
    reason = "The head unit system returned a technical error code while running the command."
    steps = [
        "Check that the USB cable is firmly seated and the multimedia screen is active.",
        "Run a check from the menu: \"[3] Check head unit status (Connection diagnostics)\"."
    ]
    return title, reason, steps


class AppState:
    def __init__(self):
        self.lock = threading.Lock()
        self.os_name = platform.system().lower()  # 'windows', 'darwin', 'linux'
        self.adb_path = None
        self.adb_ready = False
        self.status = "idle"  # idle, working, success, error
        self.status_message = "Ready"
        self.last_error_details = None
        self.device_serial = None
        self.device_state = "disconnected"
        self.last_test = None
        self.logs = []
        self.stop_worker = False

    def log(self, text, level="info"):
        timestamp = time.strftime("%H:%M:%S")
        prefix = {
            "info": "[i]",
            "success": "[OK]",
            "warning": "[!]",
            "error": "[X]",
            "cmd": "[*]"
        }.get(level, "•")

        # Strip any legacy leading emojis so terminal fonts never show broken ?? boxes
        clean_text = text.strip()
        for em in ["ℹ️", "✅", "⚠️", "❌", "⚡", "🔍", "🔑", "📂", "💡", "⚙️", "🔄", "📱", "🎉", "🚘", "🇪🇺", "🔒", "🔓", "📋", "📡", "🏆"]:
            if clean_text.startswith(em):
                clean_text = clean_text[len(em):].strip()

        entry = f"[{timestamp}] {prefix} {clean_text}"

        with self.lock:
            self.logs.append({"time": timestamp, "text": clean_text, "level": level, "formatted": entry})
            if len(self.logs) > 500:
                self.logs.pop(0)

        try:
            log_file = os.path.join(BASE_DIR, "debug.log")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
        except Exception:
            pass

    def set_error(self, title, reason="", steps=None, raw=""):
        details = {
            "title": title,
            "reason": reason,
            "steps": steps or [],
            "raw": str(raw).strip() if raw else ""
        }
        with self.lock:
            self.status = "error"
            self.status_message = title
            self.last_error_details = details
        self.log(title, level="error")

    def set_status(self, status, message, step=None):
        with self.lock:
            self.status = status
            self.status_message = message
            if status != "error":
                self.last_error_details = None
            elif not self.last_error_details:
                title, reason, steps = humanize_adb_error(message)
                self.last_error_details = {
                    "title": title,
                    "reason": reason,
                    "steps": steps,
                    "raw": message
                }
        self.log(message, level="info" if status != "error" else "error")


STATE = AppState()


def locate_or_download_adb():
    """Finds adb in bundle, bin/, system PATH, or downloads it automatically."""
    is_win = STATE.os_name == "windows"
    adb_binary = "adb.exe" if is_win else "adb"

    # 1. Check embedded resource path
    bundled_adb = get_resource_path(os.path.join("bin", adb_binary))
    if os.path.isfile(bundled_adb):
        if not is_win:
            try:
                os.chmod(bundled_adb, 0o755)
            except Exception:
                pass
        STATE.adb_path = bundled_adb
        STATE.adb_ready = True
        return bundled_adb

    # 2. Check core/bin/
    local_adb = os.path.join(BIN_DIR, adb_binary)
    if not os.path.isfile(local_adb):
        if STATE.os_name == "darwin":
            darwin_pkg = get_resource_path(os.path.join("bin", "adb-darwin"))
            if os.path.isfile(darwin_pkg):
                try:
                    import shutil
                    shutil.copy2(darwin_pkg, local_adb)
                except Exception:
                    local_adb = darwin_pkg
        elif STATE.os_name == "linux":
            linux_pkg = get_resource_path(os.path.join("bin", "adb-linux"))
            if os.path.isfile(linux_pkg):
                try:
                    import shutil
                    shutil.copy2(linux_pkg, local_adb)
                except Exception:
                    local_adb = linux_pkg

    if os.path.isfile(local_adb):
        if not is_win:
            try:
                os.chmod(local_adb, 0o755)
            except Exception:
                pass
        STATE.adb_path = local_adb
        STATE.adb_ready = True
        return local_adb

    # 3. Check system PATH
    system_adb = None
    try:
        which_cmd = ["where", "adb"] if is_win else ["which", "adb"]
        res = subprocess.run(which_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if lines:
                system_adb = lines[0].strip()
    except Exception:
        pass

    if system_adb and os.path.isfile(system_adb):
        STATE.adb_path = system_adb
        STATE.adb_ready = True
        return system_adb

    # 4. Auto-download from Google
    STATE.log("ADB not found on the computer. Downloading the official Google Platform-Tools...", "warning")
    os.makedirs(BIN_DIR, exist_ok=True)

    urls = {
        "windows": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
        "darwin": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
        "linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
    }
    url = urls.get(STATE.os_name, urls["windows"])
    try:
        import urllib.request
        import zipfile
        import io

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        z = zipfile.ZipFile(io.BytesIO(data))
        for member in z.namelist():
            filename = os.path.basename(member)
            if not filename:
                continue
            if filename in ["adb", "adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "lib64"]:
                target_path = os.path.join(BIN_DIR, filename)
                with open(target_path, "wb") as f:
                    f.write(z.read(member))
                if not is_win:
                    os.chmod(target_path, 0o755)
        if os.path.isfile(local_adb):
            if not is_win:
                os.chmod(local_adb, 0o755)
            STATE.adb_path = local_adb
            STATE.adb_ready = True
            STATE.log("ADB downloaded and prepared successfully!", "success")
            return local_adb
    except Exception as e:
        STATE.log(f"Failed to download ADB automatically: {e}", "error")

    STATE.adb_ready = False
    return None


def run_adb(args, timeout=30):
    """Executes an adb command safely without opening popup windows and with robust UTF-8 encoding."""
    if not STATE.adb_path or not os.path.isfile(STATE.adb_path):
        locate_or_download_adb()
        if not STATE.adb_path:
            return -1, "", "ADB unavailable"

    cmd = [STATE.adb_path] + args
    try:
        creationflags = 0x08000000 if STATE.os_name == "windows" else 0
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "ADB command timeout"
    except Exception as e:
        return -1, "", str(e)


def kill_adb_processes():
    """Kills conflicting adb server processes to free the port and restarts daemon."""
    STATE.log("Clearing stuck ADB processes in the system...", "cmd")
    try:
        if STATE.os_name == "windows":
            subprocess.run(["taskkill", "/F", "/IM", "adb.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["killall", "-9", "adb"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    time.sleep(1)
    code, stdout, stderr = run_adb(["start-server"], timeout=10)
    if code == 0:
        STATE.set_status("success", "ADB service restarted from scratch successfully")
        STATE.log("ADB service restarted from scratch", "success")
    else:
        title, reason, steps = humanize_adb_error(stderr or stdout, context="Failed to start the ADB server")
        STATE.set_error(title, reason, steps, raw=stderr or stdout)


def stop_adb_server():
    """Completely terminates ADB server processes so that the browser (WebUSB) can exclusively access the vehicle."""
    STATE.log("Stopping the ADB service to free the USB port...", "cmd")
    try:
        if STATE.adb_path and os.path.isfile(STATE.adb_path):
            subprocess.run([STATE.adb_path, "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass
    try:
        if STATE.os_name == "windows":
            subprocess.run(["taskkill", "/F", "/IM", "adb.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["killall", "-9", "adb"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    STATE.device_state = "disconnected"
    STATE.device_serial = None
    STATE.log("Background ADB service stopped. The USB port is fully handed over to the browser.", "success")


def check_devices():
    """Checks connected devices."""
    code, stdout, _ = run_adb(["devices"])
    if code != 0:
        STATE.device_state = "error"
        STATE.device_serial = None
        return False

    lines = stdout.splitlines()[1:] if stdout else []
    devices = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])

    if len(devices) == 1:
        STATE.device_serial = devices[0]
        STATE.device_state = "connected"
        return True
    elif len(devices) > 1:
        STATE.device_serial = devices[0]
        STATE.device_state = "multiple"
        return True
    else:
        STATE.device_serial = None
        STATE.device_state = "disconnected"
        return False


def test_adb_connection():
    """Runs a comprehensive test of the ADB connection, head unit state, and security locks."""
    STATE.log("🔍 Starting the connection check with the car (ADB test)...", "cmd")

    if not STATE.adb_path or not os.path.isfile(STATE.adb_path):
        locate_or_download_adb()
        if not STATE.adb_path:
            res = {
                "ok": False,
                "connected": False,
                "error": "ADB not found on the computer",
                "recommendation": "check_adb"
            }
            STATE.last_test = res
            STATE.log("❌ Error: the ADB executable was not found.", "error")
            return res

    # 1. Devices check
    code, stdout, _ = run_adb(["devices"], timeout=5)
    lines = stdout.splitlines()[1:] if stdout else []
    connected_devs = []
    unauth_devs = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            if parts[1] == "device":
                connected_devs.append(parts[0])
            elif parts[1] == "unauthorized":
                unauth_devs.append(parts[0])

    if unauth_devs and not connected_devs:
        STATE.device_state = "unauthorized"
        STATE.log("⚠️ A device was found, but debugging must be authorized on the car screen (unauthorized).", "warning")
        res = {
            "ok": True,
            "connected": False,
            "state": "unauthorized",
            "message": "USB debugging must be confirmed on the multimedia screen",
            "recommendation": "authorize"
        }
        STATE.last_test = res
        return res

    if not connected_devs:
        STATE.device_state = "disconnected"
        STATE.device_serial = None
        title, reason, steps = humanize_adb_error("no devices/emulators found")
        STATE.log("Car not detected on the USB bus (the adb devices list is empty)", "warning")
        STATE.set_error(title, reason, steps, raw="no devices/emulators found")
        res = {
            "ok": False,
            "connected": False,
            "state": "disconnected",
            "message": title,
            "reason": reason,
            "steps": steps,
            "recommendation": "not_connected"
        }
        STATE.last_test = res
        return res

    serial = connected_devs[0]
    STATE.device_serial = serial
    STATE.device_state = "connected"
    STATE.log(f"✅ Car connected successfully! Serial number: {serial}", "success")

    # 2. Test root access
    STATE.log("🔑 Checking superuser access (adb root)...", "cmd")
    code_r, out_r, _ = run_adb(["root"], timeout=8)
    time.sleep(1)
    run_adb(["wait-for-device"], timeout=5)

    root_ok = ("already running as root" in out_r.lower() or "restarting adbd as root" in out_r.lower() or code_r == 0)
    code_id, out_id, _ = run_adb(["shell", "id", "-u"], timeout=5)
    if code_id == 0 and out_id.strip() == "0":
        root_ok = True
        STATE.log("✅ Root access confirmed (UID: 0).", "success")
    else:
        STATE.log(f"⚠️ Response to root request: {out_r or out_id}", "warning")

    # 3. Read firmware & system properties
    STATE.log("📋 Reading head unit firmware details...", "cmd")
    _, fw_build, _ = run_adb(["shell", "getprop", "ro.build.display.id"], timeout=5)
    _, fw_inc, _ = run_adb(["shell", "getprop", "ro.build.version.incremental"], timeout=5)
    _, model, _ = run_adb(["shell", "getprop", "ro.product.model"], timeout=5)
    firmware_info = fw_build.strip() or fw_inc.strip() or "Unknown"
    model_info = model.strip() or "Stock Geely head unit"
    STATE.log(f"🚘 Head unit model: {model_info} | Firmware: {firmware_info}", "info")

    # 4. Check Parrot app_verify
    _, product_val, _ = run_adb(["shell", "getprop", "ro.build.product"], timeout=5)
    is_eu = "e245_eu" in (product_val or "").lower()
    _, parrot_val, _ = run_adb(["shell", "getprop", "ro.vendor.ecarx.app_verify"], timeout=5)
    parrot_val = parrot_val.strip().lower()
    if is_eu:
        parrot_locked = False
        STATE.log("🇪🇺 Head unit version: export European (e245_eu) - Parrot is built into the system and does not block installation", "info")
    elif parrot_val == "true":
        parrot_locked = True
        STATE.log("🔒 Parrot certificates protection: ENABLED (blocks installing third-party APKs)", "warning")
    else:
        parrot_locked = False
        STATE.log("🔓 Parrot certificates protection: DISABLED (installing third-party APKs is allowed)", "success")

    # 5. Check AutoInstallVerifier package
    _, pm_out, _ = run_adb(["shell", "pm", "list", "packages", "-e"], timeout=8)
    verifier_active = "com.ecarx.xsfinstallverifier" in (pm_out or "")
    if verifier_active:
        STATE.log("🔒 System AutoInstallVerifier: ACTIVE", "warning")
    else:
        STATE.log("🔓 System AutoInstallVerifier: DISABLED or absent", "success")

    # 6. Check toggle app
    _, toggle_out, _ = run_adb(["shell", "pm", "list", "packages"], timeout=5)
    toggle_installed = any(pkg in (toggle_out or "") for pkg in ["com.yahooeu2k.ex5.adbtoggle", "com.geely.adbtoggle", "adbtoggle", "geelyadbtoggle"])
    if toggle_installed:
        STATE.log("📱 ADB-Toggle switch app: already installed on the head unit", "info")
    else:
        STATE.log("📱 ADB-Toggle switch app: not found (will be installed if needed)", "info")

    needs_unlock = parrot_locked or verifier_active or not toggle_installed
    if needs_unlock:
        recommendation = "quick_unlock"
        STATE.log("💡 VERDICT: ADB is active! No jumper required.", "success")
        STATE.log("💡 It is enough to run the one-click express removal of restrictions.", "success")
    else:
        recommendation = "ready"
        STATE.log("🎉 VERDICT: All locks are already removed! The head unit is ready to install any apps and GeelyTune tweaks.", "success")

    res = {
        "ok": True,
        "connected": True,
        "serial": serial,
        "model": model_info,
        "firmware": firmware_info,
        "root_ok": root_ok,
        "parrot_locked": parrot_locked,
        "verifier_active": verifier_active,
        "toggle_installed": toggle_installed,
        "needs_unlock": needs_unlock,
        "recommendation": recommendation,
        "message": "ADB is active! No jumper required." if needs_unlock else "Head unit is fully unlocked!"
    }
    STATE.last_test = res
    return res


# ==================== STEP 2: FACTORY RESET CATCH ====================
def worker_catch_factory_reset():
    """Continuously waits for device reboot, grants root, and sets VHAL property."""
    STATE.set_status("working", "Waiting for the head unit to reboot after a factory reset... Do not close the window!", 2)
    STATE.log("ATTENTION: On the car screen go to: \"Main application\" -> \"My car\" -> \"Factory reset\" and accept the warnings.", "warning")
    STATE.log("💡 How it works: during a normal reset the system briefly opens a 20-second debugging window. The program continuously scans the USB port and will intercept it automatically.", "info")

    vhal_cmd = "/system/bin/lshal debug android.hardware.automotive.vehicle@2.0::IVehicle/default --set 557872680 i 0 a 0"
    attempt = 0

    while not STATE.stop_worker:
        code, stdout, _ = run_adb(["get-state"], timeout=2)
        if code != 0 or stdout != "device":
            time.sleep(0.5)
            continue

        attempt += 1
        STATE.log(f"⚡ Device detected on the USB bus! Attempt to intercept the service window #{attempt}...", "cmd")
        STATE.log("🔑 Requesting superuser privileges (adb root)...", "info")

        run_adb(["root"], timeout=5)
        time.sleep(0.5)
        run_adb(["wait-for-device"], timeout=5)
        run_adb(["remount"], timeout=5)

        STATE.log("📡 Sending the car the VHAL lock-in command: USB_SWITCH=0 (persistent ADB)...", "cmd")
        STATE.log("💡 What the command does: lshal writes a persistent-ADB-mode flag to the car's system bus so it no longer turns off after reboots.", "info")
        code, out, err = run_adb(["shell", vhal_cmd], timeout=8)
        combined_out = f"{out} {err}".strip()
        STATE.log(f"Car system response: {combined_out}")

        if "Set property" in combined_out:
            play_sound("catch")
            STATE.log("🎉 SUCCESS! The car confirmed the port lock-in (Set property)! Persistent ADB is activated.", "success")
            STATE.set_status("success", "ADB locked in! Remove the jumper and confirm the head unit reboot.", 3)
            return

        if "Must be root" in combined_out:
            STATE.log("⚠️ The service window (20 sec) closed before the lock-in. No problem: tap \"Factory reset\" again (Main application -> My car) on the car screen - the script keeps waiting...", "warning")

        time.sleep(1)


# ==================== STEP 3: REBOOT & VERIFY ====================
def worker_reboot_and_verify():
    """Reboots HU without jumper and waits for full boot."""
    STATE.set_status("working", "Rebooting the head unit... This will take about 1.5 - 2 minutes.", 3)
    STATE.log("🔄 Sending the head unit reboot command...", "cmd")
    STATE.log("💡 Explanation: the jumper is removed, now we verify whether ADB access persists in the car's normal operating mode.", "info")
    run_adb(["reboot"], timeout=10)
    time.sleep(15)

    start_time = time.time()
    while not STATE.stop_worker:
        if time.time() - start_time > 300:
            STATE.set_error(
                title="Timed out waiting for the head unit to boot (5 minutes)",
                reason="The head unit did not finish the boot cycle or there is no USB connection.",
                steps=[
                    "Make sure the car's multimedia screen turned on and booted.",
                    "Check that the USB-A cable is firmly connected to the head unit port and the laptop.",
                    "If needed, reboot the head unit screen manually by holding the volume button."
                ],
                raw="Boot verification timeout (300s)"
            )
            return

        code, out, _ = run_adb(["shell", "getprop", "sys.boot_completed"], timeout=5)
        if code == 0 and out.strip() == "1":
            STATE.log("✅ The head unit has fully booted! Checking the persistence of the ADB connection...", "success")
            time.sleep(2)
            check_devices()
            if STATE.device_state == "connected":
                STATE.log("🎉 Connection confirmed! ADB is stably active without the jumper.", "success")
                STATE.set_status("success", "Head unit rebooted, ADB is active. Moving on to removing system restrictions.", 4)
                return
        time.sleep(3)


# ==================== STEP 4: UNLOCK PARROT & INSTALL TOGGLE ====================
def worker_unlock_and_install():
    """Executes unlock-hu.sh and installs Geely-ADB-Toggle apk."""
    STATE.set_status("working", "Removing install restrictions and configuring the system...", 4)
    unlock_script = get_resource_path("unlock-hu.sh")
    apk_file = get_resource_path("Geely-ADB-Toggle-1.1.0.apk")

    if not os.path.isfile(unlock_script):
        STATE.set_error(
            title="The system script unlock-hu.sh is missing",
            reason=f"The script file was not found inside the program package: {unlock_script}",
            steps=["Make sure the integrity of the program's files has not been compromised."],
            raw=""
        )
        return

    # 1. Pre-flight check: is device physically connected?
    STATE.log("🔍 Checking the connection to the car's head unit...", "cmd")
    code, stdout, _ = run_adb(["get-state"], timeout=2)
    if code != 0 or stdout.strip() != "device":
        run_adb(["wait-for-device"], timeout=3)
        code2, stdout2, err2 = run_adb(["get-state"], timeout=2)
        if code2 != 0 or stdout2.strip() != "device":
            title, reason, steps = humanize_adb_error(err2 or "no devices/emulators found")
            STATE.set_error(title, reason, steps, raw=err2 or "no devices/emulators found")
            return

    # 2. Check root access
    STATE.log("🔑 Checking superuser privileges (adb root)...", "cmd")
    run_adb(["root"], timeout=10)
    time.sleep(1)
    run_adb(["wait-for-device"], timeout=5)

    code_id, out_id, err_id = run_adb(["shell", "id", "-u"], timeout=5)
    if code_id != 0 or out_id.strip() != "0":
        err_msg = err_id or out_id or "UID != 0"
        title, reason, steps = humanize_adb_error("must be root", context="No superuser (root) privileges on the head unit")
        STATE.set_error(title, reason, steps, raw=err_msg)
        return

    # 3. Push script
    STATE.log("📂 Uploading the system unlock script (unlock-hu.sh) to the head unit...", "cmd")
    STATE.log("💡 Explanation: by default the Geely firmware rejects installing any apps without a Parrot digital certificate. The script disables this block in build.prop and turns off the system verifier.", "info")
    code, out_p, err_p = run_adb(["push", unlock_script, "/data/local/tmp/gt-unlock.sh"], timeout=15)
    if code != 0:
        title, reason, steps = humanize_adb_error(err_p or out_p, context="Error uploading the script to the head unit")
        STATE.set_error(title, reason, steps, raw=err_p or out_p)
        return

    # Run loop
    unlocked_ok = False
    for pass_num in range(1, 9):
        if STATE.stop_worker:
            STATE.log("⚠️ Operation canceled by the user", "warning")
            return

        play_sound("step")
        STATE.log(f"⚙️ Running the protection-removal procedures (pass {pass_num}/8)...", "cmd")
        code, out, _ = run_adb(["shell", "sh", "/data/local/tmp/gt-unlock.sh"], timeout=60)

        for line in out.splitlines():
            line_str = line.strip()
            if line_str and not line_str.startswith("GT:"):
                STATE.log(line_str)

        if "GT:OK" in out:
            run_adb(["shell", "rm", "-f", "/data/local/tmp/gt-unlock.sh"], timeout=5)
            STATE.log("✅ Parrot restrictions and the system verifier have been disabled successfully!", "success")
            STATE.log("💡 The car system will now allow installing any standard Android APK: a catalog of software tuned for the car screen is available at https://ex5app.wingie.ru/ (author - pioneer @wingus), or use your own APKs.", "info")
            unlocked_ok = True
            break
        elif "GT:PARROT" in out:
            run_adb(["shell", "rm", "-f", "/data/local/tmp/gt-unlock.sh"], timeout=5)
            STATE.log("ℹ️ Export European version detected (e245_eu): Parrot protection is built in at the kernel level.", "info")
            STATE.log("✅ System verifiers (AutoInstallVerifier) and global checks have been disabled successfully!", "success")
            unlocked_ok = True
            break
        elif "GT:REMOUNT" in out:
            STATE.log("🔄 Opening the head unit system partition for writing (remount)...", "info")
            run_adb(["remount"], timeout=15)
            time.sleep(2)
        elif "GT:REBOOT" in out:
            STATE.log("🔄 An intermediate head unit reboot is required to apply the settings (about 1.5 - 2 minutes)...", "info")
            run_adb(["reboot"], timeout=10)
            time.sleep(20)
            reboot_start = time.time()
            reboot_ok = False
            while not STATE.stop_worker:
                if time.time() - reboot_start > 300:
                    STATE.set_error(
                        title="Head unit reboot timed out (5-minute timeout)",
                        reason="The head unit did not come back online after the reboot command.",
                        steps=[
                            "Make sure the car's multimedia screen turned on and booted.",
                            "Check that the USB-A cable is firmly connected to the head unit port and the laptop."
                        ],
                        raw="Reboot timeout exceeded 300s"
                    )
                    return
                c, b_out, _ = run_adb(["shell", "getprop", "sys.boot_completed"], timeout=5)
                if c == 0 and b_out.strip() == "1":
                    reboot_ok = True
                    break
                time.sleep(3)
            if not reboot_ok or STATE.stop_worker:
                return
            run_adb(["root"], timeout=10)
            time.sleep(2)
            run_adb(["wait-for-device"], timeout=10)
        else:
            title, reason, steps = humanize_adb_error(out, context="Unexpected response from the unlock script")
            STATE.set_error(title, reason, steps, raw=out)
            return

    if not unlocked_ok:
        title, reason, steps = humanize_adb_error(out, context="Failed to finish removing restrictions within 8 passes")
        STATE.set_error(title, reason, steps, raw=out)
        return

    # Install Toggle APK if not already installed
    _, toggle_check, _ = run_adb(["shell", "pm", "list", "packages"], timeout=5)
    already_installed = any(pkg in (toggle_check or "") for pkg in ["com.yahooeu2k.ex5.adbtoggle", "com.geely.adbtoggle", "adbtoggle", "geelyadbtoggle"])

    if already_installed:
        STATE.log("📱 The Geely-ADB-Toggle switch is already installed on the head unit. Skipping reinstall.", "success")
    elif os.path.isfile(apk_file):
        STATE.log("📱 Installing the Geely-ADB-Toggle app on the multimedia screen...", "cmd")
        STATE.log("💡 What it is for: this handy toggle in the car menu lets you switch the USB port between a regular music flash drive and a debugging cable in one click.", "info")
        code, out, err = run_adb(["install", "-r", "--user", "10", apk_file], timeout=60)
        if code == 0 and "Success" in out:
            STATE.log("✅ The Geely-ADB-Toggle app was installed successfully into the user profile!", "success")
        else:
            STATE.log(f"Installing into profile 10 returned: {out} {err}. Trying a standard install...", "warning")
            code2, out2, _ = run_adb(["install", "-r", apk_file], timeout=60)
            if "Success" in out2:
                STATE.log("✅ The Geely-ADB-Toggle app was installed successfully!", "success")
            else:
                STATE.log(f"Warning while installing the APK: {out2}", "warning")
    else:
        STATE.log("The toggle APK file was not found in the core folder, skipping the toggle install", "warning")

    # Post-unlock verification
    STATE.log("🔍 Checking the car system's final status...", "cmd")
    _, parrot_check, _ = run_adb(["shell", "getprop", "ro.vendor.ecarx.app_verify"], timeout=5)
    _, pm_check, _ = run_adb(["shell", "pm", "list", "packages", "-e"], timeout=5)
    final_parrot_locked = (parrot_check.strip().lower() == "true")
    final_verifier_active = "com.ecarx.xsfinstallverifier" in (pm_check or "")

    if not final_parrot_locked:
        STATE.log("🔓 Parrot certificates protection: DISABLED (installing APKs is allowed)", "success")
    if not final_verifier_active:
        STATE.log("🔓 System AutoInstallVerifier: DISABLED", "success")

    # Update STATE.last_test so UI reflects unlocked status
    if STATE.last_test and isinstance(STATE.last_test, dict):
        STATE.last_test["parrot_locked"] = final_parrot_locked
        STATE.last_test["verifier_active"] = final_verifier_active
        STATE.last_test["toggle_installed"] = True
        STATE.last_test["needs_unlock"] = False
        STATE.last_test["recommendation"] = "ready"
        STATE.last_test["message"] = "Head unit is fully unlocked!"
    else:
        STATE.last_test = {
            "ok": True,
            "connected": True,
            "serial": STATE.device_serial,
            "model": "Geely Head Unit",
            "firmware": "2.1.4.5+",
            "root_ok": True,
            "parrot_locked": final_parrot_locked,
            "verifier_active": final_verifier_active,
            "toggle_installed": True,
            "needs_unlock": False,
            "recommendation": "ready",
            "message": "Head unit is fully unlocked!"
        }

    STATE.set_status("success", "Congratulations! The unlock is fully complete!", 5)
    STATE.log("🏆 ALL UNLOCK STAGES COMPLETE! Restrictions removed: install apps from https://ex5app.wingie.ru/ (by @wingus), your own APKs, or GeelyTune tweaks.", "success")
