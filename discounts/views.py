from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import DiscountCode, DiscountCodeUsage
from .serializers import (
    DiscountCodeSerializer,
    DiscountCodeDetailSerializer,
    DiscountCodeUsageSerializer,
)


@extend_schema(tags=['Discounts'])
class DiscountCodeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DiscountCode.objects.filter(
        is_active=True
    )

    serializer_class = DiscountCodeSerializer

    def get_queryset(self):
        """
        کاربر عمومی فقط برای validate_code
        به یک کد فعال دسترسی دارد.
        Admin می‌تواند همه کدها را ببیند.
        """

        if self.request.user.is_staff:
            return DiscountCode.objects.all().order_by(
                '-created_at'
            )

        return DiscountCode.objects.filter(
            is_active=True
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DiscountCodeDetailSerializer

        return DiscountCodeSerializer

    def get_permissions(self):
        """
        validate_code عمومی است.
        مشاهده کدهای تخفیف فقط برای Admin.
        """

        if self.action == 'validate_code':
            return [AllowAny()]

        return [IsAdminUser()]

    @action(
        detail=False,
        methods=['post']
    )
    def validate_code(self, request):
        """
        بررسی اولیه معتبر بودن کد تخفیف.
        """

        code_str = request.data.get('code')
        order_amount = request.data.get(
            'order_amount',
            0
        )

        if not code_str:
            return Response(
                {
                    'valid': False,
                    'error': 'کد تخفیف الزامی است.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order_amount = int(order_amount)

        except (TypeError, ValueError):
            return Response(
                {
                    'valid': False,
                    'error': 'مبلغ سفارش نامعتبر است.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order_amount < 0:
            return Response(
                {
                    'valid': False,
                    'error': 'مبلغ سفارش نمی‌تواند منفی باشد.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = (
            DiscountCode.objects
            .filter(code=code_str)
            .first()
        )

        if code is None:
            return Response(
                {
                    'valid': False,
                    'error': 'کد تخفیف معتبر نیست.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        is_valid, message = code.is_valid()

        if not is_valid:
            return Response(
                {
                    'valid': False,
                    'error': message,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order_amount < code.min_order_amount:
            return Response(
                {
                    'valid': False,
                    'error': (
                        f'حداقل مبلغ سفارش '
                        f'{code.min_order_amount} '
                        f'تومان است.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        discount_amount = code.calculate_discount(
            order_amount
        )

        final_amount = max(
            0,
            order_amount - discount_amount
        )

        return Response(
            {
                'valid': True,
                'code': code.code,
                'discount_type': code.discount_type,
                'discount_value': code.discount_value,
                'discount_amount': discount_amount,
                'final_amount': final_amount,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=['Management - Discounts'])
class DiscountCodeUsageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    سابقه استفاده از کدهای تخفیف.
    فقط Admin مجاز است.
    """

    queryset = (
        DiscountCodeUsage.objects
        .select_related(
            'discount_code',
            'user',
        )
        .all()
    )

    serializer_class = DiscountCodeUsageSerializer
    permission_classes = [IsAdminUser]