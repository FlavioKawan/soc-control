from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model_name", "object_repr", "client")
    list_filter = ("action", "app_label", "model_name", "client")
    search_fields = ("object_repr", "object_id")
    readonly_fields = (
        "timestamp", "user", "action", "app_label", "model_name",
        "object_id", "object_repr", "client", "changes",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
