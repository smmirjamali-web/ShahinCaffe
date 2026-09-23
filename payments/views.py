from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import PaymentGatewayConfig, PaymentTransaction
from .serializers import (PaymentGatewayConfigSerializer, PaymentTransactionSerializer, 
                         InitiatePaymentSerializer)
from .services import initiate_payment, verify_payment

class PaymentGatewayConfigViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaymentGatewayConfig.objects.filter(is_active=True)
    serializer_class = PaymentGatewayConfigSerializer
    permission_classes = []


class PaymentTransactionViewSet(viewsets.ModelViewSet):
    queryset = PaymentTransaction.objects.all()
    serializer_class = PaymentTransactionSerializer
    permission_classes = []
    
    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """شروع فرآیند پرداخت"""
        serializer = InitiatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        result = initiate_payment(
            data['order_id'],
            data['gateway'],
            data['callback_url'],
            request.data.get('customer_email', ''),
            request.data.get('customer_phone', '')
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def callback(self, request):
        """بازگشت از درگاه پرداخت"""
        authority = request.data.get('Authority')
        status_response = request.data.get('Status')
        amount = request.data.get('amount')
        
        if status_response != 'OK' or not authority:
            return Response({
                'success': False,
                'error': 'پرداخت لغو شد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = verify_payment(authority, amount)
        return Response(result, status=status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST)