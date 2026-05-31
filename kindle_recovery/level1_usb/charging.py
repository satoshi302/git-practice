import time

from kindle_recovery.common.logger import get_logger
from kindle_recovery.common.usb_utils import DeviceMode, wait_for_device

log = get_logger(__name__)

# Amazon VID - any PID
AMAZON_VID = 0x1949
NXP_VID = 0x15A2
NXP_PID_IMX7 = 0x0076
NXP_PID_IMX6SL = 0x007D


def wait_for_min_charge(timeout_minutes: float = 20.0, poll_seconds: float = 15.0) -> bool:
    """
    Wait for a completely dead device to charge enough to enumerate on USB.

    A fully discharged Li-ion may need 15-20 minutes before the PMU allows
    USB enumeration. We poll for any Amazon or NXP VID on the bus.
    """
    log.warning("Device not detected. Waiting up to %.0f minutes for charge...", timeout_minutes)
    log.warning("Connect the Kindle to a WALL CHARGER (not a PC USB hub) for best results.")

    deadline = time.monotonic() + timeout_minutes * 60
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        remaining = (deadline - time.monotonic()) / 60
        log.info("[attempt %d] Polling USB... (%.1f min remaining)", attempt, remaining)

        for pid in (0x0004, 0x0005, 0x0006):
            dev = wait_for_device(AMAZON_VID, pid, timeout=poll_seconds)
            if dev:
                log.info("Device appeared in mode: %s", dev.mode.value)
                return True

        for pid in (NXP_PID_IMX7, NXP_PID_IMX6SL):
            dev = wait_for_device(NXP_VID, pid, timeout=2.0)
            if dev:
                log.info("Device in SDP ROM mode (NXP VID detected).")
                return True

    log.error("Device did not appear after %.0f minutes.", timeout_minutes)
    log.error("Possible causes: dead battery cell, faulty cable, or USB port power limit.")
    log.error("Try a different cable, a 5V/2A wall charger, and wait another 30 minutes.")
    return False


def check_charging_status() -> bool:
    """Return True if any Kindle or NXP device is visible on USB."""
    import usb.core
    for vid in (AMAZON_VID, NXP_VID):
        if usb.core.find(idVendor=vid) is not None:
            return True
    return False
