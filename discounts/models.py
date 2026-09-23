from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

class DiscountCode(models.Model):
    """کدهای تخفیف"""
    DISCOUNT_TYPE = [
        ('percentage', 'درصد'),
        ('fixed', 'مبلغ ثابت'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name="کد تخفیف")
    description = models.TextField(blank=True, verbose_name="توضیح")
    
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE, 
                                     default='percentage', verbose_name="نوع تخفیف")
    discount_value = models.DecimalField(max_digits=5, decimal_places=2, 
                                         validators=[MinValueValidator(0)],
                                         verbose_name="مقدار تخفیف")
    
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=0, 
                                              null=True, blank=True,
                                              verbose_name="حداکثر تخفیف (تومان)")
    
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=0, 
                                           default=0,
                                           verbose_name="حداقل مبلغ سفارش")
    max_usage_per_customer = models.IntegerField(default=1, 
                                                 verbose_name="حداکثر استفاده برای هر مشتری")
    max_total_usage = models.IntegerField(null=True, blank=True,
                                          verbose_name="حداکثر کل استفاده")
    current_usage = models.IntegerField(default=0, verbose_name="استفاده‌های فعلی")
    
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    valid_from = models.DateTimeField(default=timezone.now, verbose_name="تاریخ شروع")
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ انقضا")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.discount_value} {self.get_discount_type_display()}"
    
    def is_valid(self):
        """بررسی معتبر بودن کد"""
        now = timezone.now()
        
        if not self.is_active:
            return False, "کد تخفیف غیرفعال است"
        if now < self.valid_from:
            return False, "کد تخفیف هنوز فعال نشده"
        if self.valid_until and now > self.valid_until:
            return False, "کد تخفیف منقضی شده"
        if self.max_total_usage and self.current_usage >= self.max_total_usage:
            return False, "کد تخفیف تمام شده"
        
        return True, ""
    
    def calculate_discount(self, order_amount):
        """محاسبه مقدار تخفیف"""
        if self.discount_type == 'percentage':
            discount = order_amount * (self.discount_value / 100)
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
            return int(discount)
        else:
            return int(self.discount_value)


class DiscountCodeUsage(models.Model):
    """ثبت استفاده از کدهای تخفیف"""
    discount_code = models.ForeignKey(DiscountCode, on_delete=models.CASCADE,
                                      related_name='usage_records',
                                      verbose_name="کد تخفیف")
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                            null=True, blank=True, verbose_name="کاربر")
    guest_phone = models.CharField(max_length=11, blank=True, 
                                   verbose_name="شماره تلفن میهمان")
    
    # استفاده از string reference به جای ForeignKey
    order_id = models.IntegerField(null=True, blank=True, verbose_name="شماره سفارش")
    
    discount_amount = models.DecimalField(max_digits=10, decimal_places=0,
                                         verbose_name="مقدار تخفیف")
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "ثبت استفاده کد تخفیف"
        verbose_name_plural = "ثبت استفاده کدهای تخفیف"
        ordering = ['-used_at']
    
    def __str__(self):
        customer = self.user.phone_number if self.user else self.guest_phone
        return f"{self.discount_code.code} - {customer}"