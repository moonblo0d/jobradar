"""Оцінка вакансії 0–100 під профіль кандидата: студент, вечір/part-time, без великого досвіду.

Правила прості й прозорі: кожне дає бали та людську мітку, тож у дашборді видно, ЧОМУ вакансія отримала свою оцінку.
"""
import re
from dataclasses import dataclass, field

from django.conf import settings

BASE_SCORE = 40


@dataclass
class Rule:
    label: str
    points: int
    pattern: re.Pattern


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


POSITIVE = [
    Rule("Віддалено", 10, _rx(r"віддален|дистанц|remote|удален")),
    Rule("Part-time", 15, _rx(r"part[- ]?time|неповн|часткова зайнят|півставки|подработ|підробіт")),
    Rule("Гнучкий графік", 10, _rx(r"гнучк\w* графік|вільний графік|гибк\w* график|flexible")),
    Rule("Вечір / ніч", 10, _rx(r"вечір|вечерн|вечірн|нічн\w* змін|ночн\w* смен|evening|night shift")),
    Rule("Без досвіду", 15, _rx(r"без досвіду|без опыта|no experience|trainee|стаж(ер|ист)|навчаємо|навчання з нуля")),
    Rule("Junior", 10, _rx(r"\bjunior\b|джуніор|молодш")),
    Rule("Студентам", 10, _rx(r"студент")),
    Rule("Оплачуване тестове", 5, _rx(r"оплачуван\w* тестов|paid test")),
]

NEGATIVE = [
    Rule("Дзвінки", -15, _rx(r"дзвінк|холодн\w* дзвін|звонк|колл?-?центр|call[- ]?cent")),
    Rule("Жорсткий 5/2 вдень", -10, _rx(r"5/2[^.\n]{0,25}(9|10)[:.]00\s*[-–—]\s*(18|19)[:.]00")),
    Rule("Досвід 2+ роки", -20, _rx(r"(досвід|experience|опыт)\D{0,15}(від|от|from)?\s*([2-9]|\d{2})\+?\s*(рок|рік|рр|years|лет|год)")),
    Rule("Senior / Lead", -25, _rx(r"\bsenior\b|\blead\b|\bсеньйор|тімлід|team ?lead|\bCTO\b")),
    Rule("Відеоефіри / відеочат", -30, _rx(r"прям\w* (відео)?ефір|відеоефір|відеочат|відеодзвінк\w* з іноземц")),
]

# Ознаки сірих або шахрайських пропозицій — оцінка падає до мінімуму
RED_FLAGS = [
    Rule("Схоже на скам", -100, _rx(r"передоплат|предоплат|внесок за навчання|дроп|обнал|ставки на спорт|казино")),
    Rule("18+ / вебкам", -100, _rx(r"onlyfans|онліфанс|вебкам|webcam|стримінгов\w* платформ\w* для дівчат")),
]


def skill_pattern(skill: str) -> re.Pattern:
    """Навичка шукається з початку слова: «бот» знайде «боти», але не «робота».
    Короткі латинські абревіатури («ai», «api») — лише як окреме слово."""
    escaped = re.escape(skill)
    whole_word = len(skill) <= 2 or (skill.isascii() and len(skill) <= 3)
    return _rx(rf"\b{escaped}\b" if whole_word else rf"\b{escaped}")


@dataclass
class ScoreResult:
    score: int
    tags: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)


def score_vacancy(title: str, text: str, salary_uah: int | None = None, experience: str = "") -> ScoreResult:
    haystack = f"{title}\n{experience}\n{text}"
    score = BASE_SCORE
    tags: list[str] = []
    red: list[str] = []

    for rule in POSITIVE + NEGATIVE:
        if rule.pattern.search(haystack):
            score += rule.points
            tags.append(rule.label)

    skills = [s for s in settings.PROFILE_SKILLS if skill_pattern(s).search(haystack)]
    if skills:
        score += min(len(skills) * 5, 15)
        tags.append("Навички: " + ", ".join(dict.fromkeys(skills[:4])))

    if salary_uah:
        if salary_uah >= 40_000:
            score += 10
            tags.append("ЗП від 40k")
        elif salary_uah >= 25_000:
            score += 5

    for rule in RED_FLAGS:
        if rule.pattern.search(haystack):
            red.append(rule.label)

    if red:
        score = 0
    return ScoreResult(score=max(0, min(100, score)), tags=tags, red_flags=red)
