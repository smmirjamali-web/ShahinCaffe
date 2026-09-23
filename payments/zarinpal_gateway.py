"""درگاه پرداخت زرین‌پال"""
import requests
import json
from django.conf import settings

class ZarinpalGateway:
    def __init__(self):
        self.merchant_id = settings.ZARINPAL_MERCHANT_ID
        self.api_url = settings.ZARINPAL_API_URL
        self.request_url = f'{self.api_url}/payment/request.json'
        self.verify_url = f'{self.api_url}/payment/verify.json'
    
    def request_payment(self, amount, order_id, customer_email, customer_phone, callback_url):
        """درخواست پرداخت از زرین‌پال"""
        data = {
            'merchant_id': self.merchant_id,
            'amount': int(amount),
            'currency': 'IRT',
            'description': f'سفارش #{order_id} - کافه شاهین',
            'email': customer_email,
            'mobile': customer_phone,
            'callback_url': callback_url,
            'metadata': [
                {
                    'key': 'order_id',
                    'value': str(order_id)
                }
            ]
        }
        
        try:
            response = requests.post(
                self.request_url,
                json=data,
                timeout=10
            )
            result = response.json()
            
            if result['data']['code'] == 100:
                return {
                    'success': True,
                    'authority': result['data']['authority'],
                    'payment_url': f"https://www.zarinpal.com/pg/StartPay/{result['data']['authority']}"
                }
            else:
                return {
                    'success': False,
                    'error': result['errors']['message']
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_payment(self, authority, amount):
        """تایید پرداخت"""
        data = {
            'merchant_id': self.merchant_id,
            'authority': authority,
            'amount': int(amount)
        }
        
        try:
            response = requests.post(
                self.verify_url,
                json=data,
                timeout=10
            )
            result = response.json()
            
            if result['data']['code'] in [100, 101]:
                return {
                    'success': True,
                    'ref_id': result['data']['ref_id'],
                    'card_hash': result['data'].get('card_hash', '')
                }
            else:
                return {
                    'success': False,
                    'error': result['errors']['message']
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }