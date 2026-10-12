from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser, GuestCustomer
from menu.models import Category, MenuItem
from orders.models import Order, OrderItem


class OrderAPITests(TestCase):
    """تست دسترسی و ثبت سفارش."""

    def setUp(self):
        self.client = APIClient()

        # ایجاد دو کاربر عادی
        self.user_a = CustomUser.objects.create_user(
            phone_number='09120000011',
            password='UserPass123!',
        )

        self.user_b = CustomUser.objects.create_user(
            phone_number='09120000012',
            password='UserPass123!',
        )

        # ساخت دسته‌بندی و محصول آزمایشی
        self.category = Category.objects.create(
            name='Test Drinks',
            slug='test-drinks',
            p_name='نوشیدنی آزمایشی',
            icon='',
        )

        self.menu_item = MenuItem.objects.create(
            category=self.category,
            name='Test Coffee',
            description='Test coffee description',
            price=Decimal('50000'),
            image='',
            is_active=True,
            is_available=True,
        )

        # سفارش‌های دو کاربر را ایجاد می‌کنیم.
        self.order_a = self.create_order(self.user_a)
        self.order_b = self.create_order(self.user_b)

    def create_order(self, user):
        """ساخت سفارش آزمایشی برای یک کاربر."""

        order = Order.objects.create(
            user=user,
            delivery_method='delivery',
            delivery_address='Test Street',
        )

        OrderItem.objects.create(
            order=order,
            menu_item=self.menu_item,
            quantity=1,
            price=self.menu_item.price,
        )

        order.calculate_total()

        return order

    def test_guest_cannot_list_orders(self):
        """کاربر واردنشده نمی‌تواند فهرست سفارش‌ها را ببیند."""

        response = self.client.get(
            reverse('order-list')
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_sees_only_own_orders(self):
        """کاربر فقط سفارش‌های خودش را می‌بیند."""

        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.get(
            reverse('order-list')
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            order['id']
            for order in response.data['results']
        }

        self.assertIn(self.order_a.id, returned_ids)
        self.assertNotIn(self.order_b.id, returned_ids)

    def test_user_cannot_retrieve_another_users_order(self):
        """دسترسی مستقیم به سفارش کاربر دیگر رد می‌شود."""

        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.get(
            reverse(
                'order-detail',
                kwargs={'pk': self.order_b.id},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_my_orders_returns_only_current_users_orders(self):
        """تاریخچه سفارش فقط متعلق به کاربر فعلی است."""

        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.get(
            reverse('order-my-orders')
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            order['id']
            for order in response.data
        }

        self.assertIn(self.order_a.id, returned_ids)
        self.assertNotIn(self.order_b.id, returned_ids)

    def test_regular_user_cannot_update_order_status(self):
        """کاربر عادی اجازه تغییر وضعیت سفارش را ندارد."""

        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.patch(
            reverse(
                'order-update-status',
                kwargs={'pk': self.order_a.id},
            ),
            {
                'status': 'served',
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.order_a.refresh_from_db()

        self.assertEqual(
            self.order_a.status,
            'pending',
        )

    def test_regular_user_cannot_access_table_orders(self):
        """فهرست سفارش‌های میز مخصوص مدیر است."""

        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.get(
            reverse('order-table-orders'),
            {'table_id': 1},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_authenticated_user_cannot_impersonate_another_user(self):
        """
        ارسال user_id کاربر دیگر نباید مالک سفارش را تغییر دهد.
        """

        self.client.force_authenticate(
            user=self.user_a
        )

        response = self.client.post(
            reverse('order-list'),
            {
                'user_id': self.user_b.id,
                'delivery_method': 'delivery',
                'delivery_address': 'New Test Street',
                'items': [
                    {
                        'menu_item_id': self.menu_item.id,
                        'quantity': 2,
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        created_order = Order.objects.get(
            id=response.data['id']
        )

        self.assertEqual(
            created_order.user_id,
            self.user_a.id,
        )

        self.assertNotEqual(
            created_order.user_id,
            self.user_b.id,
        )

    def test_guest_can_create_order_with_phone_number(self):
        """ثبت سفارش مهمان بدون حساب کاربری مجاز است."""

        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse('order-list'),
            {
                'guest_phone': '09120000013',
                'guest_name': 'Guest Test',
                'delivery_method': 'delivery',
                'delivery_address': 'Guest Test Street',
                'items': [
                    {
                        'menu_item_id': self.menu_item.id,
                        'quantity': 1,
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        created_order = Order.objects.get(
            id=response.data['id']
        )

        self.assertIsNone(created_order.user)

        self.assertIsNotNone(
            created_order.guest_customer
        )

        self.assertEqual(
            created_order.guest_customer.phone_number,
            '09120000013',
        )