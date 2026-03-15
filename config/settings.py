import os
import sys


ENVIRONMENT_ALIASES = {
    'dev': 'development',
    'development': 'development',
    'prod': 'production',
    'production': 'production',
    'test': 'test',
    'testing': 'test',
}


environment = os.getenv('DJANGO_ENV', '').strip().lower()
if not environment and len(sys.argv) > 1 and sys.argv[1] == 'test':
    environment = 'test'

environment = ENVIRONMENT_ALIASES.get(environment, 'development')

if environment == 'production':
    from .settings_prod import *  # noqa: F401,F403
elif environment == 'test':
    from .settings_test import *  # noqa: F401,F403
else:
    from .settings_dev import *  # noqa: F401,F403
