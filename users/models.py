# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from .managers import CustomUserManager

class CustomUser(AbstractUser):
    """کاربر ثبت‌شده - برای تاریخچه سفارشات و اطلاع‌رسانی"""
    phone_number = models.CharField(max_length=11, unique=True, 
                                     verbose_name="شماره تلفن")
    date_of_birth = models.DateField(null=True, blank=True, 
                                      verbose_name="تاریخ تولد")
    
    total_orders = models.IntegerField(default=0, verbose_name="تعداد کل سفارشات")
    total_spent = models.DecimalField(max_digits=12, decimal_places=0, 
                                       default=0, verbose_name="کل مبلغ خرید")
    loyalty_points = models.IntegerField(default=0, verbose_name="امتیاز وفاداری")
    
    # تنظیمات اطلاع‌رسانی
    notify_via_sms = models.BooleanField(default=True, verbose_name="اطلاع رسانی پیامکی")
    notify_via_email = models.BooleanField(default=True, verbose_name="اطلاع رسانی ایمیل")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    
    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.phone_number}"


class GuestCustomer(models.Model):
    """مشتری میهمان (بدون اکاونت)"""
    phone_number = models.CharField(max_length=11, unique=True, 
                                     verbose_name="شماره تلفن")
    name = models.CharField(max_length=100, verbose_name="نام")
    email = models.EmailField(blank=True, verbose_name="ایمیل")
    
    total_orders = models.IntegerField(default=0, verbose_name="تعداد کل سفارشات")
    total_spent = models.DecimalField(max_digits=12, decimal_places=0, 
                                       default=0, verbose_name="کل مبلغ خرید")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "مشتری میهمان"
        verbose_name_plural = "مشتری‌های میهمان"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.phone_number}"