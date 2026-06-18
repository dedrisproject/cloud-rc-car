"""Centralized configuration for the cloud RC car server.

Every setting can be overridden through an environment variable, so no value is
hardcoded in the source any more. Copy ``.env.example`` to ``.env`` and adjust
it for your own car; ``app.py`` loads that file automatically when present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader (no external dependency).

    Lines like ``KEY=value`` are loaded into the environment unless the key is
    already set, so real environment variables always win.
    """
    path = Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        os.environ.setdefault(key, value)


_load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # --- Web server -----------------------------------------------------
    host: str = field(default_factory=lambda: _env("RC_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("RC_PORT", 8080))

    # Optional shared secret. When set, clients must connect with
    # ws://host/ws?token=SECRET (and the UI is served the token). Leave empty
    # to disable. Strongly recommended when the car is reachable over 4G.
    auth_token: str = field(default_factory=lambda: _env("RC_AUTH_TOKEN", ""))

    # --- Arduino / motor control ---------------------------------------
    serial_port: str = field(default_factory=lambda: _env("RC_SERIAL_PORT", "/dev/ttyACM0"))
    serial_baud: int = field(default_factory=lambda: _env_int("RC_SERIAL_BAUD", 115200))

    # --- Camera ---------------------------------------------------------
    # Source: "auto" (try picamera2 then OpenCV), "picamera2", "opencv" or
    # "mock" (synthetic frames, no hardware needed).
    camera_source: str = field(default_factory=lambda: _env("RC_CAMERA_SOURCE", "auto"))
    camera_device: int = field(default_factory=lambda: _env_int("RC_CAMERA_DEVICE", 0))
    camera_width: int = field(default_factory=lambda: _env_int("RC_CAMERA_WIDTH", 640))
    camera_height: int = field(default_factory=lambda: _env_int("RC_CAMERA_HEIGHT", 480))
    camera_fps: int = field(default_factory=lambda: _env_int("RC_CAMERA_FPS", 15))
    camera_quality: int = field(default_factory=lambda: _env_int("RC_CAMERA_QUALITY", 70))

    # --- Safety ---------------------------------------------------------
    # If no command is received for this many seconds, the car is stopped and
    # the wheels recentered automatically. 0 disables the watchdog.
    safety_timeout: float = field(
        default_factory=lambda: float(_env("RC_SAFETY_TIMEOUT", "1.5"))
    )

    # Force mock hardware regardless of what is installed (handy for dev).
    mock_hardware: bool = field(default_factory=lambda: _env_bool("RC_MOCK", False))


config = Config()
