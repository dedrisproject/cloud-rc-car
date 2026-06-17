"""Camera capture and MJPEG encoding.

Supports the Raspberry Pi camera (picamera2), any USB webcam (OpenCV) and a
hardware-free synthetic source ("mock") so the stream works even on a dev
machine. A single capture loop runs in a background thread and the latest JPEG
frame is shared with all connected viewers, so adding clients costs nothing
extra on the encoder side.
"""

from __future__ import annotations

import logging
import threading
import time

from config import Config

log = logging.getLogger("rc.camera")


class CameraStreamer:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._frame: bytes | None = None
        self._lock = threading.Condition()
        self._running = False
        self._thread: threading.Thread | None = None
        self._backend = "mock" if cfg.mock_hardware else cfg.camera_source

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def get_frame(self, last_frame: bytes | None, timeout: float = 5.0) -> bytes | None:
        """Block until a frame newer than ``last_frame`` is available."""
        with self._lock:
            if self._frame is None or self._frame is last_frame:
                self._lock.wait(timeout)
            return self._frame

    # -- capture loop ----------------------------------------------------
    def _publish(self, jpeg: bytes) -> None:
        with self._lock:
            self._frame = jpeg
            self._lock.notify_all()

    def _run(self) -> None:
        order = (
            [self._backend]
            if self._backend in {"picamera2", "opencv", "mock"}
            else ["picamera2", "opencv", "mock"]
        )
        for backend in order:
            try:
                if backend == "picamera2":
                    return self._run_picamera2()
                if backend == "opencv":
                    return self._run_opencv()
                if backend == "mock":
                    return self._run_mock()
            except Exception as exc:  # noqa: BLE001 - try the next backend
                log.warning("camera backend %s failed: %s", backend, exc)
        log.error("no working camera backend, falling back to mock")
        self._run_mock()

    def _run_picamera2(self) -> None:
        from picamera2 import Picamera2  # type: ignore
        import cv2  # type: ignore

        cam = Picamera2()
        cfg = cam.create_video_configuration(
            main={"size": (self.cfg.camera_width, self.cfg.camera_height), "format": "RGB888"}
        )
        cam.configure(cfg)
        cam.start()
        log.info("camera: picamera2 %dx%d", self.cfg.camera_width, self.cfg.camera_height)
        delay = 1.0 / max(self.cfg.camera_fps, 1)
        params = [cv2.IMWRITE_JPEG_QUALITY, self.cfg.camera_quality]
        try:
            while self._running:
                frame = cam.capture_array()
                ok, jpeg = cv2.imencode(".jpg", frame, params)
                if ok:
                    self._publish(jpeg.tobytes())
                time.sleep(delay)
        finally:
            cam.stop()

    def _run_opencv(self) -> None:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(self.cfg.camera_device)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.camera_height)
        if not cap.isOpened():
            raise RuntimeError(f"cannot open camera device {self.cfg.camera_device}")
        log.info("camera: opencv device %d", self.cfg.camera_device)
        delay = 1.0 / max(self.cfg.camera_fps, 1)
        params = [cv2.IMWRITE_JPEG_QUALITY, self.cfg.camera_quality]
        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    time.sleep(delay)
                    continue
                ok, jpeg = cv2.imencode(".jpg", frame, params)
                if ok:
                    self._publish(jpeg.tobytes())
                time.sleep(delay)
        finally:
            cap.release()

    def _run_mock(self) -> None:
        """Synthetic frames: a moving bar + clock, no hardware required."""
        try:
            from PIL import Image, ImageDraw  # type: ignore
        except Exception:  # noqa: BLE001 - Pillow optional
            return self._run_mock_minimal()

        import io
        import math

        w, h = self.cfg.camera_width, self.cfg.camera_height
        delay = 1.0 / max(self.cfg.camera_fps, 1)
        log.info("camera: mock %dx%d", w, h)
        i = 0
        while self._running:
            img = Image.new("RGB", (w, h), (20, 24, 28))
            draw = ImageDraw.Draw(img)
            x = int((math.sin(i / 10) * 0.5 + 0.5) * (w - 60))
            draw.rectangle([x, h // 2 - 30, x + 60, h // 2 + 30], fill=(0, 180, 255))
            draw.text((10, 10), f"MOCK CAMERA  frame {i}", fill=(230, 230, 230))
            draw.text((10, h - 20), time.strftime("%Y-%m-%d %H:%M:%S"), fill=(160, 160, 160))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=self.cfg.camera_quality)
            self._publish(buf.getvalue())
            i += 1
            time.sleep(delay)

    def _run_mock_minimal(self) -> None:
        """Last-resort mock when Pillow is unavailable: a tiny static JPEG."""
        # 1x1 black pixel JPEG.
        import base64

        jpeg = base64.b64decode(
            "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAP//////////////////////////////"
            "////////////////////////////////////////////////////wgARCAABAAED"
            "ASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAA"
            "AAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/a"
            "AAwDAQACEQMRAD8AvwA//9k="
        )
        delay = 1.0 / max(self.cfg.camera_fps, 1)
        log.info("camera: minimal mock (install Pillow for a nicer test image)")
        while self._running:
            self._publish(jpeg)
            time.sleep(delay)
