from __future__ import annotations
"""
NXP Serial Download Protocol (SDP) over USB HID.

When the i.MX7 SoC cannot find a valid boot image in eMMC, it enters ROM
download mode (VID 0x15A2, PID 0x0076). This module communicates with that
ROM via HID to load U-Boot into RAM and execute it.

Reference: NXP i.MX7 Reference Manual, chapter "Serial Download Protocol".
"""
import math
import struct
import time

import hid

from kindle_recovery.common.exceptions import HABSecurityError, SDPError
from kindle_recovery.common.logger import get_logger

log = get_logger(__name__)

# USB HID VID/PID for NXP i.MX7 and i.MX6SL in SDP mode
SDP_DEVICES = [
    (0x15A2, 0x0076),  # i.MX7
    (0x15A2, 0x007D),  # i.MX6SL
]

# SDP command types
CMD_READ_REGISTER  = 0x0101
CMD_WRITE_REGISTER = 0x0202
CMD_WRITE_FILE     = 0x0404
CMD_ERROR_STATUS   = 0x0505
CMD_DCD_WRITE      = 0x0A0A
CMD_JUMP_ADDRESS   = 0x0B0B
CMD_SKIP_DCD       = 0x0C0C

# HAB status codes
HAB_OPEN   = 0x56787856  # device is open (no HAB enforcement)
HAB_CLOSED = 0x12343412  # device is closed (signed images only)

# i.MX7 on-chip RAM: safe load address before DDR init
OCRAM_BASE = 0x00910000
# DDR base address (valid after DDRC init via DCD in SPL)
DDR_BASE   = 0x80000000

# HID report sizes
CMD_REPORT_ID   = 1
DATA_REPORT_ID  = 2
HAB_REPORT_ID   = 3
DCD_REPORT_ID   = 4
DATA_CHUNK_SIZE = 1024  # payload bytes per HID write report


def _pack_command(cmd_type: int, addr: int, fmt: int, data_count: int, data: int) -> bytes:
    return struct.pack(">HIBIH", cmd_type, addr, fmt, data_count, data) + b"\x00"


class SDPClient:
    def __init__(self, vid: int = 0x15A2, pid: int = 0x0076):
        self._vid = vid
        self._pid = pid
        self._dev: hid.device | None = None

    def open(self) -> None:
        self._dev = hid.device()
        self._dev.open(self._vid, self._pid)
        self._dev.set_nonblocking(False)
        log.info("Opened SDP device %04x:%04x", self._vid, self._pid)

    def close(self) -> None:
        if self._dev:
            self._dev.close()
            self._dev = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def _send_command(self, cmd_type: int, addr: int, fmt: int, data_count: int, data: int) -> None:
        payload = _pack_command(cmd_type, addr, fmt, data_count, data)
        report = bytes([CMD_REPORT_ID]) + payload
        self._dev.write(report)

    def _read_hab_status(self) -> int:
        resp = bytes(self._dev.read(5, timeout_ms=1000))
        if len(resp) < 5:
            raise SDPError("Short HAB status response")
        return struct.unpack(">I", resp[1:5])[0]

    def get_error_status(self) -> int:
        self._send_command(CMD_ERROR_STATUS, 0, 0, 0, 0)
        status = self._read_hab_status()
        if status == HAB_CLOSED:
            log.warning("HAB fuses blown: device only boots signed images.")
        elif status == HAB_OPEN:
            log.info("HAB status: OPEN (unsigned images accepted)")
        else:
            log.debug("HAB status: 0x%08x", status)
        return status

    def read_register(self, addr: int, fmt: int = 0x20) -> int:
        self._send_command(CMD_READ_REGISTER, addr, fmt, 4, 0)
        resp = bytes(self._dev.read(5, timeout_ms=1000))
        return struct.unpack(">I", resp[1:5])[0]

    def write_register(self, addr: int, value: int, fmt: int = 0x20) -> None:
        self._send_command(CMD_WRITE_REGISTER, addr, fmt, 4, value)
        self._read_hab_status()

    def write_file(self, data: bytes, load_addr: int) -> None:
        total = len(data)
        self._send_command(CMD_WRITE_FILE, load_addr, 0, total, 0)

        chunks = math.ceil(total / DATA_CHUNK_SIZE)
        for i in range(chunks):
            chunk = data[i * DATA_CHUNK_SIZE: (i + 1) * DATA_CHUNK_SIZE]
            padded = chunk.ljust(DATA_CHUNK_SIZE, b"\x00")
            report = bytes([DATA_REPORT_ID]) + padded
            self._dev.write(report)

        hab_status = self._read_hab_status()
        if hab_status == HAB_CLOSED:
            raise HABSecurityError(
                "HAB verification failed: device requires a signed image. "
                "Obtain a signed U-Boot SPL from Amazon GPL sources."
            )
        log.info("write_file: %d bytes loaded at 0x%08x", total, load_addr)

    def jump_address(self, addr: int) -> None:
        self._send_command(CMD_JUMP_ADDRESS, addr, 0, 0, 0)
        log.info("Jumping to 0x%08x", addr)
        time.sleep(0.1)

    def load_and_execute(self, binary_path: str, load_addr: int = OCRAM_BASE) -> None:
        with open(binary_path, "rb") as f:
            data = f.read()
        log.info("Loading %s (%d bytes) to 0x%08x", binary_path, len(data), load_addr)
        self.write_file(data, load_addr)
        self.jump_address(load_addr)


def find_sdp_device() -> tuple[int, int] | None:
    for vid, pid in SDP_DEVICES:
        for info in hid.enumerate(vid, pid):
            log.info("Found SDP device: %04x:%04x %s", vid, pid, info.get("product_string", ""))
            return vid, pid
    return None


def recover_via_sdp(binary_path: str, load_addr: int = OCRAM_BASE) -> None:
    result = find_sdp_device()
    if result is None:
        raise SDPError(
            "No NXP SDP device found. The Kindle must be in ROM download mode. "
            "Try holding the power button for 60 seconds to force a hard reset, "
            "then reconnect USB."
        )
    vid, pid = result
    with SDPClient(vid, pid) as client:
        status = client.get_error_status()
        if status == HAB_CLOSED:
            log.warning("Proceeding with signed-image requirement enforced by HAB.")
        client.load_and_execute(binary_path, load_addr)
    log.info("SDP recovery initiated. Watch UART for U-Boot output.")
