from django.db import models


class Source(models.Model):
    """Звідки беремо вакансії: Djinni (сторінка пошуку) або Telegram-канал."""

    class Kind(models.TextChoices):
        DJINNI = "djinni", "Djinni"
        TELEGRAM = "telegram", "Telegram-канал"

    name = models.CharField("Назва", max_length=100)
    kind = models.CharField("Тип", max_length=20, choices=Kind.choices)
    target = models.CharField(
        "URL або канал", max_length=300,
        help_text="Для Djinni — URL сторінки пошуку, для Telegram — username каналу без @",
    )
    is_active = models.BooleanField("Активне", default=True)
    last_run_at = models.DateTimeField("Останній запуск", null=True, blank=True)
    last_error = models.TextField("Остання помилка", blank=True)

    class Meta:
        verbose_name = "Джерело"
        verbose_name_plural = "Джерела"

    def __str__(self) -> str:
        return f"{self.name} ({self.get_kind_display()})"


class Vacancy(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Нова"
        FAVORITE = "favorite", "Обране"
        APPLIED = "applied", "Відгукнувся"
        HIDDEN = "hidden", "Приховано"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="vacancies")
    external_id = models.CharField(max_length=100)
    title = models.CharField("Посада", max_length=300)
    company = models.CharField("Компанія", max_length=200, blank=True)
    url = models.URLField("Посилання", max_length=500)
    salary_text = models.CharField("Зарплата", max_length=120, blank=True)
    salary_uah = models.PositiveIntegerField("Зарплата до, грн", null=True, blank=True)
    location = models.CharField("Локація", max_length=200, blank=True)
    experience = models.CharField("Досвід", max_length=100, blank=True)
    english = models.CharField("Англійська", max_length=60, blank=True)
    text = models.TextField("Опис", blank=True)
    published_at = models.DateTimeField("Опубліковано", null=True, blank=True)
    applications = models.PositiveIntegerField("Відгуків", null=True, blank=True)

    score = models.PositiveSmallIntegerField("Оцінка", default=0, db_index=True)
    tags = models.JSONField("Мітки", default=list, blank=True)
    red_flags = models.JSONField("Червоні прапорці", default=list, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Вакансія"
        verbose_name_plural = "Вакансії"
        ordering = ["-score", "-published_at"]
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], name="unique_vacancy_per_source"),
        ]

    def __str__(self) -> str:
        return self.title
