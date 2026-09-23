from rest_framework import serializers
from .models import PaymentGatewayConfig, PaymentTransaction

class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGatewayConfig
        fields = ['id', 'gateway_name', 'is_active']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = ['id', 'order', 'gateway', 'amount', 'status', 'reference_id', 
                  'created_at', 'verified_at']


class InitiatePaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    gateway = serializers.CharField(max_length=50)
    callback_url = serializers.URLField()