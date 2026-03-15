import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Auditoria, CargaPresupuesto, Departamento, Documento, RegistroPresupuesto, TipoDocumento


class EnlaceDocumentoPresupuestoTests(TestCase):
    def test_documento_y_presupuesto_se_pueden_vincular(self):
        usuario = User.objects.create(username='tester')
        depto = Departamento.objects.create(nombre='Operaciones')
        tipo = TipoDocumento.objects.create(nombre='Factura')
        carga = CargaPresupuesto.objects.create(
            nombre='Carga demo',
            hoja='Hoja1',
            total_registros=1,
            creado_por=usuario,
            archivo='presupuestos/demo.xlsx',
        )
        registro = RegistroPresupuesto.objects.create(
            carga=carga,
            fila_origen=2,
            presupuesto='PRES-001',
            descripcion='Trabajo demo',
        )
        documento = Documento.objects.create(
            titulo='Factura demo',
            tipo_documento=tipo,
            departamento=depto,
            archivo_actual='documentos/factura.pdf',
            creado_por=usuario,
        )

        documento.presupuestos.add(registro)

        self.assertEqual(documento.presupuestos.count(), 1)
        self.assertEqual(registro.documentos.count(), 1)


class SubirVersionViewTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override.enable()

        self.usuario = User.objects.create_user(username='editor', password='secreta123')
        permiso = Permission.objects.get(codename='add_versiondocumento')
        self.usuario.user_permissions.add(permiso)
        self.client.force_login(self.usuario)

        self.departamento = Departamento.objects.create(nombre='Operaciones')
        self.tipo = TipoDocumento.objects.create(nombre='Procedimiento')
        self.documento = Documento.objects.create(
            titulo='Documento base',
            tipo_documento=self.tipo,
            departamento=self.departamento,
            archivo_actual='documentos/base.pdf',
            creado_por=self.usuario,
        )

    def tearDown(self):
        self.override.disable()
        self.temp_media.cleanup()

    def test_subir_version_actualiza_documento_y_registra_auditoria(self):
        archivo = SimpleUploadedFile('actualizado.pdf', b'pdf-content', content_type='application/pdf')

        response = self.client.post(reverse('subir_version', args=[self.documento.id]), {
            'numero_version': '2.0',
            'archivo': archivo,
            'comentario': 'Ajuste operativo',
        })

        self.assertRedirects(response, reverse('listar_documentos'))
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.version_actual, '2.0')
        self.assertEqual(self.documento.versiones.count(), 1)
        self.assertTrue(
            Auditoria.objects.filter(
                entidad='Documento',
                entidad_id=self.documento.id,
                accion='Nueva versión',
            ).exists()
        )

    def test_subir_version_inexistente_retorna_404(self):
        response = self.client.get(reverse('subir_version', args=[9999]))

        self.assertEqual(response.status_code, 404)

    def test_subir_version_sin_permiso_retorna_403(self):
        usuario = User.objects.create_user(username='lector', password='secreta123')
        self.client.force_login(usuario)

        response = self.client.get(reverse('subir_version', args=[self.documento.id]))

        self.assertEqual(response.status_code, 403)


class DashboardViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='dashboard', password='secreta123')
        self.client.force_login(self.usuario)
        self.carga = CargaPresupuesto.objects.create(
            nombre='Carga dashboard',
            hoja='Hoja1',
            total_registros=2,
            creado_por=self.usuario,
            archivo='presupuestos/dashboard.xlsx',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=1,
            presupuesto='PEND-001',
            descripcion='Trabajo aceptado sin pago',
            nota_pedido='OC-123',
            valor='250000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=2,
            presupuesto='PAG-001',
            descripcion='Trabajo pagado',
            nota_pedido='OC-124',
            valor='180000',
            fecha_pago_texto='10/03/2026',
        )

    @patch('core.views_dashboard.obtener_indicadores', return_value={'uf': 'N/D', 'dolar': 'N/D', 'utm': 'N/D'})
    def test_dashboard_muestra_alerta_pendientes_por_cobrar(self, _mock_indicadores):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pendientes por cobrar')
        self.assertContains(response, 'Trabajos aceptados con nota de pedido que aún no pasan a estado pagado.')
        self.assertNotContains(response, 'Pendientes de aprobación')
