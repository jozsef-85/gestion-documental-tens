from io import StringIO

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import CargaPresupuesto, Cliente, RegistroPresupuesto
from core.services.cobranzas import (
    construir_resumen_cobranzas,
    enviar_recordatorios_clientes,
    enviar_resumen_operador,
    obtener_facturas_pendientes_queryset,
)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='cobranzas@sysnergia.test',
    COBRANZA_OPERATOR_EMAILS=['cobranzas@sysnergia.test'],
    COBRANZA_REPLY_TO=['cobranzas@sysnergia.test'],
    COBRANZA_APP_URL='https://app.sysnergia.com/gestion/presupuestos/?estado=por_cobrar',
)
class CobranzasEmailTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='cobranza', password='secreta123')
        self.carga = CargaPresupuesto.objects.create(
            nombre='Carga cobranza',
            hoja='Hoja1',
            total_registros=3,
            creado_por=self.usuario,
            archivo='presupuestos/cobranza.xlsx',
        )
        self.cliente_con_email = Cliente.objects.create(
            nombre='Constructora Sur',
            contacto='Patricia Diaz',
            email='pagos@constructora-sur.cl',
        )
        self.cliente_sin_email = Cliente.objects.create(
            nombre='Electrica Norte',
            contacto='Area de pagos',
            email='',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            cliente=self.cliente_con_email,
            fila_origen=1,
            presupuesto='PRES-FACT-1',
            descripcion='Trabajo facturado',
            nota_pedido='OC-101',
            factura='FAC-101',
            fecha_facturacion_texto='10/03/2026',
            monto='500000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            cliente=self.cliente_sin_email,
            fila_origen=2,
            presupuesto='PRES-FACT-2',
            descripcion='Trabajo facturado sin email',
            nota_pedido='OC-102',
            factura='FAC-102',
            fecha_facturacion_texto='11/03/2026',
            monto='350000',
        )
        RegistroPresupuesto.objects.create(
            carga=self.carga,
            cliente=self.cliente_con_email,
            fila_origen=3,
            presupuesto='PRES-PAG-1',
            descripcion='Trabajo pagado',
            nota_pedido='OC-103',
            factura='FAC-103',
            fecha_facturacion_texto='01/03/2026',
            fecha_pago_texto='12/03/2026',
            monto='200000',
        )

    def test_obtener_facturas_pendientes_queryset_excluye_pagadas(self):
        registros = list(obtener_facturas_pendientes_queryset())

        self.assertEqual(len(registros), 2)
        self.assertEqual({registro.presupuesto for registro in registros}, {'PRES-FACT-1', 'PRES-FACT-2'})

    def test_enviar_resumen_operador_envia_correo_interno(self):
        registros = list(obtener_facturas_pendientes_queryset())
        resumen = construir_resumen_cobranzas(registros)

        self.assertEqual(resumen['total_registros'], 2)
        self.assertEqual(resumen['total_con_email'], 1)
        self.assertEqual(resumen['total_sin_email'], 1)

        resultado = enviar_resumen_operador(registros)

        self.assertTrue(resultado['enviado'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('2 factura(s) pendiente(s)', mail.outbox[0].subject)
        self.assertIn('PRES-FACT-1', mail.outbox[0].body)
        self.assertIn('PRES-FACT-2', mail.outbox[0].body)

    def test_enviar_recordatorios_clientes_agrupa_por_email(self):
        registros = list(obtener_facturas_pendientes_queryset())

        enviados = enviar_recordatorios_clientes(registros)

        self.assertEqual(len(enviados), 1)
        self.assertEqual(enviados[0]['email'], 'pagos@constructora-sur.cl')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('PRES-FACT-1', mail.outbox[0].body)
        self.assertNotIn('PRES-FACT-2', mail.outbox[0].body)

    def test_comando_dry_run_no_envia_correos(self):
        salida = StringIO()

        call_command('enviar_alertas_cobro', '--dry-run', '--enviar-clientes', stdout=salida)

        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('Modo simulacion', salida.getvalue())
        self.assertIn('Facturas pendientes detectadas: 2', salida.getvalue())
