"""Парсер сторінок пошуку Djinni (розділ /jobs/ дозволений у robots.txt)."""
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.conf import settings

from .base import PoliteSession, ScrapedVacancy

BASE_URL = "https://djinni.co"
KYIV = ZoneInfo("Europe/Kyiv")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_listing(html: str) -> list[ScrapedVacancy]:
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for item in soup.select("div.job-item[id^=job-item-]"):
        link = item.select_one("a.job_item__header-link")
        title_el = item.select_one(".job-item__position")
        if not link or not title_el:
            continue
        external_id = item["id"].removeprefix("job-item-")

        # Зарплата — текст поруч із посадою ("до $1000", "$1500-2000"); значки "$$" ігноруємо
        salary_text = ""
        for span in item.select("header span"):
            t = _clean(span.get_text())
            if re.search(r"\d", t) and "$" in t:
                salary_text = t
                break

        company_el = item.select_one("header .text-secondary.fw-medium")
        meta = [_clean(s.get_text()) for s in item.select("div.fw-medium.text-gray-800 > span")]
        experience = next((m for m in meta if "досвід" in m.lower() or "experience" in m.lower()), "")
        english = next((m for m in meta if m.lower().startswith(("англійська", "english"))), "")
        location = _clean(item.select_one(".location-text").get_text()) if item.select_one(".location-text") else ""
        remote = next((m for m in meta if "віддалено" in m.lower() or "remote" in m.lower()), "")
        if remote and remote not in location:
            location = f"{remote} · {location}" if location else remote

        desc_el = item.select_one(".js-original-text") or item.select_one("[id^=job-description]")
        text = _clean(desc_el.get_text(" ")) if desc_el else ""

        published_at = None
        for el in item.select("[title]"):
            m = re.fullmatch(r"(\d{2}):(\d{2}) (\d{2})\.(\d{2})\.(\d{4})", el["title"].strip())
            if m:
                hh, mm, dd, mo, yy = map(int, m.groups())
                published_at = datetime(yy, mo, dd, hh, mm, tzinfo=KYIV)
                break

        applications = None
        m = re.search(r"(\d+)\s+відгук", item.get_text(" "))
        if m:
            applications = int(m.group(1))

        result.append(ScrapedVacancy(
            external_id=external_id,
            title=_clean(title_el.get_text()),
            url=urljoin(BASE_URL, link["href"]),
            company=_clean(company_el.get_text()) if company_el else "",
            salary_text=salary_text,
            location=location,
            experience=experience,
            english=english,
            text=text[:4000],
            published_at=published_at,
            applications=applications,
        ))
    return result


def _with_page(url: str, page: int) -> str:
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query))
    if page > 1:
        query["page"] = str(page)
    else:
        query.pop("page", None)
    return urlunparse(parts._replace(query=urlencode(query)))


def fetch(search_url: str, session: PoliteSession | None = None, max_pages: int | None = None) -> list[ScrapedVacancy]:
    session = session or PoliteSession()
    max_pages = max_pages or settings.SCRAPER_MAX_PAGES
    seen, result = set(), []
    for page in range(1, max_pages + 1):
        items = parse_listing(session.get(_with_page(search_url, page)).text)
        fresh = [v for v in items if v.external_id not in seen]
        if not fresh:
            break
        seen.update(v.external_id for v in fresh)
        result.extend(fresh)
    return result
