from rest_framework import serializers

from .models import Order, OrderItem, Payment


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(
        source='menu_item.name',
        read_only=True
    )

    menu_item_image = serializers.SerializerMethodField()

    total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem

        fields = [
            'id',
            'menu_item',
            'menu_item_name',
            'menu_item_image',
            'quantity',
            'price',
            'total',
            'notes',
        ]

        read_only_fields = [
            'id',
            'menu_item',
            'menu_item_name',
            'menu_item_image',
            'price',
            'total',
        ]

    def get_menu_item_image(self, obj):
        if obj.menu_item.image:
            request = self.context.get('request')

            if request:
                return request.build_absolute_uri(
                    obj.menu_item.image.url
                )

            return obj.menu_item.image.url

        return None

    def get_total(self, obj):
        return obj.get_total()


class CreateOrderItemSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(
        required=False,
        allow_blank=True
    )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True,
        read_only=True
    )

    user_name = serializers.CharField(
        source='get_customer_name',
        read_only=True
    )

    user_phone = serializers.CharField(
        source='get_customer_phone',
        read_only=True
    )

    class Meta:
        model = Order

        fields = [
            'id',
            'table',
            'status',
            'payment_status',
            'total_amount',
            'discount',
            'tax',
            'user_name',
            'user_phone',
            'items',
            'notes',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'table',
            'status',
            'payment_status',
            'total_amount',
            'discount',
            'tax',
            'user_name',
            'user_phone',
            'items',
            'created_at',
            'updated_at',
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True,
        read_only=True
    )

    user_name = serializers.CharField(
        source='get_customer_name',
        read_only=True
    )

    user_phone = serializers.CharField(
        source='get_customer_phone',
        read_only=True
    )

    class Meta:
        model = Order

        fields = [
            'id',
            'table',
            'user',
            'guest_customer',
            'status',
            'payment_status',
            'total_amount',
            'discount',
            'tax',
            'user_name',
            'user_phone',
            'items',
            'notes',
            'created_at',
            'updated_at',
            'served_at',
        ]

        read_only_fields = fields


class CreateOrderSerializer(serializers.Serializer):
    table_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1
    )

    guest_phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=11
    )

    guest_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100
    )

    delivery_method = serializers.ChoiceField(
        choices=['pickup', 'delivery'],
        default='pickup'
    )

    delivery_address = serializers.CharField(
        required=False,
        allow_blank=True
    )

    items = CreateOrderItemSerializer(
        many=True,
        allow_empty=False
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate(self, attrs):
        request = self.context.get('request')

        is_authenticated = (
            request
            and request.user
            and request.user.is_authenticated
        )

        delivery_method = attrs.get(
            'delivery_method',
            'pickup'
        )

        delivery_address = attrs.get(
            'delivery_address',
            ''
        )

        guest_phone = attrs.get(
            'guest_phone',
            ''
        )

        if delivery_method == 'delivery' and not delivery_address.strip():
            raise serializers.ValidationError({
                'delivery_address': 'برای سفارش ارسال‌شونده، آدرس الزامی است.'
            })

        if not is_authenticated and not guest_phone.strip():
            raise serializers.ValidationError({
                'guest_phone': 'برای سفارش مهمان، شماره تلفن الزامی است.'
            })

        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment

        fields = [
            'id',
            'order',
            'amount',
            'method',
            'transaction_id',
            'is_successful',
            'error_message',
            'created_at',
        ]

        read_only_fields = fields