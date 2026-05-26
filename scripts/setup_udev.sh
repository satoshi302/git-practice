#!/usr/bin/env bash
# Install udev rules for passwordless USB access to Kindle recovery devices.

set -e

RULES_SRC="$(cd "$(dirname "$0")/.." && pwd)/udev/99-kindle-recovery.rules"
RULES_DST="/etc/udev/rules.d/99-kindle-recovery.rules"

if [ ! -f "$RULES_SRC" ]; then
  echo "ERROR: rules file not found: $RULES_SRC"
  exit 1
fi

echo "Installing udev rules to $RULES_DST..."
sudo cp "$RULES_SRC" "$RULES_DST"
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "Done. Reconnect your device for rules to take effect."

# Ensure current user is in plugdev and dialout groups
for grp in plugdev dialout; do
  if ! id -nG | grep -qw "$grp"; then
    echo "Adding $USER to $grp group..."
    sudo usermod -aG "$grp" "$USER"
    echo "  (log out and back in for group change to take effect)"
  fi
done
