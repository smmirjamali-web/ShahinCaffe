from celery import shared_task
from .models import Notification, NotificationTemplate
from orders.models import Order
import requests
import json

@shared_task
def send_order_notification(order_id, notification_type):
    """ارسال اطلاع‌رسانی برای وضعیت سفارش"""
    try:
        order = Order.objects.get(id=order_id)
        
        # دریافت قالب
        try:
            template = NotificationTemplate.objects.get(notification_type=notification_type)
        except NotificationTemplate.DoesNotExist:
            return False
        
        # تعیین گیرنده
        customer_phone = order.get_customer_phone()
        customer_name = order.get_customer_name()
        
        if not customer_phone:
            return False
        
        # ایجاد اطلاع‌رسانی برای پیامک
        notification = Notification.objects.create(
            notification_type=notification_type,
            channel='sms',
            user=order.user,
            guest_customer=order.guest_customer,
            order=order,
            title=template.sms_template[:50],
            message=template.sms_template.format(
                order_id=order.id,
                customer_name=customer_name,
                table_number=order.table.table_number
            )
        )
        
        # ارسال پیامک (کاوه نگار)
        success = send_sms(customer_phone, notification.message)
        
        if success:
            notification.is_sent = True
            notification.send_attempts = 1
            from django.utils import timezone
            notification.sent_at = timezone.now()
        else:
            notification.send_attempts += 1
        
        notification.save()
        return success
        
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return False


def send_sms(phone_number, message):
    """ارسال پیامک از طریق کاوه نگار"""
    from django.conf import settings
    
    api_key = settings.KAVEH_NEGAR_API_KEY
    sender = settings.KAVEH_NEGAR_SENDER
    
    if not api_key or not sender:
        print("SMS credentials not configured")
        return False
    
    try:
        url = 'https://api.kavenegar.com/v1/{}/sms/send.json'.format(api_key)
        params = {
            'receptor': phone_number,
            'message': message,
            'sender': sender
        }
        
        response = requests.post(url, data=params, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"SMS Error: {str(e)}")
        return False