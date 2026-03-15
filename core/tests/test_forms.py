from django.test import SimpleTestCase

from core.forms import DocumentoForm, RegistroPresupuestoForm


class RegistroPresupuestoFormTests(SimpleTestCase):
    def test_normaliza_fechas_texto_en_edicion(self):
        form = RegistroPresupuestoForm(data={
            'presupuesto': 'Presupuesto demo',
            'descripcion': 'Servicio',
            'solicitante': 'Usuario',
            'valor': '150000',
            'fecha_texto': '17 de enero del 2025',
            'nota_pedido': '',
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


class DocumentoFormTests(SimpleTestCase):
    def test_formulario_documento_expone_presupuestos(self):
        form = DocumentoForm()

        self.assertIn('presupuestos', form.fields)
