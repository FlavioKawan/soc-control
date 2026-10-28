from django.contrib import admin

from .models import (
    Category,
    Framework,
    FrameworkControl,
    ResponsibleParty,
    RuleType,
    Severity,
    Status,
    Tag,
    Technology,
)


class ConfigurableOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    prepopulated_fields = {"code": ("name",)}


@admin.register(Technology)
class TechnologyAdmin(ConfigurableOptionAdmin):
    list_display = ConfigurableOptionAdmin.list_display + ("category",)
    autocomplete_fields = ("category",)


@admin.register(Status)
class StatusAdmin(ConfigurableOptionAdmin):
    list_display = ConfigurableOptionAdmin.list_display + ("category", "scope")
    list_filter = ConfigurableOptionAdmin.list_filter + ("category",)


@admin.register(Severity)
class SeverityAdmin(ConfigurableOptionAdmin):
    list_display = ConfigurableOptionAdmin.list_display + ("weight",)


@admin.register(Category)
class CategoryAdmin(ConfigurableOptionAdmin):
    list_display = ConfigurableOptionAdmin.list_display + ("applicable_to",)
    search_fields = ConfigurableOptionAdmin.search_fields


@admin.register(Tag)
class TagAdmin(ConfigurableOptionAdmin):
    pass


@admin.register(RuleType)
class RuleTypeAdmin(ConfigurableOptionAdmin):
    pass


@admin.register(ResponsibleParty)
class ResponsiblePartyAdmin(ConfigurableOptionAdmin):
    pass


class FrameworkControlInline(admin.TabularInline):
    model = FrameworkControl
    extra = 1
    fk_name = "framework"
    fields = ("code", "name", "parent", "is_active")
    autocomplete_fields = ("parent",)


@admin.register(Framework)
class FrameworkAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [FrameworkControlInline]


@admin.register(FrameworkControl)
class FrameworkControlAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "framework", "parent", "is_active")
    list_filter = ("framework", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("framework", "parent")
