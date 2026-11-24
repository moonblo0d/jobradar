from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from radar import services
from radar.models import Source, Vacancy
from radar.scoring import score_vacancy
from radar.scrapers.base import ScrapedVacancy


@override_settings(PROFILE_SKILLS=["python", "telegram"])
class ScoringTests(TestCase):
    def test_student_friendly_vacancy_scores_high(self):
        r = score_vacancy("Junior Python Developer", "Віддалено, part-time, можна без досвіду. Telegram-боти.", 45000)
        self.assertGreaterEqual(r.score, 90)
        self.assertIn("Part-time", r.tags)
        self.assertIn("Без досвіду", r.tags)
        self.assertEqual(r.red_flags, [])

    def test_calls_and_senior_lower_the_score(self):
        r = score_vacancy("Senior Sales", "Холодні дзвінки, досвід від 3 років, 5/2 з 9:00-18:00", None)
        self.assertLess(r.score, 20)
        self.assertIn("Дзвінки", r.tags)

    @override_settings(PROFILE_SKILLS=["бот", "ai"])
    def test_skills_match_whole_words_only(self):
        r = score_vacancy("Віддалена робота", "Trainee, email-розсилки", None)
        self.assertFalse(any(t.startswith("Навички") for t in r.tags))  # «робота», «trainee», «email» — не збіг
        r = score_vacancy("Розробник ботів", "AI-асистенти", None)
        self.assertIn("Навички: бот, ai", r.tags)

    def test_video_streaming_is_penalised(self):
        r = score_vacancy("Спеціаліст з комунікацій", "Участь у прямих відеоефірах, без досвіду, віддалено", None)
        self.assertIn("Відеоефіри / відеочат", r.tags)
        self.assertLess(r.score, 60)

    def test_scam_is_zeroed(self):
        r = score_vacancy("Оператор", "Потрібна передоплата за навчання, віддалено, без досвіду", 90000)
        self.assertEqual(r.score, 0)
        self.assertIn("Схоже на скам", r.red_flags)


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
class ServiceTests(TestCase):
    def setUp(self):
        self.source = Source.objects.create(name="Test", kind=Source.Kind.TELEGRAM, target="testchan")
        self.items = [
            ScrapedVacancy(external_id="1", title="Junior Python", url="https://t.me/testchan/1",
                           text="Віддалено, без досвіду, ЗП до 30 000 грн"),
            ScrapedVacancy(external_id="2", title="Монтажер", url="https://t.me/testchan/2", text="Part-time"),
        ]

    def test_run_creates_then_updates_without_duplicates(self):
        with patch.object(services, "fetch_source", return_value=self.items):
            first = services.run([self.source])
            Vacancy.objects.filter(external_id="1").update(status=Vacancy.Status.APPLIED)
            second = services.run([self.source])
        self.assertEqual((first.created, first.updated), (2, 0))
        self.assertEqual((second.created, second.updated), (0, 2))
        self.assertEqual(Vacancy.objects.count(), 2)
        # Статус, виставлений користувачем, не перезаписується при повторному зборі
        self.assertEqual(Vacancy.objects.get(external_id="1").status, Vacancy.Status.APPLIED)
        self.assertEqual(Vacancy.objects.get(external_id="1").salary_uah, 30000)

    def test_broken_source_is_reported_not_raised(self):
        with patch.object(services, "fetch_source", side_effect=RuntimeError("boom")):
            stats = services.run([self.source])
        self.assertEqual(stats.errors, ["Test: boom"])
        self.source.refresh_from_db()
        self.assertEqual(self.source.last_error, "boom")

    @override_settings(TELEGRAM_BOT_TOKEN="x", TELEGRAM_CHAT_ID="1", NOTIFY_MIN_SCORE=60)
    def test_only_strong_new_vacancies_are_notified(self):
        with patch.object(services, "fetch_source", return_value=self.items), \
             patch("radar.notify.send_message", return_value=True) as send:
            stats = services.run([self.source])
        self.assertEqual(stats.notified, send.call_count)
        notified = Vacancy.objects.filter(notified=True)
        self.assertTrue(all(v.score >= 60 for v in notified))


class DashboardTests(TestCase):
    def setUp(self):
        src = Source.objects.create(name="Djinni", kind=Source.Kind.DJINNI, target="https://djinni.co/jobs/")
        self.good = Vacancy.objects.create(source=src, external_id="a", title="Junior Python", url="https://x/a", score=85)
        Vacancy.objects.create(source=src, external_id="b", title="Скам", url="https://x/b", score=0,
                               red_flags=["Схоже на скам"])

    def test_dashboard_hides_flagged_by_default(self):
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "Junior Python")
        self.assertNotContains(resp, "https://x/b")

    def test_status_update(self):
        resp = self.client.post(reverse("set_status", args=[self.good.pk]), {"status": "favorite"})
        self.assertEqual(resp.json()["status"], "favorite")
        self.good.refresh_from_db()
        self.assertEqual(self.good.status, "favorite")

    def test_status_rejects_unknown_value(self):
        resp = self.client.post(reverse("set_status", args=[self.good.pk]), {"status": "deleted"})
        self.assertEqual(resp.status_code, 400)
