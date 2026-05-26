import re
import time
from dataclasses import dataclass, field

from kindle_recovery.common.logger import get_logger
from kindle_recovery.level2_uart.console import UARTConsole

log = get_logger(__name__)


@dataclass
class BootDiagnosis:
    bootloader_reached: bool = False
    uboot_interrupt_possible: bool = False
    emmc_detected: bool = False
    kernel_reached: bool = False
    failure_stage: str = "unknown"
    recommended_action: str = ""
    patterns_matched: list[str] = field(default_factory=list)


_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, field_or_flag, description)
    (r"U-Boot",                         "bootloader_reached",        "U-Boot started"),
    (r"Hit any key to stop autoboot",   "uboot_interrupt_possible",  "U-Boot autoboot interruptable"),
    (r"MMC:\s+no card present",         "emmc_missing",              "eMMC not detected"),
    (r"mmc\d+: error",                  "emmc_error",                "eMMC I/O error"),
    (r"spl: image checksum invalid",    "spl_checksum",              "SPL checksum failed"),
    (r"HAB Authentication (Warning|Error)", "hab_error",             "HAB security violation"),
    (r"Kernel panic",                   "kernel_panic",              "Kernel panic"),
    (r"EXT4-fs error",                  "fs_error",                  "Root filesystem corrupt"),
    (r"Starting kernel",                "kernel_reached",            "Kernel started"),
    (r"Waiting for USB",                "usb_download",              "USB download mode"),
    (r"Please wait",                    "recovery_partition",        "Recovery partition active"),
]


def capture_bootlog(uart: UARTConsole, duration: float = 30.0) -> str:
    log.info("Capturing boot log for %.0f seconds...", duration)
    log.info("Power cycle the Kindle now.")
    buf = ""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        line = uart.get_line(timeout=0.5)
        if line:
            log.debug("[BOOT] %s", line)
            buf += line + "\n"
    return buf


def save_bootlog(text: str, path: str) -> None:
    import datetime
    header = f"# Boot log captured {datetime.datetime.now().isoformat()}\n\n"
    with open(path, "w") as f:
        f.write(header + text)
    log.info("Boot log saved to %s", path)


def analyze_bootlog(text: str) -> BootDiagnosis:
    diag = BootDiagnosis()

    for pattern, flag, desc in _PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            diag.patterns_matched.append(desc)
            if flag == "bootloader_reached":
                diag.bootloader_reached = True
            elif flag == "uboot_interrupt_possible":
                diag.uboot_interrupt_possible = True
            elif flag == "kernel_reached":
                diag.kernel_reached = True
            elif flag == "emmc_missing":
                diag.failure_stage = "emmc_hardware"
                diag.recommended_action = (
                    "eMMC not detected by U-Boot. Likely hardware failure "
                    "(loose connector or dead eMMC chip). Re-seat the eMMC connector "
                    "or attempt BGA rework."
                )
            elif flag == "spl_checksum":
                diag.failure_stage = "bootloader_corrupt"
                diag.recommended_action = (
                    "U-Boot SPL in eMMC is corrupt. Use SDP mode to load U-Boot from USB: "
                    "python scripts/recover.py sdp --binary uboot-spl.bin"
                )
            elif flag == "hab_error":
                diag.failure_stage = "hab_security"
                diag.recommended_action = (
                    "HAB security error. Only signed Amazon firmware images will boot. "
                    "Obtain official firmware and re-flash via recovery partition."
                )
            elif flag in ("emmc_error", "fs_error"):
                diag.failure_stage = "filesystem_corrupt"
                diag.recommended_action = (
                    "eMMC detected but filesystem is corrupt. "
                    "Interrupt U-Boot and re-flash OS partition via UART/TFTP."
                )
            elif flag == "kernel_panic":
                diag.failure_stage = "kernel_crash"
                diag.recommended_action = (
                    "Kernel boots but panics. Re-flash the OS partition."
                )

    if not diag.bootloader_reached and not diag.failure_stage:
        diag.failure_stage = "pre_bootloader"
        diag.recommended_action = (
            "No U-Boot output detected. Either the device is not powered, "
            "UART connection is wrong, or the SPL/eMMC is completely unreadable. "
            "Try SDP USB recovery first."
        )

    if diag.bootloader_reached and diag.uboot_interrupt_possible and not diag.failure_stage:
        diag.failure_stage = "boot_config"
        diag.recommended_action = (
            "U-Boot is running and can be interrupted. "
            "Run: python scripts/recover.py uboot --port <port>"
        )

    log.info("Boot diagnosis: stage=%s", diag.failure_stage)
    for match in diag.patterns_matched:
        log.info("  [+] %s", match)
    if diag.recommended_action:
        log.info("Recommended action: %s", diag.recommended_action)

    return diag
