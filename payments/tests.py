from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser
from orders.models import Order
from payments.models import (
    PaymentGatewayConfig,
    PaymentTransaction,
)
from payments.services import initiate_payment, verify_payment

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

    @patch('payments.views.verify_payment')
    def test_callback_verifies_gateway_even_when_status_is_nok(
        self,
        mock_verify,
    ):
        mock_verify.return_value = {
            'success': True,
            'ref_id': 'REF-CALLBACK-123',
            'order_id': self.order_a.id,
            'already_verified': False,
        }

        response = self.client.get(
            reverse('transaction-callback'),
            {
                'Authority': 'AUTH-TEST-A',
                'Status': 'NOK',
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        mock_verify.assert_called_once_with(
            'AUTH-TEST-A',
        )

class VerifyPaymentServiceTests(TestCase):
    """تست تأیید پرداخت بدون تماس با درگاه واقعی."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='09120000023',
            password='UserPass123!',
        )

        PaymentGatewayConfig.objects.create(
            gateway_name='zarinpal',
            merchant_id='test-merchant-id',
            api_key='test-api-key',
            callback_url=(
                'http://127.0.0.1:8000/'
                'api/payments/transactions/callback/'
            ),
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


class InitiatePaymentServiceTests(TestCase):
    """تست شروع پرداخت و جلوگیری از درخواست تکراری."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='09120000024',
            password='UserPass123!',
        )

        self.callback_url = (
            'https://example.com/api/payments/transactions/callback/'
        )

        PaymentGatewayConfig.objects.create(
            gateway_name='zarinpal',
            merchant_id='test-merchant-id',
            api_key='test-api-key',
            callback_url=self.callback_url,
        )

        self.order = Order.objects.create(
            user=self.user,
            delivery_method='delivery',
            delivery_address='Test Street',
            total_amount=Decimal('50000'),
        )

    @patch('payments.services.ZarinpalGateway.request_payment')
    def test_initiation_creates_pending_transaction(
        self,
        mock_request,
    ):
        mock_request.return_value = {
            'success': True,
            'authority': 'AUTH-START-TEST',
            'payment_url': (
                'https://www.zarinpal.com/pg/StartPay/'
                'AUTH-START-TEST'
            ),
        }

        result = initiate_payment(
            order_id=self.order.id,
            gateway_name='zarinpal',
            callback_url=self.callback_url,
            customer_email='',
            customer_phone=self.user.phone_number,
        )

        self.assertTrue(result['success'])

        payment = PaymentTransaction.objects.get(
            order=self.order,
        )

        self.assertEqual(payment.status, 'pending')
        self.assertEqual(
            payment.reference_id,
            'AUTH-START-TEST',
        )

        mock_request.assert_called_once()


    @patch('payments.services.ZarinpalGateway.request_payment')
    def test_second_initiation_reuses_existing_pending_payment(
        self,
        mock_request,
    ):
        mock_request.return_value = {
            'success': True,
            'authority': 'AUTH-SECOND-TEST',
            'payment_url': (
                'https://www.zarinpal.com/pg/StartPay/'
                'AUTH-SECOND-TEST'
            ),
        }

        first_result = initiate_payment(
            order_id=self.order.id,
            gateway_name='zarinpal',
            callback_url=self.callback_url,
            customer_email='',
            customer_phone=self.user.phone_number,
        )

        second_result = initiate_payment(
            order_id=self.order.id,
            gateway_name='zarinpal',
            callback_url=self.callback_url,
            customer_email='',
            customer_phone=self.user.phone_number,
        )

        self.assertTrue(first_result['success'])
        self.assertTrue(second_result['success'])
        self.assertTrue(second_result['reused'])

        self.assertEqual(
            second_result['authority'],
            first_result['authority'],
        )

        self.assertEqual(
            second_result['payment_url'],
            first_result['payment_url'],
        )

        self.assertEqual(
            PaymentTransaction.objects.filter(
                order=self.order,
                status='pending',
            ).count(),
            1,
        )

        mock_request.assert_called_once()

    @patch('payments.services.ZarinpalGateway.request_payment')
    def test_retryable_gateway_error_keeps_reservation_pending(
        self,
        mock_request,
    ):
        mock_request.return_value = {
            'success': False,
            'retryable': True,
            'error': 'ارتباط با درگاه برقرار نشد.',
        }

        first_result = initiate_payment(
            order_id=self.order.id,
            gateway_name='zarinpal',
            callback_url=self.callback_url,
            customer_email='',
            customer_phone=self.user.phone_number,
        )

        self.assertFalse(first_result['success'])
        self.assertTrue(first_result['retryable'])

        payment = PaymentTransaction.objects.get(
            order=self.order,
        )

        self.assertEqual(payment.status, 'pending')
        self.assertIsNone(payment.reference_id)

        second_result = initiate_payment(
            order_id=self.order.id,
            gateway_name='zarinpal',
            callback_url=self.callback_url,
            customer_email='',
            customer_phone=self.user.phone_number,
        )

        self.assertFalse(second_result['success'])
        mock_request.assert_called_once()

    @patch('payments.services.ZarinpalGateway.request_payment')
    def test_unexpected_gateway_exception_keeps_reservation_pending(
        self,
        mock_request,
    ):
        mock_request.side_effect = RuntimeError(
            'Unexpected gateway error'
        )

        with self.assertLogs('payments.services', level='ERROR') as captured_logs:
            with self.assertRaises(RuntimeError):
                initiate_payment(
                    order_id=self.order.id,
                    gateway_name='zarinpal',
                    callback_url=self.callback_url,
                    customer_email='',
                    customer_phone=self.user.phone_number,
                )

        self.assertTrue(
            any(
                'Unexpected error while requesting payment'
                in message
                for message in captured_logs.output
            )
        )

        payment = PaymentTransaction.objects.get(
            order=self.order,
        )

        self.assertEqual(payment.status, 'pending')
        self.assertIsNone(payment.reference_id)