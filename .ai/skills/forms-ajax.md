# Formularios y AJAX — callcenter

Contrato real del panel. **No es el de fastchatdj**: aquí no hay jQuery, DataTables ni
SweetAlert. El despachador es `static/js/app.js` (objeto `App`) y el backend responde
`JsonResponse`.

---

## Contrato de la vista

```
GET  sin action      → listado paginado
GET  ?action=add     → JSON con el HTML del formulario (va a un modal)
GET  ?action=change  → igual, con la instancia cargada
GET  ?action=ver     → plantilla de detalle (HTML, no JSON)
POST action=add      → crea
POST action=change   → edita
POST action=delete   → borrado lógico: status = False
```

### GET de formulario

```python
return JsonResponse({'result': True, 'data': plantilla.render(data, request)})
# error
return JsonResponse({'result': False, 'message': 'El registro no existe.'})
```

`App` inyecta `data` dentro del modal. Si `result` es `False`, pinta `message`.

### POST

Devuelve una **lista con un objeto** (`App.procesarRespuesta` acepta lista u objeto suelto,
pero `core/crud.py` usa lista y conviene no divergir):

```python
# éxito, recargando el listado
return JsonResponse([{'error': False, 'reload': True}], safe=False)

# éxito sin recargar
return JsonResponse([{'error': False, 'message': 'Indexado.', 'reload': False}], safe=False)

# error general
return JsonResponse([{'error': True, 'message': 'No se pudo conectar con el proveedor.'}],
                    safe=False)

# errores de formulario, campo por campo
return JsonResponse([{'error': True, 'message': 'Revisa los datos.',
                      'errores': [{'campo': 'numero', 'mensaje': 'Formato inválido.'}]}],
                    safe=False)
```

Claves que entiende el cliente:

| Clave | Efecto |
|---|---|
| `error` | `true` pinta el aviso en rojo y no cierra el modal |
| `message` | texto del aviso |
| `reload` | `false` evita el recargado de página tras guardar |
| `errores` | lista `{campo, mensaje}`; se pintan bajo cada input |

En vistas propias (fuera de `vista_crud`) el error se devuelve con la línea, que ahorra
media hora de búsqueda:

```python
except Exception as ex:
    linea = sys.exc_info()[-1].tb_lineno
    return JsonResponse({'error': True, 'message': f'{ex} - Línea {linea}'}, status=400)
```

---

## Del lado de la plantilla

Los botones no llevan `onclick`: declaran su intención y `App` los engancha solo.

```html
<button class="boton boton-primario" data-accion="add" data-titulo="Nuevo número">Nuevo número</button>
<button class="boton boton-sm" data-accion="change" data-id="{{ filtro.id }}" data-titulo="Editar número">Editar</button>
<button class="boton boton-sm boton-peligro" data-accion="delete" data-id="{{ filtro.id }}"
        data-mensaje="¿Eliminar el número {{ filtro.numero }}?">Eliminar</button>
```

Para una acción propia se hace el `fetch` a mano, siempre con el token:

```javascript
const cuerpo = new FormData();
cuerpo.append('action', 'sincronizar');
cuerpo.append('csrfmiddlewaretoken', App.token());
fetch(window.location.pathname, { method: 'POST', body: cuerpo })
    .then((respuesta) => respuesta.json())
    .then((datos) => App.aviso(datos.message || 'Listo.', datos.error ? 'error' : 'exito'));
```

`App.aviso(texto, tipo)` — tipo ∈ `exito` | `error` | `alerta`.

---

## Formularios

Heredan de `FormularioBase`, que hace tres cosas que no hay que repetir en cada form:
aplica las clases del diseño, filtra `status=True` en los querysets de las FK y los acota al
cliente activo. Un `forms.ModelForm` pelado sale sin estilo y, peor, ofrece registros de
otros clientes en sus desplegables.

```python
class NumeroForm(FormularioBase):
    class Meta:
        model = NumeroTelefonico
        fields = ('numero', 'proveedor', 'flujo', 'agente_ia', 'activo')
        labels = {'numero': 'Número', 'agente_ia': 'Agente IA'}

    def clean_numero(self):
        numero = (self.cleaned_data['numero'] or '').strip()
        if not numero.startswith('+'):
            raise forms.ValidationError('Usa el formato internacional: +593987654321.')
        return numero
```

Un `forms.Form` plano (no ModelForm) **no** pasa por `FormularioBase`: hay que aplicar las
clases a mano en `__init__`, como hace `RegistroForm`.

Archivos: todo `FileField`/`ImageField` declara `FileExtensionValidator` y un validador de
tamaño de `core/validadores.py`.

---

## Errores frecuentes

❌:
```python
JsonResponse({'success': True})            # la clave es 'error', invertida
return JsonResponse(respuesta)             # falta safe=False si es lista
<button onclick="editar(3)">              # App engancha por data-accion
Modulo.objects.filter(...)                 # sin acotar al cliente
forms.ModelForm                            # sin FormularioBase: fuga entre clientes
```

✅:
```python
JsonResponse([{'error': False, 'reload': True}], safe=False)
<button data-accion="change" data-id="3" data-titulo="Editar">
acotar(NumeroTelefonico.objects.filter(status=True), request)
class NumeroForm(FormularioBase):
```
