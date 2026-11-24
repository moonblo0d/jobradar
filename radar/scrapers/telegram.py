"""Парсер публічних веб-превʼю Telegram-каналів (https://t.me/s/<channel>)."""
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup
from django.conf import settings

from .base import PoliteSession, ScrapedVacancy, parse_salary

# Пост вважаємо вакансією, якщо в ньому є хоча б один із маркерів
VACANCY_MARKERS = re.compile(
    r"вакансі|ваканси|шукаємо|шукаю|запрошуємо|ищем|требуется|зп|з/п|зарплат|оплата|ставка|обов.язки|вимоги|hiring|salary",
    re.IGNORECASE,
)
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")
# Загальні заголовки дайджестів — назвою вакансії не є, беремо наступний рядок
_GENERIC_HEADER = re.compile(
    r"^(#\S+\s*)*(актуальн\w*|нов\w*|гаряч\w*|топ)?\s*(вакансі\w*|ваканси\w*|підбірка\w*)\s*(дня|тижня)?[!:.]?$",
    re.IGNORECASE,
)


def _title_from(text: str) -> str:
    for line in text.splitlines():
        line = _EMOJI.sub("", line).strip(" •-—|*#✨")
        if len(line) >= 6 and not _GENERIC_HEADER.match(line):
            return line[:200]
    return text[:120]


def parse_channel(html: str, channel: str) -> list[ScrapedVacancy]:
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for msg in soup.select(".tgme_widget_message[data-post]"):
        body = msg.select_one(".tgme_widget_message_text")
        if not body:
            continue
        for br in body.find_all("br"):
            br.replace_with("\n")
        text = body.get_text().strip()
        if len(text) < 80 or not VACANCY_MARKERS.search(text):
            continue  # реклама, анонси, опитування тощо
        post_id = msg["data-post"].split("/")[-1]
        time_el = msg.select_one("time[datetime]")
        published_at = datetime.fromisoformat(time_el["datetime"]) if time_el else None
        salary_text, _ = parse_salary(text)
        result.append(ScrapedVacancy(
            external_id=post_id,
            title=_title_from(text),
            url=f"https://t.me/{channel}/{post_id}",
            company="",
            salary_text=salary_text,
            text=text[:4000],
            published_at=published_at,
        ))
    return result


def fetch(channel: str, session: PoliteSession | None = None, max_pages: int | None = None,
          max_age_days: int = 7) -> list[ScrapedVacancy]:
    """Гортає канал назад сторінками (параметр before), доки пости не стануть старшими за max_age_days."""
    session = session or PoliteSession()
    max_pages = max_pages or settings.SCRAPER_MAX_PAGES
    since = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    url = f"https://t.me/s/{channel}"
    result, before = [], None
    for _ in range(max_pages):
        html = session.get(url, params={"before": before} if before else None).text
        soup = BeautifulSoup(html, "html.parser")
        ids = [int(m["data-post"].split("/")[-1]) for m in soup.select(".tgme_widget_message[data-post]")]
        if not ids:
            break
        items = [v for v in parse_channel(html, channel) if not v.published_at or v.published_at >= since]
        result.extend(items)
        oldest = soup.select_one(".tgme_widget_message[data-post] time[datetime]")
        if oldest and datetime.fromisoformat(oldest["datetime"]) < since:
            break
        before = min(ids)
    return result
