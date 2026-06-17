"""Motor and headlight control.

Translates the semantic commands sent by the browser (``forward``, ``left`` …)
into the numeric serial protocol understood by the Arduino motor-shield sketch,
and drives the headlights directly through a GPIO pin.

The module degrades gracefully: if ``pyserial`` / ``gpiozero`` are missing or no
hardware is present (e.g. running on a laptop) it falls back to a mock backend
that just logs what it would have done, so the whole stack stays testable.
"""

from __future__ import annotations

import logging
import threading

from config import Config

log = logging.getLogger("rc.motor")

# Semantic command -> Arduino serial code (matches firmware/motorshield).
SERIAL_CODES = {
    "forward": "7",
    "brake": "6",
    "reverse": "1",
    "left": "14",
    "right": "15",
    "center": "12",
}

# Commands understood by the controller (serial + light commands).
VALID_COMMANDS = set(SERIAL_CODES) | {"lights_on", "lights_off", "lights_toggle"}


class _MockSerial:
    def write(self, payload: bytes) -> None:
        log.info("[mock-serial] %s", payload.decode(errors="replace").strip())

    def close(self) -> None:  # pragma: no cover - trivial
        pass


class _MockLights:
    def __init__(self) -> None:
        self.state = False

    def on(self) -> None:
        self.state = True
        log.info("[mock-gpio] lights ON")

    def off(self) -> None:
        self.state = False
        log.info("[mock-gpio] lights OFF")

    def close(self) -> None:  # pragma: no cover - trivial
        pass


class MotorController:
    """Thread-safe facade over the serial link and the headlight GPIO."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()
        self._last_drive_code: str | None = None
        self._lights_on = False
        self._serial = self._open_serial()
        self._lights = self._open_lights()

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

    def _open_lights(self):
        if self.cfg.mock_hardware:
            return _MockLights()
        try:
            from gpiozero import LED  # type: ignore

            led = LED(self.cfg.lights_pin)
            log.info("Lights on GPIO %d", self.cfg.lights_pin)
            return led
        except Exception as exc:  # noqa: BLE001 - any failure -> mock
            log.warning("GPIO unavailable (%s); using mock lights", exc)
            return _MockLights()

    # -- public API ------------------------------------------------------
    def handle(self, command: str) -> dict:
        """Execute a semantic command; returns the resulting state."""
        if command not in VALID_COMMANDS:
            raise ValueError(f"unknown command: {command!r}")

        with self._lock:
            if command in SERIAL_CODES:
                self._send_drive(SERIAL_CODES[command])
            elif command == "lights_on":
                self._set_lights(True)
            elif command == "lights_off":
                self._set_lights(False)
            elif command == "lights_toggle":
                self._set_lights(not self._lights_on)
            return self.state()

    def stop(self) -> dict:
        """Safety stop: brake and recenter the wheels."""
        with self._lock:
            self._send_drive(SERIAL_CODES["brake"], force=True)
            self._send_drive(SERIAL_CODES["center"], force=True)
            return self.state()

    def state(self) -> dict:
        return {"lights": self._lights_on, "last_drive": self._last_drive_code}

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self._serial.close()
            self._lights.close()

    # -- internals -------------------------------------------------------
    def _send_drive(self, code: str, force: bool = False) -> None:
        # De-duplicate repeated identical commands to avoid flooding the
        # serial link (the UI sends them ~10x/second while a key is held).
        if not force and code == self._last_drive_code:
            return
        self._last_drive_code = code
        try:
            self._serial.write(f"{code}|".encode())
            log.debug("serial -> %s|", code)
        except Exception as exc:  # noqa: BLE001
            log.error("serial write failed: %s", exc)

    def _set_lights(self, on: bool) -> None:
        if on:
            self._lights.on()
        else:
            self._lights.off()
        self._lights_on = on
