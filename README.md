# cloud-rc-car

An RC car you drive over the internet (4G / cloud) from any browser, with a live
camera feed. Built around a Raspberry Pi (running the server) and an Arduino +
motor shield (driving the motors).

This is a full rewrite of the original PHP + multi-script prototype into a single
Python server plus a modern web UI. Everything — web page, control channel and
video stream — runs on **one port**, so only one port has to be forwarded over
your 4G/cloud link.

## How it works

```
 Browser (phone / pc)                Raspberry Pi                     Arduino
 ┌───────────────────┐   WebSocket   ┌──────────────────────┐  serial ┌──────────┐
 │ web/ UI           │ ───/ws──────▶ │ server/app.py         │ ──────▶ │ firmware │ ─▶ motors
 │ touch+pad+keyboard │              │  • aiohttp web server │  "7|"   │ (shield) │
 │ MJPEG <img>       │ ◀──/stream─── │  • motor.py (serial)  │         └──────────┘
 └───────────────────┘               │  • camera.py (MJPEG) │ ─GPIO─▶ headlights
                                      └──────────────────────┘ ◀USB/CSI─ camera
```

The browser sends **semantic commands** (`forward`, `left`, `lights_toggle`, …);
the server translates them into the numeric serial protocol the Arduino expects
and drives the headlights over GPIO.

## Hardware

1. An RC car to disassemble
2. Raspberry Pi (mounted on the car)
3. Arduino + motor shield
4. USB webcam or Raspberry Pi camera module
5. Optional: an Xbox / any gamepad on the browser side

## Repository layout

| Path | What it is |
|------|------------|
| `server/app.py` | aiohttp server: web UI + `/ws` control + `/stream` MJPEG |
| `server/motor.py` | serial link to Arduino + headlight GPIO (mock fallback) |
| `server/camera.py` | camera capture & MJPEG (picamera2 / OpenCV / mock) |
| `server/config.py` | all settings, from env vars / `.env` (no hardcoded IPs) |
| `web/` | frontend: touch buttons, keyboard and gamepad control |
| `firmware/motorshield/motorshield.ino` | Arduino sketch |
| `scripts/` | `notify_ip.py` + systemd units for boot-time startup |

## Quick start (development, no hardware)

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
RC_MOCK=1 python app.py
```

Open <http://localhost:8080/>. With `RC_MOCK=1` the serial link, GPIO and camera
are all simulated (the video shows a synthetic test image), so you can try the
whole UI on a laptop.

## Running on the Raspberry Pi

1. Install dependencies (uncomment the hardware lines in
   `server/requirements.txt` first):
   ```bash
   pip install -r server/requirements.txt
   sudo apt install python3-picamera2   # if using the Pi camera module
   ```
2. Configure: `cp server/.env.example server/.env` and edit it
   (serial port, camera, and — important over 4G — `RC_AUTH_TOKEN`).
3. Run: `python3 server/app.py`, then open `http://<pi-ip>:8080/`.
   If you set a token: `http://<pi-ip>:8080/?token=YOUR_TOKEN`.

### Start on boot + email the IP

```bash
sudo cp server/.env.example /etc/rc-car.env   # edit: SMTP + RC_* settings
sudo cp scripts/systemd/rc-car.service /etc/systemd/system/
sudo cp scripts/systemd/rc-car-notify-ip.service /etc/systemd/system/
sudo systemctl enable --now rc-car
sudo systemctl enable rc-car-notify-ip
```

On boot the car emails its local & public IP, so you just click the link and
drive.

## Controls

| Input | Action |
|-------|--------|
| On-screen buttons | steering ◀●▶ and drive ▲■▼ (touch & mouse) |
| Keyboard | ↑ forward · ↓ reverse · ← → steer · space brake · L lights |
| Gamepad | RT throttle · LT reverse · left stick steering · A lights |

## Command protocol

| Semantic (browser → server) | Serial code (server → Arduino) |
|------|------|
| `forward` | `7\|` |
| `brake` | `6\|` |
| `reverse` | `1\|` |
| `left` | `14\|` |
| `right` | `15\|` |
| `center` | `12\|` |
| `lights_on` / `lights_off` / `lights_toggle` | GPIO pin (no serial) |

A safety watchdog stops the car and recenters the wheels if no command arrives
within `RC_SAFETY_TIMEOUT` seconds (e.g. the connection drops).
