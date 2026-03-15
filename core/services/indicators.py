import json
import logging
from urllib.error import URLError
from urllib.request import urlopen

from django.core.cache import cache

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - fallback until dependency is installed
    requests = None


logger = logging.getLogger(__name__)

CACHE_KEY = 'core.indicadores.economicos'
LAST_SUCCESS_CACHE_KEY = 'core.indicadores.economicos.last_success'
CACHE_TIMEOUT = 900
LAST_SUCCESS_CACHE_TIMEOUT = 86400
REFRESH_COMMAND_NOTICE = 'Ejecuta "python manage.py refresh_indicadores" para recalentar la caché.'
DEFAULT_INDICADORES = {
    'uf': 'N/D',
    'dolar': 'N/D',
    'utm': 'N/D',
}
API_URL = 'https://mindicador.cl/api'
REQUEST_TIMEOUT = 3


def _fetch_payload():
    if requests is not None:
        response = requests.get(API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    with urlopen(API_URL, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode('utf-8'))


def _build_indicadores(payload):
    datos = DEFAULT_INDICADORES.copy()

    datos['uf'] = payload.get('uf', {}).get('valor', 'N/D')
    datos['dolar'] = payload.get('dolar', {}).get('valor', 'N/D')
    datos['utm'] = payload.get('utm', {}).get('valor', 'N/D')
    return datos


def refrescar_indicadores():
    try:
        payload = _fetch_payload()
    except (
        URLError,
        TimeoutError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        AttributeError,
    ) as exc:
        logger.warning('No se pudieron obtener indicadores externos: %s', exc)
        return cache.get(LAST_SUCCESS_CACHE_KEY, DEFAULT_INDICADORES.copy())
    except Exception as exc:
        logger.warning('No se pudieron obtener indicadores externos: %s', exc)
        return cache.get(LAST_SUCCESS_CACHE_KEY, DEFAULT_INDICADORES.copy())

    datos = _build_indicadores(payload)
    cache.set(CACHE_KEY, datos, CACHE_TIMEOUT)
    cache.set(LAST_SUCCESS_CACHE_KEY, datos, LAST_SUCCESS_CACHE_TIMEOUT)
    return datos


def obtener_indicadores(solo_cache=False):
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    if solo_cache:
        logger.info('Indicadores no disponibles en caché. %s', REFRESH_COMMAND_NOTICE)
        return cache.get(LAST_SUCCESS_CACHE_KEY, DEFAULT_INDICADORES.copy())

    return refrescar_indicadores()
