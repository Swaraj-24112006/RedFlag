import os

from .base import *

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Database configuration: env-driven with SQLite fallback for quick local evaluation
DB_NAME = os.environ.get("DATABASE_NAME") or os.environ.get("POSTGRES_DB")
DB_USER = os.environ.get("DATABASE_USER") or os.environ.get("POSTGRES_USER")
DB_PASSWORD = os.environ.get("DATABASE_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")
DB_HOST = os.environ.get("DATABASE_HOST") or os.environ.get("POSTGRES_HOST") or "localhost"
DB_PORT = os.environ.get("DATABASE_PORT") or os.environ.get("POSTGRES_PORT", "5432")

if DB_NAME and DB_USER:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DB_NAME,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
