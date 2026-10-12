import requests
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser
from orders.models import Order
from payments.models import (
    PaymentGatewayConfig,
    PaymentReservationResolution,
    PaymentTransaction,
)
from payments.services import (
    initiate_payment,
    resolve_unreferenced_payment_reservation,
    verify_payment,
)
from payments.zarinpal_gateway import ZarinpalGateway


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

class ZarinpalGatewayRequestTests(TestCase):
    """تست خطاهای مبهم هنگام درخواست پرداخت."""

    def setUp(self):
        self.gateway = ZarinpalGateway(
            merchant_id='test-merchant-id',
            api_url='https://example.com/api',
        )

    @patch('payments.zarinpal_gateway.requests.post')
    def test_request_timeout_is_retryable(self, mock_post):
        mock_post.side_effect = requests.Timeout(
            'Connection timed out'
        )

        result = self.gateway.request_payment(
            amount=50000,
            order_id=123,
            customer_email='',
            customer_phone='09120000000',
            callback_url='https://example.com/callback/',
        )

        self.assertFalse(result['success'])
        self.assertTrue(result['retryable'])

    @patch('payments.zarinpal_gateway.requests.post')
    def test_invalid_json_response_is_retryable(self, mock_post):
        mock_post.return_value.json.side_effect = ValueError(
            'Invalid JSON'
        )

        result = self.gateway.request_payment(
            amount=50000,
            order_id=123,
            customer_email='',
            customer_phone='09120000000',
            callback_url='https://example.com/callback/',
        )

        self.assertFalse(result['success'])
        self.assertTrue(result['retryable'])


class PaymentReservationResolutionTests(TestCase):
    """تست تعیین تکلیف کنترل‌شده رزروهای پرداخت."""

    def setUp(self):
        self.customer = CustomUser.objects.create_user(
            phone_number='09120000026',
            password='CustomerPass123!',
        )

        self.admin_user = CustomUser.objects.create_user(
            phone_number='09120000027',
            password='AdminPass123!',
            is_staff=True,
        )

        self.order = Order.objects.create(
            user=self.customer,
            delivery_method='delivery',
            delivery_address='Test Street',
            total_amount=Decimal('50000'),
        )

        self.payment = PaymentTransaction.objects.create(
            order=self.order,
            gateway='zarinpal',
            reference_id=None,
            amount=Decimal('50000'),
            status='pending',
            customer_phone=self.customer.phone_number,
            error_message=(
                'ارتباط با درگاه برقرار نشد؛ '
                'نتیجه درخواست نامشخص است.'
            ),
        )

        # ایجاد رزرو قدیمی برای تست شرط گذشت زمان.
        PaymentTransaction.objects.filter(
            pk=self.payment.pk,
        ).update(
            created_at=timezone.now() - timedelta(minutes=11),
        )

        self.reason = (
            'پنل پذیرنده بررسی شد و عدم ثبت درخواست '
            'برای این رزرو تأیید شد.'
        )

    def resolve(self, **overrides):
        params = {
            'transaction_id': self.payment.pk,
            'resolved_by': self.admin_user,
            'reason': self.reason,
            'confirmed_not_registered': True,
        }
        params.update(overrides)

        return resolve_unreferenced_payment_reservation(
            **params,
        )

    def test_admin_can_resolve_valid_old_reservation(self):
        result = self.resolve()

        self.assertTrue(result['success'])

        self.payment.refresh_from_db()

        self.assertEqual(self.payment.status, 'failed')

        resolution = PaymentReservationResolution.objects.get(
            transaction=self.payment,
        )

        self.assertEqual(
            resolution.resolved_by,
            self.admin_user,
        )
        self.assertEqual(resolution.reason, self.reason)

    def test_non_staff_user_cannot_resolve_reservation(self):
        result = self.resolve(
            resolved_by=self.customer,
        )

        self.assertFalse(result['success'])

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

        self.assertFalse(
            PaymentReservationResolution.objects.filter(
                transaction=self.payment,
            ).exists()
        )

    def test_recent_reservation_cannot_be_resolved(self):
        PaymentTransaction.objects.filter(
            pk=self.payment.pk,
        ).update(
            created_at=timezone.now(),
        )

        result = self.resolve()

        self.assertFalse(result['success'])

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_transaction_with_authority_cannot_be_resolved(self):
        self.payment.reference_id = 'AUTH-RESOLUTION-TEST'
        self.payment.save(update_fields=['reference_id'])

        result = self.resolve()

        self.assertFalse(result['success'])

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_paid_order_cannot_have_reservation_released(self):
        self.order.payment_status = 'paid'
        self.order.save(update_fields=['payment_status'])

        result = self.resolve()

        self.assertFalse(result['success'])

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_duplicate_authority_conflict_requires_separate_review(self):
        self.payment.error_message = (
            'شناسه دریافتی از درگاه تکراری است؛ '
            'نیاز به بررسی دستی دارد.'
        )
        self.payment.save(update_fields=['error_message'])

        result = self.resolve()

        self.assertFalse(result['success'])

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_resolution_requires_reason_and_explicit_confirmation(self):
        short_reason_result = self.resolve(reason='بررسی شد')

        self.assertFalse(short_reason_result['success'])

        unconfirmed_result = self.resolve(
            confirmed_not_registered=False,
        )

        self.assertFalse(unconfirmed_result['success'])

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

        self.assertFalse(
            PaymentReservationResolution.objects.filter(
                transaction=self.payment,
            ).exists()
        )


