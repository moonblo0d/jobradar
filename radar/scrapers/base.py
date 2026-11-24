"""Спільне для парсерів: модель результату, HTTP-сесія з ввічливою паузою, розбір зарплати."""
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
from django.conf import settings


@dataclass
class ScrapedVacancy:
    external_id: str
    title: str
    url: str
    company: str = ""
    salary_text: str = ""
    location: str = ""
    experience: str = ""
    english: str = ""
    text: str = ""
    published_at: Optional[datetime] = None
    applications: Optional[int] = None
    extra: dict = field(default_factory=dict)


class PoliteSession:
    """requests.Session з власним User-Agent і паузою між запитами до одного сайту."""

    def __init__(self, delay: Optional[float] = None):
        self.delay = settings.SCRAPER_DELAY_SECONDS if delay is None else delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.SCRAPER_USER_AGENT,
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.6",
        })
        self._last = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self.session.get(url, timeout=20, **kwargs)
        self._last = time.monotonic()
        resp.raise_for_status()
        return resp


_NUM = r"\d[\d\s .,]*"
_SALARY_RE = re.compile(
    rf"(?:від|до|from|up to)?\s*\$?\s*({_NUM})(?:\s*[-–—]\s*\$?\s*({_NUM}))?\s*(\$|usd|доларів|долар|грн|₴|uah)",
    re.IGNORECASE,
)
_SALARY_PREFIX_RE = re.compile(rf"\$\s*({_NUM})(?:\s*[-–—]\s*\$?\s*({_NUM}))?")


def _to_int(raw: str) -> Optional[int]:
    digits = re.sub(r"[^\d]", "", raw or "")
    return int(digits) if digits else None


def parse_salary(text: str) -> tuple[str, Optional[int]]:
    """Шукає в тексті зарплату. Повертає (як написано, верхня межа в гривнях)."""
    if not text:
        return "", None
    m = _SALARY_RE.search(text)
    currency = None
    if m:
        low, high, currency = m.group(1), m.group(2), m.group(3).lower()
    else:
        m = _SALARY_PREFIX_RE.search(text)
        if not m:
            return "", None
        low, high, currency = m.group(1), m.group(2), "$"
    top = _to_int(high) or _to_int(low)
    if not top:
        return "", None
    is_usd = currency in ("$", "usd", "доларів", "долар")
    # Відсіюємо номери телефонів, роки тощо
    if is_usd and not 100 <= top <= 20_000:
        return "", None
    if not is_usd and not 3_000 <= top <= 500_000:
        return "", None
    uah = round(top * settings.USD_TO_UAH) if is_usd else top
    return m.group(0).strip(), uah
