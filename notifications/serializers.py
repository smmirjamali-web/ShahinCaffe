from rest_framework import serializers
from .models import Notification, NotificationTemplate

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'channel', 'title', 'message', 
                  'is_sent', 'sent_at', 'created_at']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ['id', 'notification_type', 'sms_template', 'email_subject', 
                  'email_template', 'description']