from rest_framework import serializers
from .models import DiscountCode, DiscountCodeUsage

class DiscountCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscountCode
        fields = ['id', 'code', 'description', 'discount_type', 'discount_value',
                  'max_discount_amount', 'min_order_amount', 'is_active']


class DiscountCodeDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscountCode
        fields = ['id', 'code', 'description', 'discount_type', 'discount_value',
                  'max_discount_amount', 'min_order_amount', 'max_usage_per_customer',
                  'max_total_usage', 'current_usage', 'is_active', 'valid_from', 'valid_until']


class DiscountCodeUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscountCodeUsage
        fields = ['id', 'discount_code', 'user', 'guest_phone', 'order', 
                  'discount_amount', 'used_at']