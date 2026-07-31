from core.custom_forms import FormularioBase

from .models import AgenteIA, ApiKeyIA, ColeccionConocimiento, DocumentoConocimiento


class ApiKeyForm(FormularioBase):
    class Meta:
        model = ApiKeyIA
        fields = ('cliente', 'alias', 'proveedor', 'clave', 'modelo', 'modelo_embeddings',
                  'base_url', 'limite_mensual_llamadas', 'activo', 'por_defecto')
        labels = {
            'cliente': 'Cliente', 'alias': 'Alias', 'proveedor': 'Proveedor', 'clave': 'Clave API',
            'modelo': 'Modelo', 'modelo_embeddings': 'Modelo de embeddings',
            'base_url': 'URL base (opcional)',
            'limite_mensual_llamadas': 'Límite mensual de llamadas', 'activo': 'Activa',
            'por_defecto': 'Usar por defecto',
        }
        help_texts = {
            'cliente': 'Vacío: llave compartida, disponible para todos los clientes.',
            'por_defecto': 'La que usan los agentes que no eligen llave propia. '
                           'Marcar esta desmarca la anterior del mismo ámbito.',
        }

    def clean(self):
        datos = super().clean()
        if datos.get('por_defecto') and not datos.get('activo'):
            self.add_error('por_defecto', 'Una llave inactiva no puede ser la de por defecto.')
        return datos


class AgenteForm(FormularioBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # En un agente nuevo viene marcada la llave «por defecto», que es lo que
        # se espera al dar de alta el agente de un cliente.
        if not (self.instance and self.instance.pk) and not self.initial.get('apikey'):
            from clientes.contexto import cliente_actual
            from core.custom_middleware import get_current_request

            from .models import ApiKeyIA

            peticion = get_current_request()
            cliente = cliente_actual(peticion) if peticion is not None else None
            defecto = ApiKeyIA.por_defecto_de(cliente)
            if defecto is not None:
                self.fields['apikey'].initial = defecto.pk

    class Meta:
        model = AgenteIA
        fields = ('nombre', 'descripcion', 'apikey', 'coleccion', 'prompt_sistema', 'tono',
                  'idioma', 'temperatura', 'max_tokens_respuesta', 'maximo_oraciones',
                  'usar_rag', 'fragmentos_contexto', 'activo')
        labels = {
            'nombre': 'Nombre', 'descripcion': 'Descripción del negocio', 'apikey': 'Llave de IA',
            'coleccion': 'Base de conocimiento', 'prompt_sistema': 'Instrucciones del sistema',
            'tono': 'Tono', 'idioma': 'Idioma', 'temperatura': 'Temperatura',
            'max_tokens_respuesta': 'Máximo de tokens', 'maximo_oraciones': 'Máximo de oraciones',
            'usar_rag': 'Usar base de conocimiento', 'fragmentos_contexto': 'Fragmentos de contexto',
            'activo': 'Activo',
        }


class ColeccionForm(FormularioBase):
    class Meta:
        model = ColeccionConocimiento
        fields = ('nombre', 'descripcion', 'backend', 'motor_embeddings', 'apikey_embeddings')
        labels = {
            'nombre': 'Nombre', 'descripcion': 'Descripción',
            'backend': 'Dónde se guarda el índice',
            'motor_embeddings': 'Motor de embeddings',
            'apikey_embeddings': 'Llave para embeddings',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo tiene sentido ofrecer llaves de proveedores que generen embeddings.
        # Se vuelve a acotar al cliente porque este queryset pisa al de la base.
        from clientes.contexto import acotar
        from core.custom_middleware import get_current_request

        llaves = ApiKeyIA.objects.filter(status=True, proveedor=1)
        peticion = get_current_request()
        if peticion is not None and getattr(peticion.user, 'is_authenticated', False):
            llaves = acotar(llaves, peticion)
        self.fields['apikey_embeddings'].queryset = llaves.order_by('-activo', 'alias')

    def clean(self):
        datos = super().clean()
        if datos.get('motor_embeddings') == 'gemini' and not datos.get('apikey_embeddings'):
            self.add_error('apikey_embeddings',
                           'Con embeddings de Gemini hay que elegir la llave que los genera.')
        return datos


class DocumentoForm(FormularioBase):
    class Meta:
        model = DocumentoConocimiento
        fields = ('coleccion', 'titulo', 'archivo', 'contenido')
        labels = {
            'coleccion': 'Colección', 'titulo': 'Título', 'archivo': 'Archivo',
            'contenido': 'Texto (opcional si subes archivo)',
        }
