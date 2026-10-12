from django.db import transaction as db_transaction
from django.utils import timezone

from .models import PaymentTransaction, PaymentGatewayConfig
from .zarinpal_gateway import ZarinpalGateway
from orders.models import Order


def initiate_payment(
    order_id,
    gateway_name,
    callback_url,
    customer_email='',
    customer_phone='',
):
    """شروع فرآیند پرداخت سفارش."""

    try:
        order = Order.objects.get(id=order_id)

    except Order.DoesNotExist:
        return {
            'success': False,
            'error': 'سفارش یافت نشد.',
        }

    if order.payment_status == 'paid':
        return {
            'success': False,
            'error': 'این سفارش قبلاً پرداخت شده است.',
        }

    if order.total_amount <= 0:
        return {
            'success': False,
            'error': 'مبلغ سفارش برای پرداخت معتبر نیست.',
        }

    try:
        gateway_config = PaymentGatewayConfig.objects.get(
            gateway_name=gateway_name,
            is_active=True,
        )

    except PaymentGatewayConfig.DoesNotExist:
        return {
            'success': False,
            'error': 'درگاه پرداخت فعال نیست.',
        }

    if gateway_name != 'zarinpal':
        return {
            'success': False,
            'error': 'درگاه پرداخت پشتیبانی نشده است.',
        }

    gateway = ZarinpalGateway(
        merchant_id=gateway_config.merchant_id,
    )

    if not customer_phone:
        customer_phone = order.get_customer_phone() or ''

    if not customer_phone:
        return {
            'success': False,
            'error': 'شماره تلفن مشتری مشخص نیست.',
        }

    result = gateway.request_payment(
        order.total_amount,
        order.id,
        customer_email,
        customer_phone,
        callback_url,
    )

    if not result['success']:
        return {
            'success': False,
            'error': result.get(
                'error',
                'خطا در ایجاد درخواست پرداخت.',
            ),
        }

    payment_transaction = PaymentTransaction.objects.create(
        order=order,
        gateway=gateway_name,
        reference_id=result['authority'],
        amount=order.total_amount,
        status='pending',
        customer_phone=customer_phone,
        customer_email=customer_email,
    )

    return {
        'success': True,
        'transaction_id': payment_transaction.id,
        'authority': result['authority'],
        'payment_url': result['payment_url'],
    }


def verify_payment(authority, amount=None):
    """
    تأیید پرداخت با استفاده از مبلغ ذخیره‌شده در دیتابیس.

    مبلغ دریافتی از callback مبنای تأیید نیست.
    """

    if not authority:
        return {
            'success': False,
            'error': 'شناسه پرداخت الزامی است.',
        }

    with db_transaction.atomic():

        try:
            payment_transaction = (
                PaymentTransaction.objects
                .select_for_update()
                .select_related('order')
                .get(reference_id=authority)
            )

        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'error': 'تراکنش پرداخت یافت نشد.',
            }

        # اگر قبلاً تأیید شده، نتیجه موفق قبلی را برگردان.
        # این کار از پردازش مجدد callback موفق جلوگیری می‌کند.
        if payment_transaction.status == 'success':
            gateway_response = (
                payment_transaction.gateway_response or {}
            )

            return {
                'success': True,
                'ref_id': gateway_response.get('ref_id'),
                'order_id': payment_transaction.order_id,
                'already_verified': True,
            }

        if payment_transaction.status != 'pending':
            return {
                'success': False,
                'error': 'این تراکنش در وضعیت قابل تأیید نیست.',
            }

        if payment_transaction.gateway != 'zarinpal':
            return {
                'success': False,
                'error': 'درگاه پرداخت پشتیبانی نشده است.',
            }

        # مبلغ معتبر از رکورد ذخیره‌شده در دیتابیس گرفته می‌شود.
        trusted_amount = payment_transaction.amount

        gateway_config = PaymentGatewayConfig.objects.filter(
            gateway_name=payment_transaction.gateway,
        ).first()

        if gateway_config is None or not gateway_config.merchant_id:
            return {
                'success': False,
                'error': 'تنظیمات درگاه برای تأیید تراکنش موجود نیست.',
            }

        gateway = ZarinpalGateway(
            merchant_id=gateway_config.merchant_id,
        )

        result = gateway.verify_payment(
            authority,
            int(trusted_amount),
        )

        if not result['success']:
            payment_transaction.status = 'failed'
            payment_transaction.error_message = result.get(
                'error',
                'تأیید پرداخت ناموفق بود.',
            )

            payment_transaction.save(
                update_fields=[
                    'status',
                    'error_message',
                ]
            )

            return {
                'success': False,
                'error': payment_transaction.error_message,
            }

        # ثبت نتیجه موفق پرداخت
        payment_transaction.status = 'success'
        payment_transaction.verified_at = timezone.now()
        payment_transaction.gateway_response = {
            'ref_id': result['ref_id'],
            'card_hash': result.get('card_hash', ''),
        }

        payment_transaction.save(
            update_fields=[
                'status',
                'verified_at',
                'gateway_response',
            ]
        )

        # تغییر وضعیت سفارش تنها پس از تأیید درگاه
        order = payment_transaction.order

        if order.payment_status != 'paid':
            order.payment_status = 'paid'

            order.save(
                update_fields=[
                    'payment_status',
                    'updated_at',
                ]
            )

            # اعلان فقط پس از ثبت موفق تراکنش در دیتابیس ارسال شود.
            db_transaction.on_commit(
                lambda order_id=order.id: (
                    _send_payment_notification(order_id)
                )
            )

        return {
            'success': True,
            'ref_id': result['ref_id'],
            'order_id': order.id,
            'already_verified': False,
        }


def _send_payment_notification(order_id):
    """ارسال اعلان پرداخت پس از ثبت تراکنش."""

    from notifications.services import send_order_notification

    send_order_notification.delay(
        order_id,
        'payment_received',
    )