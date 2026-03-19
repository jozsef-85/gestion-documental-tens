from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from core.forms import (
    CargaPresupuestoForm,
    ClienteForm,
    DocumentoForm,
    MAX_DOCUMENT_UPLOAD_SIZE,
    MAX_PERSONAL_UPLOAD_SIZE,
    MAX_SPREADSHEET_UPLOAD_SIZE,
    PersonalTrabajoForm,
    RegistroPresupuestoForm,
    VersionDocumentoForm,
)


class RegistroPresupuestoFormTests(SimpleTestCase):
    def test_normaliza_fechas_texto_en_edicion(self):
        form = RegistroPresupuestoForm(data={
            'presupuesto': 'Presupuesto demo',
            'tipo_trabajo': 'instalacion',
            'ubicacion_obra': 'Obra demo',
            'descripcion': 'Servicio',
            'solicitante': 'Usuario',
            'monto': '150000',
            'fecha_texto': '17 de enero del 2025',
            'nota_pedido': '',
            'estado_oc': 'En curso',
            'recepcion': '',
            'guia_despacho': '',
            'factura': '',
            'fecha_facturacion_texto': '',
            'fecha_pago_texto': '',
            'estado_manual': '',
            'observaciones': 'Ajuste manual',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['fecha_texto'], '17/01/2025')

    def test_estado_oc_se_muestra_como_lista_desplegable(self):
        form = RegistroPresupuestoForm()

        self.assertEqual(form.fields['estado_oc'].__class__.__name__, 'ChoiceField')
        self.assertIn(('En curso', 'En curso'), form.fields['estado_oc'].choices)
        self.assertIn('cliente', form.fields)
        self.assertIn('tipo_trabajo', form.fields)
        self.assertIn('ubicacion_obra', form.fields)

    def test_rechaza_monto_negativo(self):
        form = RegistroPresupuestoForm(data={
            'presupuesto': 'Presupuesto demo',
            'tipo_trabajo': 'instalacion',
            'ubicacion_obra': 'Obra demo',
            'descripcion': 'Servicio',
            'solicitante': 'Usuario',
            'monto': '-1',
            'fecha_texto': '17/01/2025',
            'nota_pedido': '',
            'estado_oc': '',
            'recepcion': '',
            'guia_despacho': '',
            'factura': '',
            'fecha_facturacion_texto': '',
            'fecha_pago_texto': '',
            'estado_manual': '',
            'observaciones': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('no puede ser negativo', form.errors['monto'][0])


class DocumentoFormTests(SimpleTestCase):
    def test_formulario_documento_expone_presupuestos(self):
        form = DocumentoForm()

        self.assertIn('presupuestos', form.fields)


class VersionDocumentoFormTests(SimpleTestCase):
    def test_rechaza_tipo_no_permitido(self):
        archivo = SimpleUploadedFile(
            'payload.exe',
            b'fake-binary',
            content_type='application/octet-stream',
        )

        form = VersionDocumentoForm(
            data={'numero_version': '2.0', 'comentario': 'Actualizacion'},
            files={'archivo': archivo},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('formatos permitidos', form.errors['archivo'][0])

    def test_rechaza_archivo_excesivamente_grande(self):
        archivo = SimpleUploadedFile(
            'manual.pdf',
            b'a' * (MAX_DOCUMENT_UPLOAD_SIZE + 1),
            content_type='application/pdf',
        )

        form = VersionDocumentoForm(
            data={'numero_version': '2.0', 'comentario': 'Actualizacion'},
            files={'archivo': archivo},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('tamaño máximo permitido', form.errors['archivo'][0])


class CargaPresupuestoFormTests(SimpleTestCase):
    def test_acepta_planilla_valida(self):
        archivo = SimpleUploadedFile(
            'control.xlsx',
            b'PK\x03\x04planilla',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        form = CargaPresupuestoForm(
            data={'nombre': 'Carga demo'},
            files={'archivo': archivo},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_rechaza_planilla_demasiado_grande(self):
        archivo = SimpleUploadedFile(
            'control.xlsx',
            b'a' * (MAX_SPREADSHEET_UPLOAD_SIZE + 1),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        form = CargaPresupuestoForm(
            data={'nombre': 'Carga demo'},
            files={'archivo': archivo},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('tamaño máximo permitido', form.errors['archivo'][0])


class ClienteFormTests(TestCase):
    def test_normaliza_rut_vacio_a_none(self):
        form = ClienteForm(data={
            'nombre': 'Cliente demo',
            'rut': '   ',
            'contacto': 'Maria',
            'email': 'maria@example.com',
            'telefono': '+56 9 1111 2222',
            'direccion': 'Av. Siempre Viva 123',
            'activo': 'True',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['rut'])

    def test_normaliza_rut_valido_con_formato_chileno(self):
        form = ClienteForm(data={
            'nombre': 'Cliente demo',
            'rut': '76086428-5',
            'contacto': 'Maria',
            'email': 'maria@example.com',
            'telefono': '+56 9 1111 2222',
            'direccion': 'Av. Siempre Viva 123',
            'activo': 'True',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['rut'], '76.086.428-5')

    def test_rechaza_rut_con_digito_verificador_invalido(self):
        form = ClienteForm(data={
            'nombre': 'Cliente demo',
            'rut': '76.123.456-8',
            'contacto': 'Maria',
            'email': 'maria@example.com',
            'telefono': '+56 9 1111 2222',
            'direccion': 'Av. Siempre Viva 123',
            'activo': 'True',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('no es válido', form.errors['rut'][0])


class PersonalTrabajoFormTests(TestCase):
    def test_normaliza_run_valido_con_formato_chileno(self):
        form = PersonalTrabajoForm(data={
            'nombre': 'Luis Toro',
            'run': '12345678-5',
            'cargo': 'Electricista',
            'area': 'Operaciones',
            'email': '',
            'telefono': '',
            'fecha_ingreso': '',
            'activo': 'True',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['run'], '12.345.678-5')

    def test_rechaza_run_con_digito_verificador_invalido(self):
        form = PersonalTrabajoForm(data={
            'nombre': 'Luis Toro',
            'run': '12.345.678-9',
            'cargo': 'Electricista',
            'area': 'Operaciones',
            'email': '',
            'telefono': '',
            'fecha_ingreso': '',
            'activo': 'True',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('no es válido', form.errors['run'][0])

    def test_rechaza_respaldo_personal_con_extension_no_permitida(self):
        archivo = SimpleUploadedFile(
            'fonasa.exe',
            b'fake-binary',
            content_type='application/octet-stream',
        )

        form = PersonalTrabajoForm(
            data={
                'nombre': 'Luis Toro',
                'cargo': 'Electricista',
                'area': 'Operaciones',
                'email': '',
                'telefono': '',
                'fecha_ingreso': '',
                'activo': 'True',
            },
            files={'certificado_fonasa': archivo},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('formatos permitidos', form.errors['certificado_fonasa'][0])

    def test_rechaza_curriculum_demasiado_grande(self):
        archivo = SimpleUploadedFile(
            'cv.pdf',
            b'a' * (MAX_PERSONAL_UPLOAD_SIZE + 1),
            content_type='application/pdf',
        )

        form = PersonalTrabajoForm(
            data={
                'nombre': 'Luis Toro',
                'cargo': 'Electricista',
                'area': 'Operaciones',
                'email': '',
                'telefono': '',
                'fecha_ingreso': '',
                'activo': 'True',
            },
            files={'curriculum': archivo},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('tamaño máximo permitido', form.errors['curriculum'][0])
