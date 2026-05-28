import re
import time

from kindle_recovery.common.exceptions import UBootError
from kindle_recovery.common.logger import get_logger
from kindle_recovery.level2_uart.console import UARTConsole

log = get_logger(__name__)

UBOOT_PROMPT = r"(=>|Kindle>|\$)\s*$"
AUTOBOOT_PATTERN = r"Hit any key to stop autoboot"
AUTOBOOT_INTERRUPT_KEYS = (" ", "\r", "f")
AUTOBOOT_WINDOW_SECONDS = 3.0


class UBootConsole:
    def __init__(self, uart: UARTConsole):
        self._uart = uart

    def interrupt_autoboot(self) -> bool:
        log.info("Waiting for U-Boot autoboot prompt (power cycle the device now)...")
        start = time.monotonic()
        buf = ""
        while time.monotonic() - start < 60:
            line = self._uart.get_line(timeout=0.2)
            if line:
                log.debug("[UBOOT] %s", line)
                buf += line
                if re.search(AUTOBOOT_PATTERN, buf):
                    log.info("Autoboot window detected! Sending interrupt keys...")
                    deadline = time.monotonic() + AUTOBOOT_WINDOW_SECONDS
                    while time.monotonic() < deadline:
                        for key in AUTOBOOT_INTERRUPT_KEYS:
                            self._uart.send(key, newline=False)
                        self._uart.send_break()
                        time.sleep(0.05)
                    return self.wait_for_prompt(timeout=3.0)
        log.warning("Autoboot pattern not seen within 60s. Is UART connected correctly?")
        return False

    def wait_for_prompt(self, timeout: float = 10.0) -> bool:
        buf = self._uart.read_until(UBOOT_PROMPT, timeout=timeout)
        if re.search(UBOOT_PROMPT, buf):
            log.info("U-Boot prompt obtained.")
            return True
        return False

    def run(self, cmd: str, timeout: float = 10.0) -> str:
        log.debug("U-Boot> %s", cmd)
        self._uart.send(cmd)
        output = self._uart.read_until(UBOOT_PROMPT, timeout=timeout)
        return output

    def get_env(self, var: str) -> str | None:
        output = self.run(f"printenv {var}", timeout=3.0)
        m = re.search(rf"{re.escape(var)}=(.+)", output)
        return m.group(1).strip() if m else None

    def set_env(self, var: str, value: str) -> None:
        self.run(f"setenv {var} {value}")

    def save_env(self) -> None:
        self.run("saveenv", timeout=5.0)

    def mmc_info(self) -> dict:
        output = self.run("mmc info", timeout=5.0)
        info = {}
        for line in output.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                info[k.strip()] = v.strip()
        log.info("eMMC info: %s", info)
        return info

    def mmc_read(self, ram_addr: int, blk_start: int, blk_count: int) -> bool:
        cmd = f"mmc read {ram_addr:#010x} {blk_start:#x} {blk_count:#x}"
        output = self.run(cmd, timeout=30.0)
        return "ok" in output.lower()

    def mmc_write(self, ram_addr: int, blk_start: int, blk_count: int) -> bool:
        cmd = f"mmc write {ram_addr:#010x} {blk_start:#x} {blk_count:#x}"
        output = self.run(cmd, timeout=120.0)
        return "ok" in output.lower()

    def setup_usbnet_tftp(
        self,
        device_ip: str = "192.168.2.2",
        server_ip: str = "192.168.2.1",
    ) -> None:
        self.set_env("ipaddr", device_ip)
        self.set_env("serverip", server_ip)
        log.info("USBNet configured: device=%s server=%s", device_ip, server_ip)

    def tftpboot(self, filename: str, load_addr: int = 0x80800000) -> bool:
        output = self.run(f"tftpboot {load_addr:#010x} {filename}", timeout=60.0)
        return "Bytes transferred" in output

    def boot_image(self, load_addr: int = 0x80800000) -> None:
        log.info("Booting image at 0x%08x", load_addr)
        self._uart.send(f"bootm {load_addr:#010x}")

    def flash_image_from_tftp(
        self,
        filename: str,
        blk_start: int,
        load_addr: int = 0x80800000,
    ) -> bool:
        log.info("Downloading %s via TFTP...", filename)
        if not self.tftpboot(filename, load_addr):
            raise UBootError(f"TFTP download of {filename} failed")

        filesize_str = self.get_env("filesize")
        if not filesize_str:
            raise UBootError("Could not read filesize env var after tftpboot")
        filesize = int(filesize_str, 16)
        blk_count = (filesize + 511) // 512

        log.info("Writing %d bytes (%d blocks) to eMMC at block 0x%x...", filesize, blk_count, blk_start)
        if not self.mmc_write(load_addr, blk_start, blk_count):
            raise UBootError("mmc write failed")
        log.info("Flash complete.")
        return True
