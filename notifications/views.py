from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notification, NotificationTemplate
from .serializers import NotificationSerializer, NotificationTemplateSerializer

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = []
    
    @action(detail=False, methods=['get'])
    def unsent(self, request):
        """دریافت اطلاع‌رسانی‌های ارسال نشده"""
        notifications = Notification.objects.filter(is_sent=False).order_by('created_at')
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)


class NotificationTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = []