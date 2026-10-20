# Demo API

A FastAPI CRUD API backed by the existing MySQL `demo.product` table.

## Requirements

- Python 3.10 or newer
- MySQL 8.x (or a compatible MySQL server)

## Setup

Create and activate a virtual environment from this project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Ensure your MySQL server has the `demo` database and `product` table. The database connection defaults to `root` with password `1234`; update `.env` if needed:

```sql
CREATE DATABASE demo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Copy `.env.example` to `.env`. Set `SECRET_KEY` and `ADMIN_RESET_TOKEN` to separate random secrets (generate each with `py -c "import secrets; print(secrets.token_urlsafe(32))"`). The existing `product` table has an auto-incrementing `id` and nullable `productname VARCHAR(45)`:

```text
DATABASE_URL=mysql+pymysql://root:1234@localhost:3306/demo
```

The app loads `.env` automatically. You can also override the value for the current PowerShell session:

```powershell
$env:DATABASE_URL = "mysql+pymysql://root:1234@localhost:3306/demo"
uvicorn app.main:app --reload
```

## Database migrations

The API does not alter database tables on startup. The current migrations add `product.description` and create the `users` table. For future model changes, generate and apply a migration:

```powershell
\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe your change"
\.venv\Scripts\python.exe -m alembic upgrade head
```

Review each file in `migrations/versions/` before applying it. This project assumes the existing `product` table is already present; a fresh database needs its initial table created separately.

The API runs at `http://127.0.0.1:8000`. Interactive API docs are at `http://127.0.0.1:8000/docs`.

## User authentication

User accounts are managed separately under `app/users/`. Passwords are hashed with Argon2; login returns a bearer token. The API expects an existing `users` table, created by migration:

```powershell
\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "add users table"
\.venv\Scripts\python.exe -m alembic upgrade head
```

Register with `POST /api/v1/users/register`:

```json
{
  "username": "alice",
  "password": "a-long-password"
}
```

Log in with `POST /api/v1/users/login` using the same JSON shape. Send the returned `access_token` as `Authorization: Bearer <token>` to the authenticated account routes:

- `GET /api/v1/users/me` reads your account.
- `PUT /api/v1/users/me` updates your username with `{"username": "new-name"}`.
- `DELETE /api/v1/users/me` deletes your account.
- `POST /api/v1/users/reset-password` changes your password with `{"current_password": "old", "new_password": "new"}`.
- `POST /api/v1/users/forgot-password` resets a user's password using the configured admin reset token. Request body: `{"username": "alice", "admin_token": "your-admin-reset-token", "new_password": "new"}`.

The self-service password endpoint requires the current password. Keep the admin reset token private; anyone holding it can reset accounts. This admin-token reset is intended for controlled development/admin use, not public self-service recovery.

## Endpoints

- `GET /health`
- `POST /api/v1/products`
- `GET /api/v1/products`
- `GET /api/v1/products/{product_id}`
- `PUT /api/v1/products/{product_id}`
- `DELETE /api/v1/products/{product_id}`

POST and PUT request body:

```json
{
  "productname": "Notebook",
  "description": "A lined notebook"
}
```

## Project layout

```text
app/
  routers/
    products.py
  users/
    models.py
    router.py
    schemas.py
  database.py
  main.py
  models.py
  schemas.py
requirements.txt
alembic.ini
migrations/
.env.example
.gitignore
README.md
```
