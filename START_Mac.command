#!/usr/bin/env bash
cd "$(dirname "$0")"
clear
echo "==================================================="
echo "    Starting Geely ADB Unlock Master..."
echo "==================================================="
echo ""

chmod +x "core/bin/adb"* 2>/dev/null
chmod +x "core/unlock-hu.sh" 2>/dev/null

if [ -f "core/geely_unlock" ]; then
    chmod +x "core/geely_unlock"
    "./core/geely_unlock"
    exit 0
elif [ -f "core/GeelyUnlock-macOS" ]; then
    chmod +x "core/GeelyUnlock-macOS"
    "./core/GeelyUnlock-macOS"
    exit 0
elif [ -f "core/geely_unlock_mac" ]; then
    chmod +x "core/geely_unlock_mac"
    "./core/geely_unlock_mac"
    exit 0
fi

if command -v python3 >/dev/null 2>&1; then
    python3 "core/main.py"
elif command -v python >/dev/null 2>&1; then
    python "core/main.py"
else
    echo "ERROR: Python 3 was not found on the system."
    echo "Please install Python 3 to run."
    read -p "Press Enter to exit..."
fi
