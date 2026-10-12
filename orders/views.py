from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAdminUser,
    IsAuthenticated,
)
from rest_framework.response import Response

from .models import Order, OrderItem, Payment
from .serializers import (
    CreateOrderSerializer,
    OrderDetailSerializer,
    OrderSerializer,
    PaymentSerializer,
)

from menu.models import MenuItem, Table
from users.models import GuestCustomer
from users.permissions import IsOrderOwnerOrStaff

@extend_schema(tags=['Orders'])
class OrderViewSet(viewsets.ModelViewSet):
    queryset = (
        Order.objects
        .select_related(
            'user',
            'guest_customer',
            'table',
        )
        .prefetch_related(
            'items__menu_item'
        )
        .all()
    )

    serializer_class = OrderSerializer

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer

        if self.action == 'create':
            return CreateOrderSerializer

        return OrderSerializer

    def get_queryset(self):
        """
        staff همه سفارش‌ها را می‌بیند.
        کاربر عادی فقط سفارش‌های خودش را می‌بیند.
        """

        queryset = super().get_queryset()

        if self.request.user.is_staff:
            return queryset

        return queryset.filter(
            user=self.request.user
        )

    def get_permissions(self):
        """
        تعیین permission بر اساس نوع درخواست.
        """

        if self.action == 'create':
            return [AllowAny()]

        if self.action in [
            'update_status',
            'table_orders',
            'update',
            'partial_update',
            'destroy',
        ]:
            return [IsAdminUser()]

        if self.action == 'my_orders':
            return [IsAuthenticated()]

        return [
            IsAuthenticated(),
            IsOrderOwnerOrStaff(),
        ]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        ایجاد سفارش جدید.

        کاربر authenticated:
            سفارش به request.user متصل می‌شود.

        کاربر مهمان:
            GuestCustomer بر اساس شماره تلفن ایجاد/دریافت می‌شود.
        """

        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        table = None

        table_id = data.get('table_id')

        if table_id is not None:
            table = Table.objects.filter(
                id=table_id,
                is_active=True
            ).first()

            if table is None:
                return Response(
                    {
                        'error': 'میز موردنظر وجود ندارد یا غیرفعال است.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        delivery_method = data.get(
            'delivery_method',
            'pickup'
        )

        if (
            table is None
            and delivery_method != 'delivery'
        ):
            table, _ = Table.objects.get_or_create(
                table_number=0,
                defaults={
                    'qr_code': 'pickup-default',
                    'capacity': 0,
                }
            )

        user = None
        guest_customer = None

        if request.user.is_authenticated:
            user = request.user

        else:
            guest_phone = data['guest_phone'].strip()
            guest_name = data.get(
                'guest_name',
                ''
            ).strip() or 'میهمان'

            guest_customer, _ = (
                GuestCustomer.objects.get_or_create(
                    phone_number=guest_phone,
                    defaults={
                        'name': guest_name,
                    }
                )
            )

        order = Order.objects.create(
            table=table,
            user=user,
            guest_customer=guest_customer,
            notes=data.get('notes', ''),
            delivery_method=delivery_method,
            delivery_address=data.get(
                'delivery_address',
                ''
            ),
        )

        for item_data in data['items']:
            menu_item = (
                MenuItem.objects
                .filter(
                    id=item_data['menu_item_id'],
                    is_active=True,
                    is_available=True,
                )
                .first()
            )

            if menu_item is None:
                return Response(
                    {
                        'error': (
                            f"محصول با شناسه "
                            f"{item_data['menu_item_id']} "
                            f"وجود ندارد یا در دسترس نیست."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=item_data['quantity'],
                price=menu_item.price,
                notes=item_data.get(
                    'notes',
                    ''
                ),
            )

        order.calculate_total()

        response_serializer = OrderDetailSerializer(
            order,
            context={'request': request}
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    @transaction.atomic
    @action(
        detail=True,
        methods=['post']
    )
    def apply_discount(self, request, pk=None):
        """
        اعمال کد تخفیف روی سفارش.
        """

        from discounts.models import (
            DiscountCode,
            DiscountCodeUsage,
        )

        order = self.get_object()

        if order.payment_status == 'paid':
            return Response(
                {
                    'error': (
                        'برای سفارش پرداخت‌شده '
                        'امکان اعمال تخفیف وجود ندارد.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if order.discount_code_id is not None:
            return Response(
                {
                    'error': (
                        'قبلاً برای این سفارش '
                        'کد تخفیف اعمال شده است.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        code_str = request.data.get('code')

        if not code_str:
            return Response(
                {
                    'error': 'کد تخفیف الزامی است.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        discount_code = (
            DiscountCode.objects
            .select_for_update()
            .filter(code=code_str)
            .first()
        )

        if discount_code is None:
            return Response(
                {
                    'error': 'کد تخفیف معتبر نیست.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        is_valid, message = discount_code.is_valid()

        if not is_valid:
            return Response(
                {
                    'error': message
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        items_total = sum(
            item.get_total()
            for item in order.items.all()
        )

        if items_total < discount_code.min_order_amount:
            return Response(
                {
                    'error': (
                        f'حداقل مبلغ سفارش '
                        f'{discount_code.min_order_amount} '
                        f'تومان است.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # بررسی محدودیت استفاده برای مشتری
        usage_query = DiscountCodeUsage.objects.filter(
            discount_code=discount_code
        )

        if order.user:
            customer_usage_count = usage_query.filter(
                user=order.user
            ).count()

        else:
            customer_usage_count = usage_query.filter(
                guest_phone=order.guest_customer.phone_number
            ).count()

        if (
            discount_code.max_usage_per_customer
            and customer_usage_count
            >= discount_code.max_usage_per_customer
        ):
            return Response(
                {
                    'error': (
                        'این کد تخفیف قبلاً '
                        'به حداکثر میزان استفاده '
                        'برای این مشتری رسیده است.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        discount_amount = discount_code.calculate_discount(
            items_total
        )

        order.discount_code_id = discount_code.id
        order.discount = discount_amount

        order.calculate_total()

        DiscountCodeUsage.objects.create(
            discount_code=discount_code,
            user=order.user,
            guest_phone=(
                order.guest_customer.phone_number
                if order.guest_customer
                else ''
            ),
            order_id=order.id,
            discount_amount=discount_amount,
        )

        discount_code.current_usage += 1

        discount_code.save(
            update_fields=[
                'current_usage',
                'updated_at',
            ]
        )

        response_serializer = OrderDetailSerializer(
            order,
            context={'request': request}
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK
        )

    @action(
        detail=True,
        methods=['patch']
    )
    def update_status(self, request, pk=None):
        """
        تغییر وضعیت سفارش.
        فقط staff/admin مجاز است.
        """

        order = self.get_object()

        new_status = request.data.get(
            'status'
        )

        valid_statuses = dict(
            Order.STATUS_CHOICES
        )

        if new_status not in valid_statuses:
            return Response(
                {
                    'error': 'وضعیت سفارش نامعتبر است.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = order.status

        order.status = new_status

        if new_status == 'served':
            order.served_at = timezone.now()

        else:
            order.served_at = None

        order.save(
            update_fields=[
                'status',
                'served_at',
                'updated_at',
            ]
        )

        from notifications.services import (
            send_order_notification
        )

        send_order_notification.delay(
            order.id,
            new_status
        )

        return Response(
            {
                'message': (
                    'وضعیت سفارش با موفقیت تغییر یافت.'
                ),
                'old_status': old_status,
                'new_status': new_status,
            },
            status=status.HTTP_200_OK
        )

    @action(
        detail=False,
        methods=['get']
    )
    def table_orders(self, request):
        """
        دریافت سفارش‌های فعال یک میز.
        فقط staff/admin مجاز است.
        """

        table_id = request.query_params.get(
            'table_id'
        )

        if not table_id:
            return Response(
                {
                    'error': 'table_id الزامی است.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            table_id = int(table_id)

        except (TypeError, ValueError):
            return Response(
                {
                    'error': 'table_id نامعتبر است.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        orders = self.get_queryset().filter(
            table_id=table_id,
            status__in=[
                'pending',
                'confirmed',
                'preparing',
                'ready',
            ]
        )

        serializer = OrderSerializer(
            orders,
            many=True,
            context={'request': request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    @action(
        detail=False,
        methods=['get']
    )
    def my_orders(self, request):
        """
        تاریخچه سفارش‌های کاربر فعلی.

        دیگر از شماره تلفن ارسالی کاربر
        برای پیدا کردن سفارش‌ها استفاده نمی‌شود.
        """

        orders = (
            Order.objects
            .select_related(
                'user',
                'guest_customer',
                'table',
            )
            .prefetch_related(
                'items__menu_item'
            )
            .filter(
                user=request.user
            )
            .order_by('-created_at')
        )

        serializer = OrderSerializer(
            orders,
            many=True,
            context={'request': request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

@extend_schema(tags=['Management - Payments'])
class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    مشاهده پرداخت‌های ثبت‌شده.

    ایجاد و مدیریت Payment از این endpoint
    انجام نمی‌شود و فرآیند پرداخت در app payments
    مدیریت می‌شود.
    """

    queryset = (
        Payment.objects
        .select_related(
            'order__user',
            'order__guest_customer',
        )
        .all()
    )

    serializer_class = PaymentSerializer

    permission_classes = [
        IsAuthenticated,
    ]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()

        return super().get_queryset().filter(
            order__user=self.request.user
        )