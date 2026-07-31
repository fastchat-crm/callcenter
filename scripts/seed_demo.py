"""Carga inicial: usuario admin, proveedor gratuito, agente IA y un flujo IVR completo.

Uso:
    python manage.py shell < scripts/seed_demo.py

Es idempotente: se puede ejecutar varias veces sin duplicar registros.
"""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'callcenterdj.settings')
try:
    django.setup()
except RuntimeError:
    pass

from agentes_ia.models import AgenteIA, ApiKeyIA, ColeccionConocimiento, DocumentoConocimiento  # noqa: E402
from autenticacion.models import Usuario  # noqa: E402
from ivr.models import FlujoVoz, OpcionPaso, PasoVoz  # noqa: E402
from telefonia.models import AsesorHumano, ProveedorTelefonia  # noqa: E402

print('→ Usuario administrador')
usuario, creado = Usuario.objects.get_or_create(
    username='admin',
    defaults={'first_name': 'Administrador', 'last_name': 'Callcenter',
              'email': 'admin@callcenter.local', 'is_staff': True, 'is_superuser': True,
              'perfil': 'administrador'},
)
if creado:
    usuario.set_password('admin1234')
    usuario.save()
    print('  admin / admin1234  (cámbiala apenas el sistema salga a producción)')
else:
    print('  ya existía')

print('→ Proveedor de telefonía auto-hospedado')
proveedor, _ = ProveedorTelefonia.objects.get_or_create(
    nombre='Asterisk local',
    defaults={'driver': 'asterisk', 'activo': True, 'costo_minuto_entrante': 0,
              'notas': 'Instancia propia en el servidor. Sin costo por minuto.'},
)

print('→ Llave de IA (Ollama local, sin costo ni API key)')
llave, _ = ApiKeyIA.objects.get_or_create(
    alias='ollama-local',
    defaults={'proveedor': 4, 'clave': '', 'modelo': 'qwen2.5:7b-instruct',
              'base_url': 'http://127.0.0.1:11434', 'activo': True},
)

print('→ Colección de conocimiento de ejemplo')
coleccion, _ = ColeccionConocimiento.objects.get_or_create(
    nombre='Planes y servicios',
    defaults={'descripcion': 'Tarifario y preguntas frecuentes que responde el agente.'},
)
DocumentoConocimiento.objects.get_or_create(
    coleccion=coleccion,
    titulo='Preguntas frecuentes',
    defaults={'contenido': (
        'Horario de atención: lunes a viernes de 08:00 a 18:00, sábados de 09:00 a 13:00. '
        'El plan Básico cuesta 25 dólares mensuales e incluye soporte por correo. '
        'El plan Empresarial cuesta 90 dólares mensuales, incluye soporte telefónico prioritario '
        'y hasta cinco usuarios. La activación se realiza en 24 horas hábiles. '
        'Para reclamos técnicos se transfiere la llamada a un asesor humano.'
    )},
)

print('→ Agente IA')
agente, _ = AgenteIA.objects.get_or_create(
    nombre='Recepcionista virtual',
    defaults={'apikey': llave, 'coleccion': coleccion, 'activo': True,
              'descripcion': 'Atiende la línea principal, informa sobre planes y toma datos del cliente.'},
)

print('→ Asesor humano de respaldo')
asesor, _ = AsesorHumano.objects.get_or_create(
    nombre='Asesor comercial',
    defaults={'numero_destino': '+593987654321', 'extension_sip': '1001',
              'departamento': 'Comercial', 'horario': 'laboral', 'prioridad': 1},
)

print('→ Flujo IVR de ejemplo')
flujo, creado_flujo = FlujoVoz.objects.get_or_create(
    nombre='Recepción principal',
    defaults={'agente_ia': agente, 'asesor_respaldo': asesor,
              'descripcion': 'Saludo, menú, captura de cédula, agente IA y transferencia.'},
)

if creado_flujo or not flujo.pasos.exists():
    despedida = PasoVoz.objects.create(
        flujo=flujo, codigo='despedida', nombre='Despedida', tipo='colgar', orden=99,
        texto='Gracias por comunicarte con nosotros. Que tengas un excelente día.',
    )
    transferencia = PasoVoz.objects.create(
        flujo=flujo, codigo='transferir', nombre='Transferir a asesor', tipo='transferencia',
        orden=50, asesor=asesor, texto='Te comunico con un asesor. Un momento por favor.',
    )
    consulta_ia = PasoVoz.objects.create(
        flujo=flujo, codigo='consulta_ia', nombre='Consulta con el agente IA', tipo='agente_ia',
        orden=30, agente_ia=agente, max_turnos_ia=8, paso_siguiente=despedida,
        texto='Con gusto. Cuéntame qué necesitas saber sobre nuestros planes.',
    )
    captura_cedula = PasoVoz.objects.create(
        flujo=flujo, codigo='captura_cedula', nombre='Captura de cédula', tipo='captura',
        orden=20, variable='cedula', validacion='cedula_ec', modo_captura='hibrido',
        paso_siguiente=consulta_ia, paso_error=transferencia,
        texto='Para ayudarte, dime tu número de cédula. Puedes marcarlo en el teclado.',
    )
    menu = PasoVoz.objects.create(
        flujo=flujo, codigo='menu_principal', nombre='Menú principal', tipo='menu', orden=10,
        texto='¿En qué te puedo ayudar?', paso_error=transferencia,
    )
    OpcionPaso.objects.create(paso=menu, tecla='1', etiqueta='información de planes',
                              frases='planes, precios, tarifas, costo', paso_destino=captura_cedula, orden=1)
    OpcionPaso.objects.create(paso=menu, tecla='2', etiqueta='soporte técnico',
                              frases='soporte, ayuda, no funciona, falla', paso_destino=transferencia, orden=2)
    OpcionPaso.objects.create(paso=menu, tecla='0', etiqueta='hablar con un asesor',
                              frases='asesor, humano, persona', paso_destino=transferencia, orden=3)

    flujo.paso_inicial = menu
    flujo.save()
    print('  flujo con 5 pasos y 3 opciones creado')
else:
    print('  el flujo ya tenía pasos')

print('\nListo. Ingresa en http://<ip-del-servidor>/login/')
