from django.contrib import admin
from .models import User, GlobalConfig

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'credit', 'is_superuser', 'is_active')
    search_fields = ('email', 'username')
    list_filter = ('is_superuser', 'is_active')
    ordering = ('email',)

@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = ('default_user_credit', 'updated_at')
