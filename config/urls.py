from django.contrib import admin
from django.urls import path

from radar import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("vacancy/<int:pk>/status/", views.set_status, name="set_status"),
    path("scrape/", views.start_scrape, name="start_scrape"),
    path("admin/", admin.site.urls),
]
