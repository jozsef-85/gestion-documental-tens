from django.core.management.base import BaseCommand, CommandError

from ...services.cobranzas import (
    enviar_recordatorios_clientes,
    enviar_resumen_operador,
    obtener_facturas_pendientes_queryset,
)


class Command(BaseCommand):
    help = 'Envia un resumen de cobranza y, opcionalmente, recordatorios a clientes con facturas pendientes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destinatario',
            action='append',
            default=[],
            help='Email adicional para recibir el resumen interno de cobranza. Se puede repetir.',
        )
        parser.add_argument(
            '--enviar-clientes',
            action='store_true',
            help='Envia recordatorios a los clientes que tengan email cargado.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Prepara los correos pero no los envia.',
        )

    def handle(self, *args, **options):
        registros = list(obtener_facturas_pendientes_queryset())
        if not registros:
            self.stdout.write(self.style.WARNING('No hay facturas pendientes de pago para informar.'))
            return

        resumen = enviar_resumen_operador(
            registros,
            destinatarios=options['destinatario'] or None,
            dry_run=options['dry_run'],
        )

        if resumen['motivo'] == 'sin_destinatarios':
            raise CommandError(
                'No hay destinatarios configurados para el resumen interno. '
                'Define DJANGO_COBRANZA_OPERATOR_EMAILS o usa --destinatario.'
            )

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Modo simulacion: no se enviaron correos.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Resumen interno procesado para {len(resumen['destinatarios'])} destinatario(s)."
                )
            )

        self.stdout.write(f"Facturas pendientes detectadas: {resumen['total_registros']}")

        if options['enviar_clientes']:
            enviados = enviar_recordatorios_clientes(registros, dry_run=options['dry_run'])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recordatorios a clientes procesados: {len(enviados)} correo(s)."
                )
            )
        else:
            self.stdout.write('No se enviaron recordatorios a clientes. Usa --enviar-clientes para incluirlos.')