class PaymentReservationAdminTests(TestCase):
    """تست فرم مدیریتی تعیین تکلیف رزرو پرداخت."""

    def setUp(self):
        self.customer = CustomUser.objects.create_user(
            phone_number='09120000028',
            password='CustomerPass123!',
        )

        self.admin_user = CustomUser.objects.create_superuser(
            phone_number='09120000029',
            email='admin@example.com',
            password='AdminPass123!',
        )

        self.order = Order.objects.create(
            user=self.customer,
            delivery_method='delivery',
            delivery_address='Test Street',
            total_amount=Decimal('50000'),
        )

        self.payment = PaymentTransaction.objects.create(
            order=self.order,
            gateway='zarinpal',
            reference_id=None,
            amount=Decimal('50000'),
            status='pending',
            customer_phone=self.customer.phone_number,
            error_message='ارتباط با درگاه برقرار نشد.',
        )

        PaymentTransaction.objects.filter(
            pk=self.payment.pk,
        ).update(
            created_at=timezone.now() - timedelta(minutes=11),
        )

        self.resolve_url = reverse(
            'admin:payments_paymenttransaction_resolve_reservation',
            args=[self.payment.pk],
        )

        self.change_url = reverse(
            'admin:payments_paymenttransaction_change',
            args=[self.payment.pk],
        )

        self.client = Client()

    def test_anonymous_user_cannot_open_resolution_form(self):
        response = self.client.get(self.resolve_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse('admin:login'),
            response.url,
        )

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_admin_can_open_resolution_form(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(self.resolve_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'اطلاعات تراکنش')
        self.assertContains(
            response,
            'پنل رسمی پذیرنده',
        )

    def test_admin_post_records_resolution_and_redirects(self):
        self.client.force_login(self.admin_user)

        reason = (
            'پنل پذیرنده بررسی شد و عدم ثبت درخواست '
            'برای این رزرو تأیید شد.'
        )

        response = self.client.post(
            self.resolve_url,
            {
                'reason': reason,
                'confirmed_not_registered': 'on',
            },
        )

        self.assertRedirects(
            response,
            self.change_url,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            'failed',
        )

        resolution = PaymentReservationResolution.objects.get(
            transaction=self.payment,
        )

        self.assertEqual(
            resolution.resolved_by,
            self.admin_user,
        )
        self.assertEqual(resolution.reason, reason)

    def test_missing_confirmation_does_not_resolve_payment(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self.resolve_url,
            {
                'reason': (
                    'این شرح برای بررسی رزرو پرداخت '
                    'و ثبت گزارش مدیریتی است.'
                ),
            },
        )

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            'pending',
        )

        self.assertFalse(
            PaymentReservationResolution.objects.filter(
                transaction=self.payment,
            ).exists()
        )
