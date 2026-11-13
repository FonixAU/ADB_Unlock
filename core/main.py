"""
Geely ADB Unlock Master - Native CLI / TUI Application Entry Point
Standalone executable launcher without browser or local web server requirements.
"""

import sys
import os
import time
import webbrowser

# Add current directory to path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from engine import (
    STATE,
    locate_or_download_adb,
    kill_adb_processes,
    stop_adb_server,
    check_devices,
    test_adb_connection,
    run_adb,
    worker_catch_factory_reset,
    worker_reboot_and_verify,
    worker_unlock_and_install
)

from tui import (
    init_terminal,
    clear_screen,
    print_banner,
    render_diagnostic_card,
    render_menu,
    render_recent_logs,
    run_interactive_task,
    render_help_screen,
    C_RESET,
    C_BOLD,
    C_CYAN,
    C_GREEN,
    C_YELLOW,
    C_RED,
    C_WHITE,
    C_GRAY
)

from sound import toggle_sound, play_sound


def safe_input(prompt, default=""):
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        return default


def run_full_wizard():
    """Runs the wizard for initial ADB unlock with factory reset."""
    clear_screen()
    print_banner()
    print(f"\n{C_CYAN}{C_BOLD}[*] SCENARIO: INITIAL ADB UNLOCK{C_RESET}\n")
    print(f"{C_WHITE}READY TO INTERCEPT:{C_RESET}")
    print(" 1. A USB-A <-> USB-A cable connects the laptop and the car's service port.")
    print(" 2. The jumper is installed, the head unit screen is active.")
    print(" 3. After you confirm, the connection-waiting loop will start.")
    print(f" 4. On the car screen go to:")
    print(f"    {C_YELLOW}Main application -> My car -> Factory reset{C_RESET}")
    print("    and accept all the warnings.\n")

    choice = safe_input(f"{C_CYAN}Ready to begin intercepting the service window? [Enter - Yes, 0 - Cancel] > {C_RESET}", default="0").strip()
    if choice == "0":
        return

    # Step 2: Catch factory reset
    run_interactive_task(STATE, worker_catch_factory_reset, "Step 2: Waiting for head unit factory reset and locking in VHAL")
    if STATE.status != "success":
        return

    # Step 3: Remove jumper & reboot
    clear_screen()
    print_banner()
    print(f"\n{C_GREEN}{C_BOLD}[OK] VHAL LOCKED IN (Set property received)!{C_RESET}\n")
    print(f"{C_WHITE}JUMPER ACTIONS:{C_RESET}")
    print(f" 1. {C_YELLOW}Carefully remove the jumper.{C_RESET}")
    print(" 2. The USB cable stays connected to the head unit.\n")

    ans = safe_input(f"{C_CYAN}Jumper removed? [Enter - Reboot head unit and verify ADB, 0 - Cancel] > {C_RESET}", default="0").strip()
    if ans == "0":
        return
    run_interactive_task(STATE, worker_reboot_and_verify, "Step 3: Rebooting head unit and verifying persistent ADB")
    if STATE.status != "success":
        return

    # Step 4: Unlock Parrot & Install Toggle
    run_interactive_task(STATE, worker_unlock_and_install, "Step 4: Removing Parrot, disabling the verifier and installing the toggle")
    if STATE.status == "success":
        post_unlock_prompt()


def run_quick_unlock():
    """Runs quick unlock for cars with existing ADB after dealer 2.1.4.5+ update."""
    clear_screen()
    print_banner()
    print(f"\n{C_CYAN}{C_BOLD}[*] ITEM 1: REMOVE INSTALL PROTECTION (DEALER 2.1.4.5+){C_RESET}\n")
    print(f"{C_RED}{C_BOLD}⚠️  WARNING: ITEM [1] DOES NOT OPEN A CLOSED ADB PORT!{C_RESET}")
    print(f"{C_YELLOW}This item is ONLY for cars where ADB WAS ALREADY OPEN before{C_RESET}")
    print("(for example, you opened it earlier, then updated at the dealer to 2.1.4.5+,")
    print("which reset the settings and blocked installing third-party APKs).\n")
    print(f"{C_GREEN}• The jumper and factory reset are NOT REQUIRED!{C_RESET}")
    print("• The script will instantly disable the Parrot protection in build.prop, turn off AutoInstallVerifier")
    print("  and install the Geely-ADB-Toggle switch on the car screen.\n")
    print(f"{C_GRAY}If ADB on the car is still closed from the factory - go back and choose [2] (Open ADB from scratch).{C_RESET}\n")

    # Guard: check if vehicle responds over ADB
    if STATE.device_state != "connected":
        code, stdout, _ = run_adb(["get-state"], timeout=2)
        if code != 0 or stdout.strip() != "device":
            print(f"{C_YELLOW}[!] Note: the car is not responding over ADB right now.{C_RESET}")
            print(f"If ADB is closed from the factory, Item [1] will not work - choose {C_BOLD}[2] Open ADB from scratch{C_RESET} in the menu.")
            print("If ADB was already open, check that the USB-A cable is firmly connected.\n")

    ans = safe_input(f"{C_CYAN}Start the install-protection removal procedure? [Enter - Yes, 0 - Back] > {C_RESET}", default="0").strip()
    if ans == "0":
        return

    # Run quick unlock
    run_interactive_task(STATE, worker_unlock_and_install, "Express removal of Parrot and AutoInstallVerifier protection")
    if STATE.status == "success":
        post_unlock_prompt()


