from .models import PaymentTransaction, PaymentGatewayConfig
from .zarinpal_gateway import ZarinpalGateway
from orders.models import Order
from django.utils import timezone

def initiate_payment(order_id, gateway_name, callback_url, customer_email='', customer_phone=''):
    """شروع فرآیند پرداخت"""
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return {'success': False, 'error': 'سفارش یافت نشد'}
    
    try:
        gateway_config = PaymentGatewayConfig.objects.get(
            gateway_name=gateway_name,
            is_active=True
        )
    except PaymentGatewayConfig.DoesNotExist:
        return {'success': False, 'error': 'درگاه پرداخت فعال نیست'}
    
    if gateway_name == 'zarinpal':
        gateway = ZarinpalGateway()
        
        if not customer_phone:
            customer_phone = order.get_customer_phone()
        
        result = gateway.request_payment(
            order.total_amount,
            order.id,
            customer_email,
            customer_phone,
            callback_url
        )
        
        if result['success']:
            # ثبت تراکنش
            transaction = PaymentTransaction.objects.create(
                order=order,
                gateway='zarinpal',
                reference_id=result['authority'],
                amount=order.total_amount,
                status='pending',
                customer_phone=customer_phone,
                customer_email=customer_email
            )
            
            return {
                'success': True,
                'transaction_id': transaction.id,
                'authority': result['authority'],
                'payment_url': result['payment_url']
            }
        else:
            return {
                'success': False,
                'error': result['error']
            }
    
    return {'success': False, 'error': 'درگاه پرداخت پشتیبانی نشده'}


def verify_payment(authority, amount):
    """تایید پرداخت"""
    try:
        transaction = PaymentTransaction.objects.get(
            reference_id=authority,
            status='pending'
        )
    except PaymentTransaction.DoesNotExist:
        return {'success': False, 'error': 'تراکنش یافت نشد'}
    
    if transaction.gateway == 'zarinpal':
        gateway = ZarinpalGateway()
        result = gateway.verify_payment(authority, int(amount))
        
        if result['success']:
            # به‌روزرسانی تراکنش
            transaction.status = 'success'
            transaction.verified_at = timezone.now()
            transaction.gateway_response = {'ref_id': result['ref_id']}
            transaction.save()
            
            # به‌روزرسانی سفارش
            order = transaction.order
            order.payment_status = 'paid'
            order.save()
            
            # ارسال اطلاع‌رسانی
            from notifications.services import send_order_notification
            send_order_notification.delay(order.id, 'payment_received')
            
            return {
                'success': True,
                'ref_id': result['ref_id'],
                'order_id': order.id
            }
        else:
            transaction.status = 'failed'
            transaction.save()
            return {'success': False, 'error': result['error']}
    
    return {'success': False, 'error': 'درگاه پرداخت پشتیبانی نشده'}