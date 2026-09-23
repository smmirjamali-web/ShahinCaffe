from rest_framework import serializers
from .models import Order, OrderItem, Payment
from menu.models import MenuItem

class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    menu_item_image = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'menu_item', 'menu_item_name', 'menu_item_image', 
                  'quantity', 'price', 'total', 'notes']
    
    def get_menu_item_image(self, obj):
        if obj.menu_item.image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.menu_item.image.url) if request else obj.menu_item.image.url
        return None
    
    def get_total(self, obj):
        return obj.get_total()


class CreateOrderItemSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source='get_customer_name', read_only=True)
    user_phone = serializers.CharField(source='get_customer_phone', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'table', 'status', 'payment_status', 'total_amount', 
                  'discount', 'tax', 'user_name', 'user_phone', 'items', 
                  'notes', 'created_at', 'updated_at']


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user_name = serializers.CharField(source='get_customer_name', read_only=True)
    user_phone = serializers.CharField(source='get_customer_phone', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'table', 'user', 'guest_customer', 'status', 'payment_status',
                  'total_amount', 'discount', 'tax', 'user_name', 
                  'user_phone', 'items', 'notes', 'created_at', 'updated_at', 'served_at']


class CreateOrderSerializer(serializers.Serializer):
    table_id = serializers.IntegerField(required=False, allow_null=True)
    user_id = serializers.IntegerField(required=False, allow_null=True)
    guest_phone = serializers.CharField(required=False, allow_blank=True)
    guest_name = serializers.CharField(required=False, allow_blank=True)
    delivery_method = serializers.ChoiceField(choices=['pickup', 'delivery'], default='pickup')
    delivery_address = serializers.CharField(required=False, allow_blank=True)
    items = CreateOrderItemSerializer(many=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order', 'amount', 'method', 'transaction_id', 
                  'is_successful', 'error_message', 'created_at']