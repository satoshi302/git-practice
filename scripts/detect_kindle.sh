#!/usr/bin/env bash
# Quick Kindle PW4 USB diagnosis without Python.

echo "=== Kindle PW4 USB Detection ==="
echo

echo "--- lsusb (Amazon VID 0x1949 / NXP VID 0x15a2) ---"
lsusb | grep -iE "(1949|15a2|amazon|kindle)" || echo "  (none found)"
echo

echo "--- Network interfaces (USBNet) ---"
ip link show usb0 2>/dev/null || true
ip link show rndis0 2>/dev/null || true
ip link show | grep -iE "(usb|rndis)" || echo "  (none found)"
echo

echo "--- Serial devices ---"
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "  (none found)"
echo

echo "--- Recent dmesg (Amazon/NXP) ---"
dmesg --time-format reltime 2>/dev/null | tail -30 \
  | grep -iE "(kindle|amazon|1949|15a2|usb|serial)" || \
  dmesg | tail -30 | grep -iE "(kindle|amazon|1949|15a2|usb|serial)" || \
  echo "  (no relevant entries)"
echo

echo "Done."
