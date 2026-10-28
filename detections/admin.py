from django.contrib import admin

from .models import Rule, RuleColumnPreference


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ("internal_id", "name", "client", "technology", "severity", "status", "next_review_at")
    list_filter = ("client", "technology", "severity", "status", "rule_type")
    search_fields = ("internal_id", "vendor_rule_id", "name", "description")
    autocomplete_fields = (
        "client", "technology", "rule_type", "log_source", "severity", "status", "category",
        "use_cases", "framework_controls", "tags",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(RuleColumnPreference)
class RuleColumnPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "visible_columns")
    autocomplete_fields = ("user",)
    search_fields = ("user__username",)
