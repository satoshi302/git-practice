#!/usr/bin/env bash
# Setup script for Kindle PW4 recovery tool dependencies.
# Supports macOS (Homebrew) and Linux (udev).

set -e

OS="$(uname -s)"

if [ "$OS" = "Darwin" ]; then
    echo "=== macOS Setup ==="

    if ! command -v brew &>/dev/null; then
        echo "Homebrew not found. Install it from https://brew.sh first."
        exit 1
    fi

    echo "Installing system dependencies via Homebrew..."
    brew install libusb hidapi python3

    echo "Installing Python packages..."
    pip3 install -r "$(dirname "$0")/../requirements.txt"

    echo
    echo "Done. On macOS, USB device access requires no special permissions."
    echo "USB-UART adapters will appear as /dev/cu.usbserial-* or /dev/cu.SLAB_USBtoUART"
    echo "Run: python scripts/recover.py detect"

else
    echo "=== Linux Setup (udev) ==="

    RULES_SRC="$(cd "$(dirname "$0")/.." && pwd)/udev/99-kindle-recovery.rules"
    RULES_DST="/etc/udev/rules.d/99-kindle-recovery.rules"

    if [ ! -f "$RULES_SRC" ]; then
        echo "ERROR: rules file not found: $RULES_SRC"
        exit 1
    fi

    echo "Installing system dependencies..."
    sudo apt-get install -y libhidapi-libusb0 python3-pip

    echo "Installing Python packages..."
    pip3 install -r "$(dirname "$0")/../requirements.txt"

    echo "Installing udev rules to $RULES_DST..."
    sudo cp "$RULES_SRC" "$RULES_DST"
    sudo udevadm control --reload-rules
    sudo udevadm trigger

    for grp in plugdev dialout; do
        if ! id -nG | grep -qw "$grp"; then
            echo "Adding $USER to $grp group..."
            sudo usermod -aG "$grp" "$USER"
            echo "  (log out and back in for group change to take effect)"
        fi
    done

    echo "Done. Reconnect your device for udev rules to take effect."
fi
