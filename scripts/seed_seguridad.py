"""Carga inicial de seguridad: módulos, secciones del menú y roles.

    ./venv/bin/python manage.py shell < scripts/seed_seguridad.py

Idempotente. Sincroniza los módulos con las URLs reales del proyecto, arma las
secciones del menú y crea cuatro roles con permisos razonables.
"""
from django.contrib.auth.models import Group

from seguridad.models import GroupModulo, Modulo, ModuloGrupo
from seguridad.sincronizacion import sincronizar_modulos

print('→ Sincronizando módulos con las URLs del proyecto')
creados, existentes = sincronizar_modulos()
print(f'  {creados} nuevos · {existentes} ya existían · {Modulo.objects.count()} en total')

SECCIONES = (
    (10, 'Operación', ('/panel/', '/llamadas/listado/', '/llamadas/monitor/', '/llamadas/transferencias/')),
    (20, 'Configuración de voz', ('/ivr/flujos/', '/agentes-ia/agentes/', '/agentes-ia/conocimiento/',
                                  '/agentes-ia/apikeys/', '/agentes-ia/consumo/', '/voz/demo/')),
    (30, 'Telefonía', ('/telefonia/proveedores/', '/telefonia/numeros/', '/telefonia/asesores/')),
    (40, 'Seguridad', ('/seguridad/usuarios/', '/seguridad/roles/', '/seguridad/modulos/',
                       '/seguridad/secciones/', '/seguridad/auditoria/')),
    (50, 'Ayuda', ('/doc/', '/perfilpanel/')),
)

print('\n→ Secciones del menú')
for prioridad, nombre, urls in SECCIONES:
    seccion, creada = ModuloGrupo.objects.get_or_create(
        nombre=nombre, defaults={'prioridad': prioridad},
    )
    if creada:
        seccion.prioridad = prioridad
        seccion.save()
    modulos = list(Modulo.objects.filter(url__in=urls))
    seccion.modulos.set(modulos)
    faltantes = set(urls) - {modulo.url for modulo in modulos}
    print(f'  {nombre}: {len(modulos)} módulos' + (f' · no encontrados: {sorted(faltantes)}' if faltantes else ''))

# Los módulos que nadie reclamó quedan visibles pero fuera del menú, para que no
# ensucien la barra lateral mientras siguen protegidos.
sin_seccion = Modulo.objects.filter(grupos_menu__isnull=True)
if sin_seccion.exists():
    print(f'  sin sección: {sin_seccion.count()} → se ocultan del menú')
    sin_seccion.update(visible_menu=False)

ROLES = {
    'Administrador': None,  # todos los módulos
    'Supervisor': ('/panel/', '/llamadas/', '/ivr/', '/agentes-ia/', '/telefonia/', '/voz/', '/doc/', '/perfilpanel/'),
    'Asesor': ('/panel/', '/llamadas/listado/', '/llamadas/monitor/', '/voz/demo/', '/doc/', '/perfilpanel/'),
    'Auditor': ('/panel/', '/llamadas/', '/agentes-ia/consumo/', '/seguridad/auditoria/', '/doc/', '/perfilpanel/'),
}

print('\n→ Roles')
todos = list(Modulo.objects.filter(status=True))
for nombre, prefijos in ROLES.items():
    rol, _ = Group.objects.get_or_create(name=nombre)
    permisos, _ = GroupModulo.objects.get_or_create(group=rol)
    if prefijos is None:
        modulos = todos
        permisos.descripcion = 'Acceso completo al sistema.'
    else:
        modulos = [m for m in todos if any(m.url.startswith(prefijo) for prefijo in prefijos)]
        permisos.descripcion = {
            'Supervisor': 'Opera y configura flujos, agentes y telefonía.',
            'Asesor': 'Atiende llamadas y consulta el historial.',
            'Auditor': 'Solo lectura de llamadas, consumo y auditoría.',
        }.get(nombre, '')
    permisos.modulos.set(modulos)
    permisos.save()
    print(f'  {nombre}: {len(modulos)} módulos')

print('\nListo. Los superusuarios siguen viendo todo, sin importar su rol.')
