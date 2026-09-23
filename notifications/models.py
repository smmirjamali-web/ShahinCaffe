from django.db import models
from django.conf import settings
from orders.models import Order
from users.models import GuestCustomer

class Notification(models.Model):
    """یادآوری‌ها برای مشتری‌ها"""
    NOTIFICATION_TYPE = [
        ('order_confirmed', 'سفارش تایید شده'),
        ('order_preparing', 'سفارش درحال تهیه'),
        ('order_ready', 'سفارش آماده'),
        ('order_served', 'سفارش تحویل داده شد'),
        ('payment_received', 'پرداخت دریافت شد'),
        ('order_cancelled', 'سفارش لغو شد'),
    ]
    
    NOTIFICATION_CHANNEL = [
        ('sms', 'پیامک'),
        ('email', 'ایمیل'),
        ('in_app', 'درون‌برنامه'),
    ]
    
    # نوع و کانال
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE,
                                        verbose_name="نوع یادآوری")
    channel = models.CharField(max_length=20, choices=NOTIFICATION_CHANNEL,
                              verbose_name="کانال")
    
    # ارسال کننده
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                            null=True, blank=True, related_name='notifications',
                            verbose_name="کاربر ثبت‌شده")
    guest_customer = models.ForeignKey(GuestCustomer, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='notifications',
                                      verbose_name="مشتری میهمان")
    
    # ارتباط با سفارش
    order = models.ForeignKey(Order, on_delete=models.CASCADE,
                             related_name='notifications', verbose_name="سفارش")
    
    # محتوا
    title = models.CharField(max_length=200, verbose_name="عنوان")
    message = models.TextField(verbose_name="متن یادآوری")
    
    # وضعیت ارسال
    is_sent = models.BooleanField(default=False, verbose_name="ارسال شده")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ارسال")
    
    # برای ناموفق‌های ارسال
    send_attempts = models.IntegerField(default=0, verbose_name="تعداد تلاش‌های ارسال")
    last_attempt_at = models.DateTimeField(null=True, blank=True, 
                                          verbose_name="آخرین تلاش")
    error_message = models.TextField(blank=True, verbose_name="پیام خطا")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "یادآوری"
        verbose_name_plural = "یادآوری‌ها"
        indexes = [
            models.Index(fields=['is_sent', 'created_at']),
            models.Index(fields=['order']),
        ]
    
    def __str__(self):
        if self.user:
            recipient = self.user.phone_number
        else:
            recipient = self.guest_customer.phone_number if self.guest_customer else "نامشخص"
        return f"{self.get_notification_type_display()} - {recipient}"
    
    def get_recipient(self):
        """دریافت شماره تلفن یا ایمیل مشتری"""
        if self.user:
            return self.user.phone_number if self.channel == 'sms' else self.user.email
        else:
            return self.guest_customer.phone_number if self.channel == 'sms' else None


class NotificationTemplate(models.Model):
    """قالب‌های متن یادآوری"""
    notification_type = models.CharField(max_length=30, unique=True,
                                        verbose_name="نوع یادآوری")
    
    sms_template = models.TextField(verbose_name="قالب پیامک")
    email_subject = models.CharField(max_length=200, verbose_name="عنوان ایمیل")
    email_template = models.TextField(verbose_name="قالب ایمیل")
    
    description = models.TextField(blank=True, 
                                  verbose_name="توضیح متغیرها (مثلا {order_id}, {customer_name})")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "قالب یادآوری"
        verbose_name_plural = "قالب‌های یادآوری"
    
    def __str__(self):
        return f"قالب {self.notification_type}"