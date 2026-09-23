from django.contrib import admin
from .models import DiscountCode, DiscountCodeUsage

@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'is_active', 
                    'current_usage', 'max_total_usage']
    list_filter = ['discount_type', 'is_active', 'created_at']
    search_fields = ['code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('اطلاعات کد', {
            'fields': ('code', 'description', 'is_active')
        }),
        ('نوع و مقدار تخفیف', {
            'fields': ('discount_type', 'discount_value', 'max_discount_amount')
        }),
        ('شرایط استفاده', {
            'fields': ('min_order_amount', 'max_usage_per_customer', 'max_total_usage', 'current_usage')
        }),
        ('تاریخ اعتبار', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('تاریخ', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(DiscountCodeUsage)
class DiscountCodeUsageAdmin(admin.ModelAdmin):
    list_display = ['discount_code', 'user', 'guest_phone', 'discount_amount', 'used_at']
    list_filter = ['discount_code', 'used_at']
    search_fields = ['user__phone_number', 'guest_phone', 'discount_code__code']
    readonly_fields = ['used_at']