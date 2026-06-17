#!/usr/bin/env python3
"""Email the car's current IP addresses at boot.

Over a 4G/cloud link the public IP is usually dynamic, so the car emails its
address on startup; you then just open http://<ip>:<port>/ to drive.

Configure via environment variables (e.g. in /etc/rc-car.env):
    RC_SMTP_HOST, RC_SMTP_PORT, RC_SMTP_USER, RC_SMTP_PASS
    RC_MAIL_TO, RC_MAIL_FROM (defaults to RC_SMTP_USER)
    RC_PORT (web port to advertise, default 8080)
"""

from __future__ import annotations

import os
import smtplib
import socket
import ssl
import urllib.request
from email.message import EmailMessage


def local_ips() -> list[str]:
    ips: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def public_ip() -> str | None:
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=10) as r:
            return r.read().decode().strip()
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    host = os.environ.get("RC_SMTP_HOST")
    user = os.environ.get("RC_SMTP_USER")
    password = os.environ.get("RC_SMTP_PASS")
    mail_to = os.environ.get("RC_MAIL_TO")
    if not all((host, user, password, mail_to)):
        print("SMTP settings missing; set RC_SMTP_* and RC_MAIL_TO. Skipping.")
        return 1

    port = int(os.environ.get("RC_SMTP_PORT", "465"))
    web_port = os.environ.get("RC_PORT", "8080")
    locals_ = local_ips()
    public = public_ip()

    lines = ["Cloud RC car is online.", ""]
    for ip in locals_:
        lines.append(f"  Local:  http://{ip}:{web_port}/")
    if public:
        lines.append(f"  Public: http://{public}:{web_port}/  (needs port forwarding)")

    msg = EmailMessage()
    msg["Subject"] = "Cloud RC car online"
    msg["From"] = os.environ.get("RC_MAIL_FROM", user)
    msg["To"] = mail_to
    msg.set_content("\n".join(lines))

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.send_message(msg)
    print("IP notification sent to", mail_to)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
