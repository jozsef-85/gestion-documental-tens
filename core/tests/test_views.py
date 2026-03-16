import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    AsignacionTrabajo,
    Auditoria,
    CargaPresupuesto,
    Cliente,
    Departamento,
    Documento,
    PersonalTrabajo,
    RegistroPresupuesto,
    TipoDocumento,
    TrabajoPresupuesto,
)


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
        permiso_version = Permission.objects.get(codename='add_versiondocumento')
        permiso_documento = Permission.objects.get(codename='view_documento')
        self.usuario.user_permissions.add(permiso_version, permiso_documento)
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


class SubirDocumentoViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='documentador', password='secreta123')
        permisos = Permission.objects.filter(codename__in=['add_documento', 'view_registropresupuesto'])
        self.usuario.user_permissions.add(*permisos)
        self.client.force_login(self.usuario)
        self.cliente = Cliente.objects.create(nombre='Constructora Norte', creado_por=self.usuario)
        self.carga = CargaPresupuesto.objects.create(
            nombre='Carga documentos',
            hoja='Hoja1',
            total_registros=1,
            creado_por=self.usuario,
            archivo='presupuestos/documentos.xlsx',
        )
        self.registro = RegistroPresupuesto.objects.create(
            carga=self.carga,
            cliente=self.cliente,
            fila_origen=1,
            presupuesto='OBRA-001',
            tipo_trabajo='instalacion',
            ubicacion_obra='Edificio Centro',
            descripcion='Instalacion de tablero general',
        )

    def test_subir_documento_prefija_registro_relacionado_desde_el_historial(self):
        response = self.client.get(reverse('subir_documento'), {'registro_id': self.registro.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OBRA-001')
        self.assertContains(response, 'Constructora Norte')
        self.assertEqual(response.context['registro_relacionado'], self.registro)
        self.assertEqual(response.context['form']['presupuestos'].value(), [self.registro.id])


class DashboardViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='dashboard', password='secreta123')
        permiso = Permission.objects.get(codename='view_registropresupuesto')
        self.usuario.user_permissions.add(permiso)
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
            monto='250000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=2,
            presupuesto='PAG-001',
            descripcion='Trabajo pagado',
            nota_pedido='OC-124',
            monto='180000',
            fecha_facturacion_texto='08/03/2026',
            fecha_pago_texto='10/03/2026',
        )

    @patch('core.views_dashboard.obtener_indicadores', return_value={'uf': 'N/D', 'dolar': 'N/D', 'utm': 'N/D'})
    def test_dashboard_muestra_alerta_pendientes_por_cobrar(self, _mock_indicadores):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pendientes por cobrar')
        self.assertContains(response, f'{reverse("listar_presupuestos")}?estado=por_cobrar')
        self.assertContains(response, 'Fecha de facturación')
        self.assertContains(response, 'Trabajos aceptados o realizados que aún no pasan a estado pagado.')
        self.assertNotContains(response, 'Pendientes de aprobación')
        self.assertContains(response, 'Solo incluye presupuestos actualmente en curso.')
        self.assertEqual([registro.presupuesto for registro in response.context['dashboard_registros']], ['PEND-001'])

    def test_dashboard_requiere_permiso_de_acceso(self):
        self.client.logout()
        usuario = User.objects.create_user(username='sinpermiso', password='secreta123')
        self.client.force_login(usuario)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'No tienes acceso a esta operación', status_code=403)

    @patch('core.views_dashboard.obtener_indicadores', return_value={'uf': 'N/D', 'dolar': 'N/D', 'utm': 'N/D'})
    def test_dashboard_respeta_estado_manual_en_totales(self, _mock_indicadores):
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=3,
            presupuesto='MANUAL-PEND',
            nota_pedido='OC-125',
            estado_manual='pendiente',
            monto='500000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=4,
            presupuesto='MANUAL-FACT',
            nota_pedido='OC-126',
            estado_manual='facturado',
            monto='900000',
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_con_nota_pedido'], 3)
        self.assertEqual(response.context['total_pendientes_por_cobrar'], 2)
        self.assertEqual(response.context['total_monto_por_cobrar'], 1150000)


class ListadoClientesAccessTests(TestCase):
    def test_listar_clientes_requiere_permiso_del_modelo(self):
        usuario = User.objects.create_user(username='sinpermiso_clientes', password='secreta123')
        self.client.force_login(usuario)

        with self.assertLogs('security', level='WARNING') as captured:
            response = self.client.get(reverse('listar_clientes'))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(any('Permiso insuficiente' in line for line in captured.output))

    def test_listar_documentos_acepta_permiso_view(self):
        usuario = User.objects.create_user(username='lector_documentos', password='secreta123')
        permiso = Permission.objects.get(codename='view_documento')
        usuario.user_permissions.add(permiso)
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_documentos'))

        self.assertEqual(response.status_code, 200)


class ControlPresupuestosViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='presupuestos', password='secreta123')
        permisos = Permission.objects.filter(
            codename__in=['view_registropresupuesto', 'change_registropresupuesto', 'add_asignaciontrabajo']
        )
        self.usuario.user_permissions.add(*permisos)
        self.client.force_login(self.usuario)
        self.carga = CargaPresupuesto.objects.create(
            nombre='Carga control',
            hoja='Hoja1',
            total_registros=2,
            creado_por=self.usuario,
            archivo='presupuestos/control.xlsx',
        )
        self.registro_pendiente = RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=1,
            presupuesto='PRES-PEND',
            descripcion='Pendiente',
        )
        self.registro_en_proceso = RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=2,
            presupuesto='PRES-ACEP',
            descripcion='Aceptado',
            nota_pedido='OC-999',
            monto='800000',
        )
        self.trabajador = PersonalTrabajo.objects.create(
            nombre='Ana Perez',
            cargo='Tecnica',
            area='Operaciones',
            activo=True,
        )
        self.cliente = Cliente.objects.create(nombre='Constructora Sur')

    def test_listar_presupuestos_gestion_expone_resumen(self):
        with patch('core.views_control_presupuestos.render') as mocked_render:
            mocked_render.side_effect = lambda request, template, context: HttpResponse('ok')

            response = self.client.get(reverse('listar_presupuestos_gestion'))

        self.assertEqual(response.status_code, 200)
        template_name = mocked_render.call_args.args[1]
        context = mocked_render.call_args.args[2]
        self.assertEqual(template_name, 'listar_presupuestos_gestion.html')
        self.assertEqual(context['total_presupuestos'], 2)
        self.assertEqual(context['total_pendientes_aprobacion'], 1)
        self.assertEqual(context['total_aceptados'], 1)
        self.assertEqual(context['monto_por_cobrar'], 800000)

    def test_editar_presupuesto_actualiza_registro_y_auditoria(self):
        response = self.client.post(
            reverse('editar_presupuesto', args=[self.registro_pendiente.id]),
            {
                'presupuesto': 'PRES-PEND',
                'cliente': self.cliente.id,
                'tipo_trabajo': 'mantencion',
                'ubicacion_obra': 'Faena San Pedro',
                'descripcion': 'Pendiente actualizado',
                'solicitante': 'Usuario Control',
                'monto': '250000',
                'fecha_texto': '17/01/2025',
                'nota_pedido': 'OC-321',
                'estado_oc': 'En curso',
                'observacion_oc': 'Observacion',
                'recepcion': 'Recepción parcial',
                'estado_recepcion': 'Parcial',
                'guia_despacho': 'GD-55',
                'factura': '',
                'fecha_facturacion_texto': '',
                'fecha_pago_texto': '',
                'estado_manual': '',
                'observaciones': 'Seguimiento actualizado',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('historial_presupuesto', args=[self.registro_pendiente.id]))

        self.registro_pendiente.refresh_from_db()
        self.assertEqual(self.registro_pendiente.cliente, self.cliente)
        self.assertEqual(self.registro_pendiente.tipo_trabajo, 'mantencion')
        self.assertEqual(self.registro_pendiente.ubicacion_obra, 'Faena San Pedro')
        self.assertEqual(self.registro_pendiente.nota_pedido, 'OC-321')
        self.assertEqual(self.registro_pendiente.descripcion, 'Pendiente actualizado')
        self.assertEqual(self.registro_pendiente.estado_oc, 'En curso')
        self.assertEqual(self.registro_pendiente.estado_seguimiento, 'Aceptado / En curso')
        self.assertTrue(
            Auditoria.objects.filter(
                entidad='RegistroPresupuesto',
                entidad_id=self.registro_pendiente.id,
                accion='Edicion de control',
            ).exists()
        )
        self.assertIsNotNone(self.registro_pendiente.trabajo)
        self.assertEqual(self.registro_pendiente.trabajo.presupuesto, 'PRES-PEND')

    def test_historial_presupuesto_permite_vincular_trabajador(self):
        trabajo = TrabajoPresupuesto.objects.create(presupuesto=self.registro_en_proceso.presupuesto)
        self.registro_en_proceso.trabajo = trabajo
        self.registro_en_proceso.save(update_fields=['trabajo'])

        response = self.client.post(
            reverse('historial_presupuesto', args=[self.registro_en_proceso.id]),
            {
                'trabajador': self.trabajador.id,
                'rol': 'Supervisor en terreno',
                'estado': 'activo',
                'fecha_inicio': '2026-03-15',
                'fecha_fin': '',
                'horas_estimadas': '16',
                'horas_reales': '',
                'observaciones': 'Coordina la ejecucion del servicio',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('historial_presupuesto', args=[self.registro_en_proceso.id]))
        self.assertTrue(
            AsignacionTrabajo.objects.filter(
                trabajo=trabajo,
                trabajador=self.trabajador,
                rol='Supervisor en terreno',
            ).exists()
        )
        self.assertTrue(
            Auditoria.objects.filter(
                entidad='TrabajoPresupuesto',
                entidad_id=trabajo.id,
                accion='Asignacion de personal',
            ).exists()
        )

    def test_listar_presupuestos_filtra_pendientes_por_cobrar(self):
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=3,
            presupuesto='PRES-FACT',
            descripcion='Facturado',
            nota_pedido='OC-333',
            factura='FAC-333',
            monto='500000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=4,
            presupuesto='PRES-PAG',
            descripcion='Pagado',
            nota_pedido='OC-444',
            fecha_pago_texto='15/03/2026',
            monto='400000',
        )

        response = self.client.get(reverse('listar_presupuestos'), {'estado': 'por_cobrar'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PRES-ACEP')
        self.assertContains(response, 'PRES-FACT')
        self.assertNotContains(response, 'PRES-PAG')


class TemplateSmokeTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='smoke', password='secreta123')
        permisos = Permission.objects.filter(
            codename__in=['view_cliente', 'view_personaltrabajo', 'view_registropresupuesto', 'view_documento']
        )
        self.usuario.user_permissions.add(*permisos)
        self.client.force_login(self.usuario)
        self.carga = CargaPresupuesto.objects.create(
            nombre='Carga smoke',
            hoja='Hoja1',
            total_registros=1,
            creado_por=self.usuario,
            archivo='presupuestos/smoke.xlsx',
        )
        self.registro = RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=1,
            presupuesto='PRES-SMOKE',
            descripcion='Smoke',
            monto='1000',
        )
        departamento = Departamento.objects.create(nombre='Calidad smoke')
        tipo = TipoDocumento.objects.create(nombre='Procedimiento smoke')
        Documento.objects.create(
            titulo='Documento smoke',
            tipo_documento=tipo,
            departamento=departamento,
            archivo_actual='documentos/smoke.pdf',
            creado_por=self.usuario,
        )

    def test_rutas_principales_con_plantillas_nuevas_renderizan(self):
        rutas = [
            reverse('listar_clientes'),
            reverse('listar_personal'),
            reverse('listar_presupuestos_gestion'),
            reverse('listar_presupuestos'),
            reverse('historial_presupuesto', args=[self.registro.id]),
            reverse('listar_documentos'),
        ]

        for ruta in rutas:
            response = self.client.get(ruta)
            self.assertEqual(response.status_code, 200, ruta)


@override_settings(LOGIN_RATE_LIMIT_ATTEMPTS=2, LOGIN_RATE_LIMIT_WINDOW=60)
class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user(username='acceso', password='clave-segura-123')

    def test_bloquea_login_tras_demasiados_intentos_fallidos(self):
        url = reverse('login')

        self.client.post(url, {'username': 'acceso', 'password': 'incorrecta'}, REMOTE_ADDR='10.0.0.1')
        with self.assertLogs('security', level='WARNING') as captured:
            response = self.client.post(url, {'username': 'acceso', 'password': 'incorrecta'}, REMOTE_ADDR='10.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Demasiados intentos de acceso fallidos')
        self.assertTrue(any('Login paso a estado bloqueado' in line for line in captured.output))

        response = self.client.post(url, {'username': 'acceso', 'password': 'clave-segura-123'}, REMOTE_ADDR='10.0.0.1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Demasiados intentos de acceso fallidos')

    def test_login_exitoso_limpia_contador_de_intentos(self):
        url = reverse('login')

        self.client.post(url, {'username': 'acceso', 'password': 'incorrecta'}, REMOTE_ADDR='10.0.0.2')
        response = self.client.post(url, {'username': 'acceso', 'password': 'clave-segura-123'}, REMOTE_ADDR='10.0.0.2')

        self.assertEqual(response.status_code, 302)

        self.client.logout()
        response = self.client.post(url, {'username': 'acceso', 'password': 'incorrecta'}, REMOTE_ADDR='10.0.0.2')

        self.assertNotContains(response, 'Demasiados intentos de acceso fallidos')
