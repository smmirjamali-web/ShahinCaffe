from django.db import models
from django.conf import settings
from django.utils import timezone
from menu.models import MenuItem, Table
from users.models import GuestCustomer

class Order(models.Model):
    """سفارشات مشتری‌ها"""
    STATUS_CHOICES = [
        ('pending', 'درحال انتظار'),
        ('confirmed', 'تایید شده'),
        ('preparing', 'درحال تهیه'),
        ('ready', 'آماده'),
        ('served', 'تحویل داده شده'),
        ('cancelled', 'لغو شده'),
    ]
    
    PAYMENT_STATUS = [
        ('unpaid', 'پرداخت نشده'),
        ('paid', 'پرداخت شده'),
        ('refunded', 'بازگردانده شده'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                            null=True, blank=True, related_name='orders',
                            verbose_name="کاربر ثبت‌شده")
    guest_customer = models.ForeignKey(GuestCustomer, on_delete=models.SET_NULL, 
                                       null=True, blank=True, related_name='orders',
                                       verbose_name="مشتری میهمان")
    
    table = models.ForeignKey(Table, on_delete=models.SET_NULL,
                            null=True, blank=True,
                            related_name='orders', verbose_name="میز")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, 
                              default='pending', verbose_name="وضعیت")
    DELIVERY_METHOD = [('pickup', 'حضوری'),('delivery', 'تحویل درب منزل'),]

    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, 
                                       default='unpaid', verbose_name="وضعیت پرداخت")
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=0, 
                                        default=0, verbose_name="کل مبلغ")
    discount = models.DecimalField(max_digits=10, decimal_places=0, 
                                    default=0, verbose_name="تخفیف")
    
    # استفاده از integer به جای ForeignKey
    discount_code_id = models.IntegerField(null=True, blank=True, 
                                           verbose_name="کد تخفیف ID")
    
    tax = models.DecimalField(max_digits=10, decimal_places=0, 
                              default=0, verbose_name="مالیات")
    
    notes = models.TextField(blank=True, verbose_name="یادداشت")
    delivery_method = models.CharField(
        max_length=20, choices=DELIVERY_METHOD,
        default='pickup', verbose_name="روش تحویل"
    )
    delivery_address = models.TextField(blank=True, verbose_name="آدرس تحویل")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان سفارش")
    updated_at = models.DateTimeField(auto_now=True)
    served_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تحویل")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "سفارش"
        verbose_name_plural = "سفارشات"
        indexes = [
            models.Index(fields=['table', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"سفارش #{self.id} - میز {self.table.table_number}"
    
    def calculate_total(self):
        """محاسبه کل مبلغ سفارش"""
        items_total = sum(item.get_total() for item in self.items.all())
        self.total_amount = items_total - self.discount + self.tax
        self.save(update_fields=['total_amount'])
        return self.total_amount
    
    def get_customer_phone(self):
        """دریافت شماره تلفن مشتری برای اطلاع‌رسانی"""
        if self.user:
            return self.user.phone_number
        return self.guest_customer.phone_number if self.guest_customer else None
    
    def get_customer_name(self):
        """دریافت نام مشتری"""
        if self.user:
            return self.user.get_full_name()
        return self.guest_customer.name if self.guest_customer else "میهمان"


class OrderItem(models.Model):
    """آیتم‌های درون سفارش"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, 
                              related_name='items', verbose_name="سفارش")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, 
                                  verbose_name="محصول")
    quantity = models.PositiveIntegerField(default=1, verbose_name="تعداد")
    price = models.DecimalField(max_digits=10, decimal_places=0, 
                                verbose_name="قیمت واحد")
    notes = models.TextField(blank=True, verbose_name="یادداشت خاص")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"
    
    def __str__(self):
        return f"{self.menu_item.name} x{self.quantity}"
    
    def get_total(self):
        """محاسبه کل قیمت این آیتم"""
        return self.price * self.quantity


class Payment(models.Model):
    """پرداخت‌ها"""
    PAYMENT_METHOD = [
        ('card', 'کارت بانکی'),
        ('wallet', 'کیف پول'),
        ('cash', 'نقد'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, 
                                 related_name='payment', verbose_name="سفارش")
    amount = models.DecimalField(max_digits=10, decimal_places=0, 
                                 verbose_name="مبلغ")
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD, 
                              verbose_name="روش پرداخت")
    transaction_id = models.CharField(max_length=200, blank=True, 
                                       unique=True, verbose_name="شماره تراکنش")
    
    is_successful = models.BooleanField(default=False, verbose_name="موفق")
    error_message = models.TextField(blank=True, verbose_name="پیام خطا")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"پرداخت #{self.id} - {self.amount} تومان"