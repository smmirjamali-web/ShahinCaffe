from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import PaymentGatewayConfig, PaymentTransaction
from .serializers import (
    PaymentGatewayConfigSerializer,
    PaymentTransactionSerializer,
    InitiatePaymentSerializer,
)
from .services import initiate_payment, verify_payment

from orders.models import Order


@extend_schema(tags=['Payment Methods'])
class PaymentGatewayConfigViewSet(viewsets.ReadOnlyModelViewSet):
    """
    نمایش درگاه‌های پرداخت فعال.

    اطلاعات محرمانه درگاه در Serializer نمایش داده نمی‌شود.
    """

    queryset = PaymentGatewayConfig.objects.filter(
        is_active=True
    )

    serializer_class = PaymentGatewayConfigSerializer
    permission_classes = [AllowAny]


@extend_schema(tags=['Payments'])
class PaymentTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    مشاهده تراکنش‌های کاربر و مدیریت فرایند پرداخت.
    """

    queryset = (
        PaymentTransaction.objects
        .select_related(
            'order',
            'order__user',
            'order__guest_customer',
        )
        .all()
    )

    serializer_class = PaymentTransactionSerializer

    def get_permissions(self):
        """
        Callback باید بدون JWT قابل دسترسی باشد؛
        سایر عملیات نیازمند ورود هستند.
        """

        if self.action == 'callback':
            return [AllowAny()]

        return [IsAuthenticated()]

    def get_queryset(self):
        """
        مدیر همه تراکنش‌ها را می‌بیند.
        کاربر عادی فقط تراکنش‌های سفارش‌های خودش را می‌بیند.
        """

        queryset = super().get_queryset()

        if not self.request.user.is_authenticated:
            return queryset.none()

        if self.request.user.is_staff:
            return queryset

        return queryset.filter(
            order__user=self.request.user
        )

    @action(
        detail=False,
        methods=['post'],
    )
    def initiate(self, request):
        """
        شروع پرداخت سفارش متعلق به کاربر واردشده.
        """

        serializer = InitiatePaymentSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # کاربر عادی فقط برای سفارش خودش پرداخت را شروع می‌کند.
        if request.user.is_staff:
            order_queryset = Order.objects.all()
        else:
            order_queryset = Order.objects.filter(
                user=request.user
            )

        order = order_queryset.filter(
            id=data['order_id']
        ).first()

        if order is None:
            return Response(
                {
                    'success': False,
                    'error': 'سفارش یافت نشد یا اجازه دسترسی به آن را ندارید.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.payment_status == 'paid':
            return Response(
                {
                    'success': False,
                    'error': 'این سفارش قبلاً پرداخت شده است.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        gateway_config = PaymentGatewayConfig.objects.filter(
            gateway_name=data['gateway'],
            is_active=True,
        ).first()

        if gateway_config is None:
            return Response(
                {
                    'success': False,
                    'error': 'درگاه پرداخت فعال نیست.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # اطلاعات مشتری از سفارش ذخیره‌شده خوانده می‌شود.
        customer_phone = order.get_customer_phone() or ''

        if order.user:
            customer_email = order.user.email or ''
        elif order.guest_customer:
            customer_email = order.guest_customer.email or ''
        else:
            customer_email = ''

        # آدرس Callback از تنظیمات سرور گرفته می‌شود،
        # نه از URL دلخواهی که کلاینت ارسال کرده است.
        result = initiate_payment(
            order_id=order.id,
            gateway_name=data['gateway'],
            callback_url=gateway_config.callback_url,
            customer_email=customer_email,
            customer_phone=customer_phone,
        )

        if not result['success']:
            return Response(
                result,
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            result,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=['get', 'post'],
    )
    def callback(self, request):
        """
        دریافت نتیجه بازگشت از درگاه پرداخت.

        پس از دریافت Authority، نتیجه پرداخت مستقیماً
        با درگاه بررسی می‌شود.
        """

        if request.method == 'GET':
            callback_data = request.query_params
        else:
            callback_data = request.data

        authority = (
            callback_data.get('Authority')
            or callback_data.get('authority')
        )

        payment_status = (
            callback_data.get('Status')
            or callback_data.get('status')
        )

        if not authority:
            return Response(
                {
                    'success': False,
                    'error': 'شناسه پرداخت در درخواست وجود ندارد.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment_status != 'OK':
            return Response(
                {
                    'success': False,
                    'error': 'پرداخت توسط کاربر لغو شده یا موفق نبوده است.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # مبلغ از callback دریافت نمی‌شود.
        # سرویس مبلغ ذخیره‌شده در دیتابیس را استفاده می‌کند.
        result = verify_payment(authority)

        if not result['success']:
            return Response(
                result,
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            result,
            status=status.HTTP_200_OK,
        )