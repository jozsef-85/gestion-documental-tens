from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, TestCase

from core.models import Auditoria
from core.services.audit import registrar_auditoria
from core.services.indicators import DEFAULT_INDICADORES, obtener_indicadores, refrescar_indicadores
from core.services.roles import sync_role_groups_permissions


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

    def test_solo_cache_no_sale_a_red_en_cache_miss(self):
        with patch('core.services.indicators._fetch_payload') as mocked_fetch:
            indicadores = obtener_indicadores(solo_cache=True)

        self.assertEqual(indicadores, DEFAULT_INDICADORES)
        mocked_fetch.assert_not_called()

    def test_refrescar_indicadores_reutiliza_ultimo_valor_exitoso_si_falla_api(self):
        cache.set(
            'core.indicadores.economicos.last_success',
            {'uf': 39400, 'dolar': 1005, 'utm': 70300},
            86400,
        )

        with patch('core.services.indicators._fetch_payload', side_effect=OSError('sin red')):
            indicadores = refrescar_indicadores()

        self.assertEqual(indicadores['uf'], 39400)
        self.assertEqual(indicadores['utm'], 70300)

    def test_solo_cache_retorna_ultimo_valor_exitoso_si_existe(self):
        cache.set(
            'core.indicadores.economicos.last_success',
            {'uf': 39500, 'dolar': 1010, 'utm': 70400},
            86400,
        )

        with patch('core.services.indicators._fetch_payload') as mocked_fetch:
            indicadores = obtener_indicadores(solo_cache=True)

        self.assertEqual(indicadores['dolar'], 1010)
        mocked_fetch.assert_not_called()

    def test_refrescar_indicadores_actualiza_cache(self):
        payload = {'uf': {'valor': 39200}, 'dolar': {'valor': 995}, 'utm': {'valor': 70100}}

        with patch('core.services.indicators._fetch_payload', return_value=payload) as mocked_fetch:
            indicadores = refrescar_indicadores()

        self.assertEqual(indicadores['uf'], 39200)
        self.assertEqual(cache.get('core.indicadores.economicos')['utm'], 70100)
        mocked_fetch.assert_called_once()

    def test_management_command_refresca_indicadores(self):
        with patch('core.management.commands.refresh_indicadores.refrescar_indicadores', return_value={
            'uf': 39300,
            'dolar': 1000,
            'utm': 70200,
        }) as mocked_refresh:
            out = []
            call_command('refresh_indicadores', stdout=self._build_stdout(out))

        mocked_refresh.assert_called_once()
        self.assertTrue(any('Indicadores actualizados' in line for line in out))

    def _build_stdout(self, lines):
        class Recorder:
            def write(self, text):
                lines.append(text)

        return Recorder()


class AuditoriaServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

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
        self.assertTrue(any('La auditoría está fallando' in line for line in captured.output))

    def test_alerta_critica_de_auditoria_se_emite_una_sola_vez_por_ventana(self):
        usuario = User.objects.create(username='audit-user')
        request = RequestFactory().get('/')
        request.user = usuario

        with patch('core.services.audit.Auditoria.objects.create', side_effect=RuntimeError('sin espacio')):
            with self.assertLogs('security', level='ERROR') as captured:
                registrar_auditoria(request, 'Prueba', 'Documento', 7, 'Registro de prueba')
                registrar_auditoria(request, 'Prueba', 'Documento', 7, 'Registro de prueba')

        mensajes_criticos = [line for line in captured.output if 'La auditoría está fallando' in line]
        self.assertEqual(len(mensajes_criticos), 1)


class RolesServiceTests(TestCase):
    def test_sync_role_groups_permissions_configura_editores_y_lectores(self):
        grupos = sync_role_groups_permissions()

        self.assertSetEqual(set(grupos.keys()), {'Administradores', 'Editores', 'Lectores'})

        editores = Group.objects.get(name='Editores')
        lectores = Group.objects.get(name='Lectores')
        admins = Group.objects.get(name='Administradores')

        self.assertTrue(editores.permissions.filter(codename='view_registropresupuesto').exists())
        self.assertTrue(editores.permissions.filter(codename='change_registropresupuesto').exists())
        self.assertTrue(editores.permissions.filter(codename='add_asignaciontrabajo').exists())
        self.assertFalse(editores.permissions.filter(codename='delete_cliente').exists())

        self.assertTrue(lectores.permissions.filter(codename='view_documento').exists())
        self.assertFalse(lectores.permissions.filter(codename='change_registropresupuesto').exists())

        self.assertGreater(admins.permissions.count(), editores.permissions.count())
