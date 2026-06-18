"""Motor control.

Translates the semantic commands sent by the browser (``forward``, ``left`` …)
into the numeric serial protocol understood by the Arduino motor-shield sketch.

The module degrades gracefully: if ``pyserial`` is missing or no hardware is
present (e.g. running on a laptop) it falls back to a mock backend that just
records what it would have sent, so the whole stack stays testable.
"""

from __future__ import annotations

import logging
import threading

from config import Config

log = logging.getLogger("rc.motor")

# Channel A drives the rear motor (throttle / reverse), channel B the steering.
# Keeping the two channels separate lets us de-duplicate each axis on its own,
# so holding "forward + left" together does not defeat de-duplication.
DRIVE_CODES = {"forward": "7", "brake": "6", "reverse": "1"}   # channel A
STEER_CODES = {"left": "14", "right": "15", "center": "12"}    # channel B
SERIAL_CODES = {**DRIVE_CODES, **STEER_CODES}

VALID_COMMANDS = set(SERIAL_CODES)


class _MockSerial:
    """Stand-in for a serial port; records writes for inspection/tests."""

    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, payload: bytes) -> None:
        text = payload.decode(errors="replace")
        self.writes.append(text)
        log.info("[mock-serial] %s", text.strip())

    def close(self) -> None:  # pragma: no cover - trivial
        pass


class MotorController:
    """Thread-safe facade over the serial link to the Arduino."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()
        self._last_drive: str | None = None   # last channel A code sent
        self._last_steer: str | None = None   # last channel B code sent
        self._serial = self._open_serial()

    # -- backend setup ---------------------------------------------------
    def _open_serial(self):
        if self.cfg.mock_hardware:
            log.warning("RC_MOCK set: using mock serial")
            return _MockSerial()
        try:
            import serial  # type: ignore

            link = serial.Serial(self.cfg.serial_port, self.cfg.serial_baud, timeout=1)
            log.info("Serial open on %s @ %d", self.cfg.serial_port, self.cfg.serial_baud)
            return link
        except Exception as exc:  # noqa: BLE001 - any failure -> mock
            log.warning("Serial unavailable (%s); using mock serial", exc)
            return _MockSerial()

    # -- public API ------------------------------------------------------
    def handle(self, command: str) -> dict:
        """Execute a semantic command; returns the resulting state."""
        if command not in VALID_COMMANDS:
            raise ValueError(f"unknown command: {command!r}")
        with self._lock:
            if command in DRIVE_CODES:
                self._send_drive(DRIVE_CODES[command])
            else:
                self._send_steer(STEER_CODES[command])
            return self.state()

    def stop(self) -> dict:
        """Safety stop: brake and recenter the wheels."""
        with self._lock:
            self._send_drive(DRIVE_CODES["brake"], force=True)
            self._send_steer(STEER_CODES["center"], force=True)
            return self.state()

    def state(self) -> dict:
        return {"last_drive": self._last_drive, "last_steer": self._last_steer}

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self._serial.close()

    # -- internals -------------------------------------------------------
    def _send_drive(self, code: str, force: bool = False) -> None:
        # De-duplicate repeated identical throttle commands (the UI sends them
        # many times per second while a control is held).
        if not force and code == self._last_drive:
            return
        self._last_drive = code
        self._write(code)

    def _send_steer(self, code: str, force: bool = False) -> None:
        if not force and code == self._last_steer:
            return
        self._last_steer = code
        self._write(code)

    def _write(self, code: str) -> None:
        try:
            self._serial.write(f"{code}|".encode())
            log.debug("serial -> %s|", code)
        except Exception as exc:  # noqa: BLE001
            log.error("serial write failed: %s", exc)
