from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from core.forms import (
    CargaPresupuestoForm,
    DocumentoForm,
    MAX_DOCUMENT_UPLOAD_SIZE,
    MAX_SPREADSHEET_UPLOAD_SIZE,
    RegistroPresupuestoForm,
    VersionDocumentoForm,
)


class RegistroPresupuestoFormTests(SimpleTestCase):
    def test_normaliza_fechas_texto_en_edicion(self):
        form = RegistroPresupuestoForm(data={
            'presupuesto': 'Presupuesto demo',
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
