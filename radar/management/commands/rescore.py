from django.core.management.base import BaseCommand

from radar.models import Vacancy
from radar.scoring import score_vacancy


class Command(BaseCommand):
    help = "Переоцінює всі збережені вакансії (після зміни профілю чи правил оцінки)"

    def handle(self, *args, **opts):
        changed = 0
        for v in Vacancy.objects.all().iterator():
            r = score_vacancy(v.title, v.text, v.salary_uah, v.experience)
            if (v.score, v.tags, v.red_flags) != (r.score, r.tags, r.red_flags):
                v.score, v.tags, v.red_flags = r.score, r.tags, r.red_flags
                v.save(update_fields=["score", "tags", "red_flags", "updated_at"])
                changed += 1
        self.stdout.write(self.style.SUCCESS(f"Переоцінено: {changed} з {Vacancy.objects.count()}"))
