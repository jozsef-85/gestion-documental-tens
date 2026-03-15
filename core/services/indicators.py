import json
import logging
from urllib.error import URLError
from urllib.request import urlopen

from django.core.cache import cache


logger = logging.getLogger(__name__)

CACHE_KEY = 'core.indicadores.economicos'
CACHE_TIMEOUT = 900
DEFAULT_INDICADORES = {
    'uf': 'N/D',
    'dolar': 'N/D',
    'utm': 'N/D',
}


def obtener_indicadores():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    datos = DEFAULT_INDICADORES.copy()

    try:
        with urlopen('https://mindicador.cl/api', timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning('No se pudieron obtener indicadores externos: %s', exc)
        return datos

    datos['uf'] = payload.get('uf', {}).get('valor', 'N/D')
    datos['dolar'] = payload.get('dolar', {}).get('valor', 'N/D')
    datos['utm'] = payload.get('utm', {}).get('valor', 'N/D')
    cache.set(CACHE_KEY, datos, CACHE_TIMEOUT)
    return datos
