import logging
from datetime import timedelta

from django.db import IntegrityError, transaction as db_transaction
from django.utils import timezone

from .models import PaymentGatewayConfig, PaymentTransaction, PaymentReservationResolution
from .zarinpal_gateway import ZarinpalGateway
from orders.models import Order


logger = logging.getLogger(__name__)


def initiate_payment(
    order_id,
    gateway_name,
    callback_url,
    customer_email='',
    customer_phone='',
):
    """شروع امن فرآیند پرداخت سفارش."""

    if gateway_name != 'zarinpal':
        return {
            'success': False,
            'error': 'درگاه پرداخت پشتیبانی نشده است.',
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

    try:
        # ابتدا سفارش را قفل می‌کنیم تا درخواست‌های هم‌زمان
        # نتوانند هم‌زمان برای آن تراکنش بسازند.
        with db_transaction.atomic():
            order = Order.objects.select_for_update().get(
                id=order_id
            )

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

            if not customer_phone:
                customer_phone = order.get_customer_phone() or ''

            if not customer_phone:
                return {
                    'success': False,
                    'error': 'شماره تلفن مشتری مشخص نیست.',
                }

            pending_payment = (
                PaymentTransaction.objects
                .select_for_update()
                .filter(
                    order=order,
                    status='pending',
                )
                .first()
            )

            if pending_payment:
                # اگر شناسه درگاه وجود دارد، همان پرداخت را ادامه بده.
                # برای این سفارش درخواست پرداخت جدید نمی‌سازیم.
                if pending_payment.reference_id:
                    return {
                        'success': True,
                        'transaction_id': pending_payment.id,
                        'authority': pending_payment.reference_id,
                        'payment_url': (
                            'https://www.zarinpal.com/pg/StartPay/'
                            f'{pending_payment.reference_id}'
                        ),
                        'reused': True,
                    }

                # اگر هنوز شناسه درگاه نداریم، معلوم نیست درخواست قبلی
                # در سمت درگاه ثبت شده یا نه؛ بنابراین پرداخت دوم نساز.
                return {
                    'success': False,
                    'retryable': True,
                    'error': (
                        'نتیجه درخواست پرداخت قبلی هنوز مشخص نیست. '
                        'برای جلوگیری از پرداخت تکراری، درخواست جدید '
                        'ایجاد نشد و این تراکنش نیاز به بررسی دارد.'
                    ),
                }
            # پیش از تماس با درگاه، یک تراکنش رزرو می‌کنیم.
            # شناسه درگاه پس از دریافت پاسخ ثبت خواهد شد.
            payment_transaction = PaymentTransaction.objects.create(
                order=order,
                gateway=gateway_name,
                reference_id=None,
                amount=order.total_amount,
                status='pending',
                customer_phone=customer_phone,
                customer_email=customer_email,
            )

    except Order.DoesNotExist:
        return {
            'success': False,
            'error': 'سفارش یافت نشد.',
        }

    except IntegrityError:
        # محدودیت دیتابیس، آخرین لایه دفاع در برابر
        # ایجاد تراکنش معلق تکراری است.
        return {
            'success': False,
            'error': 'برای این سفارش یک پرداخت در حال انجام است.',
        }

    gateway = ZarinpalGateway(
        merchant_id=gateway_config.merchant_id,
    )

    try:
        # تماس شبکه خارج از transaction.atomic انجام می‌شود
        # تا قفل سفارش هنگام انتظار برای درگاه نگه داشته نشود.
        result = gateway.request_payment(
            payment_transaction.amount,
            order.id,
            customer_email,
            customer_phone,
            callback_url,
        )
    except Exception:
        # ممکن است درگاه درخواست را ثبت کرده باشد اما پاسخ به برنامه
        # نرسیده باشد؛ رزرو را pending نگه می‌داریم تا دوباره پرداخت
        # مستقل ساخته نشود. خطا نیز برای بررسی ثبت می‌شود.
        logger.exception(
            'Unexpected error while requesting payment for order %s.',
            order.id,
        )
        PaymentTransaction.objects.filter(
            pk=payment_transaction.pk,
            status='pending',
            reference_id__isnull=True,
        ).update(
            error_message=(
                'خطای داخلی هنگام ایجاد درخواست پرداخت؛ '
                'نتیجه درخواست باید بررسی شود.'
            ),
        )
        raise

    if not isinstance(result, dict):
        result = {
            'success': False,
            'retryable': True,
            'error': 'پاسخ دریافتی برای ایجاد درخواست پرداخت معتبر نیست.',
        }

    authority = result.get('authority')
    payment_url = result.get('payment_url')

    # پاسخ موفق بدون authority یا URL کامل نیست و نتیجه درخواست
    # را نباید با قطعیت ناموفق تلقی کرد.
    if result.get('success') and (not authority or not payment_url):
        result = {
            'success': False,
            'retryable': True,
            'error': 'پاسخ درگاه فاقد شناسه یا آدرس پرداخت است.',
        }

    if not result.get('success') or not authority or not payment_url:
        error_message = result.get(
            'error',
            'پاسخ معتبر برای ایجاد درخواست پرداخت دریافت نشد.',
        )

        if result.get('retryable', False):
            PaymentTransaction.objects.filter(
                pk=payment_transaction.pk,
                status='pending',
                reference_id__isnull=True,
            ).update(
                error_message=error_message,
            )
            return {
                'success': False,
                'retryable': True,
                'error': error_message,
            }

        PaymentTransaction.objects.filter(
            pk=payment_transaction.pk,
            status='pending',
            reference_id__isnull=True,
        ).update(
            status='failed',
            error_message=error_message,
        )

        return {
            'success': False,
            'error': error_message,
        }

    # شناسه دریافتی از درگاه را روی رکورد رزروشده ذخیره می‌کنیم.
    try:
        with db_transaction.atomic():
            payment_transaction = (
                PaymentTransaction.objects
                .select_for_update()
                .get(pk=payment_transaction.pk)
            )

            payment_transaction.reference_id = authority
            payment_transaction.save(
                update_fields=['reference_id']
            )

    except IntegrityError:
        # شناسه تکراری معمولاً به معنی پاسخ غیرعادی یا تعارض داده است.
        # رزرو را باز نگه می‌داریم تا سفارش دوباره پرداخت نشود و موضوع
        # به‌صورت دستی بررسی شود.
        PaymentTransaction.objects.filter(
            pk=payment_transaction.pk,
            status='pending',
            reference_id__isnull=True,
        ).update(
            error_message=(
                'شناسه دریافتی از درگاه تکراری است؛ '
                'نیاز به بررسی دستی دارد.'
            ),
        )

        logger.exception(
            'Duplicate gateway authority returned for order %s.',
            order.id,
        )

        return {
            'success': False,
            'error': (
                'ثبت شناسه پرداخت با تعارض مواجه شد؛ '
                'تراکنش نیاز به بررسی دارد.'
            ),
        }

    return {
        'success': True,
        'transaction_id': payment_transaction.id,
        'authority': authority,
        'payment_url': payment_url,
    }




def verify_payment(authority, amount=None):
    """
    تأیید پرداخت با مبلغ ذخیره‌شده در دیتابیس.

    درخواست HTTP بیرون از تراکنش دیتابیس اجرا می‌شود.
    """

    if not authority:
        return {
            'success': False,
            'error': 'شناسه پرداخت الزامی است.',
        }

    now = timezone.now()
    verification_timeout = timedelta(minutes=2)

    # مرحله اول: رزرو تلاش برای تأیید در یک تراکنش کوتاه.
    with db_transaction.atomic():
        try:
            payment_transaction = (
                PaymentTransaction.objects
                .select_for_update()
                .get(reference_id=authority)
            )
        except PaymentTransaction.DoesNotExist:
            return {
                'success': False,
                'error': 'تراکنش پرداخت یافت نشد.',
            }

        if payment_transaction.status == 'success':
            gateway_response = payment_transaction.gateway_response or {}

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

        # اگر تأیید دیگری هنوز در جریان است، درخواست موازی نفرست.
        started_at = payment_transaction.verification_started_at

        if (
            started_at is not None
            and started_at > now - verification_timeout
        ):
            return {
                'success': False,
                'retryable': True,
                'error': 'تأیید این پرداخت در حال انجام است.',
            }

        if payment_transaction.gateway != 'zarinpal':
            return {
                'success': False,
                'error': 'درگاه پرداخت پشتیبانی نشده است.',
            }

        gateway_config = PaymentGatewayConfig.objects.filter(
            gateway_name=payment_transaction.gateway,
        ).first()

        if gateway_config is None or not gateway_config.merchant_id:
            return {
                'success': False,
                'retryable': True,
                'error': 'تنظیمات درگاه برای تأیید تراکنش موجود نیست.',
            }

        # مبلغ فقط از دیتابیس خوانده می‌شود.
        trusted_amount = payment_transaction.amount
        payment_transaction.verification_started_at = now
        payment_transaction.save(
            update_fields=['verification_started_at']
        )

        verification_started_at = payment_transaction.verification_started_at
        payment_transaction_id = payment_transaction.id
        payment_order_id = payment_transaction.order_id
        merchant_id = gateway_config.merchant_id

    # مرحله دوم: تماس با درگاه بدون نگه‌داشتن قفل دیتابیس.
    try:
        gateway = ZarinpalGateway(merchant_id=merchant_id)

        result = gateway.verify_payment(
            authority,
            int(trusted_amount),
        )
    except Exception:
        # نتیجه تماس ممکن است نامشخص باشد؛ وضعیت پرداخت را قطعی
        # ناموفق نمی‌کنیم و جزئیات خطا را در لاگ نگه می‌داریم.
        logger.exception(
            'Unexpected error while verifying payment authority %s.',
            authority,
        )
        result = {
            'success': False,
            'retryable': True,
            'error': 'هنگام ارتباط با درگاه خطای غیرمنتظره‌ای رخ داد.',
        }

    if (
        not isinstance(result, dict)
        or not isinstance(result.get('success'), bool)
    ):
        result = {
            'success': False,
            'retryable': True,
            'error': 'ساختار پاسخ تأیید درگاه معتبر نیست.',
        }

    if result.get('success') and not result.get('ref_id'):
        result = {
            'success': False,
            'retryable': True,
            'error': 'کد رهگیری تأیید درگاه دریافت نشد.',
        }

    # مرحله سوم: ثبت نتیجه در یک تراکنش کوتاه دیگر.
    with db_transaction.atomic():
        try:
            # ترتیب قفل‌ها باید با initiate_payment یکسان باشد:
            # ابتدا سفارش، سپس تراکنش پرداخت.
            order = Order.objects.select_for_update().get(
                pk=payment_order_id
            )

            payment_transaction = (
                PaymentTransaction.objects
                .select_for_update()
                .get(pk=payment_transaction_id)
            )

        except (Order.DoesNotExist, PaymentTransaction.DoesNotExist):
            return {
                'success': False,
                'error': 'سفارش یا تراکنش پرداخت یافت نشد.',
            }

        if payment_transaction.status == 'success':
            gateway_response = payment_transaction.gateway_response or {}

            return {
                'success': True,
                'ref_id': gateway_response.get('ref_id'),
                'order_id': payment_transaction.order_id,
                'already_verified': True,
            }

        if payment_transaction.status != 'pending':
            return {
                'success': False,
                'error': 'وضعیت تراکنش در حین تأیید تغییر کرده است.',
            }

        # اگر یک تلاش جدید مالک رزرو شده باشد، نتیجه تلاش قدیمی
        # نباید وضعیت تراکنش را تغییر دهد.
        if (
            payment_transaction.verification_started_at
            != verification_started_at
        ):
            return {
                'success': False,
                'retryable': True,
                'error': 'تلاش تأیید دیگری جایگزین این درخواست شده است.',
            }

        if not result.get('success'):
            error_message = result.get(
                'error',
                'تأیید پرداخت ناموفق بود.',
            )

            payment_transaction.error_message = error_message
            payment_transaction.verification_started_at = None

            if result.get('retryable', False):
                payment_transaction.save(
                    update_fields=[
                        'error_message',
                        'verification_started_at',
                    ]
                )

                return {
                    'success': False,
                    'retryable': True,
                    'error': error_message,
                }

            payment_transaction.status = 'failed'
            payment_transaction.save(
                update_fields=[
                    'status',
                    'error_message',
                    'verification_started_at',
                ]
            )

            return {
                'success': False,
                'retryable': False,
                'error': error_message,
            }

        # ثبت نتیجه موفق درگاه.
        payment_transaction.status = 'success'
        payment_transaction.verified_at = timezone.now()
        payment_transaction.verification_started_at = None
        payment_transaction.gateway_response = {
            'ref_id': result['ref_id'],
            'card_hash': result.get('card_hash', ''),
        }

        payment_transaction.save(
            update_fields=[
                'status',
                'verified_at',
                'verification_started_at',
                'gateway_response',
            ]
        )

        if order.payment_status != 'paid':
            order.payment_status = 'paid'
            order.save(
                update_fields=[
                    'payment_status',
                    'updated_at',
                ]
            )

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


def resolve_unreferenced_payment_reservation(
    transaction_id,
    resolved_by,
    reason,
    *,
    confirmed_not_registered=False,
):
    """
    آزادسازی کنترل‌شده رزرو پرداخت پس از بررسی دستی درگاه.

    فقط تراکنش معلقی قابل تعیین تکلیف است که:
    - هنوز شناسه درگاه ندارد.
    - نتیجه درخواست قبلی در دیتابیس ثبت شده است.
    - حداقل ۱۰ دقیقه از ایجاد آن گذشته است.
    - کاربر فعال و دارای دسترسی مدیریتی باشد.
    - عدم ثبت درخواست در درگاه به‌صورت دستی تأیید شده باشد.
    """

    reason = (reason or '').strip()

    if (
        not getattr(resolved_by, 'is_authenticated', False)
        or not getattr(resolved_by, 'is_active', False)
        or not (
            getattr(resolved_by, 'is_staff', False)
            or getattr(resolved_by, 'is_superuser', False)
        )
    ):
        return {
            'success': False,
            'error': 'فقط کاربر مدیریتی فعال مجاز به این عملیات است.',
        }

    if len(reason) < 20:
        return {
            'success': False,
            'error': 'شرح بررسی باید حداقل ۲۰ نویسه داشته باشد.',
        }

    if confirmed_not_registered is not True:
        return {
            'success': False,
            'error': (
                'ابتدا باید بررسی دستی درگاه و عدم ثبت درخواست '
                'تأیید شود.'
            ),
        }

    try:
        order_id = PaymentTransaction.objects.values_list(
            'order_id',
            flat=True,
        ).get(pk=transaction_id)
    except PaymentTransaction.DoesNotExist:
        return {
            'success': False,
            'error': 'تراکنش پرداخت یافت نشد.',
        }

    with db_transaction.atomic():
        # ترتیب قفل‌ها با منطق پرداخت هماهنگ است:
        # ابتدا سفارش، سپس تراکنش.
        try:
            order = Order.objects.select_for_update().get(
                pk=order_id,
            )

            payment = (
                PaymentTransaction.objects
                .select_for_update()
                .get(
                    pk=transaction_id,
                    order_id=order_id,
                )
            )
        except (
            Order.DoesNotExist,
            PaymentTransaction.DoesNotExist,
        ):
            return {
                'success': False,
                'error': 'سفارش یا تراکنش پرداخت یافت نشد.',
            }

        if payment.status != 'pending':
            return {
                'success': False,
                'error': 'تراکنش دیگر در وضعیت معلق نیست.',
            }

        if payment.reference_id:
            return {
                'success': False,
                'error': (
                    'این تراکنش شناسه درگاه دارد؛ '
                    'باید وضعیت آن از طریق درگاه بررسی شود.'
                ),
            }

        if order.payment_status != 'unpaid':
            return {
                'success': False,
                'error': (
                    'وضعیت پرداخت سفارش اجازه آزادسازی رزرو را نمی‌دهد.'
                ),
            }

        if PaymentTransaction.objects.filter(
            order_id=order.id,
            status='success',
        ).exists():
            return {
                'success': False,
                'error': (
                    'برای این سفارش سابقه پرداخت موفق وجود دارد؛ '
                    'بررسی دستی بیشتری لازم است.'
                ),
            }

        if (
            payment.created_at
            > timezone.now() - timedelta(minutes=10)
        ):
            return {
                'success': False,
                'error': (
                    'حداقل ۱۰ دقیقه از ایجاد رزرو نگذشته است.'
                ),
            }

        # اگر نتیجه درخواست قبلی اصلاً در دیتابیس ثبت نشده باشد،
        # ممکن است فرایند درخواست هنوز فعال یا متوقف‌شده باشد.
        if not payment.error_message.strip():
            return {
                'success': False,
                'error': (
                    'نتیجه درخواست قبلی ثبت نشده است؛ '
                    'این رزرو با این روش قابل آزادسازی نیست.'
                ),
            }

        # تعارض شناسه درگاه وضعیت ویژه‌ای است و به بررسی جداگانه نیاز دارد.
        if (
            'شناسه دریافتی از درگاه تکراری است'
            in payment.error_message
            or (
                isinstance(payment.gateway_response, dict)
                and payment.gateway_response.get(
                    'duplicate_authority'
                )
            )
        ):
            return {
                'success': False,
                'error': (
                    'تعارض شناسه درگاه وجود دارد؛ '
                    'این تراکنش به بررسی جداگانه نیاز دارد.'
                ),
            }

        if PaymentReservationResolution.objects.filter(
            transaction_id=payment.id,
        ).exists():
            return {
                'success': False,
                'error': 'برای این تراکنش سابقه تعیین تکلیف ثبت شده است.',
            }

        resolution = PaymentReservationResolution.objects.create(
            transaction=payment,
            resolved_by=resolved_by,
            reason=reason,
        )

        payment.status = 'failed'
        payment.error_message = (
            f'{payment.error_message.strip()}\n\n'
            'رزرو پس از بررسی دستی و تأیید عدم ثبت درخواست '
            'در درگاه، آزاد شد.'
        )
        payment.save(
            update_fields=['status', 'error_message'],
        )

        return {
            'success': True,
            'transaction_id': payment.id,
            'order_id': order.id,
            'resolution_id': resolution.id,
        }


def _send_payment_notification(order_id):
    """ارسال اعلان پرداخت پس از ثبت تراکنش."""

    from notifications.services import send_order_notification

    send_order_notification.delay(
        order_id,
        'payment_received',
    )