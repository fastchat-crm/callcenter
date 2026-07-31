"""Crea el cliente inicial y le asigna todo lo que ya existía.

Antes de esta migración el sistema era de un solo dueño implícito. Se toma el
nombre de la empresa de la configuración general y se lo convierte en el primer
cliente, para que ningún registro quede huérfano.
"""
from django.db import migrations

MODELOS = (
    ('telefonia', 'NumeroTelefonico'),
    ('telefonia', 'AsesorHumano'),
    ('ivr', 'FlujoVoz'),
    ('agentes_ia', 'AgenteIA'),
    ('agentes_ia', 'ColeccionConocimiento'),
    ('llamadas', 'Llamada'),
)


def crear_cliente_inicial(apps, schema_editor):
    Cliente = apps.get_model('clientes', 'Cliente')
    Configuracion = apps.get_model('core', 'Configuracion')

    huerfanos = any(
        apps.get_model(app, modelo).objects.filter(cliente__isnull=True).exists()
        for app, modelo in MODELOS
    )
    if not huerfanos and not Cliente.objects.exists():
        return

    configuracion = Configuracion.objects.order_by('id').first()
    nombre = (getattr(configuracion, 'nombre_empresa', '') or '').strip() or 'Cliente principal'
    cliente = Cliente.objects.filter(nombre=nombre).first()
    if cliente is None:
        cliente = Cliente.objects.create(
            nombre=nombre,
            zona_horaria=getattr(configuracion, 'zona_horaria', None) or 'America/Guayaquil',
            minutos_incluidos_mes=getattr(configuracion, 'minutos_incluidos_mes', None) or 3500,
            correo=getattr(configuracion, 'correo_notificaciones', None),
            telefono=getattr(configuracion, 'telefono_soporte', None),
        )

    for app, modelo in MODELOS:
        apps.get_model(app, modelo).objects.filter(cliente__isnull=True).update(cliente=cliente)


def revertir(apps, schema_editor):
    for app, modelo in MODELOS:
        apps.get_model(app, modelo).objects.update(cliente=None)


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0001_initial'),
        ('core', '0002_alter_configuracion_logo'),
        ('telefonia', '0002_asesorhumano_cliente_numerotelefonico_cliente'),
        ('ivr', '0004_flujovoz_cliente'),
        ('agentes_ia', '0005_agenteia_cliente_coleccionconocimiento_cliente'),
        ('llamadas', '0002_llamada_cliente'),
    ]

    operations = [
        migrations.RunPython(crear_cliente_inicial, revertir),
    ]
