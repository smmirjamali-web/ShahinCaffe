from io import BytesIO
import base64

import qrcode

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import Category, MenuItem, Table
from .serializers import (
    CategorySerializer,
    MenuItemSerializer,
    MenuItemDetailSerializer,
    TableSerializer,
)


@extend_schema(tags=['Menu'])
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_queryset(self):
        """
        کاربران عادی فقط دسته‌بندی‌های فعال را می‌بینند.
        Admin همه دسته‌بندی‌ها را می‌بیند.
        """
        if self.request.user.is_staff:
            return Category.objects.all().order_by('order')

        return Category.objects.filter(
            is_active=True
        ).order_by('order')

    def get_permissions(self):
        """
        مشاهده Menu عمومی است.
        تغییرات فقط برای Admin است.
        """
        if self.action in ['list', 'retrieve', 'active_categories']:
            return [AllowAny()]

        return [IsAdminUser()]

    @action(
        detail=False,
        methods=['get']
    )
    def active_categories(self, request):
        """
        دریافت دسته‌بندی‌های فعال به همراه اقلام.
        """

        categories = self.get_queryset()

        serializer = self.get_serializer(
            categories,
            many=True,
            context={'request': request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


@extend_schema(tags=['Menu'])
class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        'category',
        'is_available',
        'is_popular',
    ]

    search_fields = [
        'name',
        'description',
        'p_name',
        'p_description',
    ]

    ordering_fields = [
        'price',
        'name',
        'created_at',
    ]

    ordering = ['name']

    def get_queryset(self):
        """
        کاربران عادی فقط محصولات فعال و در دسترس را می‌بینند.
        Admin همه محصولات را می‌بیند.
        """

        if self.request.user.is_staff:
            return MenuItem.objects.all()

        return MenuItem.objects.filter(
            is_active=True,
            is_available=True,
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MenuItemDetailSerializer

        return MenuItemSerializer

    def get_permissions(self):
        """
        مشاهده Menu عمومی است.
        ایجاد و ویرایش و حذف فقط برای Admin است.
        """

        if self.action in ['list', 'retrieve']:
            return [AllowAny()]

        return [IsAdminUser()]


@extend_schema(tags=['Management - Tables'])
class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        """
        فقط Admin به اطلاعات میزها دسترسی دارد.
        """

        return Table.objects.all()

    @action(
        detail=True,
        methods=['get']
    )
    def generate_qr(self, request, pk=None):
        """
        تولید QR Code برای میز.
        فقط Admin مجاز است.
        """

        table = self.get_object()

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )

        qr.add_data(table.qr_code)
        qr.make(fit=True)

        img = qr.make_image(
            fill_color='black',
            back_color='white'
        )

        buffer = BytesIO()

        img.save(
            buffer,
            format='PNG'
        )

        buffer.seek(0)

        img_base64 = base64.b64encode(
            buffer.getvalue()
        ).decode()

        return Response(
            {
                'table_id': table.id,
                'table_number': table.table_number,
                'qr_code': f'data:image/png;base64,{img_base64}',
            },
            status=status.HTTP_200_OK
        )