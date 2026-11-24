"""Сповіщення в Telegram через Bot API (без зовнішніх бібліотек)."""
import logging
import time
from html import escape

import requests
from django.conf import settings

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/{method}"


def is_configured() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def format_vacancy(v) -> str:
    lines = [f"🎯 <b>{v.score}/100</b> · {escape(v.title)}"]
    meta = " · ".join(x for x in [v.company, v.salary_text, v.location] if x)
    if meta:
        lines.append(escape(meta))
    if v.tags:
        lines.append("✅ " + escape(", ".join(v.tags[:5])))
    lines.append(f"📍 {escape(v.source.name)}")
    lines.append(v.url)
    return "\n".join(lines)


def send_message(text: str) -> bool:
    if not is_configured():
        return False
    url = API.format(token=settings.TELEGRAM_BOT_TOKEN, method="sendMessage")
    payload = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    for _ in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=15)
        except requests.RequestException as e:
            log.warning("Telegram недоступний: %s", e)
            return False
        if resp.status_code == 429:  # flood control — чекаємо, скільки просить Telegram
            wait = resp.json().get("parameters", {}).get("retry_after", 5)
            if wait > 60:
                log.warning("Telegram просить зачекати %s с — пропускаю сповіщення", wait)
                return False
            time.sleep(wait + 1)
            continue
        if resp.ok:
            return True
        log.warning("Telegram відповів %s: %s", resp.status_code, resp.text[:200])
        return False
    return False
