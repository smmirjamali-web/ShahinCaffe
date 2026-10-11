from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser
from orders.models import Order
from payments.models import PaymentTransaction
from payments.services import verify_payment


class PaymentAPITests(TestCase):
    """تست دسترسی کاربران به API پرداخت."""

    def setUp(self):
        self.client = APIClient()

        self.user_a = CustomUser.objects.create_user(
            phone_number='09120000021',
            password='UserPass123!',
        )

        self.user_b = CustomUser.objects.create_user(
            phone_number='09120000022',
            password='UserPass123!',
        )

        self.order_a = self.create_order(self.user_a)
        self.order_b = self.create_order(self.user_b)

        self.payment_a = self.create_payment(
            self.order_a,
            'AUTH-TEST-A',
        )

        self.payment_b = self.create_payment(
            self.order_b,
            'AUTH-TEST-B',
        )

    def create_order(self, user):
        """ساخت سفارش آزمایشی."""

        return Order.objects.create(
            user=user,
            delivery_method='delivery',
            delivery_address='Test Street',
            total_amount=Decimal('50000'),
        )

    def create_payment(self, order, authority):
        """ساخت تراکنش آزمایشی."""

        return PaymentTransaction.objects.create(
            order=order,
            gateway='zarinpal',
            reference_id=authority,
            amount=Decimal('50000'),
            status='pending',
            customer_phone=order.user.phone_number,
            customer_email='',
        )

    def test_guest_cannot_list_transactions(self):
        response = self.client.get(
            reverse('transaction-list')
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_sees_only_own_transactions(self):
        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.get(
            reverse('transaction-list')
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            item['id']
            for item in response.data['results']
        }

        self.assertIn(self.payment_a.id, returned_ids)
        self.assertNotIn(self.payment_b.id, returned_ids)

    def test_user_cannot_retrieve_another_users_transaction(self):
        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.get(
            reverse(
                'transaction-detail',
                kwargs={'pk': self.payment_b.id},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_user_cannot_initiate_payment_for_another_users_order(self):
        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.post(
            reverse('transaction-initiate'),
            {
                'order_id': self.order_b.id,
                'gateway': 'zarinpal',
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_paid_order_cannot_start_another_payment(self):
        self.client.force_authenticate(
            user=self.user_a
        )

        self.order_a.payment_status = 'paid'
        self.order_a.save(
            update_fields=['payment_status']
        )

        response = self.client.post(
            reverse('transaction-initiate'),
            {
                'order_id': self.order_a.id,
                'gateway': 'zarinpal',
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_callback_with_unknown_authority_is_rejected(self):
        response = self.client.get(
            reverse('transaction-callback'),
            {
                'Authority': 'UNKNOWN-AUTHORITY',
                'Status': 'OK',
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class VerifyPaymentServiceTests(TestCase):
    """تست تأیید پرداخت بدون تماس با درگاه واقعی."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='09120000023',
            password='UserPass123!',
        )

        self.order = Order.objects.create(
            user=self.user,
            delivery_method='delivery',
            delivery_address='Test Street',
            total_amount=Decimal('50000'),
        )

        self.payment = PaymentTransaction.objects.create(
            order=self.order,
            gateway='zarinpal',
            reference_id='AUTH-VERIFY-TEST',
            amount=Decimal('50000'),
            status='pending',
            customer_phone=self.user.phone_number,
            customer_email='',
        )

    @patch('payments.services.ZarinpalGateway.verify_payment')
    def test_verification_uses_amount_from_database(
        self,
        mock_verify,
    ):
        mock_verify.return_value = {
            'success': True,
            'ref_id': 'REF-12345',
            'card_hash': 'TEST-HASH',
        }

        # عمداً مبلغ نادرست می‌فرستیم.
        # سرویس باید مبلغ ذخیره‌شده را به درگاه بدهد.
        result = verify_payment(
            'AUTH-VERIFY-TEST',
            amount=1,
        )

        self.assertTrue(result['success'])

        mock_verify.assert_called_once_with(
            'AUTH-VERIFY-TEST',
            50000,
        )

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            'success',
        )

        self.assertEqual(
            self.order.payment_status,
            'paid',
        )

    @patch('payments.services.ZarinpalGateway.verify_payment')
    def test_successful_payment_is_not_verified_twice(
        self,
        mock_verify,
    ):
        mock_verify.return_value = {
            'success': True,
            'ref_id': 'REF-12345',
            'card_hash': 'TEST-HASH',
        }

        first_result = verify_payment(
            'AUTH-VERIFY-TEST'
        )

        second_result = verify_payment(
            'AUTH-VERIFY-TEST'
        )

        self.assertTrue(first_result['success'])
        self.assertTrue(second_result['success'])
        self.assertFalse(first_result['already_verified'])
        self.assertTrue(second_result['already_verified'])

        mock_verify.assert_called_once_with(
            'AUTH-VERIFY-TEST',
            50000,
        )