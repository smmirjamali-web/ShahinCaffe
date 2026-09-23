# ☕ Shahin Cafe — Backend API

Backend REST API for Shahin Cafe, built with Django and Django REST Framework.

---

## 🗂️ Project Structure

```
ShahinCafe/
├── config/               # Project settings and main URL routing
├── menu/                 # Menu items, categories, and tables
├── orders/               # Orders, order items, and payments
├── users/                # Custom user model and guest customers
├── discounts/            # Discount codes (app placeholder)
├── payments/             # Payment gateway integration (app placeholder)
├── notifications/        # SMS / email notifications (app placeholder)
└── manage.py
```

---

## ⚙️ Tech Stack

- **Python** 3.14
- **Django** 6.1
- **Django REST Framework**
- **PostgreSQL**
- **Celery** + **Redis** (for async notifications)
- **django-cors-headers** (for frontend integration)
- **django-filter** (for filtering menu items)

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/shahin-cafe-backend.git
cd shahin-cafe-backend
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True

DB_NAME=shahin_cafe
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379

ZARINPAL_MERCHANT_ID=your-zarinpal-merchant-id
KAVEH_NEGAR_API_KEY=your-sms-api-key
```

### 5. Apply migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create a superuser

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`

---

## 📡 API Endpoints

### Menu

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/menu/items/` | List all active menu items |
| GET | `/api/menu/items/?category=<id>` | Filter items by category |
| GET | `/api/menu/items/?search=<query>` | Search menu items |
| GET | `/api/menu/items/<id>/` | Get single item detail |
| GET | `/api/menu/categories/` | List all categories |
| GET | `/api/menu/tables/` | List all tables |
| GET | `/api/menu/tables/<id>/generate_qr/` | Generate QR code for a table |

### Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/orders/orders/` | Create a new order |
| GET | `/api/orders/orders/<id>/` | Get order detail |
| GET | `/api/orders/orders/my_orders/?phone=<phone>` | Get order history by phone number |
| GET | `/api/orders/orders/table_orders/?table_id=<id>` | Get active orders for a table |
| PATCH | `/api/orders/orders/<id>/update_status/` | Update order status |
| POST | `/api/orders/orders/<id>/apply_discount/` | Apply a discount code |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/users/users/register/` | Register a new user |
| POST | `/api/users/users/check_phone/` | Check if a phone number exists |
| POST | `/api/users/guests/create_or_get/` | Create or retrieve a guest customer |

---

## 📦 Create Order — Request Body

```json
{
    "guest_phone": "09123456789",
    "guest_name": "علی رضایی",
    "delivery_method": "delivery",
    "delivery_address": "تهران، خیابان آزادی",
    "items": [
        { "menu_item_id": 1, "quantity": 2 },
        { "menu_item_id": 3, "quantity": 1, "notes": "بدون شکر" }
    ],
    "notes": ""
}
```

**Delivery method options:** `pickup` | `delivery`

---

## 🔑 Order Status Flow

```
pending → confirmed → preparing → ready → served
                                        ↘ cancelled
```

---

## 🛡️ Admin Panel

Django admin is available at `/admin/` for managing menu items, orders, users, and discount codes.

---

## 🌐 CORS Configuration

The API is configured to accept requests from:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

To add production frontend URLs, update `CORS_ALLOWED_ORIGINS` in `config/settings.py`.

---

## 📌 Notes

- All prices are in **Toman (تومان)**
- The API uses **session authentication** by default — JWT can be added later
- Media files (product images) are served from `/media/` in development
- `permission_classes = []` is set on all viewsets for now — **add proper permissions before deploying to production**
