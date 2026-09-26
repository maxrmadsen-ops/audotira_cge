"""Configuração Django da fundação. Segredos vêm somente do ambiente."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from aplicacao.configuracao.versao import NOME_APLICACAO

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _ambiente(nome: str, padrao: str = "") -> str:
    return os.environ.get(nome, padrao).strip()


def _ambiente_bool(nome: str, padrao: bool = False) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _lista(nome: str, padrao: str = "") -> list[str]:
    return [item.strip() for item in _ambiente(nome, padrao).split(",") if item.strip()]


def _backend_resultados(url_redis: str) -> str:
    if url_redis.endswith("/0"):
        return f"{url_redis[:-1]}1"
    base, _, _ = url_redis.rpartition("/")
    return f"{base}/1" if base else url_redis


SECRET_KEY = _ambiente("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("Defina SECRET_KEY no ambiente.")

DEBUG = _ambiente_bool("DEBUG", False)
ALLOWED_HOSTS = _lista("ALLOWED_HOSTS", "localhost,127.0.0.1")
if len(sys.argv) > 1 and sys.argv[1] == "test" and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

CSRF_TRUSTED_ORIGINS = _lista("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "aplicacao.usuarios.apps.UsuariosConfig",
    "aplicacao.auditoria.apps.AuditoriaConfig",
    "aplicacao.painel.apps.PainelConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "aplicacao.configuracao.urls"
WSGI_APPLICATION = "aplicacao.configuracao.wsgi.application"
ASGI_APPLICATION = "aplicacao.configuracao.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "aplicacao" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "aplicacao.painel.contexto.interface",
            ],
        },
    },
]

AUTH_USER_MODEL = "usuarios.Usuario"
LOGIN_URL = "painel:entrar"
LOGIN_REDIRECT_URL = "painel:inicio"
LOGOUT_REDIRECT_URL = "painel:entrar"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _ambiente("DB_NAME", "cge"),
        "USER": _ambiente("DB_USER", "cge"),
        "PASSWORD": _ambiente("DB_PASSWORD"),
        "HOST": _ambiente("DB_HOST", "cge_banco"),
        "PORT": _ambiente("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

if not DATABASES["default"]["PASSWORD"]:
    raise ImproperlyConfigured("Defina DB_PASSWORD no ambiente.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "aplicacao" / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
ARQUIVOS_RAIZ = BASE_DIR / "arquivos"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = _ambiente("REDIS_URL", "redis://cge_redis:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = _backend_resultados(REDIS_URL)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULE = {
    "verificacao-periodica-fundacao": {
        "task": "painel.verificar_operacionalidade",
        "schedule": 300.0,
    },
}

if len(sys.argv) > 1 and sys.argv[1] == "test":
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    DATABASES["default"]["CONN_MAX_AGE"] = 0

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "padrao",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "cge.auditoria": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

NOME_SISTEMA = NOME_APLICACAO
