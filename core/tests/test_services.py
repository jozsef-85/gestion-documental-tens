from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase

from core.models import Auditoria
from core.services.audit import registrar_auditoria
from core.services.indicators import DEFAULT_INDICADORES, obtener_indicadores


class IndicadoresServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_obtiene_indicadores_y_usa_cache(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"uf":{"valor":39000},"dolar":{"valor":980},"utm":{"valor":69000}}'

        with patch('core.services.indicators.urlopen', return_value=FakeResponse()) as mocked_urlopen:
            primero = obtener_indicadores()
            segundo = obtener_indicadores()

        self.assertEqual(primero['uf'], 39000)
        self.assertEqual(segundo['dolar'], 980)
        self.assertEqual(mocked_urlopen.call_count, 1)

    def test_devuelve_default_si_falla_servicio_externo(self):
        with patch('core.services.indicators.urlopen', side_effect=OSError('sin red')):
            indicadores = obtener_indicadores()

        self.assertEqual(indicadores, DEFAULT_INDICADORES)

    def test_prefiere_requests_si_esta_disponible(self):
        fake_response = type(
            'FakeResponse',
            (),
            {
                'raise_for_status': lambda self: None,
                'json': lambda self: {'uf': {'valor': 39100}, 'dolar': {'valor': 990}, 'utm': {'valor': 70000}},
            },
        )()
        fake_requests = type(
            'FakeRequests',
            (),
            {'get': staticmethod(lambda *args, **kwargs: fake_response)},
        )

        with patch('core.services.indicators.requests', fake_requests):
            indicadores = obtener_indicadores()

        self.assertEqual(indicadores['uf'], 39100)
        self.assertEqual(indicadores['dolar'], 990)


class AuditoriaServiceTests(TestCase):
    def test_prioriza_ip_forwarded_for(self):
        usuario = User.objects.create(username='audit-user')
        request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='198.51.100.10, 10.0.0.1')
        request.user = usuario

        registrar_auditoria(request, 'Prueba', 'Documento', 7, 'Registro de prueba')

        auditoria = Auditoria.objects.get()
        self.assertEqual(auditoria.ip, '198.51.100.10')

    def test_no_rompe_el_flujo_si_falla_la_auditoria(self):
        usuario = User.objects.create(username='audit-user')
        request = RequestFactory().get('/')
        request.user = usuario

        with patch('core.services.audit.Auditoria.objects.create', side_effect=RuntimeError('sin espacio')):
            with self.assertLogs('security', level='ERROR') as captured:
                registrar_auditoria(request, 'Prueba', 'Documento', 7, 'Registro de prueba')

        self.assertEqual(Auditoria.objects.count(), 0)
        self.assertTrue(any('Fallo al registrar auditoría' in line for line in captured.output))
