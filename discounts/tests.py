from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

from discounts.models import DiscountCode, DiscountCodeUsage
from users.models import CustomUser


class DiscountCodeModelTests(TestCase):
    """تست محاسبه و اعتبار کد تخفیف."""

    def test_fixed_discount_does_not_exceed_order_amount(self):
        discount = DiscountCode(
            code='FIXED80',
            discount_type='fixed',
            discount_value=Decimal('80000'),
        )

        result = discount.calculate_discount(
            Decimal('50000')
        )

        self.assertEqual(result, 50000)

    def test_percentage_discount_respects_maximum_amount(self):
        discount = DiscountCode(
            code='PERCENT10',
            discount_type='percentage',
            discount_value=Decimal('10'),
            max_discount_amount=Decimal('3000'),
        )

        result = discount.calculate_discount(
            Decimal('50000')
        )

        self.assertEqual(result, 3000)

    def test_expired_discount_is_invalid(self):
        now = timezone.now()

        discount = DiscountCode(
            code='EXPIRED',
            discount_type='fixed',
            discount_value=Decimal('1000'),
            valid_from=now - timedelta(days=2),
            valid_until=now - timedelta(minutes=1),
        )

        is_valid, message = discount.is_valid()

        self.assertFalse(is_valid)
        self.assertEqual(message, 'کد تخفیف منقضی شده')

    def test_percentage_above_100_is_invalid(self):
        discount = DiscountCode(
            code='INVALID150',
            discount_type='percentage',
            discount_value=Decimal('150'),
            valid_from=timezone.now() - timedelta(minutes=1),
        )

        is_valid, message = discount.is_valid()

        self.assertFalse(is_valid)
        self.assertEqual(
            message,
            'درصد تخفیف نمی‌تواند بیشتر از ۱۰۰ باشد',
        )


class DiscountCodeAPITests(TestCase):
    """تست دسترسی APIهای تخفیف."""

    def setUp(self):
        self.client = APIClient()

        self.discount = DiscountCode.objects.create(
            code='WELCOME10',
            description='Test discount',
            discount_type='percentage',
            discount_value=Decimal('10'),
            max_discount_amount=Decimal('20000'),
            min_order_amount=Decimal('0'),
            max_usage_per_customer=1,
            max_total_usage=100,
            current_usage=0,
            is_active=True,
            valid_from=timezone.now() - timedelta(minutes=1),
        )

        self.user = CustomUser.objects.create_user(
            phone_number='09120000001',
            password='UserPass123!',
        )

        self.admin = CustomUser.objects.create_user(
            phone_number='09120000002',
            password='AdminPass123!',
        )

        self.admin.is_staff = True
        self.admin.save(update_fields=['is_staff'])

    def test_guest_can_validate_discount_code(self):
        response = self.client.post(
            reverse('discount-code-validate-code'),
            {
                'code': 'WELCOME10',
                'order_amount': 50000,
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(response.data['valid'])
        self.assertEqual(response.data['discount_amount'], 5000)
        self.assertEqual(response.data['final_amount'], 45000)

    def test_invalid_discount_code_is_rejected(self):
        response = self.client.post(
            reverse('discount-code-validate-code'),
            {
                'code': 'DOES-NOT-EXIST',
                'order_amount': 50000,
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertFalse(response.data['valid'])

    def test_guest_cannot_list_discount_codes(self):
        response = self.client.get(
            reverse('discount-code-list')
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_regular_user_cannot_list_discount_codes(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('discount-code-list')
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_list_discount_codes(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            reverse('discount-code-list')
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_guest_cannot_view_discount_usage(self):
        response = self.client.get(
            reverse('discount-usage-list')
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_regular_user_cannot_view_discount_usage(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('discount-usage-list')
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )