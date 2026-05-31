import sys
import time
from dataclasses import dataclass
from enum import Enum

import usb.core
import usb.backend.libusb1

from kindle_recovery.common.logger import get_logger

log = get_logger(__name__)


def _get_backend():
    """Return a pyusb backend, loading the bundled libusb DLL on Windows."""
    if sys.platform == "win32":
        try:
            import libusb
            return usb.backend.libusb1.get_backend(find_library=lambda _: libusb.dll.name)
        except Exception:
            pass
    return usb.backend.libusb1.get_backend()


class DeviceMode(Enum):
    NORMAL = "normal"
    USBNET = "usbnet"
    SERIAL = "serial"
    SDP_ROM = "sdp_rom"
    SDP_ROM_ALT = "sdp_rom_alt"
    CHARGING_ONLY = "charging_only"
    NOT_FOUND = "not_found"


_KNOWN_DEVICES: dict[tuple[int, int], DeviceMode] = {
    (0x1949, 0x0004): DeviceMode.NORMAL,
    (0x1949, 0x0005): DeviceMode.USBNET,
    (0x1949, 0x0006): DeviceMode.SERIAL,
    (0x15A2, 0x0076): DeviceMode.SDP_ROM,
    (0x15A2, 0x007D): DeviceMode.SDP_ROM_ALT,
}


@dataclass
class KindleDevice:
    vid: int
    pid: int
    mode: DeviceMode
    serial: str | None
    bus: int
    address: int

    def __str__(self) -> str:
        return (
            f"VID={self.vid:#06x} PID={self.pid:#06x} "
            f"mode={self.mode.value} bus={self.bus} addr={self.address}"
        )


def list_kindle_devices() -> list[KindleDevice]:
    backend = _get_backend()
    devices = []
    for (vid, pid), mode in _KNOWN_DEVICES.items():
        found = usb.core.find(idVendor=vid, idProduct=pid, find_all=True, backend=backend)
        for dev in (found or []):
            try:
                serial = dev.serial_number
            except Exception:
                serial = None
            devices.append(KindleDevice(
                vid=vid, pid=pid, mode=mode,
                serial=serial, bus=dev.bus, address=dev.address,
            ))
    return devices


def wait_for_device(
    vid: int, pid: int, timeout: float = 30.0, poll_interval: float = 0.5
) -> KindleDevice | None:
    backend = _get_backend()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dev = usb.core.find(idVendor=vid, idProduct=pid, backend=backend)
        if dev is not None:
            try:
                serial = dev.serial_number
            except Exception:
                serial = None
            mode = _KNOWN_DEVICES.get((vid, pid), DeviceMode.NORMAL)
            return KindleDevice(
                vid=vid, pid=pid, mode=mode,
                serial=serial, bus=dev.bus, address=dev.address,
            )
        time.sleep(poll_interval)
    return None


def detect_mode() -> DeviceMode:
    devices = list_kindle_devices()
    if not devices:
        return DeviceMode.NOT_FOUND
    device = devices[0]
    log.info("Detected: %s", device)
    return device.mode
