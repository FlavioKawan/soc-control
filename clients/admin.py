from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "legal_name", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "legal_name")
    autocomplete_fields = ("status",)
    readonly_fields = ("created_at", "updated_at")
