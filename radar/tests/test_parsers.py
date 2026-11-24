from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from radar.scrapers import djinni, telegram
from radar.scrapers.base import parse_salary

DJINNI_HTML = """
<ul class="list-jobs">
  <li><div class="job-item py-2" id="job-item-101">
    <div class="card-link">
      <a class="job_item__header-link" href="/jobs/101-junior-python-developer/">
        <header>
          <h2 class="job-item__position">Junior Python Developer</h2>
          <div><span class="text-body-tertiary" title="Рівень зарплати">$$</span><span>до $900</span></div>
          <div><span class="fs-5 text-secondary fw-medium">Acme Bots</span></div>
        </header>
      </a>
      <div class="d-flex flex-column gap-1"><div class="fw-medium text-gray-800 d-flex">
        <span>Тільки віддалено</span>
        <span><span class="location-text">Україна</span></span>
        <span>Без досвіду</span>
        <span>Англійська - B1</span>
      </div></div>
      <div id="job-description-101"><span class="js-original-text"><p>Telegram-боти, Django, part-time.</p></span></div>
      <span title="18:30 24.11.2026">оновлено</span>
      <span>120 переглядів 12 відгуків</span>
    </div>
  </div></li>
  <li><div class="job-item" id="job-item-102">
    <div><a class="job_item__header-link" href="/jobs/102-video-editor/">
      <header><h2 class="job-item__position">Video Editor</h2></header></a></div>
  </div></li>
</ul>
"""

TELEGRAM_HTML = """
<div class="tgme_widget_message" data-post="testchan/501">
  <div class="tgme_widget_message_text">💼 Монтажер Reels (віддалено)<br>ЗП: від 20 000 – 30 000 грн<br>
  Шукаємо монтажера, графік гнучкий, можна без досвіду. Обов'язки: монтаж коротких відео.</div>
  <time datetime="2026-11-24T10:00:00+00:00"></time>
</div>
<div class="tgme_widget_message" data-post="testchan/502">
  <div class="tgme_widget_message_text">Друзі, підписуйтесь на наш новий канал з корисними порадами про карʼєру та резюме!</div>
  <time datetime="2026-11-24T11:00:00+00:00"></time>
</div>
"""


class DjinniParserTests(SimpleTestCase):
    def test_parses_full_item(self):
        items = djinni.parse_listing(DJINNI_HTML)
        self.assertEqual(len(items), 2)
        v = items[0]
        self.assertEqual(v.external_id, "101")
        self.assertEqual(v.title, "Junior Python Developer")
        self.assertEqual(v.url, "https://djinni.co/jobs/101-junior-python-developer/")
        self.assertEqual(v.company, "Acme Bots")
        self.assertEqual(v.salary_text, "до $900")
        self.assertIn("Тільки віддалено", v.location)
        self.assertEqual(v.english, "Англійська - B1")
        self.assertIn("Telegram-боти", v.text)
        self.assertEqual(v.applications, 12)
        self.assertEqual(v.published_at, datetime(2026, 11, 24, 18, 30, tzinfo=ZoneInfo("Europe/Kyiv")))

    def test_minimal_item_does_not_crash(self):
        v = djinni.parse_listing(DJINNI_HTML)[1]
        self.assertEqual(v.title, "Video Editor")
        self.assertEqual(v.salary_text, "")
        self.assertIsNone(v.published_at)

    def test_page_param(self):
        url = "https://djinni.co/jobs/?exp_level=no_exp"
        self.assertIn("page=3", djinni._with_page(url, 3))
        self.assertNotIn("page=", djinni._with_page(url, 1))


class TelegramParserTests(SimpleTestCase):
    def test_keeps_vacancies_skips_ads(self):
        items = telegram.parse_channel(TELEGRAM_HTML, "testchan")
        self.assertEqual(len(items), 1)
        v = items[0]
        self.assertEqual(v.external_id, "501")
        self.assertEqual(v.url, "https://t.me/testchan/501")
        self.assertEqual(v.title, "Монтажер Reels (віддалено)")
        self.assertIn("30 000", v.salary_text)

    def test_digest_header_is_skipped_in_title(self):
        html = ('<div class="tgme_widget_message" data-post="c/7"><div class="tgme_widget_message_text">'
                '⚡️ Актуальні вакансії<br>✨ Junior Support Engineer<br>Компанія: X | Віддалено | без досвіду | '
                'Fulltime, вимоги: англійська B1, оплата $500</div><time datetime="2026-11-24T10:00:00+00:00"></time></div>')
        self.assertEqual(telegram.parse_channel(html, "c")[0].title, "Junior Support Engineer")


class SalaryTests(SimpleTestCase):
    def test_uah_range(self):
        text, uah = parse_salary("ЗП: від 25 000 – 45 000 грн на місяць")
        self.assertEqual(uah, 45000)

    def test_usd_converted(self):
        with self.settings(USD_TO_UAH=40):
            _, uah = parse_salary("Оплата $500–800 на місяць")
        self.assertEqual(uah, 32000)

    def test_ignores_phone_numbers_and_years(self):
        self.assertEqual(parse_salary("Телефон 0501234567, досвід 2 роки"), ("", None))
