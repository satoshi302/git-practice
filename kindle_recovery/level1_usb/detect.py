import os
import subprocess
import sys

from kindle_recovery.common.logger import get_logger
from kindle_recovery.common.usb_utils import DeviceMode, detect_mode, list_kindle_devices

log = get_logger(__name__)

KINDLE_USBNET_IP = "192.168.2.2"
KINDLE_USBNET_IFACES = ("usb0", "rndis0", "en5", "en6")

_IS_MACOS = sys.platform == "darwin"
_IS_WINDOWS = sys.platform == "win32"


def _iface_exists(iface: str) -> bool:
    if _IS_WINDOWS:
        result = subprocess.run(["ipconfig"], capture_output=True, text=True)
        return iface.lower() in result.stdout.lower()
    if _IS_MACOS:
        result = subprocess.run(["ifconfig", iface], capture_output=True)
        return result.returncode == 0
    return os.path.exists(f"/sys/class/net/{iface}")


def _ping_cmd(ip: str, timeout: float) -> list[str]:
    if _IS_WINDOWS:
        return ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
    if _IS_MACOS:
        return ["ping", "-c", "1", "-t", str(int(timeout)), ip]
    return ["ping", "-c", "1", "-W", str(int(timeout)), ip]


def check_usbnet_reachable(timeout: float = 2.0) -> bool:
    for iface in KINDLE_USBNET_IFACES:
        if _iface_exists(iface):
            log.info("USBNet interface %s found", iface)
            try:
                result = subprocess.run(
                    _ping_cmd(KINDLE_USBNET_IP, timeout),
                    capture_output=True, timeout=timeout + 1,
                )
                if result.returncode == 0:
                    log.info("Kindle reachable at %s via %s", KINDLE_USBNET_IP, iface)
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
    return False


def get_usb_interface_details(vid: int, pid: int) -> dict:
    import usb.core
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        return {}
    try:
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
        return {
            "bDeviceClass": dev.bDeviceClass,
            "bInterfaceClass": intf.bInterfaceClass,
            "bInterfaceSubClass": intf.bInterfaceSubClass,
            "bInterfaceProtocol": intf.bInterfaceProtocol,
        }
    except Exception as e:
        log.debug("Could not read interface details: %s", e)
        return {}


def report_status() -> DeviceMode:
    mode = detect_mode()

    if mode == DeviceMode.NOT_FOUND:
        log.warning("No Kindle device found on USB.")
        log.info("Make sure the device is connected. If fully discharged, wait 15-20 minutes on a wall charger.")
        return mode

    devices = list_kindle_devices()
    for dev in devices:
        log.info("Found device: %s", dev)

    if mode == DeviceMode.NORMAL:
        log.info("Device is in normal mode (Mass Storage / USB).")
        log.info("You can access it as a drive or attempt SSH if USBNet is active.")
    elif mode == DeviceMode.USBNET:
        log.info("Device is in USBNet mode.")
        reachable = check_usbnet_reachable()
        if reachable:
            log.info("SSH to %s to run recovery commands.", KINDLE_USBNET_IP)
        else:
            log.warning("USBNet interface found but device not reachable via ping.")
    elif mode == DeviceMode.SERIAL:
        port_hint = "/dev/cu.usbmodem*" if _IS_MACOS else "/dev/ttyACM*"
        log.info("Device is in CDC-ACM serial mode. Check %s.", port_hint)
    elif mode in (DeviceMode.SDP_ROM, DeviceMode.SDP_ROM_ALT):
        log.info("Device is in NXP SDP ROM download mode.")
        log.info("Run: python scripts/recover.py sdp --binary <uboot.bin>")
    elif mode == DeviceMode.CHARGING_ONLY:
        log.info("Device is charging but not enumerating. Wait and retry.")

    return mode
