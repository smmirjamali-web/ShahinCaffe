from django.db import models
from orders.models import Order

class PaymentGatewayConfig(models.Model):
    """تنظیمات درگاه‌های پرداخت"""
    GATEWAY_CHOICES = [
        ('zarinpal', 'زرین‌پال'),
        ('starpay', 'ستارپی'),
    ]
    
    gateway_name = models.CharField(max_length=50, choices=GATEWAY_CHOICES,
                                   unique=True, verbose_name="نام درگاه")
    merchant_id = models.CharField(max_length=200, verbose_name="Merchant ID")
    api_key = models.CharField(max_length=200, verbose_name="API Key")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    
    callback_url = models.URLField(verbose_name="URL بازگشت")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "تنظیم درگاه پرداخت"
        verbose_name_plural = "تنظیمات درگاه‌های پرداخت"
    
    def __str__(self):
        return f"{self.get_gateway_name_display()} - {'فعال' if self.is_active else 'غیرفعال'}"


class PaymentTransaction(models.Model):
    """رکورد تراکنش‌های پرداخت"""
    STATUS_CHOICES = [
        ('pending', 'درحال انتظار'),
        ('success', 'موفق'),
        ('failed', 'ناموفق'),
        ('cancelled', 'لغو شده'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.PROTECT,
                             related_name='payment_transactions',
                             verbose_name="سفارش")
    
    gateway = models.CharField(max_length=50, verbose_name="درگاه پرداخت")
    reference_id = models.CharField(max_length=200, unique=True,
                                   verbose_name="شماره ارجاع درگاه")
    
    amount = models.DecimalField(max_digits=12, decimal_places=0,
                                verbose_name="مبلغ (تومان)")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                             default='pending', verbose_name="وضعیت")
    
    payment_method = models.CharField(max_length=50, blank=True,
                                     verbose_name="روش پرداخت")
    
    # جزئیات درگاه
    gateway_response = models.JSONField(blank=True, null=True,
                                       verbose_name="پاسخ درگاه")
    
    # معلومات درخواست
    customer_phone = models.CharField(max_length=11, verbose_name="شماره تلفن مشتری")
    customer_email = models.EmailField(blank=True, verbose_name="ایمیل مشتری")
    
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True,
                                      verbose_name="زمان تایید")
    
    error_message = models.TextField(blank=True, verbose_name="پیام خطا")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "تراکنش پرداخت"
        verbose_name_plural = "تراکنش‌های پرداخت"
        indexes = [
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"تراکنش {self.reference_id} - {self.amount} تومان"