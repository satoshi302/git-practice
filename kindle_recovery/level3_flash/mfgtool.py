"""
NXP Manufacturing Tool (MfgTool) protocol implementation.

MfgTool works in two phases:
  1. Load a bootstrap firmware over SDP into RAM. The bootstrap initializes
     DDR and eMMC, then re-enumerates as USB Mass Storage.
  2. Write full partition images directly to the MSC block device.

This is the highest-reliability recovery path but requires NXP-specific
bootstrap binaries (compiled from ucl2.xml with NXP's elftosb tool).
"""
import hashlib
import os
import subprocess
import time

from kindle_recovery.common.exceptions import FlashError
from kindle_recovery.common.logger import get_logger
from kindle_recovery.level1_usb.sdp import SDPClient, find_sdp_device

log = get_logger(__name__)

AMAZON_VID = 0x1949
MSC_POLL_TIMEOUT = 60.0


class MfgToolSession:
    def __init__(self):
        self._sdp: SDPClient | None = None

    def start_session(self, bootstrap_path: str, load_addr: int = 0x00910000) -> None:
        result = find_sdp_device()
        if result is None:
            raise FlashError("No NXP SDP device found for MfgTool session.")
        vid, pid = result
        self._sdp = SDPClient(vid, pid)
        self._sdp.open()
        log.info("Loading MfgTool bootstrap binary...")
        self._sdp.load_and_execute(bootstrap_path, load_addr)
        self._sdp.close()
        log.info("Bootstrap loaded. Waiting for device to re-enumerate as USB MSC...")

    def wait_for_msc_mode(self, timeout: float = MSC_POLL_TIMEOUT) -> str:
        import sys
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["wmic", "diskdrive", "get", "Model,DeviceID"],
                    capture_output=True, text=True,
                )
                for line in result.stdout.splitlines():
                    if "kindle" in line.lower() or "amazon" in line.lower():
                        device_id = line.strip().split()[-1]
                        log.info("Kindle MSC device found: %s", device_id)
                        return device_id
            elif sys.platform == "darwin":
                result = subprocess.run(
                    ["diskutil", "list", "-plist", "external"],
                    capture_output=True, text=True,
                )
                import plistlib
                try:
                    plist = plistlib.loads(result.stdout.encode())
                    for disk in plist.get("WholeDisks", []):
                        dev_path = f"/dev/{disk}"
                        log.info("External disk found: %s", dev_path)
                        return dev_path
                except Exception:
                    pass
            else:
                result = subprocess.run(
                    ["lsblk", "-o", "NAME,VENDOR,MODEL", "--nodeps"],
                    capture_output=True, text=True,
                )
                for line in result.stdout.splitlines():
                    if "kindle" in line.lower() or "amazon" in line.lower():
                        dev_name = line.split()[0]
                        dev_path = f"/dev/{dev_name}"
                        log.info("Kindle MSC device found: %s", dev_path)
                        return dev_path
                sysfs = "/sys/bus/usb/devices"
                if os.path.exists(sysfs):
                    for entry in os.listdir(sysfs):
                        vendor_path = os.path.join(sysfs, entry, "idVendor")
                        if os.path.exists(vendor_path):
                            with open(vendor_path) as f:
                                if f.read().strip() == f"{AMAZON_VID:04x}":
                                    log.info("Amazon USB device found in sysfs: %s", entry)
            time.sleep(2.0)
        raise FlashError("Timed out waiting for MfgTool MSC enumeration.")

    def flash_image(self, msc_dev: str, image_path: str, offset_sectors: int = 0) -> None:
        image_size = os.path.getsize(image_path)
        log.info(
            "Flashing %s (%d MB) to %s at sector %d...",
            image_path, image_size // 1024 // 1024, msc_dev, offset_sectors,
        )
        cmd = [
            "dd",
            f"if={image_path}",
            f"of={msc_dev}",
            "bs=512",
            f"seek={offset_sectors}",
            "status=progress",
            "conv=fsync",
        ]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise FlashError(f"dd failed with exit code {result.returncode}")
        log.info("Flash complete.")

    def verify_image(self, msc_dev: str, image_path: str, offset_sectors: int = 0) -> bool:
        image_size = os.path.getsize(image_path)
        log.info("Verifying flash...")

        with open(image_path, "rb") as f:
            expected = hashlib.sha256(f.read()).hexdigest()

        cmd = [
            "dd",
            f"if={msc_dev}",
            f"skip={offset_sectors}",
            f"count={image_size // 512}",
            "bs=512",
        ]
        result = subprocess.run(cmd, capture_output=True)
        actual = hashlib.sha256(result.stdout).hexdigest()

        if expected == actual:
            log.info("Verification passed.")
            return True
        else:
            log.error("Verification FAILED! Expected %s, got %s", expected, actual)
            return False
