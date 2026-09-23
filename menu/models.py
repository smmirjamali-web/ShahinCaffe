from django.db import models
from django.core.validators import MinValueValidator

class Category(models.Model):
    """دسته‌بندی اقلام منو"""
    name = models.CharField(max_length=100, verbose_name="نام دسته")
    slug = models.SlugField(unique=True, verbose_name="نام اختصاری")
    description = models.TextField(blank=True, verbose_name="توضیح")
    p_name = models.CharField(max_length=100, verbose_name="نام فارسی دسته", blank=True)
    icon = models.ImageField(upload_to='categories/', verbose_name="آیکون")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]
    
    def __str__(self):
        return self.name


class MenuItem(models.Model):
    """آیتم‌های منو (قهوه‌ها، نوشیدنی‌ها و...)"""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, 
                                  related_name='items', verbose_name="دسته")
    name = models.CharField(max_length=100, verbose_name="نام محصول")
    description = models.TextField(verbose_name="توضیح")
    price = models.DecimalField(max_digits=10, decimal_places=0, 
                                validators=[MinValueValidator(0)], 
                                verbose_name="قیمت (تومان)")
    image = models.ImageField(upload_to='menu_items/', verbose_name="تصویر")
    is_available = models.BooleanField(default=True, verbose_name="موجود")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    p_name = models.CharField(max_length=100, verbose_name="نام فارسی", blank=True)
    p_description = models.TextField(verbose_name="توضیح فارسی", blank=True)
    ingredients = models.TextField(verbose_name="مواد تشکیل‌دهنده", blank=True)
    p_ingredients = models.TextField(verbose_name="مواد تشکیل‌دهنده فارسی", blank=True)
    is_popular = models.BooleanField(default=False, verbose_name="محبوب")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = "آیتم منو"
        verbose_name_plural = "آیتم‌های منو"
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_available']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.price} تومان"


class Table(models.Model):
    """میز‌های کافه برای سفارش‌گیری"""
    table_number = models.IntegerField(unique=True, verbose_name="شماره میز")
    qr_code = models.CharField(max_length=500, unique=True, verbose_name="کد QR")
    capacity = models.IntegerField(verbose_name="ظرفیت نفری", default=4)
    location = models.CharField(max_length=100, blank=True, verbose_name="محل")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['table_number']
        verbose_name = "میز"
        verbose_name_plural = "میز‌ها"
        indexes = [
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"میز {self.table_number}"