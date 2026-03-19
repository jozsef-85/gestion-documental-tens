from django.test import SimpleTestCase

from core.models import RegistroPresupuesto
from core.templatetags.moneda import clp


class RegistroPresupuestoModelTests(SimpleTestCase):
    def test_calcula_estado_y_avance_flujo(self):
        registro = RegistroPresupuesto(
            presupuesto='Presupuesto demo',
            nota_pedido='OC-123',
            recepcion='Recepción 1',
            factura='FAC-9',
        )

        self.assertEqual(registro.estado_seguimiento_codigo, 'facturado')
        self.assertEqual(registro.estado_seguimiento, 'Realizado')
        self.assertEqual(registro.avance_flujo, 60)

    def test_sin_nota_pedido_no_se_considera_aceptado(self):
        registro = RegistroPresupuesto(
            presupuesto='Presupuesto demo',
            recepcion='Recepción parcial',
            guia_despacho='GD-55',
        )

        self.assertEqual(registro.estado_seguimiento_codigo, 'pendiente')
        self.assertEqual(registro.estado_seguimiento, 'Pendiente de aprobación')

    def test_estado_manual_tiene_prioridad(self):
        registro = RegistroPresupuesto(
            presupuesto='Presupuesto demo',
            factura='FAC-10',
            estado_manual='pendiente',
        )

        self.assertEqual(registro.estado_seguimiento_codigo, 'pendiente')
        self.assertEqual(registro.estado_seguimiento, 'Pendiente de aprobación')


class MonedaTemplateFilterTests(SimpleTestCase):
    def test_formatea_pesos_chilenos(self):
        self.assertEqual(clp(2572978), '$ 2.572.978')
        self.assertEqual(clp('150000'), '$ 150.000')
        self.assertEqual(clp(None), 'Sin valor')
