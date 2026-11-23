"""Django settings. Everything configurable comes from environment variables
(or the repo-root .env file, loaded below without extra dependencies)."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader: KEY=VALUE lines; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(REPO_ROOT / ".env")


def db_config_from_url(url: str) -> dict:
    u = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": unquote(u.username or ""),
        "PASSWORD": unquote(u.password or ""),
        "HOST": u.hostname or "localhost",
        "PORT": str(u.port or 5432),
    }


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "energy",
    "agent",
]

MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://wattwhere:wattwhere@localhost:5433/wattwhere"
)
READONLY_DATABASE_URL = os.environ.get(
    "READONLY_DATABASE_URL", "postgres://wattwhere_ro:wattwhere_ro@localhost:5433/wattwhere"
)
DATABASES = {"default": db_config_from_url(DATABASE_URL)}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"

# Region (Bundesland) the app covers
REGION_LAND_PREFIX = os.environ.get("REGION_LAND_PREFIX", "08")
REGION_NAME = os.environ.get("REGION_NAME", "Baden-Württemberg")

# LLM
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

# Chat endpoint limits
CHAT_MAX_BODY_BYTES = 64 * 1024
CHAT_MAX_HISTORY = 20
DATA_UPLOAD_MAX_MEMORY_SIZE = CHAT_MAX_BODY_BYTES
