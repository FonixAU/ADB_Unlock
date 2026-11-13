"""
Geely ADB Unlock Master - Zero-Dependency TUI / CLI Interface
Old-school hacker / patcher terminal style with pure ANSI escape codes.
Features dynamic terminal width detection and responsive word-wrapping.
Works out of the box on Windows (cmd/PowerShell/Windows Terminal), macOS, and Linux.
"""

import sys
import os
import time
import re
import shutil
import textwrap
import threading
import unicodedata
from sound import play_sound, is_sound_enabled

# Terminal color and style definitions
C_RESET   = "\033[0m"
C_BOLD    = "\033[1m"
C_DIM     = "\033[2m"
C_CYAN    = "\033[96;1m"
C_GREEN   = "\033[92;1m"
C_YELLOW  = "\033[93;1m"
C_RED     = "\033[91;1m"
C_WHITE   = "\033[97;1m"
C_GRAY    = "\033[90m"

ANSI_REGEX = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def get_char_width(c):
    """Returns visual terminal cell width of a character (0, 1, or 2)."""
    if c in ('︎', '️') or unicodedata.combining(c):
        return 0
    w = unicodedata.east_asian_width(c)
    if w in ('F', 'W'):
        return 2
    return 1


def visible_len(s):
    """Calculates visible display cell width of a string ignoring ANSI color codes."""
    clean = ANSI_REGEX.sub('', s)
    return sum(get_char_width(c) for c in clean)


def get_terminal_width():
    """Returns dynamic terminal width matching the actual console window."""
    cols = 0
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hOut = kernel32.CreateFileW("CONOUT$", 0x80000000 | 0x40000000, 3, None, 3, 0, None)
            if hOut != -1:
                class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
                    _fields_ = [
                        ('dwSize_X', ctypes.c_short), ('dwSize_Y', ctypes.c_short),
                        ('dwCursorPosition_X', ctypes.c_short), ('dwCursorPosition_Y', ctypes.c_short),
                        ('wAttributes', ctypes.c_ushort),
                        ('srWindow_Left', ctypes.c_short), ('srWindow_Top', ctypes.c_short),
                        ('srWindow_Right', ctypes.c_short), ('srWindow_Bottom', ctypes.c_short),
                        ('dwMaximumWindowSize_X', ctypes.c_short), ('dwMaximumWindowSize_Y', ctypes.c_short),
                    ]
                csbi = CONSOLE_SCREEN_BUFFER_INFO()
                if kernel32.GetConsoleScreenBufferInfo(hOut, ctypes.byref(csbi)):
                    cols = csbi.srWindow_Right - csbi.srWindow_Left + 1
                kernel32.CloseHandle(hOut)
        except Exception:
            pass
    if not cols:
        cols = shutil.get_terminal_size(fallback=(100, 24)).columns
    return max(65, min(cols - 2, 130))


def pad_box_line(text, inner_width):
    """Pads text with spaces so it precisely fills the inner box width in display cells."""
    vlen = visible_len(text)
    if vlen > inner_width:
        clean = ""
        cur = 0
        for ch in ANSI_REGEX.sub('', text):
            cw = get_char_width(ch)
            if cur + cw > inner_width:
                break
            clean += ch
            cur += cw
        return clean + (" " * (inner_width - cur))
    return text + (" " * (inner_width - vlen))


