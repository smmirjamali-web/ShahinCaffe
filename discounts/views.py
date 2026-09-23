from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import DiscountCode, DiscountCodeUsage
from .serializers import (DiscountCodeSerializer, DiscountCodeDetailSerializer, 
                         DiscountCodeUsageSerializer)

class DiscountCodeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DiscountCode.objects.filter(is_active=True)
    serializer_class = DiscountCodeSerializer
    permission_classes = []
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DiscountCodeDetailSerializer
        return DiscountCodeSerializer
    
    @action(detail=False, methods=['post'])
    def validate_code(self, request):
        """بررسی معتبر بودن کد"""
        code_str = request.data.get('code')
        order_amount = request.data.get('order_amount', 0)
        
        try:
            code = DiscountCode.objects.get(code=code_str)
        except DiscountCode.DoesNotExist:
            return Response({'valid': False, 'error': 'کد تخفیف معتبر نیست'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        is_valid, message = code.is_valid()
        if not is_valid:
            return Response({'valid': False, 'error': message}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # بررسی حداقل مبلغ
        if order_amount < code.min_order_amount:
            return Response({
                'valid': False, 
                'error': f'حداقل مبلغ سفارش {code.min_order_amount} تومان است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        discount_amount = code.calculate_discount(order_amount)
        
        return Response({
            'valid': True,
            'code': code.code,
            'discount_type': code.discount_type,
            'discount_value': code.discount_value,
            'discount_amount': discount_amount,
            'final_amount': order_amount - discount_amount
        })


class DiscountCodeUsageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DiscountCodeUsage.objects.all()
    serializer_class = DiscountCodeUsageSerializer
    permission_classes = []