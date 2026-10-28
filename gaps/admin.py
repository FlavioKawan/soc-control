from django.contrib import admin

from .models import Gap


@admin.register(Gap)
class GapAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "client", "status", "criticality", "responsible_party", "opened_at", "closed_at")
    list_filter = ("status", "criticality", "responsible_party")
    search_fields = ("code", "title", "description")
    autocomplete_fields = (
        "client", "criticality", "responsible_party", "status", "log_source", "use_case", "rule", "tags",
    )
    readonly_fields = ("created_at", "updated_at")
