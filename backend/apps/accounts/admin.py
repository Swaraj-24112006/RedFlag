from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "first_name", "last_name", "role", "department", "employee_id", "is_staff"]
    list_filter = ["role", "department", "is_staff", "is_superuser", "is_active"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("KSPG Profile", {"fields": ("role", "department", "employee_id", "phone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("KSPG Profile", {"fields": ("role", "department", "employee_id", "phone")}),
    )
