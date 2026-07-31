# Multi-cliente: quién es dueño de qué

El sistema es un **core que se opera por cliente**. Cada cliente registra sus números, y lo
que configura dentro no existe para los demás.

## Qué pertenece a un cliente

Estos modelos llevan FK `cliente`, y todo lo que se ve en pantalla sale filtrado por el
cliente activo:

| Modelo | App |
|---|---|
| `NumeroTelefonico` | `telefonia` |
| `AsesorHumano` | `telefonia` |
| `FlujoVoz` | `ivr` |
| `AgenteIA` | `agentes_ia` |
| `ColeccionConocimiento` | `agentes_ia` |
| `Llamada` | `llamadas` |

Un cliente puede tener **N números** apuntando al flujo que le corresponda.

Lo que **no** es por cliente, porque es infraestructura del operador:

- `ProveedorTelefonia` y `TroncalSIP` — el cable con el carrier, se comparte.
- `AudioSistema` — audios pregrabados del sistema.
- `Configuracion` — la marca del operador y el token global de IA.

## La excepción declarada

`ApiKeyIA` lleva `CLIENTE_COMPARTIBLE = True`. Su FK `cliente` es opcional:

| Campo `cliente` | Qué significa |
|---|---|
| Vacío | Llave por defecto del operador: la ven y la usan todos los clientes |
| Con cliente | Exclusiva de ese cliente |

Sirve para arrancar con una sola llave del operador y, cuando un cliente trae la suya,
asignársela sin tocar al resto. Es la única excepción; si agregas otro modelo compartible,
declara la constante y no inventes un mecanismo nuevo.

## Quién ve qué

| Usuario | Alcance |
|---|---|
| Con `cliente` asignado | Solo ese cliente. No puede cambiarlo ni sabe que existen otros |
| Sin `cliente` | Del operador: los ve todos y elige con cuál trabajar |

El cliente activo del operador vive en la **sesión**, y se cambia con el selector de la barra
superior o entrando por `/clientes/cambiar/`. El campo se asigna en *Centro de seguridad →
Usuarios*.

## Cómo se aplica el filtro

No se repite en cada vista. Hay tres puntos, y conviene conocerlos antes de escribir una
vista nueva:

1. **`core/crud.py`** — cualquier pantalla que use `vista_crud` queda acotada sola. Además
   `_obtener()` impide editar, ver o borrar un registro de otro cliente aunque se pida su id
   a mano: responde «El registro no existe».
2. **`core/custom_forms.py`** — `FormularioBase._acotar_al_cliente()` recorta los desplegables,
   para que ningún formulario ofrezca el flujo, el agente o el asesor de otro cliente.
3. **`clientes/contexto.acotar(queryset, request)`** — para las vistas que no usan el CRUD
   genérico (conocimiento, consumo, pasos del flujo, llamadas, tablero, demo, AJAX).

```python
from clientes.contexto import acotar

listado = acotar(FlujoVoz.objects.filter(status=True), request)
```

Al crear, `core/crud.py` impone el cliente activo. Los modelos compartibles quedan fuera de
esa imposición: ahí manda el formulario.

## En el motor de voz

Una llamada hereda el cliente **del número marcado**; en el demo por navegador, del flujo
elegido. Dos respaldos que parecen inofensivos y no lo son:

- Si el número no declara flujo, el respaldo se busca **dentro del mismo cliente**. Atender
  con el flujo de otro sería contestar con su guion.
- Si el flujo no declara agente, el respaldo también se busca dentro del cliente. Contestar
  con el agente de otro le entregaría **su base de conocimiento** a quien llamó.

Los dos caminos estuvieron mal al principio: tomaban el primer registro activo del sistema.

## Al agregar un modelo configurable

**Ponle la FK `cliente`.** Sin ella queda visible para todos, y el filtro automático no puede
adivinar que debía ser por cliente:

```python
cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, null=True,
                            related_name='<plural>')
```

Si el modelo tiene que poder ser del operador además de de un cliente, agrega
`CLIENTE_COMPARTIBLE = True` y deja que el formulario decida el dueño.

## Cómo comprobar que aísla

La prueba que importa no es que el listado se vea bien, sino que **pedir el id ajeno a mano
falle**:

```python
otro = FlujoVoz.objects.exclude(cliente=cliente_del_usuario).first()
respuesta = cliente_http.get(f'/ivr/flujos/?action=change&id={otro.id}')
# → {"result": false, "message": "El registro no existe."}
```
