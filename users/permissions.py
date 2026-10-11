from rest_framework.permissions import BasePermission


class IsOwnerOrStaff(BasePermission):
    """
    کاربر فقط به اطلاعات خودش دسترسی دارد.
    staff به همه کاربران دسترسی دارد.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.user.is_staff:
            return True

        return obj == request.user


class IsOrderOwnerOrStaff(BasePermission):
    """
    کاربر فقط سفارش خودش را می‌تواند ببیند.
    staff به همه سفارش‌ها دسترسی دارد.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        if request.user.is_staff:
            return True

        return obj.user_id == request.user.id