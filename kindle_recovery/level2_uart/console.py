from __future__ import annotations
import re
import select
import sys
import threading
import time

import serial

from kindle_recovery.common.exceptions import UARTError
from kindle_recovery.common.logger import get_logger

log = get_logger(__name__)


class UARTConsole:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.1):
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._ser: serial.Serial | None = None

    def open(self) -> None:
        try:
            self._ser = serial.Serial(
                self._port, self._baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self._timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except serial.SerialException as e:
            raise UARTError(f"Cannot open {self._port}: {e}") from e
        log.info("Opened UART %s at %d baud", self._port, self._baud)

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def send(self, text: str, newline: bool = True) -> None:
        payload = (text + "\r\n" if newline else text).encode()
        self._ser.write(payload)
        self._ser.flush()

    def send_break(self) -> None:
        self._ser.send_break(duration=0.25)

    def read_until(self, pattern: str, timeout: float = 5.0) -> str:
        rx = re.compile(pattern)
        buf = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = self._ser.read(256).decode(errors="replace")
            if chunk:
                buf += chunk
                if rx.search(buf):
                    return buf
        return buf

    def get_line(self, timeout: float = 1.0) -> str | None:
        self._ser.timeout = timeout
        line = self._ser.readline().decode(errors="replace").rstrip()
        self._ser.timeout = self._timeout
        return line if line else None

    def interact(self) -> None:
        log.info("Entering interactive UART mode. Press Ctrl-] to exit.")
        stop = threading.Event()

        def _read_uart():
            while not stop.is_set():
                data = self._ser.read(256)
                if data:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()

        reader = threading.Thread(target=_read_uart, daemon=True)
        reader.start()

        try:
            while True:
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ch = sys.stdin.buffer.read1(256)
                    if b"\x1d" in ch:  # Ctrl-]
                        break
                    self._ser.write(ch)
        finally:
            stop.set()
            reader.join(timeout=1.0)
