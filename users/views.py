from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from .models import CustomUser, GuestCustomer
from .serializers import (
    CustomUserSerializer,
    CustomUserDetailSerializer,
    GuestCustomerSerializer,
)
from .permissions import IsOwnerOrStaff


@extend_schema(tags=['Users'])
class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve' or self.action == 'me':
            return CustomUserDetailSerializer

        return CustomUserSerializer

    def get_queryset(self):
        """
        staff همه کاربران را می‌بیند.
        کاربر عادی فقط خودش را می‌بیند.
        """
        if self.request.user.is_staff:
            return CustomUser.objects.all()

        return CustomUser.objects.filter(
            id=self.request.user.id
        )

    def get_permissions(self):
        """
        ثبت‌نام و بررسی شماره تلفن عمومی هستند.
        سایر عملیات نیاز به احراز هویت دارند.
        """
        if self.action in ['create', 'check_phone']:
            return [AllowAny()]

        return [
            IsAuthenticated(),
            IsOwnerOrStaff(),
        ]

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        """
        دریافت یا ویرایش پروفایل کاربر فعلی.
        """

        user = request.user

        if request.method == 'GET':
            serializer = CustomUserDetailSerializer(
                user,
                context={'request': request},
            )

            return Response(serializer.data)

        serializer = CustomUserDetailSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request},
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=['post'])
    def check_phone(self, request):
        """
        بررسی وجود شماره تلفن.
        """

        phone = request.data.get('phone_number')

        if not phone:
            return Response(
                {
                    'error': 'شماره تلفن الزامی است',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        exists = CustomUser.objects.filter(
            phone_number=phone
        ).exists()

        return Response({
            'exists': exists,
        })


@extend_schema(tags=['Management - Guests'])
class GuestCustomerViewSet(viewsets.ModelViewSet):
    queryset = GuestCustomer.objects.all()
    serializer_class = GuestCustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        ایجاد یا دریافت Guest Customer عمومی است.
        مدیریت مهمان‌ها فقط برای Admin است.
        """

        if self.action == 'create_or_get':
            return [AllowAny()]

        return [IsAdminUser()]

    @action(detail=False, methods=['post'])
    def create_or_get(self, request):
        """
        ایجاد یا دریافت مشتری مهمان.
        """

        phone = request.data.get('phone_number')
        name = request.data.get('name', 'میهمان')
        email = request.data.get('email', '')

        if not phone:
            return Response(
                {
                    'error': 'شماره تلفن الزامی است',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        guest, created = GuestCustomer.objects.get_or_create(
            phone_number=phone,
            defaults={
                'name': name,
                'email': email,
            },
        )

        return Response(
            {
                'id': guest.id,
                'created': created,
            },
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )