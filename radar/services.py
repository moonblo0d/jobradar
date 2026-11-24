"""Збір вакансій: запуск парсерів, оцінка, збереження без дублікатів, сповіщення."""
import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.utils import timezone

from . import notify
from .models import Source, Vacancy
from .scoring import score_vacancy
from .scrapers import djinni, telegram
from .scrapers.base import PoliteSession, ScrapedVacancy, parse_salary

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    found: int = 0
    created: int = 0
    updated: int = 0
    notified: int = 0
    errors: list[str] = field(default_factory=list)


def fetch_source(source: Source, session: PoliteSession) -> list[ScrapedVacancy]:
    if source.kind == Source.Kind.DJINNI:
        return djinni.fetch(source.target, session=session)
    if source.kind == Source.Kind.TELEGRAM:
        return telegram.fetch(source.target.lstrip("@"), session=session)
    raise ValueError(f"Невідомий тип джерела: {source.kind}")


def save_vacancies(source: Source, items: list[ScrapedVacancy], stats: RunStats) -> list[Vacancy]:
    """Оновлює існуючі вакансії й додає нові. Статус, який виставив користувач, не чіпаємо."""
    created = []
    for item in items:
        salary_text, salary_uah = parse_salary(item.salary_text or item.text)
        result = score_vacancy(item.title, item.text, salary_uah, item.experience)
        fields = {
            "title": item.title,
            "company": item.company,
            "url": item.url,
            "salary_text": item.salary_text or salary_text,
            "salary_uah": salary_uah,
            "location": item.location,
            "experience": item.experience,
            "english": item.english,
            "text": item.text,
            "published_at": item.published_at,
            "applications": item.applications,
            "score": result.score,
            "tags": result.tags,
            "red_flags": result.red_flags,
        }
        vacancy, is_new = Vacancy.objects.update_or_create(
            source=source, external_id=item.external_id, defaults=fields,
        )
        if is_new:
            stats.created += 1
            created.append(vacancy)
        else:
            stats.updated += 1
    return created


def run(sources=None, notify_new: bool = True, min_score: int | None = None) -> RunStats:
    stats = RunStats()
    min_score = settings.NOTIFY_MIN_SCORE if min_score is None else min_score
    session = PoliteSession()
    for source in sources if sources is not None else Source.objects.filter(is_active=True):
        try:
            items = fetch_source(source, session)
            stats.found += len(items)
            new = save_vacancies(source, items, stats)
            source.last_error = ""
        except Exception as e:  # одне зламане джерело не повинно зупиняти інші
            log.exception("Помилка джерела %s", source)
            stats.errors.append(f"{source.name}: {e}")
            source.last_error = str(e)[:500]
            new = []
        source.last_run_at = timezone.now()
        source.save(update_fields=["last_run_at", "last_error"])

        if notify_new and notify.is_configured():
            for vacancy in sorted(new, key=lambda v: -v.score):
                if vacancy.score >= min_score and not vacancy.red_flags:
                    if notify.send_message(notify.format_vacancy(vacancy)):
                        vacancy.notified = True
                        vacancy.save(update_fields=["notified"])
                        stats.notified += 1
    return stats
