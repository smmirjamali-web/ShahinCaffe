from rest_framework import serializers
from .models import CustomUser, GuestCustomer

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'phone_number', 'email', 'total_orders', 
                  'total_spent', 'loyalty_points', 'notify_via_sms', 'notify_via_email']


class CustomUserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'phone_number', 'email', 'total_orders', 
                  'total_spent', 'loyalty_points', 'notify_via_sms', 'notify_via_email',
                  'is_active', 'created_at', 'updated_at']


class GuestCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestCustomer
        fields = ['id', 'name', 'phone_number', 'email', 'total_orders', 'total_spent']