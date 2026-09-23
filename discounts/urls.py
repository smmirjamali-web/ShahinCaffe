from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DiscountCodeViewSet, DiscountCodeUsageViewSet

router = DefaultRouter()
router.register(r'codes', DiscountCodeViewSet, basename='discount-code')
router.register(r'usage', DiscountCodeUsageViewSet, basename='discount-usage')

urlpatterns = [
    path('', include(router.urls)),
]