from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomUserViewSet, GuestCustomerViewSet

router = DefaultRouter()
router.register(r'registered', CustomUserViewSet, basename='custom-user')
router.register(r'guests', GuestCustomerViewSet, basename='guest-customer')

urlpatterns = [
    path('', include(router.urls)),
]