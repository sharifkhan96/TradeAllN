from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class TradeUserAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "is_staff", "date_joined"]
