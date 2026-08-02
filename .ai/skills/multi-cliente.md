# Multi-cliente — callcenter

Ocupa el lugar que en fastchatdj tiene `sweetalert-legacy.md`: es la regla propia de este
proyecto, la que más caro sale romper. Un fallo de aislamiento no da error — devuelve datos
de otro cliente con toda normalidad.

El núcleo está en `clientes/contexto.py`.

---

## Quién es quién

| | `usuario.cliente_id` | Ve |
|---|---|---|
| Operador | `None` | Todos los clientes; elige uno en la barra superior |
| Cliente | el suyo | Solo el suyo, sin selector |
| Operador en modo cliente | `None` + sesión `ver_como_cliente` | Lo que vería un cliente |

```python
from clientes.contexto import acotar, cliente_actual, en_modo_cliente, es_operador, solo_operador
```

El modo cliente existe para comprobar de verdad qué ve quien va a usar el sistema, en lugar
de imaginárselo. `RUTAS_SIEMPRE_PERMITIDAS` (en `seguridad/models.py`) mantiene abierta la
puerta de vuelta: sin ella, entrar en modo cliente dejaba encerrado al operador.

---

## Las tres capas

Ninguna sustituye a la otra. Una consulta puede estar acotada y aun así filtrarse por un id
en la URL; un permiso de rol puede conceder una pantalla que no tiene sentido para un cliente.

### 1. Consultas — `acotar()`

```python
data['numeros'] = acotar(NumeroTelefonico.objects.filter(status=True), request)
```

`core/crud.py` ya lo aplica en `vista_crud`, y `_obtener()` rechaza el id de otro cliente:
sin eso, `?action=change&pk=44` era suficiente para leer un registro ajeno.

Las consultas agregadas de `llamadas/consultas.py` reciben `cliente` y **devuelven vacío si
llega `None`**, para que una pantalla que se olvide de pasarlo no muestre los datos de todos.

### 2. Vistas — `@solo_operador`

Para lo que es del operador aunque el modelo tenga `cliente`: credenciales del carrier,
parámetros del sistema, listado de clientes.

```python
@secure_module
@solo_operador
def proveedor_view(request):
    ...
```

### 3. URLs — el perfil del módulo

`Modulo.perfil` ∈ `ambos` | `administrador` | `cliente`. Se declara en
`seguridad/sincronizacion.py` (`SOLO_ADMINISTRADOR`, `SOLO_CLIENTE`) y se aplica en
`modulos_de_usuario()`, que es lo que consultan **tanto el menú como el guardia de acceso**:
marcar una pantalla como del administrador no solo la esconde, también cierra la puerta a
quien escriba la URL a mano.

El rol sigue mandando sobre qué se concede; el perfil solo recorta. Se revisa entero en
*Seguridad → Árbol del menú*, y `_refrescar_perfil()` nunca pisa una restricción puesta a
mano desde el panel.

---

## Modelos

Todo modelo de negocio lleva su cliente:

```python
class NumeroTelefonico(ModeloBase):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT,
                                related_name='numeros')
```

La única excepción se declara explícita, y hoy solo la usa `ApiKeyIA`:

```python
class ApiKeyIA(ModeloBase):
    CLIENTE_COMPARTIBLE = True   # una llave del operador puede servir a varios clientes
```

En `vista_crud`, a un modelo no compartible se le impone el cliente activo al crear. Un
modelo compartible decide en su formulario si la fila es de un cliente o del operador.

---

## Lo que ya se rompió una vez

- Un cliente leía las credenciales SIP del operador por `?action=change`. → `@solo_operador`.
- Los desplegables ofrecían registros dados de baja y de otros clientes. → `FormularioBase`.
- `_preparar_agente` caía en cualquier agente activo del sistema si el del número faltaba:
  el asistente contestaba con la base de conocimiento **de otro cliente**. → siempre acotado
  al cliente de la llamada.
- Un cliente entraba a `/doc/despliegue/` (IP del servidor) y `/doc/propuesta/` (precios de
  venta) escribiendo la URL. → índice filtrado **y** slug bloqueado en `panel/view_doc.py`.

El patrón se repite: **filtrar la lista no basta si el acceso directo sigue abierto.**

---

## Cómo se comprueba

No con lectura de código. Se crea una cuenta de cliente y se mira:

```python
from django.test import Client
from autenticacion.models import Usuario
from seguridad.models import modulos_de_usuario, puede_entrar

u = Usuario.objects.get(username='...')
print(puede_entrar(u, '/telefonia/proveedores/'))   # False
print(sorted(modulos_de_usuario(u).values_list('url', flat=True)))
c = Client(); c.force_login(u)
print(c.get('/telefonia/proveedores/').status_code)  # 302
```
