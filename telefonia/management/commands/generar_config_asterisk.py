"""Genera la configuración de Asterisk a partir de lo cargado en el panel.

Hasta ahora las troncales del panel eran un registro decorativo: nadie las leía.
Este comando las convierte en los dos archivos que Asterisk necesita, para que
lo que se ve en pantalla sea lo que realmente atiende las llamadas.

    ./venv/bin/python manage.py generar_config_asterisk            # muestra
    ./venv/bin/python manage.py generar_config_asterisk --escribir # instala

El dialplan generado hace tres cosas por llamada: avisa por HTTP quién marcó,
entrega el audio al AudioSocket y cuelga. Nada más, para que toda la lógica de
conversación siga viviendo en un solo lugar.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

RUTA_ASTERISK = '/etc/asterisk'

CABECERA = (
    '; Generado por: manage.py generar_config_asterisk\n'
    '; NO editar a mano: se regenera desde el panel (Centro de telefonía).\n\n'
)


class Command(BaseCommand):
    help = 'Genera pjsip.conf y extensions.conf desde las troncales del panel.'

    def add_arguments(self, parser):
        parser.add_argument('--escribir', action='store_true',
                            help=f'Escribe los archivos en {RUTA_ASTERISK} en vez de mostrarlos.')
        parser.add_argument('--destino', default=RUTA_ASTERISK)

    def handle(self, *args, **opciones):
        from telefonia.models import AsesorHumano, NumeroTelefonico, TroncalSIP

        troncales = list(TroncalSIP.objects.filter(status=True, activo=True)
                         .select_related('proveedor'))
        numeros = list(NumeroTelefonico.objects.filter(status=True, activo=True)
                       .select_related('flujo', 'troncal'))
        # Los asesores con extensión son también softphones: se registran para
        # recibir las transferencias y, de paso, para probar el bot sin carrier.
        asesores = [a for a in AsesorHumano.objects.filter(status=True)
                    if (a.extension_sip or '').strip()]

        if not troncales:
            self.stdout.write(self.style.WARNING(
                'No hay troncales SIP activas. Cárgalas en Centro de telefonía → Proveedores.'))
        if not numeros:
            self.stdout.write(self.style.WARNING(
                'No hay números activos: ninguna llamada tendría a dónde ir.'))

        archivos = {
            'pjsip.conf': self._pjsip(troncales, asesores),
            'extensions.conf': self._dialplan(troncales, numeros, asesores),
        }

        if not opciones['escribir']:
            for nombre, contenido in archivos.items():
                self.stdout.write(self.style.MIGRATE_HEADING(f'\n===== {nombre} ====='))
                self.stdout.write(contenido)
            self.stdout.write(self.style.NOTICE(
                '\nNada se escribió. Agrega --escribir para instalarlos.'))
            return

        destino = opciones['destino']
        for nombre, contenido in archivos.items():
            ruta = os.path.join(destino, nombre)
            if os.path.exists(ruta):
                # El original casi siempre trae ejemplos útiles; se guarda una vez.
                respaldo = ruta + '.antes-callcenter'
                if not os.path.exists(respaldo):
                    os.rename(ruta, respaldo)
                    self.stdout.write(f'  respaldo: {respaldo}')
            with open(ruta, 'w', encoding='utf-8') as archivo:
                archivo.write(contenido)
            self.stdout.write(self.style.SUCCESS(f'  escrito: {ruta}'))

        self.stdout.write('\nAplicar sin cortar llamadas en curso:')
        self.stdout.write('  sudo asterisk -rx "pjsip reload"')
        self.stdout.write('  sudo asterisk -rx "dialplan reload"')

    def _pjsip(self, troncales, asesores):
        partes = [CABECERA, '[transport-udp]\ntype = transport\nprotocol = udp\n'
                            'bind = 0.0.0.0:5060\n']

        for asesor in asesores:
            extension = asesor.extension_sip.strip()
            clave = (asesor.clave_sip or '').strip()
            if not clave:
                partes.append(f'\n; {extension} ({asesor.nombre}) sin clave SIP: no se genera.\n'
                              f'; Ponle una en Centro de telefonía → Asesores.\n')
                continue
            partes.append(f"""
[{extension}]
type = endpoint
transport = transport-udp
context = desde-interno
disallow = all
allow = alaw,ulaw
auth = {extension}-auth
aors = {extension}
callerid = {asesor.nombre} <{extension}>
direct_media = no

[{extension}-auth]
type = auth
auth_type = userpass
username = {extension}
password = {clave}

[{extension}]
type = aor
max_contacts = 2
remove_existing = yes
""")
        return ''.join(partes) + self._pjsip_troncales(troncales)

    def _pjsip_troncales(self, troncales):
        partes = []
        for troncal in troncales:
            nombre = self._identificador(troncal)
            partes.append(f"""
[{nombre}]
type = registration
transport = transport-udp
outbound_auth = {nombre}-auth
server_uri = sip:{troncal.host}:{troncal.puerto}
client_uri = sip:{troncal.usuario or ''}@{troncal.host}
retry_interval = 60
""".rstrip() + '\n' if troncal.registrar else '')
            partes.append(f"""
[{nombre}-auth]
type = auth
auth_type = userpass
username = {troncal.usuario or ''}
password = {troncal.clave or ''}

[{nombre}-aor]
type = aor
contact = sip:{troncal.host}:{troncal.puerto}

[{nombre}-endpoint]
type = endpoint
transport = transport-udp
context = {troncal.contexto}
disallow = all
allow = {troncal.codec_preferido}
outbound_auth = {nombre}-auth
aors = {nombre}-aor
direct_media = no

[{nombre}-identify]
type = identify
endpoint = {nombre}-endpoint
match = {troncal.host}
""")
        return ''.join(partes)

    def _dialplan(self, troncales, numeros, asesores):
        host = (settings.VOZ_PUBLIC_HOST or '127.0.0.1').split('/')[0]
        aviso = f'http://127.0.0.1:{self._puerto_panel()}/telefonia/webhook/asterisk/'
        audiosocket = f'{settings.AUDIOSOCKET_HOST}:{settings.AUDIOSOCKET_PUERTO}'

        contextos = sorted({troncal.contexto for troncal in troncales} or {'desde-troncal'})
        partes = [CABECERA,
                  f'; Panel: {host}\n; Aviso de llamada: {aviso}\n'
                  f'; Audio: AudioSocket en {audiosocket}\n']

        atencion = f"""
[atender-con-ia]
exten => _X.,1,NoOp(Callcenter IA: ${{CALLERID(num)}} marca ${{EXTEN}})
 same => n,Answer()
 same => n,Set(CALLUUID=${{SHELL(uuidgen -r | tr -d '\\n')}})
 same => n,Set(AVISO=${{CURL({aviso},uuid=${{CALLUUID}}&from=${{CALLERID(num)}}&to=${{EXTEN}})}})
 same => n,GotoIf($["${{AVISO}}" = ""]?sinpanel)
 same => n,GotoIf($[${{REGEX("\\"error\\": false" ${{AVISO}})}} = 0]?sinpanel)
 same => n,AudioSocket(${{CALLUUID}},{audiosocket})
 same => n,Hangup()
 same => n(sinpanel),NoOp(El panel no aceptó la llamada: sin número o sin flujo activo)
 same => n,Playback(vm-goodbye)
 same => n,Hangup()
"""
        partes.append(atencion)

        for contexto in contextos:
            partes.append(f"""
[{contexto}]
exten => _X.,1,Goto(atender-con-ia,${{EXTEN}},1)
""")

        if numeros:
            partes.append('\n; Números cargados en el panel:\n')
            for numero in numeros:
                flujo = numero.flujo.nombre if numero.flujo_id else 'SIN FLUJO'
                partes.append(f';   {numero.numero} → {flujo}\n')

        # La extensión de prueba manda el id del flujo, no un número: sirve para
        # oír al bot antes de tener un DID contratado.
        flujo_prueba = self._flujo_de_prueba(numeros)
        partes.append(f"""
[desde-interno]
; Marca 1000 desde el softphone y te atiende la IA, sin gastar un minuto de
; teléfono ni depender del carrier. Es la forma de probar todo el pipeline.
exten => 1000,1,NoOp(Prueba del bot desde una extension interna)
 same => n,Answer()
 same => n,Set(CALLUUID=${{SHELL(uuidgen -r | tr -d '\\n')}})
 same => n,Set(AVISO=${{CURL({aviso},uuid=${{CALLUUID}}&from=${{CALLERID(num)}}&to=interno&flujo={flujo_prueba})}})
 same => n,GotoIf($[${{REGEX("\\"error\\": false" ${{AVISO}})}} = 0]?atender-con-ia,s,sinpanel)
 same => n,AudioSocket(${{CALLUUID}},{audiosocket})
 same => n,Hangup()
""")
        for asesor in asesores:
            extension = asesor.extension_sip.strip()
            partes.append(f"""exten => {extension},1,NoOp(Llamada interna a {asesor.nombre})
 same => n,Dial(PJSIP/{extension},30)
 same => n,Hangup()
""")
        if not asesores:
            partes.append('; Sin asesores con extensión: no hay softphones que registrar.\n'
                          '; Cárgalos en Centro de telefonía → Asesores, con su clave SIP.\n')
        return ''.join(partes)

    def _flujo_de_prueba(self, numeros):
        """Flujo que atiende la extensión 1000: el del primer número, o el primero activo."""
        from ivr.models import FlujoVoz

        for numero in numeros:
            if numero.flujo_id:
                return numero.flujo_id
        flujo = FlujoVoz.objects.filter(status=True, activo=True).order_by('id').first()
        return flujo.id if flujo else 0

    def _identificador(self, troncal):
        limpio = ''.join(c if c.isalnum() else '-' for c in troncal.nombre.lower())
        return f'troncal-{limpio}'.strip('-')

    def _puerto_panel(self):
        dominio = (settings.VOZ_PUBLIC_HOST or '').strip()
        if ':' in dominio:
            return dominio.rsplit(':', 1)[-1]
        return '9000'
