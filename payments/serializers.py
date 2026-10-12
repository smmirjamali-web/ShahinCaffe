from rest_framework import serializers

from .models import PaymentGatewayConfig, PaymentTransaction


class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGatewayConfig
        fields = [
            'id',
            'gateway_name',
            'is_active',
        ]

        read_only_fields = fields


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            'id',
            'order',
            'gateway',
            'amount',
            'status',
            'reference_id',
            'created_at',
            'verified_at',
        ]

        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(
        min_value=1
    )

    gateway = serializers.ChoiceField(
        choices=[
            'zarinpal',
            'starpay',
        ]
    )