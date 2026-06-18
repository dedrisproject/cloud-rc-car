<div align="center">

# 🚗 cloud-rc-car

**Guida una macchinina radiocomandata da qualsiasi browser, ovunque nel mondo, con video in diretta.**

Raspberry Pi a bordo + Arduino/motor shield per i motori + connessione 4G/cloud.

</div>

---

## Installazione (one-line)

Sul Raspberry Pi, un solo comando installa tutto e avvia una **procedura
guidata** (porta, token, seriale, camera, accesso da remoto), configura l'avvio
al boot e il comando di gestione `rc-car`:

```bash
curl -fsSL https://raw.githubusercontent.com/dedrisproject/cloud-rc-car/master/install.sh | bash
```

Al termine ti mostra l'URL a cui collegarti. Per gestire il servizio:

```bash
rc-car status        # stato del servizio
rc-car logs          # log in tempo reale
rc-car restart       # riavvia
rc-car update        # aggiorna dal repo e riavvia
rc-car reconfigure   # rilancia la procedura guidata
```

> Preferisci a mano o provare senza hardware? Vedi
> [Avvio rapido](#avvio-rapido-sviluppo-senza-hardware) e
> [Avvio manuale sul Raspberry Pi](#avvio-manuale-sul-raspberry-pi).

## Cos'è

`cloud-rc-car` trasforma una normale macchinina RC in un veicolo telecomandato via
internet. Sul Raspberry Pi montato a bordo gira **un unico server Python** che:

- serve l'**interfaccia web** di guida,
- riceve i comandi dal browser via **WebSocket**,
- li traduce nel protocollo seriale dell'**Arduino** che pilota i motori,
- e trasmette il **video della webcam** in streaming MJPEG.

Tutto su **una sola porta**: dietro una connessione 4G ne inoltri una soltanto,
senza il caos di IP/porte multiple e iframe della versione originale.

> Riscrittura completa del prototipo originale (PHP + script separati) in un
> singolo server Python + UI moderna.

## Come funziona

```
 Browser (telefono / pc)             Raspberry Pi                      Arduino
 ┌────────────────────┐  WebSocket   ┌───────────────────────┐  seriale ┌──────────┐
 │ UI web             │ ──/ws──────▶ │ server/app.py          │ ───────▶ │ firmware │ ─▶ motori
 │ touch+pad+tastiera │              │  • web server aiohttp  │  "7|"    │ (shield) │
 │ video MJPEG <img>  │ ◀─/stream─── │  • motor.py (seriale)  │          └──────────┘
 └────────────────────┘              │  • camera.py (MJPEG)   │
                                      └───────────────────────┘ ◀USB/CSI─ webcam
```

Il browser invia **comandi semantici** (`forward`, `left`, `right`, …);
il server li converte nei codici seriali dell'Arduino che pilota i motori.

## Cosa serve

| # | Componente |
|---|------------|
| 1 | Una macchinina RC da smontare |
| 2 | Raspberry Pi (montato sulla macchina) |
| 3 | Arduino + motor shield |
| 4 | Webcam USB oppure modulo camera per Raspberry Pi |
| 5 | *(opzionale)* un gamepad (Xbox o altro) lato browser |

## Struttura del progetto

| Percorso | Descrizione |
|----------|-------------|
| `server/app.py` | Server aiohttp: UI web + `/ws` controllo + `/stream` MJPEG |
| `server/motor.py` | Link seriale all'Arduino (con fallback mock) |
| `server/camera.py` | Acquisizione e streaming MJPEG (picamera2 / OpenCV / mock) |
| `server/config.py` | Tutte le impostazioni da variabili d'ambiente / `.env` |
| `web/` | Frontend: pulsanti touch, tastiera, gamepad |
| `firmware/motorshield/motorshield.ino` | Sketch Arduino |
| `install.sh` | Installer one-line + wizard di setup per Raspberry Pi |
| `scripts/` | `notify_ip.py` + unit systemd per l'avvio al boot |

## Avvio rapido (sviluppo, senza hardware)

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
RC_MOCK=1 python app.py
```

Apri <http://localhost:8080/>. Con `RC_MOCK=1` la seriale e la camera
sono **simulate** (il video mostra un'immagine di test sintetica): puoi provare
tutta l'interfaccia da un portatile, senza nulla collegato.

## Avvio manuale sul Raspberry Pi

1. **Dipendenze** (core + hardware):
   ```bash
   pip install -r server/requirements.txt -r server/requirements-pi.txt
   sudo apt install python3-picamera2   # se usi il modulo camera del Pi
   ```
2. **Configura**: `cp server/.env.example server/.env` e modificalo
   (porta seriale, camera e — importante su 4G — `RC_AUTH_TOKEN`).
3. **Avvia**: `python3 server/app.py`, poi apri `http://<ip-del-pi>:8080/`.
   Con token impostato: `http://<ip-del-pi>:8080/?token=IL_TUO_TOKEN`.

### Avvio automatico al boot + IP via email

Su 4G l'IP pubblico di solito è dinamico, quindi la macchina **invia il proprio
indirizzo via email all'accensione**: clicchi il link e guidi.

```bash
sudo cp server/.env.example /etc/rc-car.env   # imposta SMTP + variabili RC_*
sudo cp scripts/systemd/rc-car.service /etc/systemd/system/
sudo cp scripts/systemd/rc-car-notify-ip.service /etc/systemd/system/
sudo systemctl enable --now rc-car
sudo systemctl enable rc-car-notify-ip
```

## Accesso da remoto (4G / 5G)

Su rete mobile l'IP è quasi sempre dietro **CGNAT**: non è raggiungibile da
internet e il port forwarding non è possibile. Due soluzioni:

- **Cloudflare Tunnel** *(consigliato)*: dà un URL pubblico stabile in **HTTPS**
  senza IP pubblico né port forwarding. Setup completo nel file
  [`scripts/systemd/rc-car-tunnel.service`](scripts/systemd/rc-car-tunnel.service);
  per una prova veloce basta `cloudflared tunnel --url http://localhost:8080`
  (URL `*.trycloudflare.com` casuale).
- **Tailscale / ZeroTier**: VPN mesh; il Pi ottiene un IP stabile sulla tua rete
  privata. Ottimo se accedi solo dai tuoi dispositivi (richiede l'app sul
  client). `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`.

In rete locale (Wi-Fi) puoi invece usare direttamente `http://<ip-del-pi>:8080/`.

Con un tunnel hai anche TLS gratis: tieni comunque `RC_AUTH_TOKEN` impostato.

## Comandi di guida

| Input | Azione |
|-------|--------|
| Pulsanti a schermo | sterzo ◀●▶ e marcia ▲■▼ (touch e mouse) |
| Tastiera | ↑ avanti · ↓ retro · ← → sterzo · spazio freno |
| Gamepad | RT acceleratore · LT retro · stick sinistro sterzo |

L'HUD mostra stato connessione e **latenza (RTT)** misurata via ping sul
WebSocket. Trazione e sterzo sono canali indipendenti: tenerli premuti insieme
non intasa la seriale (de-duplica per canale).

## Protocollo comandi

| Semantico (browser → server) | Codice seriale (server → Arduino) |
|------------------------------|-----------------------------------|
| `forward` | `7\|` |
| `brake` | `6\|` |
| `reverse` | `1\|` |
| `left` | `14\|` |
| `right` | `15\|` |
| `center` | `12\|` |

## Test

I test girano senza hardware (mock):

```bash
pip install pytest
pytest
```

## Sicurezza

- **Watchdog**: se non arrivano comandi entro `RC_SAFETY_TIMEOUT` secondi (es.
  la connessione cade), la macchina frena e raddrizza le ruote automaticamente.
- **Token condiviso**: imposta `RC_AUTH_TOKEN` per proteggere `/ws` e `/stream`
  quando la macchina è raggiungibile da internet. **Fortemente consigliato su 4G.**
- Nessun IP o credenziale è scritto nel codice: tutto passa da `.env` /
  variabili d'ambiente (e `.env` è in `.gitignore`).

## Configurazione

Tutte le impostazioni hanno un default sensato e si sovrascrivono via ambiente o
`.env`. Le principali:

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `RC_HOST` / `RC_PORT` | `0.0.0.0` / `8080` | Bind del server web |
| `RC_AUTH_TOKEN` | *(vuoto)* | Token per `/ws` e `/stream` (vuoto = disattivo) |
| `RC_SERIAL_PORT` / `RC_SERIAL_BAUD` | `/dev/ttyACM0` / `115200` | Link Arduino (il baud deve combaciare col firmware) |
| `RC_CAMERA_SOURCE` | `auto` | `auto` / `picamera2` / `opencv` / `mock` |
| `RC_CAMERA_WIDTH/HEIGHT/FPS/QUALITY` | `640/480/15/70` | Parametri video |
| `RC_SAFETY_TIMEOUT` | `1.5` | Secondi prima dello stop di sicurezza (0 = off) |
| `RC_MOCK` | `0` | Forza hardware simulato (sviluppo) |

Elenco completo in [`server/.env.example`](server/.env.example).

## Licenza

Progetto personale/hobbistico. Usalo, modificalo e divertiti — guida con prudenza. 🏁
