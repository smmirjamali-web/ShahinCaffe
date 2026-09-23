from django.contrib import admin
from .models import Order, OrderItem, Payment

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['created_at']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'table', 'status', 'payment_status', 'total_amount', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['id', 'table__table_number']
    readonly_fields = ['created_at', 'updated_at', 'served_at']
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('معلومات سفارش', {
            'fields': ('table', 'user', 'guest_customer', 'status', 'created_at', 'updated_at')
        }),
        ('مبالغ', {
            'fields': ('total_amount', 'discount', 'discount_code', 'tax')
        }),
        ('پرداخت', {
            'fields': ('payment_status', 'served_at')
        }),
        ('یادداشت', {
            'fields': ('notes',)
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'menu_item', 'quantity', 'price']
    list_filter = ['order__created_at']
    search_fields = ['order__id', 'menu_item__name']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'amount', 'method', 'is_successful', 'created_at']
    list_filter = ['method', 'is_successful', 'created_at']
    search_fields = ['order__id', 'transaction_id']
    readonly_fields = ['created_at', 'updated_at', 'transaction_id']