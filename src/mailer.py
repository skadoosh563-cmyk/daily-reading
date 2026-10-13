"""SMTP 发送 HTML 邮件。"""
from __future__ import annotations

import os
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send(cfg: dict, subject: str, html_body: str) -> bool:
    ec = cfg["email"]
    sender = os.environ.get("SMTP_SENDER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    receiver = os.environ.get("SMTP_RECEIVER", "").strip() or sender

    if not (sender and password and receiver):
        print("  [跳过邮件] 没有配 SMTP_SENDER / SMTP_PASSWORD / SMTP_RECEIVER")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    host = ec.get("smtp_host", "smtp.qq.com")
    port = int(ec.get("smtp_port", 465))
    try:
        with smtplib.SMTP_SSL(host, port, timeout=60) as server:
            server.login(sender, password)
            server.sendmail(sender, [r.strip() for r in receiver.split(",")], msg.as_string())
        print(f"  [邮件已发送] → {receiver}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  [邮件发送失败] {type(exc).__name__} {exc}")
        return False
