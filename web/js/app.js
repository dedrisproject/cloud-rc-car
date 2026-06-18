/* Cloud RC Car — browser controller.
 *
 * Talks to the aiohttp server on the same origin:
 *   - WebSocket /ws  for control commands + latency probe
 *   - <img> /stream  for the MJPEG video feed
 *
 * Input sources: on-screen buttons (touch/mouse), keyboard and the Gamepad API.
 * Throttle and steering are de-duplicated independently, so holding e.g.
 * "forward + left" together does not flood the socket.
 */
(() => {
  "use strict";

  // Auth token can be passed in the URL: ?token=...  (kept in stream/ws URLs).
  const params = new URLSearchParams(location.search);
  const token = params.get("token");
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";

  const els = {
    video: document.getElementById("video"),
    status: document.getElementById("status"),
    latency: document.getElementById("latency"),
    gamepad: document.getElementById("gamepad"),
    fullscreen: document.getElementById("fullscreen"),
  };

  // Which control channel a command belongs to, for per-channel de-duplication.
  const CHANNEL = {
    forward: "drive", reverse: "drive", brake: "drive",
    left: "steer", right: "steer", center: "steer",
  };

  // ---- Video feed -----------------------------------------------------
  function startVideo() {
    els.video.src = `/stream${qs}${qs ? "&" : "?"}t=${Date.now()}`;
  }
  els.video.addEventListener("error", () => setTimeout(startVideo, 2000));
  startVideo();

  // ---- WebSocket control ---------------------------------------------
  let socket = null;
  const lastSent = { drive: null, steer: null };
  let reconnectTimer = null;
  let pingTimer = null;

  function setStatus(text, cls) {
    els.status.textContent = text;
    els.status.className = `badge ${cls}`;
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    setStatus("connecting", "connecting");
    socket = new WebSocket(`${proto}://${location.host}/ws${qs}`);

    socket.onopen = () => {
      setStatus("online", "online");
      lastSent.drive = lastSent.steer = null;
      clearInterval(pingTimer);
      pingTimer = setInterval(sendPing, 1000);
      sendPing();
    };
    socket.onclose = () => {
      setStatus("offline", "offline");
      setLatency(null);
      clearInterval(pingTimer);
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 1500);
    };
    socket.onerror = () => socket && socket.close();
    socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "pong") setLatency(Math.round(performance.now() - msg.t));
        else if (msg.type === "error") console.warn("server:", msg.message);
      } catch (_) { /* ignore non-JSON */ }
    };
  }

  function sendPing() {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping", t: performance.now() }));
    }
  }

  function setLatency(ms) {
    if (ms == null) {
      els.latency.textContent = "— ms";
      els.latency.className = "badge muted";
      return;
    }
    els.latency.textContent = `${ms} ms`;
    const cls = ms < 120 ? "lag-ok" : ms < 300 ? "lag-warn" : "lag-bad";
    els.latency.className = `badge ${cls}`;
  }

  // Send a command, de-duplicating consecutive identical ones per channel.
  function send(cmd, { force = false } = {}) {
    if (!cmd) return;
    const ch = CHANNEL[cmd];
    if (!force && ch && cmd === lastSent[ch]) return;
    if (ch) lastSent[ch] = cmd;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ cmd }));
    }
  }

  // ---- On-screen buttons ---------------------------------------------
  document.querySelectorAll(".ctl").forEach((btn) => {
    const press = btn.dataset.press;
    const release = btn.dataset.release;
    const onDown = (e) => { e.preventDefault(); btn.classList.add("active"); send(press, { force: true }); };
    const onUp = (e) => {
      e.preventDefault();
      btn.classList.remove("active");
      if (release) send(release, { force: true });
    };
    btn.addEventListener("pointerdown", onDown);
    btn.addEventListener("pointerup", onUp);
    btn.addEventListener("pointercancel", onUp);
    btn.addEventListener("pointerleave", (e) => { if (btn.classList.contains("active")) onUp(e); });
  });

  els.fullscreen.addEventListener("click", () => {
    const el = document.documentElement;
    if (document.fullscreenElement) document.exitFullscreen();
    else if (el.requestFullscreen) el.requestFullscreen();
  });

  // ---- Keyboard -------------------------------------------------------
  const held = new Set();
  const keyMap = {
    ArrowUp: { press: "forward", release: "brake" },
    ArrowDown: { press: "reverse", release: "brake" },
    ArrowLeft: { press: "left", release: "center" },
    ArrowRight: { press: "right", release: "center" },
    " ": { press: "brake" },
  };

  document.addEventListener("keydown", (e) => {
    const m = keyMap[e.key];
    if (!m || held.has(e.key)) return;
    e.preventDefault();
    held.add(e.key);
    send(m.press, { force: true });
  });
  document.addEventListener("keyup", (e) => {
    const m = keyMap[e.key];
    if (!m) return;
    held.delete(e.key);
    if (m.release) send(m.release, { force: true });
  });

  // ---- Gamepad --------------------------------------------------------
  // Standard mapping: axes[0]=left stick X, buttons[7]=RT (gas),
  // buttons[6]=LT (reverse). Polled on rAF but commands are rate-limited
  // (de-dup already prevents floods; this caps transition spam too).
  let gamepadIndex = null;
  let lastPoll = 0;
  const POLL_INTERVAL_MS = 50; // 20 Hz

  window.addEventListener("gamepadconnected", (e) => {
    gamepadIndex = e.gamepad.index;
    els.gamepad.textContent = "🎮 gamepad";
    els.gamepad.className = "badge online";
  });
  window.addEventListener("gamepaddisconnected", () => {
    gamepadIndex = null;
    els.gamepad.textContent = "no gamepad";
    els.gamepad.className = "badge muted";
  });

  function pollGamepad(now) {
    if (gamepadIndex !== null && now - lastPoll >= POLL_INTERVAL_MS) {
      lastPoll = now;
      const gp = navigator.getGamepads()[gamepadIndex];
      if (gp) {
        const gas = (gp.buttons[7] && gp.buttons[7].value) || 0;
        const rev = (gp.buttons[6] && gp.buttons[6].value) || 0;
        if (gas > 0.2) send("forward");
        else if (rev > 0.2) send("reverse");
        else send("brake");

        const x = gp.axes[0] || 0;
        if (x < -0.3) send("left");
        else if (x > 0.3) send("right");
        else send("center");
      }
    }
    requestAnimationFrame(pollGamepad);
  }
  requestAnimationFrame(pollGamepad);

  connect();
})();
