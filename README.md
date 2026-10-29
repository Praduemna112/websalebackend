# WebSale E-Commerce Backend (Django REST Framework)

A complete e-commerce backend API built with **Django** and **Django REST Framework (DRF)** connected to **MySQL** (`websale` database). Ready for integration with a **React.js** frontend.

---

## Table of Contents
1. [Architecture & Entities](#architecture--entities)
2. [Database Configuration (MySQL)](#database-configuration-mysql)
3. [Setup & Installation](#setup--installation)
4. [API Reference for React Frontend](#api-reference-for-react-frontend)
   - [Overview & Health Check](#1-overview--health-check)
   - [Authentication & User Profile](#2-authentication--user-profile)
   - [Categories & Products](#3-categories--products)
   - [Shopping Cart (Add to Cart)](#4-shopping-cart-add-to-cart)
   - [Orders (Taking Orders)](#5-orders-taking-orders)
   - [Payments](#6-payments)
   - [Deliveries (Shipment Tracking)](#7-deliveries-shipment-tracking)
5. [Django Admin Panel](#django-admin-panel)
6. [Running Tests](#running-tests)

---

## Architecture & Entities

The database entities are modeled to handle the full e-commerce lifecycle:

```
[ User / Guest ]
       │
       ▼
[ Product Catalog ] ──( Categorized under )──► [ Category ]
       │
       ▼ (Add to Cart)
[ Cart ] ──► [ CartItem ] (quantity, price, subtotal)
       │
       ▼ (Checkout / Taking Orders)
[ Order ] ──► [ OrderItem ] (price snapshot, quantity, subtotal)
       │
       ├──► [ Payment ] (UPI, Card, COD, transaction ID, payment status)
       │
       └──► [ Delivery ] (Courier, tracking number, status, location, date)
```

### Models Defined:
- **`Category`**: Product classification (`name`, `slug`, `description`, `image_url`).
- **`Product`**: Store items (`name`, `slug`, `description`, `price`, `original_price`, `stock`, `image_url`, `is_active`).
- **`CustomerProfile`**: Contact & address info (`phone`, `address`, `city`, `state`, `postal_code`, `country`).
- **`Cart` & `CartItem`**: Stores items added to cart for logged-in or guest users.
- **`Order` & `OrderItem`**: Confirmed checkout with shipping address details, stock reservation, and line items.
- **`Payment`**: Payment method (`UPI`, `CREDIT_CARD`, `DEBIT_CARD`, `NET_BANKING`, `COD`, `WALLET`), transaction ID, status (`PENDING`, `COMPLETED`, `FAILED`, `REFUNDED`), and amount.
- **`Delivery`**: Shipment details, courier partner, tracking number (`TRK-YYYYMMDD-XXXXXX`), status (`PENDING`, `DISPATCHED`, `IN_TRANSIT`, `OUT_FOR_DELIVERY`, `DELIVERED`, `CANCELLED`), estimated delivery date, and live tracking location.

---

## Database Configuration (MySQL)

Set these values in the backend environment. Keep real credentials out of source control:
```env
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=3306
SECRET_KEY=replace-with-a-long-random-secret
DEBUG=False
SECURE_SSL_REDIRECT=True
ALLOWED_HOSTS=api.example.com
CORS_ALLOWED_ORIGINS=https://www.example.com
```

---

## Switching between localhost and production

Do not comment and uncomment settings in Python source. Keep one local-only `websalebackend/.env` file for your computer, and configure production values in Spaceship's Python application environment. Django loads `.env` for local development only when `DEBUG` is not already set in the process environment. The hosting panel must explicitly set `DEBUG=False`; then Django will not load `.env`, even if that file was accidentally uploaded.

On Windows PowerShell, create your local file from the template:
```powershell
Set-Location .\websalebackend
Copy-Item .env.example .env
```
Edit `.env` with the MySQL database credentials for your local computer, keeping `DEBUG=True`, `ALLOWED_HOSTS=localhost,127.0.0.1`, and localhost CORS origins. Do not copy production credentials into this file.

For Spaceship, do not upload `.env`. Also omit `.env.example` from the deployment package; it contains placeholders only, but is just a local setup template. Set the production values in the Python application's environment settings instead: `DEBUG=False`, your private production `SECRET_KEY`, the Spaceship database details, `ALLOWED_HOSTS` for the backend domain, and `CORS_ALLOWED_ORIGINS` for the frontend domain. These settings are read from environment variables by `config/settings.py`, so the same source code works in both environments without edits. If you also use a local `.env` on the server, remove it; the production panel variables must be present.

For the frontend, local development uses the `/api` development proxy to Django on `http://127.0.0.1:8000`. For production, set `REACT_APP_API_URL` to the backend's HTTPS URL before running `npm run build`; this value is baked into the frontend build.

## Setup & Installation

### 1. Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Install Requirements
```powershell
python -m pip install -r requirements.txt
```

### 3. Apply Database Migrations to MySQL
```powershell
python manage.py makemigrations app
python manage.py migrate
```

### 4. Start the Server
Run with the batch script:
```powershell
.\run.bat
```
Or directly:
```powershell
python manage.py runserver 0.0.0.0:8000
```
Server runs at: `http://localhost:8000`

---

## Database-backed data

The backend does not automatically add or seed demo records. Existing database records are left unchanged. The product and category APIs read from the configured database, and staff can manage the live catalog from the storefront admin page or the API. Create a staff account with `python manage.py createsuperuser` when needed.

---

## API Reference for React Frontend

### CORS is Pre-Configured:
Requests from `http://localhost:3000` and `http://localhost:5173` (Vite) are allowed by default.

---

### 1. Overview & Health Check
- **`GET /`** or **`GET /health/`**: Returns API status and list of all endpoints.

---

### 2. Authentication & User Profile
- **`POST /api/auth/register/`**: Register a new user.
  ```json
  {
    "username": "alice",
    "password": "Password123!",
    "email": "alice@example.com",
    "first_name": "Alice",
    "last_name": "Smith",
    "phone": "+91 9876543210",
    "address": "45 Green Park",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001"
  }
  ```
  *Response:* Returns user info and JWT `token`.

- **`POST /api/auth/login/`**: User login.
  ```json
  {
    "username": "alice",
    "password": "Password123!"
  }
  ```
  *Response:* Returns JWT `token` and user profile. Send header `Authorization: Bearer <token>` in protected requests.

- **`GET /api/auth/profile/`**: View authenticated user profile.
- **`PUT /api/auth/profile/`**: Update user profile and shipping details.

---

### 3. Categories & Products
- **`GET /api/categories/`**: List all product categories.
- **`GET /api/products/`**: List active products.
  *Query Parameters:*
  - `search=watch` - Search by product name or description
  - `category=1` - Filter by category ID
  - `category_slug=electronics` - Filter by category slug
  - `min_price=50&max_price=200` - Filter by price range
  - `in_stock=true` - Show only items with available stock
- **`GET /api/products/{id}/`**: Get product details.
- **`GET /api/products/featured/`**: Get featured products for homepage.

Products can be saved with an HTTP(S) `image_url` or an uploaded JPEG, PNG, WebP, or GIF image. The storefront upload saves the image as a Base64 data URL in the product record; uploads are limited to 5 MB.

---

### 4. Shopping Cart (Add to Cart)
Guest users can pass `session_id` in request body or `X-Session-ID` header. Logged-in users will automatically use their personal cart.

- **`GET /api/cart/?session_id=<SESSION_ID>`**: View cart items, count, and total amount.
- **`POST /api/cart/add/`**: Add product to cart.
  ```json
  {
    "product_id": 1,
    "quantity": 2,
    "session_id": "guest-cart-123"
  }
  ```
- **`PUT /api/cart/items/{item_id}/`**: Update quantity of a cart item.
  ```json
  {
    "quantity": 3
  }
  ```
- **`DELETE /api/cart/items/{item_id}/`**: Remove item from cart.
- **`POST /api/cart/clear/`**: Remove all items from cart.

---

### 5. Orders (Taking Orders)
- **`POST /api/orders/create/`**: Place an order from the cart.
  *Automatically validates stock, decrements inventory, creates payment record and delivery tracking record in PENDING status, and clears the cart.*
  ```json
  {
    "session_id": "guest-cart-123",
    "shipping_name": "Alice Smith",
    "shipping_email": "alice@example.com",
    "shipping_phone": "+91 9876543210",
    "shipping_address": "45 Green Park, MG Road",
    "shipping_city": "Bengaluru",
    "shipping_state": "Karnataka",
    "shipping_postal_code": "560001",
    "shipping_country": "India",
    "payment_method": "UPI",
    "notes": "Please deliver between 10am-4pm"
  }
  ```
  *Response:* Returns full order details with `order_number` (e.g. `WS-20261028-XXXX`), `payment` info, and `delivery` info with tracking number (`TRK-YYYYMMDD-XXXXXX`).

- **`GET /api/orders/`**: List orders.
- **`GET /api/orders/{order_id_or_number}/`**: Get order details (e.g. `/api/orders/WS-20261028-A1B2/`).
- **`POST /api/orders/{order_id_or_number}/cancel/`**: Cancel order and automatically restore stock.

---

### 6. Payments
- **`GET /api/payments/`**: List all payments.
- **`GET /api/payments/order/{order_id_or_number}/`**: Get payment details for an order.
- **`POST /api/payments/process/`**: Confirm / process payment for an order.
  ```json
  {
    "order_number": "WS-20261028-A1B2",
    "payment_status": "COMPLETED",
    "transaction_id": "UPI-TXN-987654321"
  }
  ```
  *Automatically updates Order status to `CONFIRMED` and records payment timestamp.*

---

### 7. Deliveries (Shipment Tracking)
- **`GET /api/deliveries/`**: List all deliveries.
- **`GET /api/deliveries/track/{tracking_number}/`**: Track shipment by tracking number (e.g. `TRK-20261028-XXXXXX`).
  *Response:*
  ```json
  {
    "tracking_number": "TRK-20261028-984321",
    "order_number": "WS-20261028-A1B2",
    "courier_partner": "WebSale Express",
    "status": "DISPATCHED",
    "delivery_address": "45 Green Park, MG Road, Bengaluru, Karnataka - 560001, India",
    "estimated_delivery_date": "2026-11-01",
    "delivered_at": null,
    "current_location": "Bengaluru Sorting Hub",
    "status_notes": "Package dispatched from warehouse"
  }
  ```
- **`GET /api/deliveries/order/{order_id_or_number}/`**: Get delivery details for an order.
- **`PATCH /api/deliveries/{delivery_id}/update-status/`**: Update delivery progress.
  ```json
  {
    "status": "DELIVERED",
    "current_location": "Customer Doorstep, Bengaluru",
    "status_notes": "Delivered to customer"
  }
  ```
  *When status is set to `DELIVERED`, automatically marks the Order status as `DELIVERED` and records the delivery time.*

---

## Django Admin Panel
Access the Django management dashboard at:
`http://localhost:8000/admin/`

Sign in with an account created using `python manage.py createsuperuser`. You can view, search, filter, and edit:
- Categories
- Products (with inline stock and price editing)
- Customer Profiles
- Shopping Carts & Cart Items
- Orders & Order Items
- Payments
- Deliveries & Tracking

---

## Running Tests
Run the automated test suite covering all entities and workflows:
```powershell
python manage.py test app
```

## React Storefront

Start Django in one terminal from `websalebackend`:
```powershell
python manage.py migrate
python manage.py runserver
```

Start React in another terminal from `websalefrontend`:
```powershell
npm install
npm start
```

Open `http://localhost:3000`. Customers can register, browse and search products, manage a cart, check out with cash on delivery, and view their profile and orders. A guest cart is merged into the account when the customer signs in.

Create a staff account with `python manage.py createsuperuser`, then sign in through the React `/login` page. Staff users can access `/admin` to manage products, orders, stock, and categories. Customer registration never grants staff access. API order/payment/delivery data is restricted to the owner or staff, and catalog writes and order/delivery/payment management are staff-only.

Checkout currently supports **cash on delivery only**. No card details are collected and no online payment is charged. The payment-status API is for staff to record an already-collected payment; it is not a payment gateway.

## Deploying on Spaceship Web Hosting Pro

This project uses Django's WSGI entry point at `config.wsgi:application` and a MySQL-compatible database. Before deployment, confirm that the hosting account's Python app supports the Python version and packages in `requirements.txt`, and ask Spaceship for its required WSGI/Passenger setup and static-file instructions.

1. In cPanel, create a database and a dedicated database user, attach the user to the database, and grant the required privileges. Record the exact database name, user, password, host, and port cPanel provides. Shared-hosting account prefixes may be part of the database name and user.
2. In the Python application environment settings, configure `SECRET_KEY`, `DEBUG=False`, `SECURE_SSL_REDIRECT=True`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`. `DB_USER` is the **MySQL database user**, not automatically your Spaceship/cPanel login name. Use the actual database user created in cPanel. Do not commit credentials or upload a real `.env` file to a public directory.
3. Upload the backend package so `manage.py`, `config/`, and `app/` are in the configured application root. Install dependencies from `requirements.txt` using the command/environment method Spaceship documents. Set the app's WSGI entry point to `config.wsgi:application` (or its documented equivalent).
4. Run `python manage.py migrate` once against the hosted database. Create a staff user with `python manage.py createsuperuser`.
5. Run `python manage.py collectstatic` and follow Spaceship's instructions for mapping `staticfiles/` to `/static/`. Do not assume Django's development server will serve production static files.
6. Build the React app with `REACT_APP_API_URL=https://api.example.com` set in the build environment, then run `npm run build`. Upload the contents of `websalefrontend/build/` to the domain's document root. Configure the web server to route client-side paths such as `/cart` and `/account` to `index.html`.
7. Replace the example domains above with your actual frontend/backend domains. Set `ALLOWED_HOSTS` to the backend host (no scheme); set `CORS_ALLOWED_ORIGINS` to the frontend origin (include `https://`, no trailing path). Test registration, login, product listing, cart, checkout, admin, and static assets over HTTPS before opening the store.

Product image uploads are currently stored as Base64 text in the database. This avoids needing a separate media server, but increases database size; keep database backups and monitor storage.
