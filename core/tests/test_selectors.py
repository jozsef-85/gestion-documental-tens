from django.contrib.auth.models import User
from django.test import TestCase

from core.models import CargaPresupuesto, RegistroPresupuesto
from core.selectors.presupuestos import (
    aggregate_presupuesto_metrics,
    inventario_presupuestos_queryset,
    q_estado_presupuesto,
)


class PresupuestoSelectorsTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create(username='selector-user')
        self.carga = CargaPresupuesto.objects.create(
            nombre='Carga selectors',
            hoja='Hoja1',
            total_registros=3,
            creado_por=self.usuario,
            archivo='presupuestos/selectors.xlsx',
        )

    def test_estado_en_proceso_es_consistente_con_estado_seguimiento(self):
        en_proceso = RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=1,
            presupuesto='PRES-EN-PROCESO',
            nota_pedido='OC-100',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=2,
            presupuesto='PRES-FACTURADO',
            nota_pedido='OC-200',
            factura='FAC-200',
        )

        queryset = inventario_presupuestos_queryset().filter(q_estado_presupuesto('en_proceso'))

        self.assertEqual(en_proceso.estado_seguimiento, 'Aceptado / En curso')
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().id, en_proceso.id)

    def test_aggregate_presupuesto_metrics_consolida_contadores(self):
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=1,
            presupuesto='PRES-PEND',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=2,
            presupuesto='PRES-COBRO',
            nota_pedido='OC-101',
            valor='500000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=3,
            presupuesto='PRES-PAG',
            nota_pedido='OC-102',
            fecha_pago_texto='12/03/2026',
            valor='200000',
        )

        resumen = aggregate_presupuesto_metrics(inventario_presupuestos_queryset())

        self.assertEqual(resumen['total_items'], 3)
        self.assertEqual(resumen['total_pendientes_aprobacion'], 1)
        self.assertEqual(resumen['total_aceptados'], 2)
        self.assertEqual(resumen['total_pendientes_por_cobrar'], 1)
        self.assertEqual(resumen['total_pagados'], 1)
        self.assertEqual(resumen['monto_por_cobrar'], 500000)

    def test_aggregate_presupuesto_metrics_respeta_estado_manual(self):
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=1,
            presupuesto='PRES-MANUAL-PEND',
            nota_pedido='OC-777',
            estado_manual='pendiente',
            valor='300000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            fila_origen=2,
            presupuesto='PRES-MANUAL-FACT',
            nota_pedido='OC-778',
            estado_manual='facturado',
            valor='400000',
        )

        resumen = aggregate_presupuesto_metrics(inventario_presupuestos_queryset())

        self.assertEqual(resumen['total_pendientes_aprobacion'], 1)
        self.assertEqual(resumen['total_aceptados'], 1)
        self.assertEqual(resumen['total_facturados'], 1)
        self.assertEqual(resumen['total_pendientes_por_cobrar'], 1)
        self.assertEqual(resumen['monto_por_cobrar'], 400000)