def init_terminal():
    """Initializes terminal encoding and enables ANSI processing on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hOut = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(hOut, ctypes.byref(mode))
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(hOut, mode.value | 0x0004)
        except Exception:
            pass

    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def clear_screen():
    """Clears the terminal screen smoothly."""
    if sys.platform == "win32":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def print_banner():
    """Renders the cyan hacker-style header banner adaptively to window width."""
    W = get_terminal_width()
    inner = W - 2

    top = f"{C_CYAN}╔" + ("═" * inner) + f"╗{C_RESET}"
    bot = f"{C_CYAN}╚" + ("═" * inner) + f"╝{C_RESET}"

    t1 = "GEELY ADB UNLOCK MASTER v2.1.4.5"
    t2 = "Flyme Auto / Ecarx Service Terminal • EX5 EM-i / X80"

    def center_line(text, color):
        v = visible_len(text)
        left = max(0, (inner - v) // 2)
        right = max(0, inner - v - left)
        return f"{C_CYAN}║{C_RESET}{' ' * left}{color}{text}{C_RESET}{' ' * right}{C_CYAN}║{C_RESET}"

    print(top)
    print(center_line(t1, C_WHITE))
    print(center_line(t2, C_GRAY))
    print(bot)


def render_diagnostic_card(state):
    """Renders the live diagnostic status card adaptively."""
    W = get_terminal_width()
    inner = W - 4

    t = state.last_test or {}
    connected = t.get("connected", state.device_state == "connected")
    serial = t.get("serial") or state.device_serial or "Not detected"
    model = t.get("model") or ("Stock Geely head unit" if connected else "-")
    firmware = t.get("firmware") or ("2.1.4.5+" if connected else "-")

    if connected:
        adb_badge = f"{C_GREEN}[ ACTIVE ]{C_RESET}"
    elif t.get("state") == "unauthorized":
        adb_badge = f"{C_YELLOW}[ NEEDS ACCESS ]{C_RESET}"
    else:
        adb_badge = f"{C_RED}[ NOT CONNECTED ]{C_RESET}"

    if connected:
        if t.get("parrot_locked"):
            parrot_badge = f"{C_YELLOW}[ BLOCKING ]{C_RESET}"
        else:
            parrot_badge = f"{C_GREEN}[ DISABLED ]{C_RESET}"

        if t.get("verifier_active"):
            verifier_badge = f"{C_YELLOW}[ ACTIVE ]{C_RESET}"
        else:
            verifier_badge = f"{C_GREEN}[ DISABLED ]{C_RESET}"
    else:
        parrot_badge = f"{C_GRAY}[ - ]{C_RESET}"
        verifier_badge = f"{C_GRAY}[ - ]{C_RESET}"

    title_str = "┌─ CONNECTION STATUS AND DIAGNOSTICS "
    dash_count = max(2, W - visible_len(title_str) - 1)
    print(f"{C_CYAN}{title_str}{'─' * dash_count}┐{C_RESET}")

    if W >= 74:
        # Two-column layout
        half = inner // 2
        col1_w = half
        col2_w = inner - half

        l1_c1 = f"ADB link:      {adb_badge}"
        l1_c2 = f"Serial:      {C_WHITE}{serial}{C_RESET}"
        pad1 = " " * max(0, col1_w - visible_len(l1_c1))
        pad2 = " " * max(0, col2_w - visible_len(l1_c2))
        print(f"{C_CYAN}│{C_RESET} {l1_c1}{pad1}{l1_c2}{pad2} {C_CYAN}│{C_RESET}")

        l2_c1 = f"HU model:      {C_WHITE}{model}{C_RESET}"
        l2_c2 = f"Firmware:    {C_CYAN}{firmware}{C_RESET}"
        pad1 = " " * max(0, col1_w - visible_len(l2_c1))
        pad2 = " " * max(0, col2_w - visible_len(l2_c2))
        print(f"{C_CYAN}│{C_RESET} {l2_c1}{pad1}{l2_c2}{pad2} {C_CYAN}│{C_RESET}")

        l3_c1 = f"Parrot guard:  {parrot_badge}"
        l3_c2 = f"Verifier:    {verifier_badge}"
        pad1 = " " * max(0, col1_w - visible_len(l3_c1))
        pad2 = " " * max(0, col2_w - visible_len(l3_c2))
        print(f"{C_CYAN}│{C_RESET} {l3_c1}{pad1}{l3_c2}{pad2} {C_CYAN}│{C_RESET}")
    else:
        # Stacked layout for compact terminal
        def print_single(text):
            p = pad_box_line(text, inner)
            print(f"{C_CYAN}│{C_RESET} {p} {C_CYAN}│{C_RESET}")

        print_single(f"ADB link:      {adb_badge}")
        print_single(f"Serial:        {C_WHITE}{serial}{C_RESET}")
        print_single(f"HU model:      {C_WHITE}{model}{C_RESET}")
        print_single(f"Firmware:      {C_CYAN}{firmware}{C_RESET}")
        print_single(f"Parrot guard:  {parrot_badge}")
        print_single(f"Verifier:      {verifier_badge}")

    print(f"{C_CYAN}└{'─' * (W - 2)}┘{C_RESET}")


def render_menu(state):
    """Renders the action menu adaptively."""
    W = get_terminal_width()
    inner = W - 4

    t = state.last_test or {}
    connected = t.get("connected", state.device_state == "connected")
    needs_unlock = t.get("needs_unlock", True)

    title_str = "┌─ ACTION MENU "
    dash_count = max(2, W - visible_len(title_str) - 1)
    print(f"{C_CYAN}{title_str}{'─' * dash_count}┐{C_RESET}")

    def print_menu_item(text):
        p = pad_box_line(text, inner)
        print(f"{C_CYAN}│{C_RESET} {p} {C_CYAN}│{C_RESET}")

    if connected and needs_unlock:
        print_menu_item(f"{C_GREEN}{C_BOLD}[1] Remove install protection (dealer 2.1.4.5+, ONLY if ADB is already open){C_RESET}")
    else:
        print_menu_item(f"{C_WHITE}[1]{C_RESET} Remove install protection (only if ADB is already open / after dealer)")

    print_menu_item(f"{C_WHITE}[2]{C_RESET} Open ADB from scratch (lock in the port via jumper + head unit reset)")
    print_menu_item(f"{C_WHITE}[3]{C_RESET} Check head unit status (connection and lock-state diagnostics)")
    print_menu_item(f"{C_WHITE}[4]{C_RESET} Open GeelyTune in the browser (head unit tweaks and assistant)")
    print_menu_item(f"{C_GREEN}{C_BOLD}[5] Open the EX5 Apps store (install software via the browser, by @wingus){C_RESET}")
    print_menu_item(f"{C_WHITE}[6]{C_RESET} Restart the ADB service (clear stuck processes)")
    sound_badge = f"{C_GREEN}[ ON ]{C_RESET}" if is_sound_enabled() else f"{C_GRAY}[ OFF ]{C_RESET}"
    print_menu_item(f"{C_WHITE}[7]{C_RESET} Sound effects: {sound_badge}")
    print_menu_item(f"{C_YELLOW}[8]{C_RESET} Help: What does the program do? (In plain words)")
    print_menu_item(f"{C_GRAY}[0] Exit{C_RESET}")

    print(f"{C_CYAN}└{'─' * (W - 2)}┘{C_RESET}")


def render_recent_logs(state, count=5):
    """Prints recent log entries with responsive multi-line word-wrapping."""
    W = get_terminal_width()
    inner = W - 4

    title_str = "┌─ MESSAGE LOG "
    dash_count = max(2, W - visible_len(title_str) - 1)
    print(f"{C_CYAN}{title_str}{'─' * dash_count}┐{C_RESET}")

    recent = state.logs[-count:] if state.logs else []
    if not recent:
        p = pad_box_line(f"{C_GRAY}The log is empty. Choose an action in the menu above.{C_RESET}", inner)
        print(f"{C_CYAN}│{C_RESET} {p} {C_CYAN}│{C_RESET}")
    else:
        for entry in recent:
            level = entry.get("level", "info")
            color = {
                "cmd": C_CYAN,
                "success": C_GREEN,
                "warning": C_YELLOW,
                "error": C_RED,
                "info": C_WHITE
            }.get(level, C_WHITE)

            raw_text = entry.get("formatted", entry.get("text", ""))
            clean_text = ANSI_REGEX.sub('', raw_text)

            # Responsive word wrapping inside box
            wrapped_lines = textwrap.wrap(clean_text, width=inner, subsequent_indent="   ")
            for sub_line in wrapped_lines:
                colored_sub = f"{color}{sub_line}{C_RESET}"
                p = pad_box_line(colored_sub, inner)
                print(f"{C_CYAN}│{C_RESET} {p} {C_CYAN}│{C_RESET}")

    print(f"{C_CYAN}└{'─' * (W - 2)}┘{C_RESET}")


def print_error_card(err):
    """Renders a structured, clear diagnostic error card with actionable advice."""
    W = get_terminal_width()
    inner = W - 4

    title_str = "┌─ DIAGNOSTICS AND CAUSE OF FAILURE "
    dash_count = max(2, W - visible_len(title_str) - 1)
    print(f"\n{C_RED}{title_str}{'─' * dash_count}┐{C_RESET}")

    def print_line(styled_text):
        p = pad_box_line(styled_text, inner)
        print(f"{C_RED}│{C_RESET} {p} {C_RED}│{C_RESET}")

    def print_empty():
        print(f"{C_RED}│{C_RESET} {' ' * inner} {C_RED}│{C_RESET}")

    # Title
    title = err.get("title", "Operation failed")
    print_line(f"{C_RED}{C_BOLD}[!] FAILURE: {title}{C_RESET}")
    print(f"{C_RED}├{'─' * (W - 2)}┤{C_RESET}")

    # Reason
    reason = err.get("reason", "")
    if reason:
        print_line(f"{C_YELLOW}{C_BOLD}• What went wrong:{C_RESET}")
        for r_line in textwrap.wrap(reason, width=inner - 4):
            print_line(f"  {r_line}")
        print_empty()

    # Steps
    steps = err.get("steps", [])
    if steps:
        print_line(f"{C_CYAN}{C_BOLD}• Recommended actions:{C_RESET}")
        for i, step in enumerate(steps, 1):
            wrapped = textwrap.wrap(f"{i}. {step}", width=inner - 4, subsequent_indent="   ")
            for s_line in wrapped:
                print_line(f"  {s_line}")
        print_empty()

    # Technical ADB details (if available and different from title)
    raw = err.get("raw", "")
    if raw and raw.strip() != title.strip():
        print_line(f"{C_GRAY}{C_BOLD}• Raw system error code (ADB):{C_RESET}")
        clean_raw = ANSI_REGEX.sub('', str(raw)).strip()
        for raw_line in clean_raw.splitlines()[:3]:
            for w_r in textwrap.wrap(raw_line, width=inner - 4):
                print_line(f"  {C_GRAY}{w_r}{C_RESET}")

    print(f"{C_RED}└{'─' * (W - 2)}┘{C_RESET}")


def run_interactive_task(state, task_fn, title="Running operation"):
    """Runs a background task while streaming live logs and an animated spinner adaptively."""
    clear_screen()
    print_banner()
    W = get_terminal_width()

    print(f"\n{C_CYAN}{C_BOLD}[*] {title.upper()}{C_RESET}")
    print(f"{C_GRAY}Press Ctrl+C to interrupt if necessary.{C_RESET}\n")

    state.stop_worker = False
    state.status = "running"
    state.last_error_details = None
    worker_finished = threading.Event()
    play_sound("step")

    def runner():
        try:
            task_fn()
        except Exception as e:
            state.log(f"Exception in the process: {e}", "error")
        finally:
            worker_finished.set()

    t = threading.Thread(target=runner, daemon=True)
    t.start()

    spinner_frames = ["-", "\\", "|", "/"]
    idx = 0
    last_log_count = len(state.logs)

    try:
        while not worker_finished.is_set():
            # Check for new logs
            current_len = len(state.logs)
            if current_len > last_log_count:
                # Clear active spinner line before printing logs
                if sys.stdout.isatty():
                    sys.stdout.write("\r" + (" " * (W + 2)) + "\r")
                    sys.stdout.flush()
                for entry in state.logs[last_log_count:current_len]:
                    lvl = entry.get("level", "info")
                    col = {
                        "cmd": C_CYAN,
                        "success": C_GREEN,
                        "warning": C_YELLOW,
                        "error": C_RED,
                        "info": C_WHITE
                    }.get(lvl, C_WHITE)

                    raw_text = entry.get('formatted', entry.get('text', ''))
                    clean_text = ANSI_REGEX.sub('', raw_text)
                    for wrapped_line in textwrap.wrap(clean_text, width=max(40, W - 4), subsequent_indent="   "):
                        print(f" {col}{wrapped_line}{C_RESET}")
                last_log_count = current_len

            if sys.stdout.isatty():
                frame = spinner_frames[idx % len(spinner_frames)]
                status_text = state.status_message[:max(10, W - 14)]
                spinner_line = f" {C_CYAN}[{frame}]{C_RESET} {C_GRAY}{status_text}{C_RESET}"
                padding = " " * max(0, W - 2 - visible_len(spinner_line))
                sys.stdout.write(f"\r{spinner_line}{padding}\r")
                sys.stdout.flush()

            # Soft, musical sonar progress beacon every ~2.5 seconds (25 ticks * 0.1s)
            if idx > 0 and idx % 25 == 0:
                play_sound("radar")

            idx += 1
            time.sleep(0.1)

        # Clear spinner line completely
        if sys.stdout.isatty():
            sys.stdout.write("\r" + (" " * (W + 2)) + "\r")
            sys.stdout.flush()

        # Print remaining logs
        current_len = len(state.logs)
        if current_len > last_log_count:
            for entry in state.logs[last_log_count:current_len]:
                lvl = entry.get("level", "info")
                col = {
                    "cmd": C_CYAN,
                    "success": C_GREEN,
                    "warning": C_YELLOW,
                    "error": C_RED,
                    "info": C_WHITE
                }.get(lvl, C_WHITE)

                raw_text = entry.get('formatted', entry.get('text', ''))
                clean_text = ANSI_REGEX.sub('', raw_text)
                for wrapped_line in textwrap.wrap(clean_text, width=max(40, W - 4), subsequent_indent="   "):
                    print(f" {col}{wrapped_line}{C_RESET}")

        if state.status == "success":
            play_sound("success")
            print(f"\n{C_GREEN}{C_BOLD}[OK] OPERATION COMPLETED SUCCESSFULLY!{C_RESET}")
        elif state.status == "error":
            play_sound("error")
            err = getattr(state, "last_error_details", None)
            if err:
                print_error_card(err)
            else:
                title = state.status_message
                print(f"\n{C_RED}{C_BOLD}[!] AN ERROR OCCURRED: {title}{C_RESET}")

    except KeyboardInterrupt:
        state.stop_worker = True
        play_sound("step")
        print(f"\n\n{C_YELLOW}[!] Operation interrupted by the user.{C_RESET}")

    print()
    try:
        input(f"{C_CYAN}Press Enter to return to the menu...{C_RESET}")
    except (KeyboardInterrupt, EOFError):
        pass


def render_help_screen():
    """Renders a friendly, easy-to-understand explanation of what the program does with the car."""
    clear_screen()
    print_banner()
    W = get_terminal_width()
    inner = W - 4

    def box_title(title):
        t = f"┌─ {title} "
        dash = max(2, W - visible_len(t) - 1)
        print(f"\n{C_CYAN}{t}{'─' * dash}┐{C_RESET}")

    def box_line(text, color=C_WHITE):
        clean = ANSI_REGEX.sub('', text)
        for line in textwrap.wrap(clean, width=inner, subsequent_indent="  "):
            p = pad_box_line(f"{color}{line}{C_RESET}", inner)
            print(f"{C_CYAN}│{C_RESET} {p} {C_CYAN}│{C_RESET}")

    def box_bottom():
        print(f"{C_CYAN}└{'─' * (W - 2)}┘{C_RESET}")

    box_title("[1] WHAT THE PROGRAM DOES: WHAT ARE WE DOING TO THE CAR?")
    box_line("The Geely multimedia screen is just an ordinary Android tablet. But from the", C_WHITE)
    box_line("factory it is locked in an \"armored safe\":", C_WHITE)
    box_line(" 1. The USB port is locked: a cable from the laptop cannot see it.", C_YELLOW)
    box_line(" 2. You can't install your own apps (Maps, YouTube) - two \"guards\" stand watch.", C_YELLOW)
    box_line(" 3. Any temporary changes are reset when the car restarts.", C_YELLOW)
    box_line("Our program is a safe digital key that sets everything up.", C_GREEN)
    box_bottom()

    box_title("[!] WHAT'S THE DIFFERENCE: ITEM 1 OR ITEM 2?")
    box_line("• Item [1] - Remove install protection (after a dealer update to 2.1.4.5+):", C_YELLOW)
    box_line("  IMPORTANT: Item [1] does NOT open a closed ADB port! It is ONLY needed if ADB", C_RED)
    box_line("  was already open before, but a dealer update reset the right to install APKs.", C_WHITE)
    box_line("  No jumper or reset needed: the script disables Parrot and the verifiers in seconds.", C_GREEN)
    box_line("• Item [2] - Open ADB from scratch (port closed from the factory):", C_CYAN)
    box_line("  For a new car where the laptop can't see the head unit over the cable. Needs a jumper", C_WHITE)
    box_line("  and a head unit reset (Main application -> My car -> Factory reset),", C_WHITE)
    box_line("  to catch the 20-second window and open the port forever via a VHAL command.", C_GREEN)
    box_bottom()

    box_title("[STEP 1] OPENING THE SERVICE CONNECTION (ADB)")
    box_line("• Why the jumper? The factory left a hidden door for engineers. When two contacts", C_WHITE)
    box_line("  are shorted, the tablet thinks: \"I'm in service, I need to open the service port\".", C_WHITE)
    box_line("• Why the factory reset? During a factory reset (in the car menu) the tablet", C_WHITE)
    box_line("  reboots and opens a service window for exactly 20 seconds.", C_WHITE)
    box_line("• What does the program do? The computer catches those 20 seconds and instantly sends", C_CYAN)
    box_line("  the VHAL lock-in command: \"Enable persistent ADB!\". The tablet saves the flag.", C_CYAN)
    box_line("  After that the jumper is removed forever - the port will never close again.", C_GREEN)
    box_bottom()

    box_title("[STEP 2] PUTTING THE INSTALL-BLOCKING \"GUARDS\" TO SLEEP")
    box_line("1. The \"Parrot\" guard checks the Geely factory's digital signature.", C_WHITE)
    box_line("   If there's no signature it rejects the APK. We switch app_verify=false.", C_CYAN)
    box_line("   The guard calmly falls asleep and no longer nitpicks anyone.", C_GREEN)
    box_line("2. The \"AutoInstallVerifier\" guard is a system robot that blocks APK installs.", C_WHITE)
    box_line("   The program forcibly disables this robot for all head unit profiles.", C_GREEN)
    box_bottom()

    box_title("[STEP 3] THE TOGGLE (ADB TOGGLE), GEELYTUNE TWEAKS AND APPS")
    box_line("• An ADB Toggle switch is placed on the head unit screen: in one click you can switch", C_WHITE)
    box_line("  the port between a regular music flash drive and a debugging cable.", C_WHITE)
    box_line("• GeelyTune opens for installing the head unit assistant and handy interface tweaks.", C_CYAN)
    box_line("• Apps now install without obstacles: software adapted to the car screen", C_WHITE)
    box_line("  is available at https://ex5app.wingie.ru/ (author - pioneer @wingus)", C_GREEN)
    box_line("  or install any of your own APK files directly.", C_GREEN)
    box_bottom()

    box_title("[SAFETY] WHAT ABOUT THE CAR AND THE TABLET?")
    box_line("• We do NOT touch the firmware of the engine, brakes, steering or airbags.", C_WHITE)
    box_line("• System partitions are protected: changes are layered via a virtual layer (overlay).", C_WHITE)
    box_line("• Factory files are not overwritten, and old temporary layers are safely isolated.", C_WHITE)
    box_line("• European versions (e245_eu) are detected in software and protected from extra reboots.", C_WHITE)
    box_bottom()

    print()
    try:
        input(f"{C_CYAN}Press Enter to return to the main menu...{C_RESET}")
    except (KeyboardInterrupt, EOFError):
        pass
