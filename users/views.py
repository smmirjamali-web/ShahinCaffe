from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CustomUser, GuestCustomer
from .serializers import (CustomUserSerializer, CustomUserDetailSerializer, 
                         GuestCustomerSerializer)

class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = []
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CustomUserDetailSerializer
        return CustomUserSerializer
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """ثبت کاربر جدید"""
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def check_phone(self, request):
        """بررسی وجود شماره تلفن"""
        phone = request.data.get('phone_number')
        exists = CustomUser.objects.filter(phone_number=phone).exists()
        return Response({'exists': exists})


class GuestCustomerViewSet(viewsets.ModelViewSet):
    queryset = GuestCustomer.objects.all()
    serializer_class = GuestCustomerSerializer
    permission_classes = []
    
    @action(detail=False, methods=['post'])
    def create_or_get(self, request):
        """ایجاد یا دریافت مشتری میهمان"""
        phone = request.data.get('phone_number')
        name = request.data.get('name')
        email = request.data.get('email', '')
        
        guest, created = GuestCustomer.objects.get_or_create(
            phone_number=phone,
            defaults={'name': name, 'email': email}
        )
        
        serializer = GuestCustomerSerializer(guest)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)