def post_unlock_prompt():
    """Prompt after successful unlock to open ex5app store or GeelyTune."""
    clear_screen()
    print_banner()
    print(f"\n{C_GREEN}{C_BOLD}[OK] CONGRATULATIONS! THE UNLOCK IS FULLY COMPLETE!{C_RESET}\n")
    print(" • Persistent ADB: active")
    print(" • Parrot certificates check: disabled (installing third-party APKs is allowed)")
    print(" • AutoInstallVerifier: disabled")
    print(" • Geely-ADB-Toggle app: ready to use on the car screen\n")
    print(f"{C_CYAN}WHERE TO GO NEXT?{C_RESET}")
    print(f" {C_GREEN}[1]{C_RESET} Open the {C_BOLD}EX5 Apps{C_RESET} web store (https://ex5app.wingie.ru/ - software by @wingus, via the browser)")
    print(f" {C_WHITE}[2]{C_RESET} Open the {C_BOLD}GeelyTune{C_RESET} web service (https://geelytune.github.io - head unit tweaks)")
    print(f" {C_GRAY}[0] Return to the main menu{C_RESET}\n")

    ans = safe_input(f"{C_CYAN}Choose an action [1, 2, 0] > {C_RESET}", default="1").strip()
    if ans == "1":
        print(f"\n{C_CYAN}Freeing the USB port (stopping background adb.exe processes)...{C_RESET}")
        stop_adb_server()
        print(f"{C_GREEN}[OK] ADB service stopped. The port is fully free for the browser (WebUSB)!{C_RESET}")
        webbrowser.open("https://ex5app.wingie.ru/")
        print(f"{C_WHITE}In the tab that opens, click \"Connect\" and install software right from the browser.{C_RESET}")
        time.sleep(2)
    elif ans == "2":
        print(f"\n{C_CYAN}Freeing the USB port (stopping background adb.exe processes)...{C_RESET}")
        stop_adb_server()
        print(f"{C_GREEN}[OK] ADB service stopped. The port is fully free for the browser (WebUSB)!{C_RESET}")
        webbrowser.open("https://geelytune.github.io")
        print(f"{C_WHITE}In the tab that opens, click \"Connect\" and select your car.{C_RESET}")
        time.sleep(2)


def main():
    init_terminal()
    clear_screen()
    print_banner()
    print(f"\n{C_CYAN}Initializing modules and checking ADB...{C_RESET}")

    locate_or_download_adb()
    check_devices()

    # Automatic quick test on startup if device is visible
    if STATE.device_state == "connected":
        test_adb_connection()

    while True:
        clear_screen()
        print_banner()
        render_diagnostic_card(STATE)
        render_menu(STATE)
        render_recent_logs(STATE, count=4)

        choice = safe_input(f"\n{C_CYAN}{C_BOLD}Choose a menu item [0-8, S - Sound, ? - Help] > {C_RESET}", default="0").strip()

        if choice == "1":
            play_sound("step")
            run_quick_unlock()
        elif choice == "2":
            play_sound("step")
            run_full_wizard()
        elif choice == "3":
            play_sound("step")
            run_interactive_task(STATE, test_adb_connection, "Connection diagnostics and head unit status check")
        elif choice == "4":
            play_sound("step")
            print(f"\n{C_CYAN}Freeing the USB port (stopping background adb.exe processes)...{C_RESET}")
            stop_adb_server()
            print(f"{C_GREEN}[OK] ADB service stopped. The port is free for the browser (WebUSB)!{C_RESET}")
            webbrowser.open("https://geelytune.github.io")
            STATE.log("ADB service stopped. Opened GeelyTune (head unit tweaks): https://geelytune.github.io", "success")
            time.sleep(1.5)
        elif choice == "5":
            play_sound("step")
            print(f"\n{C_CYAN}Freeing the USB port (stopping background adb.exe processes)...{C_RESET}")
            stop_adb_server()
            print(f"{C_GREEN}[OK] ADB service stopped. The port is free for the browser (WebUSB)!{C_RESET}")
            webbrowser.open("https://ex5app.wingie.ru/")
            STATE.log("ADB service stopped. Opened the EX5 Apps web installer: https://ex5app.wingie.ru/", "success")
            print(f"{C_WHITE}The browser will open the app catalog by @wingus.{C_RESET}")
            print(f"{C_WHITE}Click \"Connect\" in the browser and install apps straight over WebUSB!{C_RESET}")
            time.sleep(2)
        elif choice == "6":
            play_sound("step")
            run_interactive_task(STATE, kill_adb_processes, "Restarting the ADB service")
            check_devices()
        elif choice.lower() in ["7", "s"]:
            enabled = toggle_sound()
            status_str = "ON" if enabled else "OFF"
            STATE.log(f"Sound effects: {status_str}", "info")
        elif choice.lower() in ["8", "?", "help", "h", "info"]:
            play_sound("step")
            render_help_screen()
        elif choice in ["0", "q", "exit", "quit"]:
            play_sound("step")
            stop_adb_server()
            print(f"\n{C_GREEN}Shutting down. Safe travels!{C_RESET}")
            time.sleep(0.5)
            break
        else:
            time.sleep(0.2)



if __name__ == "__main__":
    main()
