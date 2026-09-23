from django.contrib import admin
from .models import Notification, NotificationTemplate

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['notification_type', 'channel', 'is_sent', 'sent_at', 'created_at']
    list_filter = ['notification_type', 'channel', 'is_sent', 'created_at']
    search_fields = ['order__id', 'user__phone_number', 'guest_customer__phone_number']
    readonly_fields = ['created_at', 'sent_at', 'last_attempt_at']


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['notification_type']
    search_fields = ['notification_type']
    readonly_fields = ['created_at', 'updated_at']