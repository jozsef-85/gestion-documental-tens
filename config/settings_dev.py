from decouple import config

from .settings_base import *  # noqa: F401,F403


DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = split_csv(config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1'))
CSRF_TRUSTED_ORIGINS = split_csv(
    config(
        'DJANGO_CSRF_TRUSTED_ORIGINS',
        default='http://localhost:8000,http://127.0.0.1:8000',
    )
)

EMAIL_BACKEND = config('DJANGO_EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
