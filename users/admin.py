# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, GuestCustomer

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['phone_number', 'get_full_name', 'email', 'total_orders', 'total_spent', 'is_active']
    list_filter = ['is_active', 'date_joined']
    search_fields = ['phone_number', 'first_name', 'last_name', 'email']
    readonly_fields = ['date_joined', 'last_login', 'total_orders', 'total_spent']
    
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email', 'date_of_birth')}),
        ('اطلاع‌رسانی', {'fields': ('notify_via_sms', 'notify_via_email')}),
        ('سفارشات', {'fields': ('total_orders', 'total_spent', 'loyalty_points')}),
        ('دسترسی', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('تاریخ', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


@admin.register(GuestCustomer)
class GuestCustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone_number', 'email', 'total_orders', 'total_spent']
    search_fields = ['name', 'phone_number']
    readonly_fields = ['created_at', 'total_orders', 'total_spent']
    
    fieldsets = (
        ('اطلاعات', {'fields': ('name', 'phone_number', 'email')}),
        ('آمار', {'fields': ('total_orders', 'total_spent')}),
        ('تاریخ', {'fields': ('created_at',)}),
    )