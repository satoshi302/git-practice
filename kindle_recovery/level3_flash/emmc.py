"""
eMMC recovery operations via U-Boot over UART.

PW4 partition layout (approximate):
  mmcblk0boot0  - U-Boot SPL (eMMC boot partition, hardware-protected)
  mmcblk0p1     - U-Boot environment
  mmcblk0p2     - Kindle OS (ext4)
  mmcblk0p3     - User data
  mmcblk0p4     - Recovery partition (FAT32)

Block size: 512 bytes.
"""
import math

from kindle_recovery.common.exceptions import FlashError
from kindle_recovery.common.logger import get_logger
from kindle_recovery.level2_uart.uboot import UBootConsole

log = get_logger(__name__)

# Known partition start blocks for PW4 (may vary by firmware revision)
PARTITION_MAP: dict[str, int] = {
    "env":      0x0800,   # U-Boot env (~1MB offset)
    "os":       0x1000,   # Kindle OS partition
    "userdata": 0x80000,  # User data partition
    "recovery": 0xC0000,  # Recovery partition
}

LOAD_ADDR = 0x80800000  # DDR address for staging images during flash


def flash_partition(
    uboot: UBootConsole,
    partition: str,
    image_path: str,
    server_ip: str = "192.168.2.1",
    device_ip: str = "192.168.2.2",
) -> None:
    if partition not in PARTITION_MAP:
        raise FlashError(
            f"Unknown partition '{partition}'. "
            f"Valid: {list(PARTITION_MAP.keys())}"
        )
    blk_start = PARTITION_MAP[partition]

    import os
    filename = os.path.basename(image_path)

    log.info("Setting up USBNet TFTP for partition '%s'...", partition)
    uboot.setup_usbnet_tftp(device_ip=device_ip, server_ip=server_ip)
    uboot.run("mmc dev 0")

    log.info("Flashing '%s' from TFTP file '%s'...", partition, filename)
    uboot.flash_image_from_tftp(filename, blk_start, load_addr=LOAD_ADDR)
    log.info("Partition '%s' flashed successfully.", partition)


def dump_partition_ymodem(uboot: UBootConsole, blk_start: int, blk_count: int, out_path: str) -> None:
    """
    Dump eMMC blocks to a file via Y-Modem over UART.
    Slow (~10 KB/s) but works without USBNet.
    """
    log.info("Reading %d blocks from eMMC at 0x%x into RAM...", blk_count, blk_start)
    if not uboot.mmc_read(LOAD_ADDR, blk_start, blk_count):
        raise FlashError("mmc read failed")

    byte_count = blk_count * 512
    log.info("Initiating Y-Modem send (%d bytes)...", byte_count)
    uboot.run(f"loady {LOAD_ADDR:#010x} {byte_count:#x}")
    log.info("Start Y-Modem receive on your host now. Saving to: %s", out_path)


def restore_bootloader_via_sdp(uboot_spl_path: str) -> None:
    """
    When eMMC bootloader is corrupt, use SDP to load U-Boot into RAM,
    then re-flash eMMC boot partition from the running U-Boot.

    Call this after recover_via_sdp() has U-Boot running in RAM.
    Then attach UART and use this function to re-flash the eMMC SPL.
    """
    log.info(
        "To restore the bootloader:\n"
        "  1. Load U-Boot into RAM via SDP: python scripts/recover.py sdp --binary %s\n"
        "  2. Attach UART and interrupt U-Boot\n"
        "  3. In U-Boot: mmc dev 0 1  (select boot partition)\n"
        "  4. Load SPL via TFTP and write to block 0x0\n"
        "  5. mmc dev 0 0  (switch back to user area)\n",
        uboot_spl_path,
    )
