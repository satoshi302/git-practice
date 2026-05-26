#!/usr/bin/env bash
# Quick Kindle PW4 USB diagnosis without Python.
# Supports macOS and Linux.

echo "=== Kindle PW4 USB Detection ==="
echo

OS="$(uname -s)"

echo "--- USB devices (Amazon VID 0x1949 / NXP VID 0x15a2) ---"
if [ "$OS" = "Darwin" ]; then
    system_profiler SPUSBDataType 2>/dev/null \
      | grep -iE "(1949|15a2|amazon|kindle|Product ID|Vendor ID)" \
      || echo "  (none found)"
else
    lsusb | grep -iE "(1949|15a2|amazon|kindle)" || echo "  (none found)"
fi
echo

echo "--- Network interfaces (USBNet) ---"
if [ "$OS" = "Darwin" ]; then
    ifconfig 2>/dev/null | grep -iE "(usb|rndis|en[0-9])" | head -10 || echo "  (none found)"
else
    ip link show usb0 2>/dev/null || true
    ip link show rndis0 2>/dev/null || true
    ip link show | grep -iE "(usb|rndis)" || echo "  (none found)"
fi
echo

echo "--- Serial devices ---"
if [ "$OS" = "Darwin" ]; then
    ls /dev/cu.usbserial-* /dev/cu.SLAB_USBtoUART /dev/cu.usbmodem* 2>/dev/null \
      || echo "  (none found)"
else
    ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "  (none found)"
fi
echo

echo "--- Recent system log (Amazon/NXP) ---"
if [ "$OS" = "Darwin" ]; then
    log show --last 2m 2>/dev/null \
      | grep -iE "(kindle|amazon|1949|15a2|usb serial)" | tail -20 \
      || echo "  (no relevant entries)"
else
    dmesg --time-format reltime 2>/dev/null | tail -30 \
      | grep -iE "(kindle|amazon|1949|15a2|usb|serial)" || \
      dmesg | tail -30 | grep -iE "(kindle|amazon|1949|15a2|usb|serial)" || \
      echo "  (no relevant entries)"
fi
echo

echo "Done."
