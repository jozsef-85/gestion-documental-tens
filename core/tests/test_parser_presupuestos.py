from decimal import Decimal

from django.test import SimpleTestCase

from core.presupuestos import normalizar_estado_oc, parsear_planilla_presupuestos
from core.tests.builders import construir_xlsx_prueba


class PresupuestosParserTests(SimpleTestCase):
    def test_parsea_planilla_y_convierte_campos_principales(self):
        archivo = construir_xlsx_prueba()

        resultado = parsear_planilla_presupuestos(archivo)

        self.assertEqual(resultado.hoja, 'Hoja1')
        self.assertEqual(len(resultado.registros), 2)
        self.assertEqual(resultado.registros[0].presupuesto, 'Presupuesto 1')
        self.assertEqual(resultado.registros[0].fecha_texto, '22/10/2024')
        self.assertEqual(resultado.registros[0].monto, Decimal('2572978'))
        self.assertEqual(resultado.registros[0].factura, 'FAC-100')
        self.assertEqual(resultado.registros[0].estado_oc, 'En curso')
        self.assertEqual(resultado.registros[0].observacion_oc, 'Observacion de prueba')
        self.assertEqual(resultado.registros[0].estado_recepcion, 'Recibido parcialmente')

    def test_parsea_fechas_en_texto(self):
        archivo = construir_xlsx_prueba()

        resultado = parsear_planilla_presupuestos(archivo)

        self.assertEqual(resultado.registros[1].fecha_texto, '17/01/2025')

    def test_acepta_encabezado_monto_como_alias_del_importe(self):
        archivo = construir_xlsx_prueba(encabezado_monto='MONTO')

        resultado = parsear_planilla_presupuestos(archivo)

        self.assertEqual(resultado.registros[0].monto, Decimal('2572978'))

    def test_acepta_orden_de_compra_como_alias_de_nota_de_pedido(self):
        archivo = construir_xlsx_prueba(
            encabezado_monto='MONTO',
            encabezado_nota_pedido='ORDEN DE COMPRA',
        )

        resultado = parsear_planilla_presupuestos(archivo)

        self.assertEqual(resultado.registros[0].nota_pedido, 'OC-001')
        self.assertEqual(resultado.registros[0].monto, Decimal('2572978'))

    def test_acepta_encabezado_n_presupuesto_como_alias(self):
        archivo = construir_xlsx_prueba(encabezado_presupuesto='N° PRESUPUESTO')

        resultado = parsear_planilla_presupuestos(archivo)

        self.assertEqual(resultado.registros[0].presupuesto, 'Presupuesto 1')

    def test_normaliza_estado_oc_importado(self):
        self.assertEqual(normalizar_estado_oc('EN CURSO'), 'En curso')
        self.assertEqual(normalizar_estado_oc('realizado'), 'Terminado')
