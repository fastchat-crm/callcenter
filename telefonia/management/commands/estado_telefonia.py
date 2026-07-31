"""Diagnóstico de la capa telefónica desde la terminal.

    ./venv/bin/python manage.py estado_telefonia

Contesta lo mismo que la tarjeta del panel, pero sin navegador: sirve por SSH y
dentro de un cron que avise cuando una troncal se cae.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Muestra si Asterisk y el AudioSocket están arriba, y cuánto se usan.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', help='Nombre del cliente para acotar el uso.')

    def handle(self, *args, **opciones):
        from clientes.models import Cliente
        from telefonia.estado import resumen

        cliente = None
        if opciones.get('cliente'):
            cliente = Cliente.objects.filter(nombre__iexact=opciones['cliente']).first()
            if cliente is None:
                self.stderr.write(f'No existe el cliente «{opciones["cliente"]}».')
                return

        datos = resumen(cliente)
        asterisk, audiosocket, uso = datos['asterisk'], datos['audiosocket'], datos['uso']

        self.stdout.write(self.style.MIGRATE_HEADING('Asterisk'))
        self._linea('Instalado', asterisk['instalado'])
        self._linea('Servicio activo', asterisk['activo'])
        if asterisk['version']:
            self.stdout.write(f'  Versión          {asterisk["version"]}')
        self.stdout.write(f'  Estado           {asterisk["detalle"]}')
        for registro in asterisk['registros']:
            marca = 'OK ' if registro['estado'] == 'Registered' else '.. '
            self.stdout.write(f'    {marca}{registro["troncal"]}: {registro["estado"]}')
        self.stdout.write(f'  Canales activos  {asterisk["canales"]}')

        self.stdout.write(self.style.MIGRATE_HEADING('\nAudioSocket'))
        self._linea('Servicio activo', audiosocket['servicio_activo'])
        self._linea('Puerto escuchando', audiosocket['escuchando'])
        self.stdout.write(f'  Destino          {audiosocket["destino"]}')
        self.stdout.write(f'  Estado           {audiosocket["detalle"]}')

        titulo = f'\nUso{" · " + cliente.nombre if cliente else " (todos los clientes)"}'
        self.stdout.write(self.style.MIGRATE_HEADING(titulo))
        self.stdout.write(f'  Hoy              {uso["llamadas_hoy"]} llamadas · {uso["minutos_hoy"]} min')
        self.stdout.write(f'  Últimos {uso["dias"]} días  {uso["llamadas_periodo"]} llamadas · {uso["minutos_periodo"]} min')
        self.stdout.write(f'  En curso ahora   {uso["en_curso"]}')
        if uso['minutos_incluidos']:
            self.stdout.write(f'  Plan             {uso["porcentaje_plan"]}% de {uso["minutos_incluidos"]} min incluidos')

    def _linea(self, etiqueta, valor):
        estilo = self.style.SUCCESS if valor else self.style.ERROR
        self.stdout.write(f'  {etiqueta:16} {estilo("sí" if valor else "no")}')
