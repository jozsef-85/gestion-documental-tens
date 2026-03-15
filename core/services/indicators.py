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
CACHE_TIMEOUT = 900
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


def obtener_indicadores():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    datos = DEFAULT_INDICADORES.copy()

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
        return datos
    except Exception as exc:
        logger.warning('No se pudieron obtener indicadores externos: %s', exc)
        return datos

    datos['uf'] = payload.get('uf', {}).get('valor', 'N/D')
    datos['dolar'] = payload.get('dolar', {}).get('valor', 'N/D')
    datos['utm'] = payload.get('utm', {}).get('valor', 'N/D')
    cache.set(CACHE_KEY, datos, CACHE_TIMEOUT)
    return datos
