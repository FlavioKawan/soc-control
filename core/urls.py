from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("", include("accounts.urls")),
    path("", include("taxonomy.urls")),
    path("", include("clients.urls")),
    path("", include("catalog.urls")),
    path("", include("detections.urls")),
    path("", include("gaps.urls")),
    path("", include("audit.urls")),
    path("", include("search.urls")),
    path("", include("reports.urls")),
]
