import os
from pathlib import Path

from decouple import config


def split_csv(value):
    return [item.strip() for item in str(value).split(',') if item.strip()]


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_STORAGE_ROOT = BASE_DIR.parent if (BASE_DIR.parent / 'media').exists() or (BASE_DIR.parent / 'static').exists() else BASE_DIR
CURRENT_ENVIRONMENT = os.getenv('DJANGO_ENV', 'development').strip().lower() or 'development'
IS_PRODUCTION = CURRENT_ENVIRONMENT in {'prod', 'production'}


SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-local-development-key-change-me')
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = split_csv(config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1'))
CSRF_TRUSTED_ORIGINS = split_csv(config('DJANGO_CSRF_TRUSTED_ORIGINS', default=''))

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


db_engine = config('DJANGO_DB_ENGINE', default='postgresql').strip().lower()
if db_engine in {'sqlite', 'sqlite3', 'django.db.backends.sqlite3'}:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': config('DJANGO_DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
        }
    }
else:
    backend = db_engine if db_engine.startswith('django.db.backends.') else f'django.db.backends.{db_engine}'
    DATABASES = {
        'default': {
            'ENGINE': backend,
            'NAME': config('DJANGO_DB_NAME', default='gestion_documental'),
            'USER': config('DJANGO_DB_USER', default='gestdoc_user'),
            'PASSWORD': config('DJANGO_DB_PASSWORD', default='gestdoc_password'),
            'HOST': config('DJANGO_DB_HOST', default='localhost'),
            'PORT': config('DJANGO_DB_PORT', default='5432'),
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True


STATIC_URL = '/static/'
STATIC_ROOT = config('DJANGO_STATIC_ROOT', default=str(DEFAULT_STORAGE_ROOT / 'static'))

MEDIA_URL = '/media/'
MEDIA_ROOT = config('DJANGO_MEDIA_ROOT', default=str(DEFAULT_STORAGE_ROOT / 'media'))


LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
CSRF_FAILURE_VIEW = 'core.views_errors.csrf_failure'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_RATE_LIMIT_ATTEMPTS = config('DJANGO_LOGIN_RATE_LIMIT_ATTEMPTS', default=5, cast=int)
LOGIN_RATE_LIMIT_WINDOW = config('DJANGO_LOGIN_RATE_LIMIT_WINDOW', default=900, cast=int)
LOG_LEVEL = config('DJANGO_LOG_LEVEL', default='INFO')
SECURITY_LOG_LEVEL = config('DJANGO_SECURITY_LOG_LEVEL', default='WARNING')
LOG_TO_FILE = config('DJANGO_LOG_TO_FILE', default=IS_PRODUCTION, cast=bool)
LOG_TO_CONSOLE = config('DJANGO_LOG_TO_CONSOLE', default=not IS_PRODUCTION, cast=bool)
LOG_DIR = Path(config('DJANGO_LOG_DIR', default=str(DEFAULT_STORAGE_ROOT / 'logs')))
APP_LOG_FILE = config('DJANGO_APP_LOG_FILE', default='app.log')
SECURITY_LOG_FILE = config('DJANGO_SECURITY_LOG_FILE', default='security.log')
LOG_MAX_BYTES = config('DJANGO_LOG_MAX_BYTES', default=10 * 1024 * 1024, cast=int)
LOG_BACKUP_COUNT = config('DJANGO_LOG_BACKUP_COUNT', default=5, cast=int)

if LOG_TO_FILE:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

log_handlers = {}
if LOG_TO_CONSOLE:
    log_handlers['console'] = {
        'class': 'logging.StreamHandler',
        'formatter': 'standard',
    }
if LOG_TO_FILE:
    log_handlers['app_file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'formatter': 'standard',
        'filename': str(LOG_DIR / APP_LOG_FILE),
        'maxBytes': LOG_MAX_BYTES,
        'backupCount': LOG_BACKUP_COUNT,
        'encoding': 'utf-8',
    }
    log_handlers['security_file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'formatter': 'standard',
        'filename': str(LOG_DIR / SECURITY_LOG_FILE),
        'maxBytes': LOG_MAX_BYTES,
        'backupCount': LOG_BACKUP_COUNT,
        'encoding': 'utf-8',
    }

default_log_handlers = []
if LOG_TO_CONSOLE:
    default_log_handlers.append('console')
if LOG_TO_FILE:
    default_log_handlers.append('app_file')

security_log_handlers = []
if LOG_TO_CONSOLE:
    security_log_handlers.append('console')
if LOG_TO_FILE:
    security_log_handlers.append('security_file')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s %(levelname)s [%(name)s] %(message)s',
        },
    },
    'handlers': log_handlers,
    'loggers': {
        'django': {
            'handlers': default_log_handlers,
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'core': {
            'handlers': default_log_handlers,
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'security': {
            'handlers': security_log_handlers or default_log_handlers,
            'level': SECURITY_LOG_LEVEL,
            'propagate': False,
        },
    },
}
