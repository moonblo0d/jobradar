from django.core.management.base import BaseCommand

from radar import notify, services
from radar.models import Source


class Command(BaseCommand):
    help = "Збирає вакансії з активних джерел, оцінює їх і надсилає найкращі в Telegram"

    def add_arguments(self, parser):
        parser.add_argument("--source", type=int, action="append", help="ID джерела (можна кілька)")
        parser.add_argument("--no-notify", action="store_true", help="Не надсилати сповіщення")
        parser.add_argument("--min-score", type=int, help="Мінімальна оцінка для сповіщення")

    def handle(self, *args, **opts):
        sources = Source.objects.filter(is_active=True)
        if opts["source"]:
            sources = sources.filter(id__in=opts["source"])
        if not sources.exists():
            self.stdout.write(self.style.WARNING("Немає активних джерел. Запустіть: python manage.py seed_sources"))
            return
        if not opts["no_notify"] and not notify.is_configured():
            self.stdout.write("Telegram не налаштовано (.env) — лише зберігаю вакансії.")

        stats = services.run(list(sources), notify_new=not opts["no_notify"], min_score=opts["min_score"])
        self.stdout.write(self.style.SUCCESS(
            f"Знайдено: {stats.found} · нових: {stats.created} · оновлено: {stats.updated} · "
            f"сповіщень: {stats.notified}"
        ))
        for err in stats.errors:
            self.stdout.write(self.style.ERROR(err))
