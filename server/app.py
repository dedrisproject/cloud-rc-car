"""Cloud RC car server.

A single aiohttp process that serves:
  * the web UI            (GET  /)
  * the control channel   (WS   /ws)        browser -> motors
  * the live video feed   (GET  /stream)    MJPEG, multipart

Running everything on one port means only one port has to be forwarded over the
4G/cloud link, and there is no cross-origin/iframe juggling like in the old
PHP + multi-server setup.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from aiohttp import WSMsgType, web

from camera import CameraStreamer
from config import config
from motor import MotorController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("rc.app")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _authorized(request: web.Request) -> bool:
    if not config.auth_token:
        return True
    token = request.query.get("token") or request.headers.get("X-Auth-Token")
    return token == config.auth_token


async def index(request: web.Request) -> web.Response:
    return web.FileResponse(WEB_DIR / "index.html")


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)

    if not _authorized(request):
        await ws.send_json({"type": "error", "message": "unauthorized"})
        await ws.close()
        return ws

    motor: MotorController = request.app["motor"]
    request.app["clients"].add(ws)
    log.info("client connected (%d total)", len(request.app["clients"]))
    await ws.send_json({"type": "state", **motor.state()})

    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            payload = _parse_message(msg.data)
            if payload is None:
                continue

            # Latency probe: echo the client timestamp straight back.
            if payload.get("type") == "ping":
                await ws.send_json({"type": "pong", "t": payload.get("t")})
                continue

            command = payload.get("cmd")
            if not command:
                continue
            request.app["last_seen"] = time.monotonic()
            try:
                state = await asyncio.to_thread(motor.handle, command)
                await ws.send_json({"type": "state", **state})
            except ValueError as exc:
                await ws.send_json({"type": "error", "message": str(exc)})
    finally:
        request.app["clients"].discard(ws)
        log.info("client disconnected (%d total)", len(request.app["clients"]))
    return ws


def _parse_message(raw: str) -> dict | None:
    """Parse an incoming WS message into a dict.

    Accepts JSON objects (``{"cmd": "forward"}`` / ``{"type": "ping"}``) as well
    as a bare command string (``"forward"``) for convenience.
    """
    raw = raw.strip()
    if not raw:
        return None
    if raw[0] in "{[":
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except ValueError:
            return None
    return {"cmd": raw}


async def stream_handler(request: web.Request) -> web.StreamResponse:
    if not _authorized(request):
        raise web.HTTPUnauthorized(text="unauthorized")

    camera: CameraStreamer = request.app["camera"]
    boundary = "frame"
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": f"multipart/x-mixed-replace; boundary={boundary}",
            "Cache-Control": "no-cache, private",
            "Pragma": "no-cache",
        },
    )
    await response.prepare(request)
    log.info("stream viewer connected")
    last_id = -1
    try:
        while True:
            frame, last_id = await camera.wait_frame(last_id)
            await response.write(
                b"--" + boundary.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                + frame + b"\r\n"
            )
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        log.info("stream viewer disconnected")
    return response


async def config_handler(request: web.Request) -> web.Response:
    """Expose non-secret runtime info to the UI."""
    return web.json_response(
        {
            "auth_required": bool(config.auth_token),
            "camera": config.camera_source,
            "fps": config.camera_fps,
        }
    )


async def safety_watchdog(app: web.Application) -> None:
    """Stop the car if no command arrives within ``safety_timeout`` seconds."""
    motor: MotorController = app["motor"]
    timeout = config.safety_timeout
    if timeout <= 0:
        return
    stopped = True
    try:
        while True:
            await asyncio.sleep(timeout / 2)
            idle = time.monotonic() - app["last_seen"]
            if app["clients"] and idle < timeout:
                stopped = False
            elif not stopped:
                log.info("safety watchdog: stopping car (idle %.1fs)", idle)
                await asyncio.to_thread(motor.stop)
                stopped = True
    except asyncio.CancelledError:
        pass


async def on_startup(app: web.Application) -> None:
    app["camera"].start(asyncio.get_running_loop())
    app["watchdog"] = asyncio.create_task(safety_watchdog(app))


async def on_cleanup(app: web.Application) -> None:
    app["watchdog"].cancel()
    for ws in set(app["clients"]):
        await ws.close()
    app["camera"].stop()
    app["motor"].close()


def create_app() -> web.Application:
    app = web.Application()
    app["motor"] = MotorController(config)
    app["camera"] = CameraStreamer(config)
    app["clients"] = set()
    app["last_seen"] = time.monotonic()

    app.add_routes(
        [
            web.get("/", index),
            web.get("/ws", websocket_handler),
            web.get("/stream", stream_handler),
            web.get("/api/config", config_handler),
            web.static("/static", WEB_DIR),
        ]
    )
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def main() -> None:
    app = create_app()
    log.info("Cloud RC car listening on http://%s:%d", config.host, config.port)
    if config.auth_token:
        log.info("auth token required for /ws and /stream")
    web.run_app(app, host=config.host, port=config.port, print=None)


if __name__ == "__main__":
    main()
