from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Order, OrderItem, Payment
from .serializers import (OrderSerializer, OrderDetailSerializer, 
                         CreateOrderSerializer, PaymentSerializer)
from menu.models import MenuItem, Table
from users.models import CustomUser, GuestCustomer

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = []
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer
        elif self.action == 'create':
            return CreateOrderSerializer
        return OrderSerializer
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """ایجاد سفارش جدید"""
        serializer = CreateOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        table = None
        if data.get('table_id'):
            table = Table.objects.filter(id=data['table_id']).first()

        if table is None and data.get('delivery_method') != 'delivery':
            table, _ = Table.objects.get_or_create(
                table_number=0,
                defaults={'qr_code': 'pickup-default', 'capacity': 0}
            )
        # تعیین مشتری
        user = None
        guest_customer = None
        
        if data.get('user_id'):
            user = get_object_or_404(CustomUser, id=data['user_id'])
        else:
            guest_phone = data.get('guest_phone')
            guest_name = data.get('guest_name', 'میهمان')
            guest_customer, _ = GuestCustomer.objects.get_or_create(
                phone_number=guest_phone,
                defaults={'name': guest_name}
            )
        
        # ایجاد سفارش
        order = Order.objects.create(
            table=table,
            user=user,
            guest_customer=guest_customer,
            notes=data.get('notes', ''),
            delivery_method=data.get('delivery_method', 'pickup'),
            delivery_address=data.get('delivery_address', '')
        )
        
        # اضافه کردن اقلام
        for item_data in data['items']:
            menu_item = get_object_or_404(MenuItem, id=item_data['menu_item_id'])
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=item_data['quantity'],
                price=menu_item.price,
                notes=item_data.get('notes', '')
            )
        
        order.calculate_total()
        
        response_serializer = OrderDetailSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def apply_discount(self, request, pk=None):
        """اعمال کد تخفیف به سفارش"""
        from discounts.models import DiscountCode, DiscountCodeUsage
        
        order = self.get_object()
        code_str = request.data.get('code')
        
        if not code_str:
            return Response({'error': 'کد تخفیف الزامی است'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            discount_code = DiscountCode.objects.get(code=code_str)
        except DiscountCode.DoesNotExist:
            return Response({'error': 'کد تخفیف معتبر نیست'}, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی معتبر بودن کد
        is_valid, message = discount_code.is_valid()
        if not is_valid:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        # بررسی حداقل مبلغ سفارش
        items_total = sum(item.get_total() for item in order.items.all())
        if items_total < discount_code.min_order_amount:
            return Response({
                'error': f'حداقل مبلغ سفارش {discount_code.min_order_amount} تومان است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # محاسبه تخفیف
        discount_amount = discount_code.calculate_discount(items_total)
        
        order.discount_code = discount_code
        order.discount = discount_amount
        order.calculate_total()
        
        # ثبت استفاده
        DiscountCodeUsage.objects.create(
            discount_code=discount_code,
            user=order.user,
            guest_phone=order.guest_customer.phone_number if order.guest_customer else None,
            order=order,
            discount_amount=discount_amount
        )
        
        discount_code.current_usage += 1
        discount_code.save()
        
        response_serializer = OrderDetailSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """به‌روزرسانی وضعیت سفارش"""
        order = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(Order.STATUS_CHOICES):
            return Response({'error': 'وضعیت نامعتبر است'}, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = order.status
        order.status = new_status
        order.save()
        
        # ارسال اطلاع‌رسانی
        from notifications.services import send_order_notification
        send_order_notification.delay(order.id, new_status)
        
        return Response({
            'message': 'وضعیت سفارش با موفقیت تغییر یافت',
            'old_status': old_status,
            'new_status': new_status
        })
    
    @action(detail=False, methods=['get'])
    def table_orders(self, request):
        """دریافت سفارشات میز فعلی"""
        table_id = request.query_params.get('table_id')
        if not table_id:
            return Response({'error': 'table_id الزامی است'}, status=status.HTTP_400_BAD_REQUEST)
        
        orders = Order.objects.filter(table_id=table_id, status__in=['pending', 'confirmed', 'preparing', 'ready'])
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    
    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """تاریخچه سفارشات مشتری بر اساس شماره تلفن"""
        phone = request.query_params.get('phone')
        if not phone:
            return Response({'error': 'شماره تلفن الزامی است'}, status=status.HTTP_400_BAD_REQUEST)
        
        orders = Order.objects.filter(
            guest_customer__phone_number=phone
        ).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = []