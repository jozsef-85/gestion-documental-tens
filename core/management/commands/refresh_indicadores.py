from django.core.management.base import BaseCommand

from ...services.indicators import refrescar_indicadores


class Command(BaseCommand):
    help = 'Obtiene indicadores externos y recalienta la caché usada por el dashboard.'

    def handle(self, *args, **options):
        indicadores = refrescar_indicadores()
        self.stdout.write(
            self.style.SUCCESS(
                'Indicadores actualizados: '
                f"UF={indicadores['uf']} Dólar={indicadores['dolar']} UTM={indicadores['utm']}"
            )
        )
