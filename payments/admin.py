from django.contrib import admin
from .models import PaymentGatewayConfig, PaymentTransaction

@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ['gateway_name', 'is_active']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['reference_id', 'order', 'amount', 'status', 'gateway', 'created_at']
    list_filter = ['status', 'gateway', 'created_at']
    search_fields = ['reference_id', 'order__id', 'customer_phone']
    readonly_fields = ['created_at', 'verified_at', 'gateway_response']