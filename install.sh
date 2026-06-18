#!/usr/bin/env bash
#
# Cloud RC Car — one-line installer + setup wizard.
#
#   curl -fsSL https://raw.githubusercontent.com/dedrisproject/cloud-rc-car/master/install.sh | bash
#
# Installs dependencies, clones the repo, runs an interactive setup wizard,
# installs the systemd services and a `rc-car` management command.
#
# Re-run the wizard later with:  rc-car reconfigure
#
set -euo pipefail

REPO_URL="https://github.com/dedrisproject/cloud-rc-car.git"
RAW_BRANCH="master"
RC_USER="${SUDO_USER:-$(id -un)}"
RC_HOME="$(getent passwd "$RC_USER" | cut -d: -f6)"
RC_DIR="${RC_DIR:-$RC_HOME/cloud-rc-car}"
ENV_FILE="$RC_DIR/server/.env"
MODE="install"
[ "${1:-}" = "--reconfigure" ] && MODE="reconfigure"

# ---- pretty output --------------------------------------------------------
if [ -t 1 ]; then
  B="\033[1m"; DIM="\033[2m"; G="\033[32m"; Y="\033[33m"; C="\033[36m"; R="\033[31m"; N="\033[0m"
else
  B=""; DIM=""; G=""; Y=""; C=""; R=""; N=""
fi
say()  { printf "%b\n" "$*"; }
step() { printf "\n%b▸ %s%b\n" "$C$B" "$*" "$N"; }
ok()   { printf "%b✓%b %s\n" "$G" "$N" "$*"; }
warn() { printf "%b!%b %s\n" "$Y" "$N" "$*"; }
die()  { printf "%b✗ %s%b\n" "$R" "$*" "$N" >&2; exit 1; }

# Read a value from the real terminal even when piped through curl.
TTY=/dev/tty
ask() { # ask "Prompt" "default" -> echoes answer
  local prompt="$1" def="${2:-}" ans=""
  if [ -r "$TTY" ]; then
    if [ -n "$def" ]; then printf "%b  %s %b[%s]%b: " "$B" "$prompt" "$DIM" "$def" "$N" > "$TTY"
    else printf "%b  %s%b: " "$B" "$prompt" "$N" > "$TTY"; fi
    read -r ans < "$TTY" || true
  fi
  printf "%s" "${ans:-$def}"
}
ask_yn() { # ask_yn "Prompt" "y|n" -> returns 0 for yes
  local def="${2:-n}" a; a="$(ask "$1 (y/n)" "$def")"
  case "$a" in y|Y|yes|s|S|si) return 0;; *) return 1;; esac
}

banner() {
  say "${C}${B}"
  say "   ____ _                 _   ____   ____    ____"
  say "  / ___| | ___  _   _  __| | |  _ \\ / ___|  / ___|__ _ _ __"
  say " | |   | |/ _ \\| | | |/ _\` | | |_) | |     | |   / _\` | '__|"
  say " | |___| | (_) | |_| | (_| | |  _ <| |___  | |__| (_| | |"
  say "  \\____|_|\\___/ \\__,_|\\__,_| |_| \\_\\\\____|  \\____\\__,_|_|"
  say "${N}${DIM}        guida la tua RC car dal browser, ovunque${N}"
}

need_sudo() { if [ "$(id -u)" -ne 0 ]; then sudo "$@"; else "$@"; fi; }

# ---- detection ------------------------------------------------------------
detect_arch() {
  case "$(uname -m)" in
    aarch64|arm64) echo arm64;; armv7l|armv6l) echo arm;;
    x86_64|amd64) echo amd64;; *) echo "";;
  esac
}
detect_serial() {
  local p
  for p in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyUSB0 /dev/ttyUSB1; do
    [ -e "$p" ] && { echo "$p"; return; }
  done
  echo /dev/ttyACM0
}

# ---- steps ----------------------------------------------------------------
install_packages() {
  step "Installazione dipendenze di sistema"
  if command -v apt-get >/dev/null 2>&1; then
    need_sudo apt-get update -qq
    need_sudo apt-get install -y -qq git python3 python3-venv python3-pip >/dev/null
    ok "git, python3, venv, pip"
  else
    warn "apt non trovato: assicurati di avere git e python3 installati."
  fi
}

