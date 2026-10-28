from django.contrib import admin

from .models import (
    ClientLogSource,
    ClientUseCase,
    ImplementationTemplate,
    LogSource,
    TemplateLogSource,
    TemplateUseCase,
    UseCase,
)


@admin.register(LogSource)
class LogSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "technology", "is_active")
    list_filter = ("category", "technology", "is_active")
    search_fields = ("name", "description")
    autocomplete_fields = ("category", "technology", "tags")


@admin.register(ClientLogSource)
class ClientLogSourceAdmin(admin.ModelAdmin):
    list_display = ("client", "log_source", "status", "last_event_at")
    list_filter = ("status",)
    search_fields = ("client__name", "log_source__name")
    autocomplete_fields = ("client", "log_source", "status")


@admin.register(UseCase)
class UseCaseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name", "description")
    autocomplete_fields = ("category", "tags", "framework_controls")


@admin.register(ClientUseCase)
class ClientUseCaseAdmin(admin.ModelAdmin):
    list_display = ("client", "use_case", "status", "criticality", "owner", "last_validated_at")
    list_filter = ("status", "criticality")
    search_fields = ("client__name", "use_case__code", "use_case__name")
    autocomplete_fields = ("client", "use_case", "status", "criticality", "owner")


class TemplateLogSourceInline(admin.TabularInline):
    model = TemplateLogSource
    extra = 1
    autocomplete_fields = ("log_source",)


class TemplateUseCaseInline(admin.TabularInline):
    model = TemplateUseCase
    extra = 1
    autocomplete_fields = ("use_case", "default_criticality")


@admin.register(ImplementationTemplate)
class ImplementationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    inlines = [TemplateLogSourceInline, TemplateUseCaseInline]
