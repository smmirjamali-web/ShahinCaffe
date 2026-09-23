from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Category, MenuItem, Table
from .serializers import (CategorySerializer, MenuItemSerializer, 
                          MenuItemDetailSerializer, TableSerializer)
import qrcode
from io import BytesIO
import base64

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).order_by('order')
    serializer_class = CategorySerializer
    permission_classes = []
    
    @action(detail=False, methods=['get'])
    def active_categories(self, request):
        """دریافت دسته‌بندی‌های فعال به همراه اقلام"""
        categories = self.get_queryset()
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.filter(is_active=True, is_available=True)
    serializer_class = MenuItemSerializer
    permission_classes = []
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'name']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MenuItemDetailSerializer
        return MenuItemSerializer


class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.filter(is_active=True)
    serializer_class = TableSerializer
    permission_classes = []
    
    @action(detail=True, methods=['get'])
    def generate_qr(self, request, pk=None):
        """تولید QR Code برای میز"""
        table = self.get_object()
        
        # ایجاد QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(table.qr_code)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # تبدیل به base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return Response({
            'table_id': table.id,
            'table_number': table.table_number,
            'qr_code': f"data:image/png;base64,{img_base64}"
        })