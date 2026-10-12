from rest_framework import serializers

from .models import CustomUser, GuestCustomer


class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=True
    )

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'first_name',
            'last_name',
            'phone_number',
            'email',
            'password',
            'total_orders',
            'total_spent',
            'loyalty_points',
            'notify_via_sms',
            'notify_via_email',
        ]

        read_only_fields = [
            'id',
            'total_orders',
            'total_spent',
            'loyalty_points',
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')
        phone_number = validated_data.pop('phone_number')

        user = CustomUser.objects.create_user(
            phone_number,
            password=password,
            **validated_data
        )

        return user


class CustomUserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'first_name',
            'last_name',
            'phone_number',
            'email',
            'total_orders',
            'total_spent',
            'loyalty_points',
            'notify_via_sms',
            'notify_via_email',
            'is_active',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'phone_number',
            'total_orders',
            'total_spent',
            'loyalty_points',
            'is_active',
            'created_at',
            'updated_at',
        ]


class GuestCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestCustomer
        fields = [
            'id',
            'name',
            'phone_number',
            'email',
            'total_orders',
            'total_spent',
        ]

        read_only_fields = [
            'id',
            'total_orders',
            'total_spent',
        ]