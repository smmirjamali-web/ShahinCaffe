from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import Notification, NotificationTemplate
from .serializers import (
    NotificationSerializer,
    NotificationTemplateSerializer,
)


@extend_schema(tags=['Notifications'])
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    مشاهده اطلاع‌رسانی‌های مربوط به کاربر فعلی.
    مدیر می‌تواند تمام اطلاع‌رسانی‌ها را مشاهده کند.
    """

    queryset = Notification.objects.select_related(
        'user',
        'guest_customer',
        'order',
    ).all()

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        کاربران عادی فقط اطلاع‌رسانی‌های خودشان را می‌بینند.
        مدیر به تمام اطلاع‌رسانی‌ها دسترسی دارد.
        """

        queryset = super().get_queryset()

        if self.request.user.is_staff:
            return queryset

        return queryset.filter(
            user=self.request.user
        )

    def get_permissions(self):
        """
        مشاهده اطلاع‌رسانی‌های عادی نیازمند ورود است.
        صف اطلاع‌رسانی‌های ارسال‌نشده مخصوص مدیر است.
        """

        if self.action == 'unsent':
            return [IsAdminUser()]

        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def unsent(self, request):
        """
        دریافت اطلاع‌رسانی‌های ارسال‌نشده.
        فقط مدیر مجاز است.
        """

        notifications = self.get_queryset().filter(
            is_sent=False
        ).order_by('created_at')

        serializer = self.get_serializer(
            notifications,
            many=True
        )

        return Response(serializer.data)


@extend_schema(tags=['Management - Notifications'])
class NotificationTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    مشاهده قالب‌های اطلاع‌رسانی.
    دسترسی فقط برای مدیر است.
    """

    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAdminUser]