"""Levanta el servidor AudioSocket que atiende las llamadas de Asterisk.

    ./venv/bin/python manage.py audiosocket

En producción lo gobierna systemd (`deploy/callcenter-audiosocket.service`).
Corre en su propio proceso, aparte de gunicorn: una llamada de voz ocupa su hilo
durante toda la conversación y no debe competir con el panel.
"""
import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand

from voz.audiosocket import servir


class Command(BaseCommand):
    help = 'Servidor AudioSocket para Asterisk auto-hospedado.'

    def add_arguments(self, parser):
        parser.add_argument('--host', default=settings.AUDIOSOCKET_HOST)
        parser.add_argument('--puerto', type=int, default=settings.AUDIOSOCKET_PUERTO)

    def handle(self, *args, **opciones):
        host, puerto = opciones['host'], opciones['puerto']
        self.stdout.write(f'AudioSocket escuchando en {host}:{puerto} — Ctrl+C para salir')
        try:
            asyncio.run(servir(host, puerto))
        except KeyboardInterrupt:
            self.stdout.write('Detenido.')
