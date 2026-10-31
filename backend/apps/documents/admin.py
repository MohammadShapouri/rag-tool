from django.contrib import admin
from .models import Document

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'department', 'uploaded_by', 'status', 'created_at')
    list_filter = ('status', 'department__organization')
