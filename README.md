<div align="center">

# 🚗 cloud-rc-car

**Drive a radio-controlled car from any browser, anywhere in the world, with live video.**

Raspberry Pi on board + Arduino/motor shield for the motors + 4G/cloud connection.

</div>

---

## Install (one-line)

On the Raspberry Pi, a single command installs everything and launches an
**interactive setup wizard** (port, token, serial, camera, remote access),
configures boot-time startup and the `rc-car` management command:

```bash
curl -fsSL https://raw.githubusercontent.com/dedrisproject/cloud-rc-car/master/install.sh | bash
```

When it finishes it prints the URL to connect to. To manage the service:

```bash
rc-car status        # service status
rc-car logs          # live logs
rc-car restart       # restart
rc-car update        # pull from the repo and restart
rc-car reconfigure   # re-run the setup wizard
```

> Prefer to do it manually or try it without hardware? See
> [Quick start](#quick-start-development-no-hardware) and
> [Manual setup on the Raspberry Pi](#manual-setup-on-the-raspberry-pi).

## What it is

`cloud-rc-car` turns an ordinary RC car into a vehicle you control over the
internet. A **single Python server** runs on the on-board Raspberry Pi and:

- serves the **web control UI**,
- receives commands from the browser over **WebSocket**,
- translates them into the serial protocol of the **Arduino** that drives the motors,
- and streams the **webcam video** as MJPEG.

Everything on **one port**: behind a 4G connection you only forward a single
port, with none of the multi-IP/multi-port and iframe mess of the original.

> A complete rewrite of the original prototype (PHP + separate scripts) into a
> single Python server + modern UI.

## How it works

```
 Browser (phone / pc)                Raspberry Pi                     Arduino
 ┌────────────────────┐  WebSocket   ┌───────────────────────┐  serial  ┌──────────┐
 │ web UI             │ ──/ws──────▶ │ server/app.py          │ ───────▶ │ firmware │ ─▶ motors
 │ touch+pad+keyboard │              │  • aiohttp web server  │  "7|"    │ (shield) │
 │ MJPEG video <img>  │ ◀─/stream─── │  • motor.py (serial)   │          └──────────┘
 └────────────────────┘              │  • camera.py (MJPEG)   │
                                      └───────────────────────┘ ◀USB/CSI─ webcam
```

The browser sends **semantic commands** (`forward`, `left`, `right`, …); the
server converts them into the Arduino's serial codes that drive the motors.

## What you need

| # | Component |
|---|-----------|
| 1 | An RC car to take apart |
| 2 | Raspberry Pi (mounted on the car) |
| 3 | Arduino + motor shield |
| 4 | USB webcam or Raspberry Pi camera module |
| 5 | *(optional)* a gamepad (Xbox or any) on the browser side |

## Project layout

| Path | Description |
|------|-------------|
| `server/app.py` | aiohttp server: web UI + `/ws` control + `/stream` MJPEG |
| `server/motor.py` | serial link to the Arduino (with mock fallback) |
| `server/camera.py` | capture and MJPEG streaming (picamera2 / OpenCV / mock) |
| `server/config.py` | all settings from environment variables / `.env` |
| `web/` | frontend: touch buttons, keyboard, gamepad |
| `firmware/motorshield/motorshield.ino` | Arduino sketch |
| `install.sh` | one-line installer + setup wizard for the Raspberry Pi |
| `scripts/` | `notify_ip.py` + systemd units for boot-time startup |

## Quick start (development, no hardware)

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
RC_MOCK=1 python app.py
```

Open <http://localhost:8080/>. With `RC_MOCK=1` the serial link and camera are
**simulated** (the video shows a synthetic test image): you can try the whole
interface from a laptop, with nothing connected.

## Manual setup on the Raspberry Pi

1. **Dependencies** (core + hardware):
   ```bash
   pip install -r server/requirements.txt -r server/requirements-pi.txt
   sudo apt install python3-picamera2   # if you use the Pi camera module
   ```
2. **Configure**: `cp server/.env.example server/.env` and edit it
   (serial port, camera and — important on 4G — `RC_AUTH_TOKEN`).
3. **Run**: `python3 server/app.py`, then open `http://<pi-ip>:8080/`.
   With a token set: `http://<pi-ip>:8080/?token=YOUR_TOKEN`.

### Start at boot + email the IP

On 4G the public IP is usually dynamic, so the car **emails its own address at
startup**: you click the link and drive.

```bash
sudo cp server/.env.example /etc/rc-car.env   # set SMTP + RC_* variables
sudo cp scripts/systemd/rc-car.service /etc/systemd/system/
sudo cp scripts/systemd/rc-car-notify-ip.service /etc/systemd/system/
sudo systemctl enable --now rc-car
sudo systemctl enable rc-car-notify-ip
```

## Remote access (4G / 5G)

On mobile networks the IP is almost always behind **CGNAT**: not reachable from
the internet, and port forwarding is impossible. Two options:

- **Cloudflare Tunnel** *(recommended)*: gives a stable public **HTTPS** URL with
  no public IP and no port forwarding. Full setup in
  [`scripts/systemd/rc-car-tunnel.service`](scripts/systemd/rc-car-tunnel.service);
  for a quick test just run `cloudflared tunnel --url http://localhost:8080`
  (random `*.trycloudflare.com` URL).
- **Tailscale / ZeroTier**: mesh VPN; the Pi gets a stable IP on your private
  network. Great if you only connect from your own devices (requires the app on
  the client). `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`.

On the local network (Wi-Fi) you can just use `http://<pi-ip>:8080/`.

With a tunnel you also get TLS for free: keep `RC_AUTH_TOKEN` set anyway.

## Driving controls

| Input | Action |
|-------|--------|
| On-screen buttons | steering ◀●▶ and drive ▲■▼ (touch and mouse) |
| Keyboard | ↑ forward · ↓ reverse · ← → steer · space brake |
| Gamepad | RT throttle · LT reverse · left stick steering |

The HUD shows the connection status and the **latency (RTT)** measured via a
WebSocket ping. Throttle and steering are independent channels: holding them
together does not flood the serial link (per-channel de-duplication).

## Command protocol

| Semantic (browser → server) | Serial code (server → Arduino) |
|-----------------------------|--------------------------------|
| `forward` | `7\|` |
| `brake` | `6\|` |
| `reverse` | `1\|` |
| `left` | `14\|` |
| `right` | `15\|` |
| `center` | `12\|` |

## Tests

The tests run without hardware (mock):

```bash
pip install pytest
pytest
```

## Safety

- **Watchdog**: if no command arrives within `RC_SAFETY_TIMEOUT` seconds (e.g.
  the connection drops), the car brakes and recenters the wheels automatically.
- **Shared token**: set `RC_AUTH_TOKEN` to protect `/ws` and `/stream` when the
  car is reachable from the internet. **Strongly recommended on 4G.**
- No IP or credential is hardcoded: everything comes from `.env` / environment
  variables (and `.env` is in `.gitignore`).

## Configuration

Every setting has a sensible default and can be overridden via the environment
or `.env`. The main ones:

| Variable | Default | Description |
|----------|---------|-------------|
| `RC_HOST` / `RC_PORT` | `0.0.0.0` / `8080` | Web server bind |
| `RC_AUTH_TOKEN` | *(empty)* | Token for `/ws` and `/stream` (empty = disabled) |
| `RC_SERIAL_PORT` / `RC_SERIAL_BAUD` | `/dev/ttyACM0` / `115200` | Arduino link (baud must match the firmware) |
| `RC_CAMERA_SOURCE` | `auto` | `auto` / `picamera2` / `opencv` / `mock` |
| `RC_CAMERA_WIDTH/HEIGHT/FPS/QUALITY` | `640/480/15/70` | Video parameters |
| `RC_SAFETY_TIMEOUT` | `1.5` | Seconds before the safety stop (0 = off) |
| `RC_MOCK` | `0` | Force simulated hardware (development) |

Full list in [`server/.env.example`](server/.env.example).

## License

Personal/hobby project. Use it, modify it and have fun — drive responsibly. 🏁
