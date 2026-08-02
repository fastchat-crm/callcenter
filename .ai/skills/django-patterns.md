# Patrones Django — callcenter

Los patrones generales (select_related, transacciones, F, Q, signals) son los mismos que en
`fastchatdj/.ai/skills/django-patterns.md` y no se repiten aquí. Esto recoge lo que en este
proyecto se hace distinto.

---

## Soft delete

```python
# ❌
llamada.delete()

# ✅
llamada.status = False
llamada.save(request)
```

`ModeloBase.save(request)` autopobla `usuario_modificacion`. Los listados filtran siempre
`status=True`, y `status` no se muestra como columna ni como campo de formulario.

**No modificar migraciones ya aplicadas** — crear nuevas.

---

## Acotar al cliente

Toda consulta de negocio pasa por `acotar()`. Está detallado en `skills/multi-cliente.md`;
es la regla que más caro sale saltarse.

```python
from clientes.contexto import acotar

acotar(Llamada.objects.filter(status=True), request).select_related('flujo', 'numero')
```

---

## Fechas: `USE_TZ = False`

```python
# ❌ falla en este proyecto
timezone.localdate()

# ✅
timezone.now().date()
```

---

## Parámetros en caliente

Lo que se ajusta sin desplegar no va a `settings.py` ni a `credenciales.json`: se declara en
el catálogo de `core/parametros.py` y la base solo guarda los valores cambiados, con 30 s de
caché.

```python
from core.parametros import obtener

umbral = obtener('VOZ_UMBRAL_SILENCIO')
```

Agregar un parámetro es agregar una entrada al catálogo; no hace falta migración.

---

## Servicios externos: nunca tumban la pantalla

Weaviate, Asterisk, Groq o Tika pueden no responder. Consultarlos desde una vista se envuelve
siempre, porque un panel en blanco por un servicio caído es peor que un panel incompleto.

```python
def _estado_servicios():
    try:
        return estado_servicios()
    except Exception:
        return []
```

Lo mismo con lo que corre al cerrar una llamada (`interna.procesar_cierre`,
`registrar_contacto`): es de mejor esfuerzo y **no debe impedir que la llamada quede
guardada**. Se registra con `logger.exception` y se sigue.

---

## Lo que bloquea, fuera del hilo

STT, LLM, TTS y ORM se llaman desde los consumers con `asyncio.to_thread` o `sync_to_async`.
Un `await` que en realidad bloquea congela **todas** las llamadas en curso: hay un solo
proceso y los modelos de voz se comparten.

```python
texto = await asyncio.to_thread(transcribir, audio)
llamada = await sync_to_async(Llamada.objects.get)(pk=pk)
```

`voz/services.py` carga Whisper y Piper de forma perezosa y los deja en memoria: no se
instancia un modelo por llamada.

---

## Módulos y permisos

Una URL nueva no queda protegida sola. Después de agregarla:

1. Entrar a *Seguridad → Módulos del sistema* y usar **Sincronizar con las URLs**.
2. Si es del operador o del cliente, declararla en `SOLO_ADMINISTRADOR` / `SOLO_CLIENTE`
   (`seguridad/sincronizacion.py`) antes de sincronizar.
3. Darle una entrada en `core/guias.py`: de ahí sale la explicación de la pantalla **y** la
   descripción del módulo. Una sola fuente.
4. Asignarla a la sección del menú y a los roles que la necesiten.

---

## Errores frecuentes

❌:
```python
timezone.localdate()                        # USE_TZ = False
Llamada.objects.filter(status=True)         # sin acotar al cliente
modelo.delete()                             # borrado físico, pierde auditoría
instancia.save()                            # sin request: no registra quién editó
whisper.load_model('base')                  # dentro de la vista, un modelo por llamada
```

✅:
```python
timezone.now().date()
acotar(Llamada.objects.filter(status=True), request)
instancia.status = False; instancia.save(request)
from voz.services import transcribir       # carga perezosa, una sola vez
```
