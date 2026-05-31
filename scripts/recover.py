#!/usr/bin/env python3
"""
Kindle Paperwhite 4 Recovery CLI.

Usage examples:
  python scripts/recover.py detect
  python scripts/recover.py charge
  python scripts/recover.py sdp --binary uboot-spl.bin
  python scripts/recover.py bootlog --port /dev/cu.usbserial-0001  (macOS)
  python scripts/recover.py bootlog --port /dev/ttyUSB0            (Linux)
  python scripts/recover.py uboot --port <port>
  python scripts/recover.py flash os --port <port> --image firmware/os.img
  python scripts/recover.py full
"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import click

from kindle_recovery.common.logger import get_logger

log = get_logger("recover")


def _default_port() -> str:
    if sys.platform == "win32":
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            if ports:
                return ports[0].device
        except Exception:
            pass
        return "COM3"
    if sys.platform == "darwin":
        for pattern in ("/dev/cu.SLAB_USBtoUART", "/dev/cu.usbserial-*", "/dev/cu.usbmodem*"):
            matches = sorted(glob.glob(pattern))
            if matches:
                return matches[0]
        return "/dev/cu.usbserial-0001"
    return "/dev/ttyUSB0"


@click.group()
@click.option("--verbose", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool):
    import logging
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
def detect():
    """Detect connected Kindle and report USB mode."""
    from kindle_recovery.level1_usb.detect import report_status
    mode = report_status()
    click.echo(f"Mode: {mode.value}")


@cli.command()
@click.option("--timeout", default=20.0, show_default=True, help="Max wait time in minutes.")
def charge(timeout: float):
    """Wait for a fully discharged device to charge enough to enumerate."""
    from kindle_recovery.level1_usb.charging import wait_for_min_charge
    success = wait_for_min_charge(timeout_minutes=timeout)
    sys.exit(0 if success else 1)


@cli.command()
@click.option("--binary", required=True, type=click.Path(exists=True), help="U-Boot SPL binary path.")
@click.option("--addr", default=0x00910000, show_default=True, help="Load address (hex ok).")
def sdp(binary: str, addr: int):
    """Load and execute a binary via NXP SDP (ROM download mode)."""
    from kindle_recovery.level1_usb.sdp import recover_via_sdp
    recover_via_sdp(binary, load_addr=addr)


@cli.command()
@click.option("--port", default=_default_port, show_default=True)
@click.option("--baud", default=115200, show_default=True)
@click.option("--duration", default=30.0, show_default=True, help="Capture duration in seconds.")
@click.option("--save", default=None, help="Save log to file.")
def bootlog(port: str, baud: int, duration: float, save: str | None):
    """Capture and analyze the boot log via UART."""
    from kindle_recovery.level2_uart.console import UARTConsole
    from kindle_recovery.level2_uart.bootlog import capture_bootlog, analyze_bootlog, save_bootlog

    with UARTConsole(port, baud) as uart:
        text = capture_bootlog(uart, duration=duration)

    if save:
        save_bootlog(text, save)

    diag = analyze_bootlog(text)
    click.echo(f"\nDiagnosis: {diag.failure_stage}")
    click.echo(f"Action:    {diag.recommended_action}")


@cli.command()
@click.option("--port", default=_default_port, show_default=True)
@click.option("--baud", default=115200, show_default=True)
def uart(port: str, baud: int):
    """Open an interactive UART console (Ctrl-] to exit)."""
    from kindle_recovery.level2_uart.console import UARTConsole
    with UARTConsole(port, baud) as console:
        console.interact()


@cli.command()
@click.option("--port", default=_default_port, show_default=True)
@click.option("--baud", default=115200, show_default=True)
def uboot(port: str, baud: int):
    """Interrupt U-Boot and drop into automated U-Boot shell."""
    from kindle_recovery.level2_uart.console import UARTConsole
    from kindle_recovery.level2_uart.uboot import UBootConsole

    with UARTConsole(port, baud) as uart_console:
        ub = UBootConsole(uart_console)
        interrupted = ub.interrupt_autoboot()
        if not interrupted:
            click.echo("Failed to interrupt U-Boot. Check UART connection.")
            sys.exit(1)
        click.echo("U-Boot interrupted. Showing eMMC info:")
        info = ub.mmc_info()
        for k, v in info.items():
            click.echo(f"  {k}: {v}")
        click.echo("\nDropping to interactive UART (Ctrl-] to exit).")
        uart_console.interact()


@cli.command()
@click.argument("partition", type=click.Choice(["os", "recovery", "env", "userdata"]))
@click.option("--port", default=_default_port, show_default=True)
@click.option("--baud", default=115200, show_default=True)
@click.option("--image", required=True, type=click.Path(exists=True))
@click.option("--server-ip", default="192.168.2.1", show_default=True)
@click.option("--device-ip", default="192.168.2.2", show_default=True)
def flash(partition: str, port: str, baud: int, image: str, server_ip: str, device_ip: str):
    """Flash a partition image via U-Boot + TFTP over USBNet."""
    from kindle_recovery.level2_uart.console import UARTConsole
    from kindle_recovery.level2_uart.uboot import UBootConsole
    from kindle_recovery.level3_flash.emmc import flash_partition

    with UARTConsole(port, baud) as uart_console:
        ub = UBootConsole(uart_console)
        if not ub.interrupt_autoboot():
            click.echo("Could not interrupt U-Boot.")
            sys.exit(1)
        flash_partition(ub, partition, image, server_ip=server_ip, device_ip=device_ip)


@cli.command()
@click.option("--port", default=_default_port, show_default=True)
def full(port: str):
    """
    Guided recovery wizard.

    Automatically detects device state and walks through the appropriate
    recovery steps from USB detection through eMMC re-flash.
    """
    from kindle_recovery.level1_usb.detect import report_status
    from kindle_recovery.common.usb_utils import DeviceMode
    from kindle_recovery.level1_usb.charging import wait_for_min_charge

    click.echo("=== Kindle PW4 Recovery Wizard ===\n")

    click.echo("Step 1: Detecting device...")
    mode = report_status()

    if mode == DeviceMode.NOT_FOUND:
        click.echo("Device not visible on USB. Waiting for charge...")
        if not wait_for_min_charge(timeout_minutes=20):
            click.echo(
                "\nDevice not detected after 20 minutes.\n"
                "Next steps:\n"
                "  1. Open the device (see docs/pw4_hardware.md)\n"
                "  2. Connect USB-UART adapter to UART test pads\n"
                f"  3. Run: python scripts/recover.py bootlog --port {port}\n"
            )
            return
        mode = report_status()

    if mode in (DeviceMode.SDP_ROM, DeviceMode.SDP_ROM_ALT):
        click.echo(
            "\nDevice is in SDP mode (ROM bootloader).\n"
            "To proceed, you need a U-Boot SPL binary.\n"
            "Get it from: https://www.amazon.com/gp/help/customer/display.html (GPL sources)\n"
            "Then run: python scripts/recover.py sdp --binary uboot-spl.bin\n"
        )
        return

    if mode in (DeviceMode.NORMAL, DeviceMode.USBNET, DeviceMode.SERIAL):
        click.echo(
            f"\nDevice is in {mode.value} mode.\n"
            "If the device boots but is stuck, try:\n"
            "  1. Connecting via USBNet SSH to 192.168.2.2\n"
            "  2. Running OTA update from command line\n"
            "\nFor eMMC re-flash, connect UART and run:\n"
            f"  python scripts/recover.py uboot --port {port}\n"
        )
        return

    click.echo(
        "\nNo actionable USB state detected.\n"
        f"Connect UART adapter and run: python scripts/recover.py bootlog --port {port}\n"
    )


if __name__ == "__main__":
    cli()
