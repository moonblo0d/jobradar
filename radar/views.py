import threading
from collections import Counter
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .models import Source, Vacancy

SORTS = {
    "score": ["-score", "-published_at"],
    "date": ["-published_at", "-score"],
    "salary": ["-salary_uah", "-score"],
}
_scrape_lock = threading.Lock()


def dashboard(request):
    qs = Vacancy.objects.select_related("source")
    status = request.GET.get("status", "active")
    if status == "active":
        qs = qs.exclude(status=Vacancy.Status.HIDDEN)
    elif status in Vacancy.Status.values:
        qs = qs.filter(status=status)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(company__icontains=q) | Q(text__icontains=q))
    source_id = request.GET.get("source")
    if source_id and source_id.isdigit():
        qs = qs.filter(source_id=source_id)
    min_score = request.GET.get("min_score", "0")
    min_score = int(min_score) if min_score.isdigit() else 0
    if min_score:
        qs = qs.filter(score__gte=min_score)
    if request.GET.get("hide_flags", "1") == "1":
        qs = qs.filter(red_flags=[])
    sort = request.GET.get("sort", "score")
    qs = qs.order_by(*SORTS.get(sort, SORTS["score"]))

    page = Paginator(qs, 30).get_page(request.GET.get("page"))

    active = Vacancy.objects.exclude(status=Vacancy.Status.HIDDEN)
    since = timezone.now() - timedelta(days=1)
    tag_counter = Counter(
        t for tags in active.values_list("tags", flat=True) for t in tags if not t.startswith("Навички")
    )
    by_source = (
        Source.objects.annotate(n=Count("vacancies"), avg=Avg("vacancies__score")).order_by("-n")
    )
    max_n = max([s.n for s in by_source] + [1])
    stats = {
        "total": active.count(),
        "new_24h": active.filter(created_at__gte=since).count(),
        "strong": active.filter(score__gte=70).count(),
        "avg": round(active.aggregate(a=Avg("score"))["a"] or 0),
        "applied": Vacancy.objects.filter(status=Vacancy.Status.APPLIED).count(),
        "flagged": Vacancy.objects.exclude(red_flags=[]).count(),
    }
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "radar/dashboard.html", {
        "page": page,
        "stats": stats,
        "top_tags": tag_counter.most_common(8),
        "by_source": [(s, round(100 * s.n / max_n), round(s.avg or 0)) for s in by_source],
        "sources": Source.objects.all(),
        "statuses": Vacancy.Status.choices,
        "f": {"q": q, "source": source_id or "", "min_score": min_score, "status": status, "sort": sort,
              "hide_flags": request.GET.get("hide_flags", "1")},
        "query_string": params.urlencode(),
        "scraping": _scrape_lock.locked(),
    })


@require_POST
def set_status(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)
    status = request.POST.get("status")
    if status not in Vacancy.Status.values:
        return JsonResponse({"ok": False, "error": "Невідомий статус"}, status=400)
    vacancy.status = status
    vacancy.save(update_fields=["status", "updated_at"])
    return JsonResponse({"ok": True, "status": status, "label": vacancy.get_status_display()})


def _scrape_in_background():
    with _scrape_lock:
        services.run()


@require_POST
def start_scrape(request):
    if _scrape_lock.locked():
        messages.info(request, "Збір уже триває — оновіть сторінку за хвилину.")
    else:
        threading.Thread(target=_scrape_in_background, daemon=True).start()
        messages.success(request, "Збір вакансій запущено у фоні. Оновіть сторінку за 1–2 хвилини.")
    return redirect("dashboard")
