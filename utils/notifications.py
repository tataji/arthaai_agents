"""
utils/notifications.py — Telegram and email alerts
"""

import smtplib
from email.mime.text import MIMEText
from typing import Optional
import requests
import config
from utils.logger import get_logger

logger = get_logger("notifications")


def send_telegram(message: str) -> bool:
    """Send a message to Telegram channel."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def send_email(subject: str, body: str, to: Optional[str] = None) -> bool:
    """Send email alert via SMTP."""
    smtp_user = config.SMTP_USER
    smtp_pass = config.SMTP_PASSWORD
    if not smtp_user or not smtp_pass:
        return False
    try:
        msg = MIMEText(body, "html")
        msg["Subject"] = f"[ArthAI] {subject}"
        msg["From"] = smtp_user
        msg["To"] = to or config.ALERT_EMAIL
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [msg["To"]], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def alert_trade(action: str, symbol: str, qty: int, price: float,
                sl: float, target: float, rationale: str) -> None:
    """Send trade alert across all channels."""
    emoji = "🟢" if action == "BUY" else "🔴"
    msg = (
        f"{emoji} <b>ArthAI {action}</b>\n"
        f"<b>Stock:</b> {symbol}\n"
        f"<b>Qty:</b> {qty} shares\n"
        f"<b>Price:</b> ₹{price:,.2f}\n"
        f"<b>SL:</b> ₹{sl:,.2f}\n"
        f"<b>Target:</b> ₹{target:,.2f}\n"
        f"<b>R:R</b> = 1:{abs((target-price)/(price-sl)):.1f}\n"
        f"<i>{rationale}</i>"
    )
    send_telegram(msg)


def alert_daily_summary(pnl: float, trades: int, winners: int) -> None:
    """Send end-of-day summary."""
    sign = "+" if pnl >= 0 else ""
    emoji = "📈" if pnl >= 0 else "📉"
    msg = (
        f"{emoji} <b>ArthAI Daily Summary</b>\n"
        f"P&L: <b>₹{sign}{pnl:,.2f}</b>\n"
        f"Trades: {trades} | Winners: {winners} | Win%: {winners/max(trades,1)*100:.0f}%"
    )
    send_telegram(msg)


def alert_risk_breach(reason: str) -> None:
    """Urgent risk alert."""
    msg = f"⚠️ <b>RISK BREACH</b>\n{reason}\n<b>All trading halted.</b>"
    send_telegram(msg)
    logger.warning(f"RISK BREACH: {reason}")
