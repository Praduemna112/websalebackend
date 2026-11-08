import sys
from django.apps import AppConfig


class WebSaleAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"
    verbose_name = "WebSale App"

    def ready(self):
        if any(cmd in sys.argv for cmd in ["makemigrations", "migrate", "collectstatic"]):
            return
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'categories' AND COLUMN_NAME = 'is_active'"
                )
                row = cursor.fetchone()
                if row and row[0] == 0:
                    cursor.execute(
                        "ALTER TABLE `categories` ADD COLUMN `is_active` TINYINT(1) NOT NULL DEFAULT 1"
                    )
        except Exception:
            pass