clone_repo() {
  step "Download del progetto in $RC_DIR"
  if [ -d "$RC_DIR/.git" ]; then
    git -C "$RC_DIR" pull --ff-only && ok "repository aggiornato"
  else
    git clone --depth 1 -b "$RAW_BRANCH" "$REPO_URL" "$RC_DIR" && ok "repository clonato"
  fi
}

setup_venv() {
  step "Ambiente Python (con accesso ai pacchetti di sistema per picamera2)"
  python3 -m venv --system-site-packages "$RC_DIR/server/.venv"
  # shellcheck disable=SC1091
  "$RC_DIR/server/.venv/bin/pip" install -q --upgrade pip >/dev/null
  "$RC_DIR/server/.venv/bin/pip" install -q -r "$RC_DIR/server/requirements.txt" >/dev/null
  ok "dipendenze core installate"
  if [ -f "$RC_DIR/server/requirements-pi.txt" ]; then
    "$RC_DIR/server/.venv/bin/pip" install -q -r "$RC_DIR/server/requirements-pi.txt" >/dev/null \
      && ok "dipendenze hardware (pyserial, opencv)" \
      || warn "alcune dipendenze hardware non installate (ok in mock)"
  fi
}

wizard() {
  step "Configurazione guidata"
  say "${DIM}  Premi Invio per accettare il valore tra parentesi.${N}"

  local port token serial cam timeout remote
  port="$(ask 'Porta web' "${RC_PORT:-8080}")"
  local def_token; def_token="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  say "${DIM}  Il token protegge l'accesso: usalo nell'URL ?token=...  (consigliato su internet)${N}"
  token="$(ask 'Token di accesso (vuoto = nessuno)' "${RC_AUTH_TOKEN:-$def_token}")"
  serial="$(ask 'Porta seriale Arduino' "$(detect_serial)")"
  say "${DIM}  Camera: auto | picamera2 | opencv | mock${N}"
  cam="$(ask 'Sorgente camera' "${RC_CAMERA_SOURCE:-auto}")"
  timeout="$(ask 'Timeout di sicurezza in secondi (0 = off)' "${RC_SAFETY_TIMEOUT:-1.5}")"

  step "Accesso da remoto (4G/5G)"
  say "  Su rete mobile l'IP è dietro CGNAT e non è raggiungibile direttamente."
  say "    ${B}1${N}) Cloudflare Tunnel  ${DIM}(URL pubblico stabile + HTTPS, consigliato)${N}"
  say "    ${B}2${N}) Tailscale          ${DIM}(VPN privata fra i tuoi dispositivi)${N}"
  say "    ${B}3${N}) Nessuno            ${DIM}(solo rete locale Wi-Fi)${N}"
  remote="$(ask 'Scelta' '3')"

  mkdir -p "$(dirname "$ENV_FILE")"
  cat > "$ENV_FILE" <<EOF
# Generato da install.sh il $(date -Is)
RC_HOST=0.0.0.0
RC_PORT=$port
RC_AUTH_TOKEN=$token
RC_SERIAL_PORT=$serial
RC_SERIAL_BAUD=115200
RC_CAMERA_SOURCE=$cam
RC_CAMERA_WIDTH=640
RC_CAMERA_HEIGHT=480
RC_CAMERA_FPS=15
RC_CAMERA_QUALITY=70
RC_SAFETY_TIMEOUT=$timeout
RC_MOCK=0
EOF
  ok "configurazione salvata in $ENV_FILE"

  RC_REMOTE_CHOICE="$remote"
  RC_WEB_PORT="$port"
  RC_WEB_TOKEN="$token"
}

ensure_serial_access() {
  # Let the service user talk to the Arduino without sudo.
  if getent group dialout >/dev/null 2>&1; then
    need_sudo usermod -aG dialout "$RC_USER" 2>/dev/null && \
      ok "utente $RC_USER aggiunto al gruppo dialout (riavvia la sessione)"
  fi
}

install_service() {
  step "Servizio systemd (avvio automatico al boot)"
  local py="$RC_DIR/server/.venv/bin/python"
  need_sudo tee /etc/systemd/system/rc-car.service >/dev/null <<EOF
[Unit]
Description=Cloud RC Car server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RC_USER
WorkingDirectory=$RC_DIR/server
EnvironmentFile=-$ENV_FILE
ExecStart=$py $RC_DIR/server/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
  need_sudo systemctl daemon-reload
  need_sudo systemctl enable --now rc-car >/dev/null 2>&1 || need_sudo systemctl restart rc-car
  ok "servizio rc-car attivo"
}

