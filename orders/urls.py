from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, PaymentViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
]