/* Cloud RC Car — browser controller.
 *
 * Talks to the aiohttp server on the same origin:
 *   - WebSocket /ws  for control commands
 *   - <img> /stream  for the MJPEG video feed
 *
 * Input sources: on-screen buttons (touch/mouse), keyboard and the Gamepad API.
 * Commands are debounced so a held key/button does not flood the socket.
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
    gamepad: document.getElementById("gamepad"),
    lights: document.getElementById("lights"),
    fullscreen: document.getElementById("fullscreen"),
  };

  // ---- Video feed -----------------------------------------------------
  function startVideo() {
    // Cache-bust so a reconnect always pulls a fresh multipart stream.
    els.video.src = `/stream${qs}${qs ? "&" : "?"}t=${Date.now()}`;
  }
  els.video.addEventListener("error", () => setTimeout(startVideo, 2000));
  startVideo();

  // ---- WebSocket control ---------------------------------------------
  let socket = null;
  let lastSent = null;
  let reconnectTimer = null;

  function setStatus(text, cls) {
    els.status.textContent = text;
    els.status.className = `badge ${cls}`;
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    setStatus("connecting", "connecting");
    socket = new WebSocket(`${proto}://${location.host}/ws${qs}`);

    socket.onopen = () => setStatus("online", "online");
    socket.onclose = () => {
      setStatus("offline", "offline");
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 1500);
    };
    socket.onerror = () => socket && socket.close();
    socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "state") applyState(msg);
        else if (msg.type === "error") console.warn("server:", msg.message);
      } catch (_) { /* ignore non-JSON */ }
    };
  }

  function applyState(state) {
    els.lights.classList.toggle("on", !!state.lights);
  }

  // Send a command, skipping consecutive duplicates (server also dedupes).
  function send(cmd, { force = false } = {}) {
    if (!cmd) return;
    if (!force && cmd === lastSent) return;
    lastSent = cmd;
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

  els.lights.addEventListener("click", () => send("lights_toggle", { force: true }));
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
    if (e.key.toLowerCase() === "l") { send("lights_toggle", { force: true }); return; }
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
  // buttons[6]=LT (reverse), buttons[0]=A (lights).
  let gamepadIndex = null;
  let lightsBtnPrev = false;

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

  function pollGamepad() {
    if (gamepadIndex !== null) {
      const gp = navigator.getGamepads()[gamepadIndex];
      if (gp) {
        // Drive
        const gas = (gp.buttons[7] && gp.buttons[7].value) || 0;
        const rev = (gp.buttons[6] && gp.buttons[6].value) || 0;
        if (gas > 0.2) send("forward");
        else if (rev > 0.2) send("reverse");
        else send("brake");

        // Steering
        const x = gp.axes[0] || 0;
        if (x < -0.3) send("left");
        else if (x > 0.3) send("right");
        else send("center");

        // Lights on A button (edge-triggered)
        const a = !!(gp.buttons[0] && gp.buttons[0].pressed);
        if (a && !lightsBtnPrev) send("lights_toggle", { force: true });
        lightsBtnPrev = a;
      }
    }
    requestAnimationFrame(pollGamepad);
  }
  requestAnimationFrame(pollGamepad);

  connect();
})();
