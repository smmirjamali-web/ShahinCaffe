"""درگاه پرداخت زرین‌پال."""

import requests
from django.conf import settings


class ZarinpalGateway:
    def __init__(self, merchant_id=None, api_url=None):
        self.merchant_id = (
            merchant_id or settings.ZARINPAL_MERCHANT_ID
        )

        self.api_url = (
            api_url or settings.ZARINPAL_API_URL
        ).rstrip('/')

        self.request_url = (
            f'{self.api_url}/payment/request.json'
        )

        self.verify_url = (
            f'{self.api_url}/payment/verify.json'
        )

    def request_payment(
        self,
        amount,
        order_id,
        customer_email,
        customer_phone,
        callback_url,
    ):
        """درخواست پرداخت از زرین‌پال."""

        if not self.merchant_id:
            return {
                'success': False,
                'error': 'شناسه پذیرنده درگاه تنظیم نشده است.',
            }

        if int(amount) <= 0:
            return {
                'success': False,
                'error': 'مبلغ پرداخت معتبر نیست.',
            }

        data = {
            'merchant_id': self.merchant_id,
            'amount': int(amount),
            'currency': 'IRT',
            'description': (
                f'سفارش #{order_id} - کافه شاهین'
            ),
            'email': customer_email,
            'mobile': customer_phone,
            'callback_url': callback_url,
            'metadata': {
                'mobile': customer_phone,
                'email': customer_email,
            },
        }

        try:
            response = requests.post(
                self.request_url,
                json=data,
                timeout=15,
            )

            result = response.json()

        except requests.RequestException:
            return {
                'success': False,
                'error': 'ارتباط با درگاه پرداخت برقرار نشد.',
            }

        except ValueError:
            return {
                'success': False,
                'error': 'پاسخ دریافتی از درگاه معتبر نیست.',
            }

        if not response.ok:
            return {
                'success': False,
                'error': 'درگاه پرداخت درخواست را نپذیرفت.',
            }

        gateway_data = result.get('data') or {}

        if (
            gateway_data.get('code') == 100
            and gateway_data.get('authority')
        ):
            authority = gateway_data['authority']

            return {
                'success': True,
                'authority': authority,
                'payment_url': (
                    'https://www.zarinpal.com/pg/StartPay/'
                    f'{authority}'
                ),
            }

        return {
            'success': False,
            'error': 'درگاه پرداخت نتوانست درخواست را ثبت کند.',
        }

    def verify_payment(self, authority, amount):
        """استعلام و تأیید پرداخت از درگاه."""

        if not self.merchant_id:
            return {
                'success': False,
                'error': 'شناسه پذیرنده درگاه تنظیم نشده است.',
            }

        if not authority or int(amount) <= 0:
            return {
                'success': False,
                'error': 'شناسه یا مبلغ پرداخت معتبر نیست.',
            }

        data = {
            'merchant_id': self.merchant_id,
            'authority': authority,
            'amount': int(amount),
        }

        try:
            response = requests.post(
                self.verify_url,
                json=data,
                timeout=15,
            )

            result = response.json()

        except requests.RequestException:
            return {
                'success': False,
                'error': 'ارتباط با درگاه برای تأیید پرداخت برقرار نشد.',
            }

        except ValueError:
            return {
                'success': False,
                'error': 'پاسخ تأیید درگاه معتبر نیست.',
            }

        if not response.ok:
            return {
                'success': False,
                'error': 'درگاه پرداخت را تأیید نکرد.',
            }

        gateway_data = result.get('data') or {}
        gateway_code = gateway_data.get('code')

        if gateway_code in [100, 101]:
            return {
                'success': True,
                'ref_id': gateway_data.get('ref_id'),
                'card_hash': gateway_data.get(
                    'card_hash',
                    '',
                ),
            }

        return {
            'success': False,
            'error': 'تأیید پرداخت توسط درگاه ناموفق بود.',
        }