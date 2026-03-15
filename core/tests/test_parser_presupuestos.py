from decimal import Decimal

from django.test import SimpleTestCase

from core.presupuestos import parsear_planilla_presupuestos
from core.tests.builders import construir_xlsx_prueba


class PresupuestosParserTests(SimpleTestCase):
    def test_parsea_planilla_y_convierte_campos_principales(self):
        archivo = construir_xlsx_prueba()

        resultado = parsear_planilla_presupuestos(archivo)

        self.assertEqual(resultado.hoja, 'Hoja1')
        self.assertEqual(len(resultado.registros), 2)
        self.assertEqual(resultado.registros[0].presupuesto, 'Presupuesto 1')
        self.assertEqual(resultado.registros[0].fecha_texto, '22/10/2024')
        self.assertEqual(resultado.registros[0].valor, Decimal('2572978'))
        self.assertEqual(resultado.registros[0].factura, 'FAC-100')
        self.assertEqual(resultado.registros[0].estado_oc, 'En curso')
        self.assertEqual(resultado.registros[0].observacion_oc, 'Observacion de prueba')
        self.assertEqual(resultado.registros[0].estado_recepcion, 'Recibido parcialmente')

    def test_parsea_fechas_en_texto(self):
        archivo = construir_xlsx_prueba()

        resultado = parsear_planilla_presupuestos(archivo)

        self.assertEqual(resultado.registros[1].fecha_texto, '17/01/2025')