setup_remote() {
  case "${RC_REMOTE_CHOICE:-3}" in
    1) setup_cloudflare ;;
    2) setup_tailscale ;;
    *) ok "nessun accesso remoto configurato (solo rete locale)";;
  esac
}

setup_cloudflare() {
  step "Cloudflare Tunnel"
  if ! command -v cloudflared >/dev/null 2>&1; then
    local arch; arch="$(detect_arch)"
    [ -n "$arch" ] || { warn "architettura non riconosciuta, salto cloudflared"; return; }
    need_sudo curl -fsSL \
      "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$arch" \
      -o /usr/local/bin/cloudflared
    need_sudo chmod +x /usr/local/bin/cloudflared
    ok "cloudflared installato"
  fi
  say ""
  say "  Completa il setup del tunnel (una tantum):"
  say "    ${B}cloudflared tunnel login${N}"
  say "    ${B}cloudflared tunnel create rc-car${N}"
  say "    ${B}cloudflared tunnel route dns rc-car car.tuo-dominio.com${N}"
  say "  poi crea /etc/cloudflared/config.yml e abilita il servizio:"
  say "    ${B}sudo systemctl enable --now rc-car-tunnel${N}"
  say "  ${DIM}(dettagli in scripts/systemd/rc-car-tunnel.service)${N}"
  say ""
  if ask_yn "Vuoi un tunnel di prova ADESSO (URL casuale *.trycloudflare.com)" "n"; then
    say "${DIM}  Premi Ctrl+C per fermarlo.${N}"
    cloudflared tunnel --url "http://localhost:${RC_WEB_PORT}" < "$TTY" || true
  fi
}

setup_tailscale() {
  step "Tailscale"
  if ! command -v tailscale >/dev/null 2>&1; then
    curl -fsSL https://tailscale.com/install.sh | sh
  fi
  say "  Avvia e autentica con:  ${B}sudo tailscale up${N}"
  say "  Poi raggiungi la macchina al suo IP Tailscale, porta ${RC_WEB_PORT}."
}

install_cli() {
  step "Comando di gestione 'rc-car'"
  need_sudo tee /usr/local/bin/rc-car >/dev/null <<EOF
#!/usr/bin/env bash
set -euo pipefail
RC_DIR="$RC_DIR"
case "\${1:-help}" in
  start)   sudo systemctl start rc-car ;;
  stop)    sudo systemctl stop rc-car ;;
  restart) sudo systemctl restart rc-car ;;
  status)  systemctl status rc-car --no-pager ;;
  logs)    journalctl -u rc-car -f -n 100 ;;
  url)     grep -E '^RC_(PORT|AUTH_TOKEN)=' "\$RC_DIR/server/.env" ;;
  update)  git -C "\$RC_DIR" pull --ff-only && \
           "\$RC_DIR/server/.venv/bin/pip" install -q -r "\$RC_DIR/server/requirements.txt" -r "\$RC_DIR/server/requirements-pi.txt" && \
           sudo systemctl restart rc-car && echo "aggiornato" ;;
  reconfigure) bash "\$RC_DIR/install.sh" --reconfigure ;;
  *) echo "uso: rc-car {start|stop|restart|status|logs|url|update|reconfigure}";;
esac
EOF
  need_sudo chmod +x /usr/local/bin/rc-car
  ok "usa 'rc-car logs', 'rc-car restart', 'rc-car reconfigure' ..."
}

summary() {
  local ip; ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  local q=""; [ -n "${RC_WEB_TOKEN:-}" ] && q="?token=${RC_WEB_TOKEN}"
  say ""
  say "${G}${B}Installazione completata.${N}"
  say "  Apri:   ${B}http://${ip:-<ip-del-pi>}:${RC_WEB_PORT:-8080}/${q}${N}"
  [ -n "${RC_WEB_TOKEN:-}" ] && say "  Token:  ${DIM}${RC_WEB_TOKEN}${N}"
  say "  Gestione: ${B}rc-car status${N} · ${B}rc-car logs${N} · ${B}rc-car reconfigure${N}"
  say ""
}

# ---- main -----------------------------------------------------------------
main() {
  banner
  if [ "$MODE" = "reconfigure" ]; then
    wizard
    setup_remote
    need_sudo systemctl restart rc-car 2>/dev/null || true
    summary
    return
  fi
  install_packages
  clone_repo
  setup_venv
  wizard
  ensure_serial_access
  install_service
  install_cli
  setup_remote
  summary
}
main "$@"
