# Geely ADB Unlock Master 🚀

A universal, cross-platform "one-click" solution for permanently unlocking ADB debugging, disabling third-party app install restrictions (Parrot certificates, AutoInstallVerifier), and integrating with the GeelyTune web installer on Geely cars (in particular the Geely EX5 EM-i with 2.1.4.5+ / Flyme Auto / Ecarx firmware).

---

## 📦 Ready-made standalone builds (one-click download)

You do **not** need to install Python or set up an environment. Download a single file for your system from the **[Releases](https://github.com/leonkil318/ADB_Unlock/releases/latest)** page:

| Platform | Single program file | How to run |
| :--- | :--- | :--- |
| **Windows 10/11** | [⬇️ **GeelyUnlock.exe**](https://github.com/leonkil318/ADB_Unlock/releases/latest/download/GeelyUnlock.exe) | Double-click the downloaded `GeelyUnlock.exe` |
| **macOS (Apple Silicon / Intel)** | [⬇️ **GeelyUnlock-macOS**](https://github.com/leonkil318/ADB_Unlock/releases/latest/download/GeelyUnlock-macOS) | `chmod +x GeelyUnlock-macOS` and run |
| **Linux (Ubuntu / Debian / Fedora)** | [⬇️ **GeelyUnlock-Linux**](https://github.com/leonkil318/ADB_Unlock/releases/latest/download/GeelyUnlock-Linux) | `chmod +x GeelyUnlock-Linux` and run |

---

## ⚡ Quick start from source

If you cloned the whole repository:

### Windows
Run the file:
```text
START_Windows.bat
```
*(No Python required - it uses the ready-made standalone binary `core/geely_unlock.exe`.)*

### macOS
Run the file:
```bash
START_Mac.command
```
*(Or in the terminal: `./START_Mac.command`)*

### Linux
Run the file:
```bash
START_Linux.sh
```
*(Or in the terminal: `./START_Linux.sh`)*

---

## 💡 The gist: what does the program do to the car? (A plain-language explanation)

Imagine the multimedia unit in your Geely (the big tablet screen on the dashboard) is an ordinary Android tablet. But from the factory the manufacturer locked it in an **"armored safe"**:
1. 🔒 **The USB port is locked:** if you connect a laptop with an ordinary cable, the computer won't see the tablet.
2. 🚫 **You can't install your own apps:** (navigation, YouTube, streaming, games) - two strict "guards" stand watch.
3. 🔄 **Changes are wiped:** any temporary settings are reset when the ignition is turned off.

**Our app is a safe digital key and guide that solves the task in 3 clear steps:**

```mermaid
graph LR
    A["🔑 Step 1<br>Open service ADB"] --> B["👮 Step 2<br>Put the guards to sleep"]
    B --> C["📱 Step 3<br>Toggle + GeelyTune + APK"]
    style A fill:#003366,stroke:#3399ff,stroke-width:2px,color:#fff
    style B fill:#004d40,stroke:#00bfa5,stroke-width:2px,color:#fff
    style C fill:#4a148c,stroke:#ab47bc,stroke-width:2px,color:#fff
```

### 🚪 Step 1. Opening the "service window" (ADB)
* **Why the jumper?**  
  The factory left a hidden door for engineers. If you short two service contacts, the tablet thinks: *"I'm on the factory bench, I need to open the service port for the engineer."*
* **Why the factory reset?**  
  When you tap reset on the head unit screen (**Main application ➔ My car ➔ Factory reset** and accept all the warnings), the tablet reboots and opens a service window for exactly **20 seconds** with no system restrictions.
* **What does the program do?**  
  The computer continuously scans the USB port. The moment those 20 seconds arrive, the program instantly sends a VHAL command to the car system:  
  *"Switch the USB mode to persistent ADB and lock it in!"*  
  The tablet confirms the command (`Set property`). Done! You can pull out the jumper and put it away - **the port stays open forever**.

### 👮 Step 2. Putting to sleep the "guards" that forbid installing apps
Two guards are on duty in the screen's operating system:
1. **The first guard - "Parrot":**  
  It checks the digital passports (certificates) of every app. If an app is not signed with Geely's factory private key, it blocks it.  
  👉 **What the program does:** it switches the `ro.vendor.ecarx.app_verify=false` flag. The guard closes its eyes and no longer interferes with installation.
2. **The second guard - "AutoInstallVerifier":**  
  A system robot service that watches `.apk` files and blocks their installation.  
  👉 **What the program does:** it disables this service for all head unit users with one safe system command.

### 📱 Step 3. Installing the toggle (ADB Toggle), GeelyTune tweaks and any apps
1. **Toggle in the car menu:** the program installs a small app, **"ADB Toggle"**, right on the head unit screen. You'll be able to switch the port between a music flash drive and a debugging cable in one click.
2. **GeelyTune web service:** the program opens the official service in the browser to install the service assistant and handy Geely interface tweaks (customization, button and screen settings).
3. **Installing third-party apps (navigation, YouTube, etc.):** all the factory barriers (Parrot, verifiers) are fully removed! Now you can freely install any apps - a ready-made catalog of software fitted to the Geely EX5 screen resolution is available at **[ex5app.wingie.ru](https://ex5app.wingie.ru/)** (author - pioneer @wingus from the community chat), or install any of your own `.apk` files directly.

### 🛡️ What about the car's safety?
* **Full isolation:** the multimedia unit runs on a separate Android chip. The program does **NOT** touch the control modules for the engine, brakes, drivetrain or airbags.
* **System partition safety (Overlayfs / Scratch):** the factory system files are not wiped or damaged. All changes are layered with a virtual layer on top of the original firmware. If the head unit had old update files, the script carefully isolates them with no risk to the system.
* **Support for European firmware (`e245_eu`):** the program detects export versions of the Geely EX5 in software by the `ro.build.product` identifier. On such firmware the algorithm adapts to a different protection structure and disables the verifiers without extra head unit reboots.

---

## 📋 Usage scenarios

### ⚡ Scenario 1: Removing install protection (after a dealer update to 2.1.4.5+)
> ⚠️ **CRITICALLY IMPORTANT:** This scenario does **NOT open an originally closed ADB**!  
> It is **ONLY** for cars where ADB access **was already open before**, but after a dealer firmware update (to 2.1.4.5+) the blocks on installing third-party APKs turned back on.  
> **The jumper and factory reset are NOT REQUIRED!** The script instantly disables the Parrot certificates protection (`ro.vendor.ecarx.app_verify=false`), turns off the system `com.ecarx.xsfinstallverifier`, and restores `Geely-ADB-Toggle-1.1.0.apk`.  
> *If ADB on the car is closed from the factory - use Scenario 2 below.*

### 🔌 Scenario 2: Opening ADB from scratch for the first time (via a jumper and Factory Reset)
> Used if ADB debugging on the car is still closed from the factory.
1. **Step 1: Connection:**
   - Connect the laptop with a USB-A ↔ USB-A cable to the car's service port (with the jumper installed).
2. **Step 2: Factory reset:**
   - On the head unit screen go to: **Main application ➔ My car ➔ Factory reset** and accept all the warnings. Automatic interception of the 20-second service window and software lock-in of VHAL (`USB_SWITCH=0`).
3. **Step 3: Remove the jumper and reboot:**
   - Pull out the jumper, reboot the head unit and confirm persistent ADB in normal mode.
4. **Step 4: Remove install restrictions:**
   - Disable the Parrot / AutoInstallVerifier verifiers and install the ADB-Toggle switch.
5. **Step 5: GeelyTune and apps:**
   - Open the [GeelyTune](https://geelytune.github.io) web service to install head unit tweaks, and gain the ability to install any third-party apps (via the catalog of adapted apps at [ex5app.wingie.ru](https://ex5app.wingie.ru/) by @wingus, or your own .apk files).

---

## 📁 Project structure

```text
├── START_Windows.bat        # Launcher for Windows
├── START_Mac.command        # Launcher for macOS
├── START_Linux.sh           # Launcher for Linux
├── README.md                # Project documentation
├── core/                    # Internal components
│   ├── main.py              # TUI application entry point
│   ├── engine.py            # Business-logic engine (ADB, VHAL, Parrot)
│   ├── tui.py               # Zero-Dependency terminal interface
│   ├── geely_unlock.exe     # Standalone binary for Windows
│   ├── bin/                 # Bundled Android Debug Bridge binaries
│   │   ├── adb.exe          # Google ADB for Windows (+ DLLs)
│   │   ├── adb-darwin       # ADB for macOS (Universal)
│   │   └── adb-linux        # ADB for Linux (x86_64)
│   ├── unlock-hu.sh         # Script that removes head unit system restrictions
│   └── Geely-ADB-Toggle...  # APK of the system toggle
└── .agents/                 # AI development rules and knowledge base
```

---

## ⚠️ Disclaimer

Everything you do is at your own risk. Modifying the car's system settings may affect your warranty.
