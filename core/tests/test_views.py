import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
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
from core.presupuestos import PresupuestoImportado, ResultadoImportacionPresupuesto


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

    def test_subir_version_rechaza_reutilizar_version_actual(self):
        archivo = SimpleUploadedFile('mismo-numero.pdf', b'pdf-content', content_type='application/pdf')

        response = self.client.post(reverse('subir_version', args=[self.documento.id]), {
            'numero_version': '1.0',
            'archivo': archivo,
            'comentario': 'Intento duplicado',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ya es la version actual')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'id="id_numero_version-error"')
        self.assertContains(response, 'id="id_numero_version-help"')
        self.assertEqual(self.documento.versiones.count(), 0)

    def test_subir_version_rechaza_numero_duplicado_en_historial(self):
        self.documento.versiones.create(
            numero_version='1.1',
            archivo=SimpleUploadedFile('version-1-1.pdf', b'pdf-content', content_type='application/pdf'),
            comentario='Primera carga',
            subido_por=self.usuario,
        )

        segundo_archivo = SimpleUploadedFile('version-1-1-bis.pdf', b'pdf-content-2', content_type='application/pdf')
        response = self.client.post(reverse('subir_version', args=[self.documento.id]), {
            'numero_version': '1.1',
            'archivo': segundo_archivo,
            'comentario': 'Carga repetida',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe una version registrada con ese numero')
        self.assertEqual(self.documento.versiones.count(), 1)

    @patch('core.views_documentos.VersionDocumento.objects.create', side_effect=IntegrityError)
    def test_subir_version_maneja_colision_concurrente_sin_error_500(self, _mocked_create):
        archivo = SimpleUploadedFile('version-2.pdf', b'pdf-content', content_type='application/pdf')

        response = self.client.post(reverse('subir_version', args=[self.documento.id]), {
            'numero_version': '2.0',
            'archivo': archivo,
            'comentario': 'Intento concurrente',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe una versión registrada con ese número.')


class SubirDocumentoViewTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override.enable()
        self.usuario = User.objects.create_user(username='documentador', password='secreta123')
        permisos = Permission.objects.filter(codename__in=['add_documento', 'view_registropresupuesto'])
        self.usuario.user_permissions.add(*permisos)
        self.client.force_login(self.usuario)
        self.departamento = Departamento.objects.create(nombre='Calidad documental')
        self.tipo = TipoDocumento.objects.create(nombre='Informe de terreno')
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

    def tearDown(self):
        self.override.disable()
        self.temp_media.cleanup()

    def test_subir_documento_prefija_registro_relacionado_desde_el_historial(self):
        response = self.client.get(reverse('subir_documento'), {'registro_id': self.registro.id})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('crear_documento')}?registro_id={self.registro.id}")

    def test_ruta_legacy_subir_documento_permanece_operativa(self):
        response = self.client.get(reverse('subir_documento_legacy'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('crear_documento'))

    def test_crear_documento_permanece_dentro_del_modulo_documentos(self):
        response = self.client.get(reverse('crear_documento'), {'registro_id': self.registro.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nuevo documento')
        self.assertContains(response, 'OBRA-001')


class EditarDocumentoViewTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override.enable()

        self.usuario = User.objects.create_user(username='editor_documento', password='secreta123')
        permiso = Permission.objects.get(codename='change_documento')
        self.usuario.user_permissions.add(permiso)
        self.client.force_login(self.usuario)
        self.departamento = Departamento.objects.create(nombre='Operaciones')
        self.tipo = TipoDocumento.objects.create(nombre='Informe')
        self.documento = Documento.objects.create(
            titulo='Documento editable',
            tipo_documento=self.tipo,
            departamento=self.departamento,
            archivo_actual=SimpleUploadedFile('base.pdf', b'base-pdf', content_type='application/pdf'),
            creado_por=self.usuario,
        )

    def tearDown(self):
        self.override.disable()
        self.temp_media.cleanup()

    def test_editar_documento_no_permite_reemplazar_archivo_directamente(self):
        archivo = SimpleUploadedFile('nuevo.pdf', b'nuevo-pdf', content_type='application/pdf')

        response = self.client.post(
            reverse('editar_documento', args=[self.documento.id]),
            {
                'titulo': 'Documento editable',
                'descripcion': 'Actualizado',
                'tipo_documento': self.tipo.id,
                'departamento': self.departamento.id,
                'estado': 'activo',
                'nivel_confidencialidad': 'media',
                'archivo_actual': archivo,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'usa &quot;Agregar versión&quot;')
        self.documento.refresh_from_db()
        self.assertIn('base.pdf', self.documento.archivo_actual.name)
        self.assertEqual(self.documento.versiones.count(), 0)


class SubirPresupuestoViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='importador', password='secreta123')
        permiso = Permission.objects.get(codename='add_cargapresupuesto')
        self.usuario.user_permissions.add(permiso)
        self.client.force_login(self.usuario)

    @patch('core.views_control_presupuestos.parsear_planilla_presupuestos')
    def test_subir_presupuesto_redirige_a_importacion_si_usuario_no_tiene_listado(self, mocked_parser):
        mocked_parser.return_value = ResultadoImportacionPresupuesto(
            hoja='Hoja1',
            registros=[
                PresupuestoImportado(
                    fila_origen=2,
                    fecha=None,
                    fecha_texto='',
                    presupuesto='PRES-IMP-001',
                    descripcion='Carga importada',
                    solicitante='Operaciones',
                    monto=None,
                    nota_pedido='',
                    estado_oc='',
                    observacion_oc='',
                    recepcion='',
                    estado_recepcion='',
                    guia_despacho='',
                    factura='',
                    fecha_facturacion=None,
                    fecha_facturacion_texto='',
                    fecha_pago=None,
                    fecha_pago_texto='',
                ),
            ],
        )
        archivo = SimpleUploadedFile(
            'control.xlsx',
            b'fake-xlsx',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post(reverse('subir_presupuesto'), {
            'nombre': 'Carga abril',
            'archivo': archivo,
        })

        self.assertRedirects(response, reverse('subir_presupuesto'))
        self.assertTrue(CargaPresupuesto.objects.filter(nombre='Carga abril').exists())


class DocumentoDownloadAccessTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override.enable()

        self.editor = User.objects.create_user(username='editor_download', password='secreta123')
        permisos_editor = Permission.objects.filter(codename__in=['view_documento', 'change_documento', 'add_versiondocumento'])
        self.editor.user_permissions.add(*permisos_editor)

        self.lector = User.objects.create_user(username='lector_download', password='secreta123')
        permiso_view = Permission.objects.get(codename='view_documento')
        self.lector.user_permissions.add(permiso_view)

        self.departamento = Departamento.objects.create(nombre='Documentos protegidos')
        self.tipo = TipoDocumento.objects.create(nombre='Informe protegido')
        self.documento_publico = Documento.objects.create(
            titulo='Checklist obra',
            tipo_documento=self.tipo,
            departamento=self.departamento,
            archivo_actual=SimpleUploadedFile('checklist.pdf', b'pdf-checklist', content_type='application/pdf'),
            nivel_confidencialidad='media',
            creado_por=self.editor,
        )
        self.documento_reservado = Documento.objects.create(
            titulo='Contrato reservado',
            tipo_documento=self.tipo,
            departamento=self.departamento,
            archivo_actual=SimpleUploadedFile('contrato.pdf', b'pdf-contrato', content_type='application/pdf'),
            nivel_confidencialidad='alta',
            creado_por=self.editor,
        )

    def tearDown(self):
        self.override.disable()
        self.temp_media.cleanup()

    def test_descargar_documento_entrega_archivo_protegido(self):
        self.client.force_login(self.editor)

        response = self.client.get(reverse('descargar_documento', args=[self.documento_publico.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'pdf-checklist')
        self.assertTrue(
            Auditoria.objects.filter(
                entidad='Documento',
                entidad_id=self.documento_publico.id,
                accion='Descarga de documento',
            ).exists()
        )

    def test_descargar_documento_alto_restringe_a_lector(self):
        self.client.force_login(self.lector)

        response = self.client.get(reverse('descargar_documento', args=[self.documento_reservado.id]))

        self.assertEqual(response.status_code, 403)

    def test_descargar_version_requiere_acceso_al_documento(self):
        self.client.force_login(self.editor)
        archivo = SimpleUploadedFile('version-2.pdf', b'pdf-version-2', content_type='application/pdf')
        self.client.post(reverse('subir_version', args=[self.documento_reservado.id]), {
            'numero_version': '2.0',
            'archivo': archivo,
            'comentario': 'Version firmada',
        })
        version = self.documento_reservado.versiones.get()

        self.client.force_login(self.lector)
        response = self.client.get(reverse('descargar_version_documento', args=[version.id]))

        self.assertEqual(response.status_code, 403)


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

    def test_dashboard_no_se_habilita_con_permiso_de_alta_sin_view(self):
        self.client.logout()
        usuario = User.objects.create_user(username='soloalta', password='secreta123')
        permiso = Permission.objects.get(codename='add_registropresupuesto')
        usuario.user_permissions.add(permiso)
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
        self.assertFalse(response.context['consulta_activa'])

    def test_listar_documentos_acepta_permiso_add_para_ingresar_al_modulo(self):
        usuario = User.objects.create_user(username='cargador_documentos', password='secreta123')
        permiso = Permission.objects.get(codename='add_documento')
        usuario.user_permissions.add(permiso)
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_documentos'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['consulta_activa'])

    def test_listar_documentos_no_carga_resultados_sin_consulta(self):
        usuario = User.objects.create_user(username='consulta_documentos', password='secreta123')
        permiso = Permission.objects.get(codename='view_documento')
        usuario.user_permissions.add(permiso)
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_documentos'))

        self.assertContains(response, 'Aún no hay una consulta aplicada.')
        self.assertNotContains(response, 'Total documentos')
        self.assertNotContains(response, 'Versiones registradas')
        self.assertEqual(len(response.context['docs']), 0)

    def test_listar_documentos_oculta_confidencialidad_alta_a_lectores(self):
        usuario = User.objects.create_user(username='lector_simple', password='secreta123')
        permiso = Permission.objects.get(codename='view_documento')
        usuario.user_permissions.add(permiso)
        departamento = Departamento.objects.create(nombre='Operaciones docs')
        tipo = TipoDocumento.objects.create(nombre='Informe tecnico')
        creador = User.objects.create_user(username='creador_docs', password='secreta123')
        Documento.objects.create(
            titulo='Informe publico',
            tipo_documento=tipo,
            departamento=departamento,
            archivo_actual='documentos/publico.pdf',
            nivel_confidencialidad='media',
            creado_por=creador,
        )
        Documento.objects.create(
            titulo='Contrato sensible',
            tipo_documento=tipo,
            departamento=departamento,
            archivo_actual='documentos/sensible.pdf',
            nivel_confidencialidad='alta',
            creado_por=creador,
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_documentos'), {'confidencialidad': 'media'})

        self.assertContains(response, 'Informe publico')
        self.assertNotContains(response, 'Contrato sensible')

    def test_historial_versiones_restringe_documento_alto_a_lector(self):
        usuario = User.objects.create_user(username='lector_historial', password='secreta123')
        permiso = Permission.objects.get(codename='view_documento')
        usuario.user_permissions.add(permiso)
        departamento = Departamento.objects.create(nombre='Calidad docs')
        tipo = TipoDocumento.objects.create(nombre='Contrato')
        creador = User.objects.create_user(username='creador_alto', password='secreta123')
        documento = Documento.objects.create(
            titulo='Convenio reservado',
            tipo_documento=tipo,
            departamento=departamento,
            archivo_actual='documentos/reservado.pdf',
            nivel_confidencialidad='alta',
            creado_por=creador,
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse('historial_versiones', args=[documento.id]))

        self.assertEqual(response.status_code, 403)

    def test_listar_clientes_no_carga_resultados_sin_consulta(self):
        usuario = User.objects.create_user(username='lector_clientes', password='secreta123')
        permiso = Permission.objects.get(codename='view_cliente')
        usuario.user_permissions.add(permiso)
        for indice in range(12):
            Cliente.objects.create(nombre=f'Cliente {indice:02d}')
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_clientes'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mostrando los 10 clientes más recientes para acceso rápido.')
        self.assertFalse(response.context['consulta_activa'])
        self.assertContains(response, 'Cliente 11')
        self.assertContains(response, 'Cliente 02')
        self.assertNotContains(response, 'Cliente 01')

    def test_listar_clientes_con_todos_muestra_listado_completo(self):
        usuario = User.objects.create_user(username='lector_clientes_todos', password='secreta123')
        permiso = Permission.objects.get(codename='view_cliente')
        usuario.user_permissions.add(permiso)
        for indice in range(12):
            Cliente.objects.create(nombre=f'Cliente filtro {indice:02d}')
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_clientes'), {'q': '', 'estado': ''})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['consulta_activa'])
        self.assertFalse(response.context['mostrando_inicial'])
        self.assertContains(response, 'Mostrando todos los clientes ordenados por nombre comercial.')
        self.assertContains(response, 'Cliente filtro 00')
        self.assertContains(response, 'Cliente filtro 11')


class FormAccessibilityViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='forms_a11y', password='secreta123')
        permisos = Permission.objects.filter(codename__in=['add_cliente'])
        self.usuario.user_permissions.add(*permisos)
        self.client.force_login(self.usuario)

    def test_crear_cliente_renderiza_campos_requeridos_con_aria(self):
        response = self.client.get(reverse('crear_cliente'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-required="true"')
        self.assertContains(response, 'id="id_nombre-help"')

    def test_crear_cliente_invalido_marca_campo_y_resumen_accesible(self):
        response = self.client.post(reverse('crear_cliente'), {
            'nombre': '',
            'rut': '',
            'contacto': '',
            'email': '',
            'telefono': '',
            'direccion': '',
            'activo': 'True',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form-error-summary')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'id="id_nombre-error"')
        self.assertContains(response, 'firstInvalidField.focus();')

    def test_listar_personal_no_carga_resultados_sin_consulta(self):
        usuario = User.objects.create_user(username='lector_personal', password='secreta123')
        permiso = Permission.objects.get(codename='view_personaltrabajo')
        usuario.user_permissions.add(permiso)
        for indice in range(12):
            PersonalTrabajo.objects.create(nombre=f'Persona {indice:02d}', cargo='Tecnico')
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_personal'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mostrando las 10 fichas más recientes para acceso rápido.')
        self.assertFalse(response.context['consulta_activa'])
        self.assertContains(response, 'Persona 11')
        self.assertContains(response, 'Persona 02')
        self.assertNotContains(response, 'Persona 01')

    def test_listar_personal_con_todos_muestra_listado_completo(self):
        usuario = User.objects.create_user(username='lector_personal_todos', password='secreta123')
        permiso = Permission.objects.get(codename='view_personaltrabajo')
        usuario.user_permissions.add(permiso)
        for indice in range(12):
            PersonalTrabajo.objects.create(nombre=f'Persona filtro {indice:02d}', cargo='Tecnico')
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_personal'), {'q': '', 'estado': ''})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['consulta_activa'])
        self.assertFalse(response.context['mostrando_inicial'])
        self.assertContains(response, 'Mostrando todo el personal ordenado por nombre.')
        self.assertContains(response, 'Persona filtro 00')
        self.assertContains(response, 'Persona filtro 11')


class PersonalDocumentosViewTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override.enable()

        self.usuario = User.objects.create_user(username='rrhh_docs', password='secreta123')
        permisos = Permission.objects.filter(codename__in=['add_personaltrabajo', 'view_personaltrabajo', 'change_personaltrabajo'])
        self.usuario.user_permissions.add(*permisos)
        self.client.force_login(self.usuario)

    def tearDown(self):
        self.override.disable()
        self.temp_media.cleanup()

    def test_crear_personal_permite_subir_documentos_de_respaldo(self):
        response = self.client.post(
            reverse('crear_personal'),
            {
                'nombre': 'Luis Toro',
                'cargo': 'Electricista',
                'area': 'Operaciones',
                'email': 'luis@example.com',
                'telefono': '987654321',
                'fecha_ingreso': '2026-03-01',
                'certificado_fonasa': SimpleUploadedFile('fonasa.pdf', b'fonasa', content_type='application/pdf'),
                'certificado_pago_afp': SimpleUploadedFile('afp.pdf', b'afp', content_type='application/pdf'),
                'activo': 'True',
            },
        )

        self.assertRedirects(response, reverse('listar_personal'))
        trabajador = PersonalTrabajo.objects.get(nombre='Luis Toro')
        self.assertTrue(bool(trabajador.certificado_fonasa))
        self.assertTrue(bool(trabajador.certificado_pago_afp))
        self.assertEqual(trabajador.total_documentos_personal, 2)

    def test_listar_personal_muestra_estado_de_respaldos(self):
        PersonalTrabajo.objects.create(
            nombre='Ana Soto',
            cargo='Supervisora',
            area='Terreno',
            certificado_fonasa='personal/fonasa/ana.pdf',
            curriculum='personal/curriculum/ana.pdf',
        )

        response = self.client.get(reverse('listar_personal'), {'q': 'Ana'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2 / 6')
        self.assertContains(response, 'Faltan 4 respaldos')

    def test_descarga_respaldo_personal_usa_ruta_protegida(self):
        trabajador = PersonalTrabajo.objects.create(
            nombre='Ana Soto',
            cargo='Supervisora',
            area='Terreno',
            certificado_fonasa=SimpleUploadedFile('ana.pdf', b'pdf-ana', content_type='application/pdf'),
        )

        response = self.client.get(reverse('descargar_documento_personal', args=[trabajador.id, 'certificado_fonasa']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'pdf-ana')

    def test_editar_personal_muestra_enlace_de_respaldo_a_ruta_interna(self):
        trabajador = PersonalTrabajo.objects.create(
            nombre='Ana Soto',
            cargo='Supervisora',
            area='Terreno',
            certificado_fonasa=SimpleUploadedFile('ana.pdf', b'pdf-ana', content_type='application/pdf'),
        )

        response = self.client.get(reverse('editar_personal', args=[trabajador.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('descargar_documento_personal', args=[trabajador.id, 'certificado_fonasa']),
        )


class ControlPresupuestosViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='presupuestos', password='secreta123')
        permisos = Permission.objects.filter(
            codename__in=['view_registropresupuesto', 'change_registropresupuesto', 'add_registropresupuesto', 'add_asignaciontrabajo']
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
        self.registro_realizado = RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=3,
            presupuesto='PRES-REAL',
            descripcion='Realizado',
            nota_pedido='OC-777',
            factura='FAC-10',
            monto='450000',
        )
        self.trabajador = PersonalTrabajo.objects.create(
            nombre='Ana Perez',
            cargo='Tecnica',
            area='Operaciones',
            activo=True,
        )
        self.cliente = Cliente.objects.create(nombre='Constructora Sur')
        self.cliente_alt = Cliente.objects.create(nombre='Electro Minera')
        self.cliente.email = 'pagos@constructora-sur.cl'
        self.cliente.save(update_fields=['email'])
        self.registro_en_proceso.cliente = self.cliente_alt
        self.registro_en_proceso.save(update_fields=['cliente'])
        self.registro_realizado.cliente = self.cliente
        self.registro_realizado.fecha_facturacion_texto = '12/03/2026'
        self.registro_realizado.save(update_fields=['cliente', 'fecha_facturacion_texto'])

    def test_listar_presupuestos_gestion_espera_consulta_antes_de_listar(self):
        response = self.client.get(reverse('listar_presupuestos_gestion'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['consulta_activa'])
        self.assertEqual(list(response.context['registros']), [])
        self.assertContains(response, 'Nuevo presupuesto')
        self.assertContains(response, 'Aún no hay una consulta aplicada')
        self.assertContains(response, 'Gestión comercial de presupuestos')
        self.assertNotContains(response, 'Total presupuestos')
        self.assertNotContains(response, 'Pendientes de aprobación')
        self.assertNotContains(response, 'Monto por cobrar')
        self.assertNotContains(response, 'PRES-PEND')

    def test_listar_presupuestos_gestion_filtra_solo_cuando_hay_consulta(self):
        response = self.client.get(reverse('listar_presupuestos_gestion'), {'estado': 'aceptado'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['consulta_activa'])
        self.assertEqual(response.context['total_filtrados'], 1)
        self.assertContains(response, 'PRES-ACEP')
        self.assertNotContains(response, 'PRES-PEND')
        self.assertNotContains(response, 'PRES-REAL')
        self.assertContains(response, 'Historial operativo')

    def test_listar_presupuestos_gestion_no_mezcla_estados_realizados(self):
        response = self.client.get(reverse('listar_presupuestos_gestion'), {'q': 'PRES'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['consulta_activa'])
        self.assertEqual(response.context['total_filtrados'], 2)
        self.assertContains(response, 'PRES-PEND')
        self.assertContains(response, 'PRES-ACEP')
        self.assertNotContains(response, 'PRES-REAL')

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
        self.assertIsNone(self.registro_pendiente.trabajo_id)

    def test_historial_presupuesto_permite_vincular_trabajador(self):
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
        self.registro_en_proceso.refresh_from_db()
        trabajo = self.registro_en_proceso.trabajo
        self.assertIsNotNone(trabajo)
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

    def test_listar_presupuestos_recupera_trabajo_y_asignacion_existente(self):
        trabajo = TrabajoPresupuesto.objects.create(presupuesto='PRES-ACEP')
        AsignacionTrabajo.objects.create(
            trabajo=trabajo,
            trabajador=self.trabajador,
            rol='Tecnica principal',
        )

        response = self.client.get(reverse('listar_presupuestos'), {'q': 'PRES-ACEP'})

        self.assertEqual(response.status_code, 200)
        self.registro_en_proceso.refresh_from_db()
        self.assertIsNone(self.registro_en_proceso.trabajo_id)
        self.assertEqual(response.context['registros'][0].trabajo_id, trabajo.id)
        self.assertEqual(response.context['registros'][0].total_personal_asignado, 1)

    def test_historial_presupuesto_actualiza_asignacion_existente_en_vez_de_duplicarla(self):
        trabajo = TrabajoPresupuesto.objects.create(presupuesto=self.registro_en_proceso.presupuesto)
        AsignacionTrabajo.objects.create(
            trabajo=trabajo,
            trabajador=self.trabajador,
            rol='Apoyo inicial',
            estado='pausado',
            creado_por=self.usuario,
        )

        response = self.client.post(
            reverse('historial_presupuesto', args=[self.registro_en_proceso.id]),
            {
                'trabajador': self.trabajador.id,
                'rol': 'Supervisor en terreno',
                'estado': 'activo',
                'fecha_inicio': '2026-03-15',
                'fecha_fin': '',
                'horas_estimadas': '16',
                'horas_reales': '8',
                'observaciones': 'Se reactiva y lidera la ejecucion',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AsignacionTrabajo.objects.filter(trabajo=trabajo, trabajador=self.trabajador).count(), 1)
        asignacion = AsignacionTrabajo.objects.get(trabajo=trabajo, trabajador=self.trabajador)
        self.assertEqual(asignacion.rol, 'Supervisor en terreno')
        self.assertEqual(asignacion.estado, 'activo')

    def test_historial_presupuesto_resume_trabajadores_asignados_en_el_encabezado(self):
        trabajo = TrabajoPresupuesto.objects.create(presupuesto='PRES-ACEP')
        self.registro_en_proceso.trabajo = trabajo
        self.registro_en_proceso.save(update_fields=['trabajo'])
        AsignacionTrabajo.objects.create(
            trabajo=trabajo,
            trabajador=self.trabajador,
            rol='Tecnica principal',
        )

        response = self.client.get(reverse('historial_presupuesto', args=[self.registro_en_proceso.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana Perez')
        self.assertContains(response, 'Tecnica principal')

    def test_listar_presupuestos_filtra_pendientes_por_cobrar(self):
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=5,
            presupuesto='PRES-FACT',
            descripcion='Facturado',
            nota_pedido='OC-333',
            factura='FAC-333',
            monto='500000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=6,
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

    def test_listar_cobranzas_espera_consulta_antes_de_listar(self):
        response = self.client.get(reverse('listar_cobranzas'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['consulta_activa'])
        self.assertContains(response, 'Consolidado: descarga un archivo CSV')
        self.assertContains(response, 'Aún no hay una consulta aplicada')
        self.assertNotContains(response, 'PRES-REAL')

    def test_listar_cobranzas_muestra_facturas_pendientes(self):
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            cliente=self.cliente_alt,
            fila_origen=7,
            presupuesto='PRES-PAGADO',
            descripcion='Pagado',
            nota_pedido='OC-555',
            factura='FAC-555',
            fecha_facturacion_texto='10/03/2026',
            fecha_pago_texto='15/03/2026',
            monto='250000',
        )

        response = self.client.get(reverse('listar_cobranzas'), {'q': 'PRES'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['consulta_activa'])
        self.assertContains(response, 'Gestión de cobranza')
        self.assertContains(response, 'PRES-REAL')
        self.assertNotContains(response, 'PRES-PAGADO')
        self.assertEqual(response.context['resumen']['total_registros'], 1)

    def test_descargar_consolidado_cobranzas_entrega_csv_filtrado(self):
        response = self.client.get(reverse('descargar_consolidado_cobranzas'), {'q': 'PRES-REAL'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename="consolidado_cobranzas.csv"', response['Content-Disposition'])
        self.assertIn('PRES-REAL', response.content.decode('utf-8-sig'))

    def test_descargar_consolidado_cobranzas_sin_filtros_entrega_cartera_general(self):
        response = self.client.get(reverse('descargar_consolidado_cobranzas'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('PRES-REAL', response.content.decode('utf-8-sig'))

    def test_listar_cobranzas_filtra_con_email_sin_mostrar_registros_sin_correo(self):
        self.cliente.email = ''
        self.cliente.save(update_fields=['email'])

        response = self.client.get(reverse('listar_cobranzas'), {'email_estado': 'con_email'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['consulta_activa'])
        self.assertEqual(response.context['resumen']['total_registros'], 0)
        self.assertNotContains(response, 'PRES-REAL')
        self.assertContains(response, 'No hay facturas pendientes con los filtros actuales.')

    @patch('core.views_control_presupuestos.enviar_resumen_operador')
    def test_listar_cobranzas_permite_enviar_resumen_interno(self, mocked_enviar):
        mocked_enviar.return_value = {
            'motivo': 'ok',
            'total_registros': 1,
            'destinatarios': ['cobranzas@sysnergia.test'],
        }

        response = self.client.post(
            reverse('listar_cobranzas'),
            {
                'accion': 'resumen',
                'q': 'PRES-REAL',
                'cliente': self.cliente.id,
                'email_estado': 'con_email',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mocked_enviar.called)
        self.assertContains(response, 'Se envió el resumen interno de cobranza correctamente.')

    @patch('core.views_control_presupuestos.enviar_recordatorios_clientes')
    def test_listar_cobranzas_permite_enviar_recordatorios(self, mocked_enviar):
        mocked_enviar.return_value = [{'cliente': self.cliente.nombre, 'email': self.cliente.email, 'cantidad_registros': 1}]

        response = self.client.post(
            reverse('listar_cobranzas'),
            {
                'accion': 'clientes',
                'q': 'PRES-REAL',
                'cliente': self.cliente.id,
                'email_estado': 'con_email',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mocked_enviar.called)
        self.assertContains(response, 'Se procesaron 1 recordatorio(s) a clientes con email.')

    def test_listar_presupuestos_no_carga_registros_sin_consulta(self):
        response = self.client.get(reverse('listar_presupuestos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aún no hay una consulta aplicada.')
        self.assertNotContains(response, 'PRES-PEND')
        self.assertFalse(response.context['consulta_activa'])
        self.assertEqual(len(response.context['registros']), 0)

    def test_listar_presupuestos_filtra_por_cliente_tipo_y_ubicacion(self):
        self.registro_en_proceso.cliente = self.cliente
        self.registro_en_proceso.tipo_trabajo = 'instalacion'
        self.registro_en_proceso.ubicacion_obra = 'Obra Hospital Norte'
        self.registro_en_proceso.save(update_fields=['cliente', 'tipo_trabajo', 'ubicacion_obra'])

        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=5,
            cliente=self.cliente_alt,
            presupuesto='PRES-ALT',
            tipo_trabajo='mantencion',
            ubicacion_obra='Planta Sur',
            descripcion='Mantencion electrica',
            nota_pedido='OC-777',
        )

        response = self.client.get(reverse('listar_presupuestos'), {
            'cliente': self.cliente.id,
            'tipo_trabajo': 'instalacion',
            'ubicacion': 'Hospital',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PRES-ACEP')
        self.assertNotContains(response, 'PRES-ALT')
        self.assertTrue(response.context['consulta_activa'])

    def test_listar_presupuestos_no_muestra_acciones_administrativas_en_consulta(self):
        permiso_alta = Permission.objects.get(codename='add_registropresupuesto')
        permiso_carga = Permission.objects.get(codename='add_cargapresupuesto')
        self.usuario.user_permissions.add(permiso_alta, permiso_carga)

        response = self.client.get(reverse('listar_presupuestos'), {'estado': 'en_proceso'})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Nuevo registro')
        self.assertNotContains(response, 'Nuevo presupuesto')
        self.assertNotContains(response, 'Subir planilla')


class MaestrosSoftDeleteTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='admin_maestros', password='secreta123')
        permisos = Permission.objects.filter(codename__in=['delete_cliente', 'delete_personaltrabajo'])
        self.usuario.user_permissions.add(*permisos)
        self.client.force_login(self.usuario)

    def test_eliminar_cliente_lo_desactiva_y_preserva_relaciones(self):
        cliente = Cliente.objects.create(nombre='Cliente historico', activo=True)
        carga = CargaPresupuesto.objects.create(
            nombre='Carga historica',
            hoja='Hoja1',
            total_registros=1,
            creado_por=self.usuario,
            archivo='presupuestos/historico.xlsx',
        )
        registro = RegistroPresupuesto.objects.create(
            carga=carga,
            cliente=cliente,
            fila_origen=1,
            presupuesto='PRES-HIST',
            descripcion='Presupuesto con cliente historico',
        )

        response = self.client.post(reverse('eliminar_cliente', args=[cliente.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('listar_clientes'))
        cliente.refresh_from_db()
        registro.refresh_from_db()
        self.assertFalse(cliente.activo)
        self.assertEqual(registro.cliente_id, cliente.id)

    def test_eliminar_personal_lo_desactiva_y_preserva_asignaciones(self):
        personal = PersonalTrabajo.objects.create(nombre='Luis Perez', cargo='Tecnico', activo=True)
        trabajo = TrabajoPresupuesto.objects.create(presupuesto='PRES-OPER')
        asignacion = AsignacionTrabajo.objects.create(
            trabajo=trabajo,
            trabajador=personal,
            rol='Apoyo',
            estado='activo',
        )

        response = self.client.post(reverse('eliminar_personal', args=[personal.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('listar_personal'))
        personal.refresh_from_db()
        asignacion.refresh_from_db()
        self.assertFalse(personal.activo)
        self.assertEqual(asignacion.trabajador_id, personal.id)


class TemplateSmokeTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='smoke', password='secreta123')
        permisos = Permission.objects.filter(
            codename__in=['view_cliente', 'view_personaltrabajo', 'view_registropresupuesto', 'view_documento', 'add_asignaciontrabajo']
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
            reverse('listar_cobranzas'),
            reverse('historial_presupuesto', args=[self.registro.id]),
            reverse('listar_documentos'),
        ]

        for ruta in rutas:
            response = self.client.get(ruta)
            self.assertEqual(response.status_code, 200, ruta)

    def test_historial_presupuesto_usa_destinos_con_contexto(self):
        response = self.client.get(reverse('historial_presupuesto', args=[self.registro.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{reverse('listar_documentos')}?presupuesto=PRES-SMOKE")
        self.assertContains(response, f"{reverse('listar_presupuestos')}?q=PRES-SMOKE")

    def test_dashboard_cta_principal_apunta_a_seguimiento_filtrado(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{reverse('listar_presupuestos')}?estado=en_proceso")

    def test_layout_no_usa_href_vacio_para_dropdown_operacion(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="#"')

    def test_layout_oculta_navegacion_fuera_de_permiso_y_muestra_destino_valido(self):
        self.client.logout()
        usuario = User.objects.create_user(username='solo_documentos', password='secreta123')
        permiso = Permission.objects.get(codename='view_documento')
        usuario.user_permissions.add(permiso)
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_documentos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/documentos/"')
        self.assertContains(response, 'Documentos')
        self.assertNotContains(response, '>Inicio<')
        self.assertNotContains(response, '>Clientes<')
        self.assertNotContains(response, '>Personal<')
        self.assertNotContains(response, '>Seguimiento<')
        self.assertNotContains(response, '>Cobranza<')

    def test_layout_permite_entrar_a_documentos_sin_exponer_nuevo_documento(self):
        self.client.logout()
        usuario = User.objects.create_user(username='cargador_documentos', password='secreta123')
        permisos = Permission.objects.filter(codename__in=['add_documento', 'view_documento'])
        usuario.user_permissions.add(*permisos)
        self.client.force_login(usuario)

        response = self.client.get(reverse('listar_documentos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("listar_documentos")}"')
        self.assertContains(response, 'Operación')
        self.assertContains(response, '>Documentos<')
        self.assertContains(response, 'Nuevo documento')

    def test_layout_muestra_importar_planilla_con_permiso_de_carga(self):
        self.client.logout()
        usuario = User.objects.create_user(username='cargador_planillas', password='secreta123')
        permiso = Permission.objects.get(codename='add_cargapresupuesto')
        usuario.user_permissions.add(permiso)
        self.client.force_login(usuario)

        response = self.client.get(reverse('subir_presupuesto'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("subir_presupuesto")}"')
        self.assertContains(response, 'Importar planilla')

    def test_layout_expone_loading_reutilizable_en_formularios_post(self):
        response = self.client.get(reverse('historial_presupuesto', args=[self.registro.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-loading-text="Vinculando trabajador..."')
        self.assertContains(response, "form.dataset.submitting = 'true'")

    def test_listados_incluyen_caption_y_descripcion_accesible(self):
        response = self.client.get(reverse('listar_clientes'), {'q': 'smoke'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<caption class="visually-hidden">Listado de clientes filtrados por nombre, RUT, contacto y estado.</caption>', html=True)
        self.assertContains(response, 'aria-describedby="clientes-listado-ayuda"')

        response = self.client.get(reverse('listar_presupuestos'), {'q': 'PRES-SMOKE'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<caption class="visually-hidden">Listado de seguimiento operativo de presupuestos con gestión, estado, cobro, monto y acciones disponibles.</caption>', html=True)
        self.assertContains(response, 'aria-describedby="seguimiento-listado-ayuda"')

    def test_listados_muestran_estados_vacios_mas_guiados(self):
        response = self.client.get(reverse('listar_personal'), {'q': 'inexistente'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ajusta la búsqueda o limpia los filtros para continuar.')
        self.assertContains(response, 'role="status"')

        response = self.client.get(reverse('listar_documentos'), {'q': 'inexistente'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Prueba con otro presupuesto, tipo, área o limpia los filtros.')

    def test_acciones_repetidas_tienen_contexto_para_lector_de_pantalla(self):
        response = self.client.get(reverse('listar_presupuestos'), {'q': 'PRES-SMOKE'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Ver historial del presupuesto PRES-SMOKE"')

        response = self.client.get(reverse('listar_documentos'), {'q': 'Documento smoke'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Descargar documento Documento smoke"')

    def test_403_ofrece_salida_valida_para_usuario_con_acceso_parcial(self):
        self.client.logout()
        usuario = User.objects.create_user(username='parcial_403', password='secreta123')
        permiso = Permission.objects.get(codename='view_documento')
        usuario.user_permissions.add(permiso)
        self.client.force_login(usuario)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Ir a documentos', status_code=403)
        self.assertNotContains(response, 'Volver al inicio', status_code=403)
        self.assertContains(response, f'action="{reverse("logout")}" method="post"', status_code=403)
        self.assertNotContains(response, 'Iniciar sesión', status_code=403)


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

    def test_login_exitoso_expira_sesion_al_cerrar_navegador(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'acceso', 'password': 'clave-segura-123'},
            REMOTE_ADDR='10.0.0.3',
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    @override_settings(SESSION_COOKIE_AGE=900)
    def test_login_exitoso_aplica_timeout_por_inactividad_configurado(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'acceso', 'password': 'clave-segura-123'},
            REMOTE_ADDR='10.0.0.4',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get_expiry_age(), 900)
