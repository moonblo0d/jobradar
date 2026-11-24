from django.contrib import admin

from .models import Source, Vacancy


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "target", "is_active", "last_run_at", "has_error")
    list_filter = ("kind", "is_active")
    list_editable = ("is_active",)

    @admin.display(boolean=True, description="Помилка")
    def has_error(self, obj):
        return bool(obj.last_error)


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "source", "score", "salary_text", "status", "published_at")
    list_filter = ("status", "source")
    search_fields = ("title", "company", "text")
    list_editable = ("status",)
    readonly_fields = ("created_at", "updated_at")
