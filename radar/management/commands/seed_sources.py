from django.core.management.base import BaseCommand

from radar.models import Source

DEFAULT_SOURCES = [
    ("Djinni · без досвіду, віддалено", Source.Kind.DJINNI,
     "https://djinni.co/jobs/?exp_level=no_exp&employment=remote"),
    ("Djinni · Python, без досвіду", Source.Kind.DJINNI,
     "https://djinni.co/jobs/?primary_keyword=Python&exp_level=no_exp"),
    ("Djinni · part-time", Source.Kind.DJINNI,
     "https://djinni.co/jobs/?employment=parttime&exp_level=no_exp"),
    ("BEE JOB: Віддалена робота", Source.Kind.TELEGRAM, "beejob1_ua"),
    ("Робота віддалено / фриланс", Source.Kind.TELEGRAM, "robota_Frilans"),
    ("IT Бро: Junior вакансії", Source.Kind.TELEGRAM, "junior_v_it"),
]


class Command(BaseCommand):
    help = "Додає стартовий набір джерел (Djinni + Telegram-канали)"

    def handle(self, *args, **opts):
        created = 0
        for name, kind, target in DEFAULT_SOURCES:
            _, is_new = Source.objects.get_or_create(kind=kind, target=target, defaults={"name": name})
            created += is_new
        self.stdout.write(self.style.SUCCESS(f"Додано джерел: {created}, усього: {Source.objects.count()}"))
