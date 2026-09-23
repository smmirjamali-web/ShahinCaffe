from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentGatewayConfigViewSet, PaymentTransactionViewSet

router = DefaultRouter()
router.register(r'gateways', PaymentGatewayConfigViewSet, basename='gateway-config')
router.register(r'transactions', PaymentTransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
]