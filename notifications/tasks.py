from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Notification
from .services import send_sms

@shared_task
def retry_failed_notifications():
    """تلاش دوباره برای ارسال اطلاع‌رسانی‌های ناموفق"""
    failed_notifications = Notification.objects.filter(
        is_sent=False,
        send_attempts__lt=3
    )
    
    for notification in failed_notifications:
        recipient = notification.get_recipient()
        if recipient:
            success = send_sms(recipient, notification.message)
            
            if success:
                notification.is_sent = True
                notification.sent_at = timezone.now()
            
            notification.send_attempts += 1
            notification.last_attempt_at = timezone.now()
            notification.save()