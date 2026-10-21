from django.contrib import admin

from .models import Department, Line, Plant, Station


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active", "is_internal"]
    list_filter = ["is_active", "is_internal"]
    search_fields = ["code", "name"]


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["code", "name"]


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "plant", "is_active"]
    list_filter = ["plant", "is_active"]
    search_fields = ["code", "name"]


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "line", "is_active"]
    list_filter = ["line__plant", "is_active"]
    search_fields = ["code", "name"]
