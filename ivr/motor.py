"""Ejecutor del flujo IVR paso a paso.

El motor es sincrono y sin estado global: recibe la llamada, resuelve el paso
actual y devuelve un `ResultadoPaso` con lo que debe decir la IA y si espera
respuesta del cliente. El consumer de voz solo traduce eso a audio.

Reglas heredadas del motor de chatbot de fastchat:
  - comparacion insensible a mayusculas y tildes
  - ante entrada invalida se repite el paso hasta `max_reintentos`
  - agotados los reintentos se va a `paso_error` o se transfiere al asesor
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

logger = logging.getLogger('ivr')

AFIRMACIONES = ('si', 'sii', 'claro', 'correcto', 'afirmativo', 'dale', 'ok', 'exacto', 'asi es')
NEGACIONES = ('no', 'nop', 'negativo', 'incorrecto', 'nunca')
PALABRAS_ASESOR = ('asesor', 'humano', 'persona', 'operador', 'ejecutivo', 'agente real', 'hablar con alguien')
PALABRAS_FIN = ('adios', 'chao', 'hasta luego', 'gracias eso es todo', 'nada mas', 'colgar')


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y sin puntuación.

    Lo último importa más de lo que parece: Whisper devuelve "uno." y "¿planes?",
    y sin limpiar los signos ninguna opción del menú coincide jamás.
    """
    texto = (texto or '').strip().lower()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(caracter for caracter in texto if unicodedata.category(caracter) != 'Mn')
    texto = re.sub(r'[^\w\s]', ' ', texto, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', texto).strip()


def _raiz(palabra: str) -> str:
    """Raíz pobre pero suficiente: quita el plural para que 'planes' case con 'plan'."""
    palabra = palabra.strip()
    for sufijo in ('es', 's'):
        if len(palabra) > 4 and palabra.endswith(sufijo):
            return palabra[: -len(sufijo)]
    return palabra


def coincide_frase(frase: str, entrada: str) -> bool:
    """¿La frase configurada aparece en lo que dijo el cliente?

    Primero busca la frase literal; si no, compara raíces palabra por palabra,
    de modo que "planes" reconozca "plan empresarial".
    """
    frase = normalizar(frase)
    entrada = normalizar(entrada)
    if not frase or not entrada:
        return False
    if frase in entrada:
        return True
    palabras_entrada = {_raiz(palabra) for palabra in entrada.split()}
    palabras_frase = [_raiz(palabra) for palabra in frase.split()]
    return bool(palabras_frase) and all(palabra in palabras_entrada for palabra in palabras_frase)


def solo_digitos(texto: str) -> str:
    return ''.join(caracter for caracter in (texto or '') if caracter.isdigit())


NUMEROS_HABLADOS = {
    'cero': '0', 'uno': '1', 'una': '1', 'dos': '2', 'tres': '3', 'cuatro': '4',
    'cinco': '5', 'seis': '6', 'siete': '7', 'ocho': '8', 'nueve': '9',
}


def digitos_desde_voz(texto: str) -> str:
    """Convierte 'cero nueve ocho' o '098...' en una cadena de digitos."""
    directos = solo_digitos(texto)
    if directos:
        return directos
    partes = normalizar(texto).split()
    return ''.join(NUMEROS_HABLADOS[parte] for parte in partes if parte in NUMEROS_HABLADOS)


@dataclass
class ResultadoPaso:
    texto: str = ''
    esperar_respuesta: bool = True
    finalizar: bool = False
    transferir: object = None
    modo_agente_ia: bool = False
    paso_codigo: str = ''
    variables: dict = field(default_factory=dict)


class MotorIVR:
    """Recorre un `FlujoVoz` para una `Llamada` concreta."""

    def __init__(self, flujo, llamada=None):
        self.flujo = flujo
        self.llamada = llamada
        self.variables: dict = dict((llamada.datos_capturados or {}) if llamada else {})
        self.paso = None
        self.reintentos = 0
        self.turnos_ia = 0
        self.historial: list[tuple[str, str]] = []

    # --- Ciclo de vida ---
    def iniciar(self) -> ResultadoPaso:
        self.paso = self.flujo.primer_paso()
        saludo = self._interpolar(self.flujo.saludo)
        if self.paso is None:
            return ResultadoPaso(texto=saludo, esperar_respuesta=True, modo_agente_ia=True,
                                 paso_codigo='sin_pasos')
        resultado = self._ejecutar_paso(self.paso)
        resultado.texto = f'{saludo} {resultado.texto}'.strip()
        return resultado

    def procesar_entrada(self, texto: str = '', dtmf: str = '') -> ResultadoPaso:
        """Entra la respuesta del cliente (voz transcrita y/o teclas)."""
        entrada_normalizada = normalizar(texto)

        if self._pide_asesor(entrada_normalizada):
            return self._transferir(motivo='solicitud_cliente')
        if self._quiere_terminar(entrada_normalizada):
            return ResultadoPaso(texto=self._interpolar(self.flujo.despedida), esperar_respuesta=False,
                                 finalizar=True, paso_codigo='despedida')

        if self.paso is None:
            return ResultadoPaso(texto=self.flujo.mensaje_error, esperar_respuesta=True, modo_agente_ia=True)

        tipo = self.paso.tipo
        if tipo == 'menu':
            return self._resolver_menu(entrada_normalizada, dtmf)
        if tipo == 'captura':
            return self._resolver_captura(texto, dtmf)
        if tipo == 'agente_ia':
            return self._resolver_agente_ia(texto)
        return self._avanzar(self.paso.paso_siguiente)

    # --- Ejecucion de pasos ---
    def _ejecutar_paso(self, paso) -> ResultadoPaso:
        self.paso = paso
        self.reintentos = 0
        if paso is None:
            return ResultadoPaso(texto=self._interpolar(self.flujo.despedida), esperar_respuesta=False,
                                 finalizar=True, paso_codigo='fin')

        tipo = paso.tipo
        texto = self._interpolar(paso.texto or '')

        if tipo == 'mensaje':
            siguiente = paso.paso_siguiente
            if siguiente is None:
                return ResultadoPaso(texto=f'{texto} {self._interpolar(self.flujo.despedida)}'.strip(),
                                     esperar_respuesta=False, finalizar=True, paso_codigo=paso.codigo)
            resultado_siguiente = self._ejecutar_paso(siguiente)
            resultado_siguiente.texto = f'{texto} {resultado_siguiente.texto}'.strip()
            return resultado_siguiente

        if tipo == 'menu':
            opciones = self._texto_opciones(paso)
            return ResultadoPaso(texto=f'{texto} {opciones}'.strip(), esperar_respuesta=True,
                                 paso_codigo=paso.codigo)

        if tipo == 'captura':
            return ResultadoPaso(texto=texto, esperar_respuesta=True, paso_codigo=paso.codigo)

        if tipo == 'agente_ia':
            self.turnos_ia = 0
            return ResultadoPaso(texto=texto, esperar_respuesta=True, modo_agente_ia=True,
                                 paso_codigo=paso.codigo)

        if tipo == 'transferencia':
            return self._transferir(motivo='paso_flujo', asesor=paso.asesor, texto_previo=texto)

        if tipo == 'condicion':
            destino = paso.paso_siguiente if self._evaluar_condicion(paso.expresion) else paso.paso_error
            return self._ejecutar_paso(destino)

        if tipo == 'webhook':
            self._ejecutar_webhook(paso)
            return self._ejecutar_paso(paso.paso_siguiente)

        if tipo == 'colgar':
            despedida = texto or self._interpolar(self.flujo.despedida)
            return ResultadoPaso(texto=despedida, esperar_respuesta=False, finalizar=True,
                                 paso_codigo=paso.codigo)

        logger.warning('[ivr] tipo de paso desconocido: %s', tipo)
        return self._avanzar(paso.paso_siguiente)

    def _avanzar(self, paso) -> ResultadoPaso:
        return self._ejecutar_paso(paso)

    # --- Resolucion de respuestas ---
    def _resolver_menu(self, entrada, dtmf) -> ResultadoPaso:
        opciones = list(self.paso.opciones.filter(status=True).order_by('orden', 'id'))
        tecla = (dtmf or '').strip()[-1:] or digitos_desde_voz(entrada)[:1]

        if tecla:
            for opcion in opciones:
                if (opcion.tecla or '').strip() == tecla:
                    return self._avanzar(opcion.paso_destino or self.paso.paso_siguiente)

        for opcion in opciones:
            for frase in opcion.lista_frases():
                if coincide_frase(frase, entrada):
                    return self._avanzar(opcion.paso_destino or self.paso.paso_siguiente)
            if coincide_frase(opcion.etiqueta, entrada):
                return self._avanzar(opcion.paso_destino or self.paso.paso_siguiente)

        # Nadie coincidió, pero el cliente dijo algo con sentido. Antes que
        # repetirle el menú como un loro, que le conteste el agente IA.
        if entrada and self.flujo.menu_cae_en_agente and self._hay_agente():
            return ResultadoPaso(texto='', esperar_respuesta=True, modo_agente_ia=True,
                                 paso_codigo=self.paso.codigo, variables=dict(self.variables))

        return self._reintentar()

    def _hay_agente(self):
        return bool(self.flujo.agente_ia_id or (self.paso and self.paso.agente_ia_id))

    def _resolver_captura(self, texto, dtmf) -> ResultadoPaso:
        valor = self._extraer_valor(texto, dtmf)
        valido, mensaje = self._validar(valor)
        if not valido:
            return self._reintentar(mensaje)

        if self.paso.variable:
            self.variables[self.paso.variable] = valor
            self._persistir_variables()
        return self._avanzar(self.paso.paso_siguiente)

    def _resolver_agente_ia(self, texto) -> ResultadoPaso:
        """El agente IA responde; el motor solo controla cuándo salir del paso."""
        self.turnos_ia += 1
        agotado = self.turnos_ia >= (self.paso.max_turnos_ia or 8)
        if agotado and self.paso.paso_siguiente:
            return self._avanzar(self.paso.paso_siguiente)
        return ResultadoPaso(texto='', esperar_respuesta=True, modo_agente_ia=True,
                             paso_codigo=self.paso.codigo, variables=dict(self.variables))

    def _reintentar(self, mensaje='') -> ResultadoPaso:
        self.reintentos += 1
        if self.reintentos > (self.flujo.max_reintentos or 2):
            if self.paso.paso_error:
                return self._avanzar(self.paso.paso_error)
            return self._transferir(motivo='reintentos_agotados')
        texto_error = mensaje or self.flujo.mensaje_error
        repeticion = self._interpolar(self.paso.texto or '')
        if self.paso.tipo == 'menu':
            repeticion = f'{repeticion} {self._texto_opciones(self.paso)}'.strip()
        return ResultadoPaso(texto=f'{texto_error} {repeticion}'.strip(), esperar_respuesta=True,
                             paso_codigo=self.paso.codigo)

    def _transferir(self, motivo='', asesor=None, texto_previo='') -> ResultadoPaso:
        destino = asesor or self.flujo.asesor_respaldo
        if destino is None:
            texto = (f'{texto_previo} En este momento no hay asesores disponibles. '
                     f'{self._interpolar(self.flujo.despedida)}').strip()
            return ResultadoPaso(texto=texto, esperar_respuesta=False, finalizar=True,
                                 paso_codigo='transferencia_fallida')
        texto = texto_previo or f'Te comunico con un asesor, {destino.nombre}. Un momento por favor.'
        logger.info('[ivr] transferencia motivo=%s destino=%s', motivo, destino)
        return ResultadoPaso(texto=texto, esperar_respuesta=False, transferir=destino,
                             paso_codigo='transferencia', variables=dict(self.variables))

    # --- Utilidades ---
    def _extraer_valor(self, texto, dtmf):
        validacion = self.paso.validacion
        if validacion in ('numero', 'cedula_ec', 'documento', 'telefono', 'monto'):
            digitos = solo_digitos(dtmf) or digitos_desde_voz(texto)
            return digitos
        if validacion == 'si_no':
            entrada = normalizar(texto)
            if solo_digitos(dtmf).startswith('1') or any(p in entrada for p in AFIRMACIONES):
                return 'si'
            if solo_digitos(dtmf).startswith('2') or any(p in entrada for p in NEGACIONES):
                return 'no'
            return ''
        return (texto or '').strip()

    def _validar(self, valor):
        if not valor:
            return False, self.flujo.mensaje_error

        validacion = self.paso.validacion
        minimo = self.paso.longitud_minima or 0
        maximo = self.paso.longitud_maxima or 0
        if minimo and len(valor) < minimo:
            return False, f'Necesito al menos {minimo} caracteres.'
        if maximo and len(valor) > maximo:
            return False, f'El dato no puede superar {maximo} caracteres.'

        if validacion == 'cedula_ec':
            from core.validadores import validar_cedula_ecuatoriana
            from django.core.exceptions import ValidationError
            try:
                validar_cedula_ecuatoriana(valor)
            except ValidationError as ex:
                return False, ex.messages[0]
        elif validacion == 'documento' and not 5 <= len(valor) <= 15:
            return False, 'El número de documento no parece válido.'
        elif validacion == 'telefono' and len(valor) < 7:
            return False, 'El número telefónico no parece válido.'
        elif validacion == 'correo' and '@' not in valor:
            return False, 'El correo no parece válido. Dilo letra por letra o deletréalo.'
        elif validacion == 'monto':
            try:
                float(valor.replace(',', '.'))
            except ValueError:
                return False, 'No entendí el monto.'
        return True, ''

    def _texto_opciones(self, paso):
        partes = []
        for opcion in paso.opciones.filter(status=True).order_by('orden', 'id'):
            if opcion.tecla:
                partes.append(f'Marca {opcion.tecla} para {opcion.etiqueta}')
            else:
                partes.append(f'Di {opcion.etiqueta}')
        return '. '.join(partes) + ('.' if partes else '')

    def _interpolar(self, texto):
        if not texto:
            return ''
        resultado = texto
        for clave, valor in self.variables.items():
            resultado = resultado.replace('{' + str(clave) + '}', str(valor))
        return re.sub(r'\{[a-zA-Z_0-9]+\}', '', resultado).strip()

    def _evaluar_condicion(self, expresion):
        """Evalua expresiones simples del tipo `variable operador valor`."""
        if not expresion:
            return False
        patron = re.match(r'^\s*([a-zA-Z_0-9]+)\s*(==|!=|>=|<=|>|<|contiene)\s*(.+?)\s*$', expresion)
        if not patron:
            return False
        nombre, operador, esperado = patron.groups()
        actual = self.variables.get(nombre, '')
        esperado = esperado.strip().strip('"').strip("'")
        try:
            if operador in ('>', '<', '>=', '<='):
                actual_num, esperado_num = float(actual), float(esperado)
                return {
                    '>': actual_num > esperado_num,
                    '<': actual_num < esperado_num,
                    '>=': actual_num >= esperado_num,
                    '<=': actual_num <= esperado_num,
                }[operador]
        except (TypeError, ValueError):
            return False
        if operador == '==':
            return normalizar(str(actual)) == normalizar(esperado)
        if operador == '!=':
            return normalizar(str(actual)) != normalizar(esperado)
        if operador == 'contiene':
            return normalizar(esperado) in normalizar(str(actual))
        return False

    def _ejecutar_webhook(self, paso):
        if not paso.url_webhook:
            return
        try:
            import requests
            metodo = (paso.metodo_webhook or 'POST').upper()
            respuesta = requests.request(metodo, paso.url_webhook, json=self.variables, timeout=8)
            if respuesta.headers.get('content-type', '').startswith('application/json'):
                datos = respuesta.json()
                if isinstance(datos, dict):
                    self.variables.update({str(k): v for k, v in datos.items()})
                    self._persistir_variables()
        except Exception:
            logger.exception('[ivr] webhook falló en paso %s', paso.codigo)

    def _persistir_variables(self):
        if self.llamada is None:
            return
        try:
            self.llamada.datos_capturados = self.variables
            self.llamada.save(update_fields=['datos_capturados'])
        except Exception:
            logger.exception('[ivr] no se pudieron guardar las variables de la llamada')

    def _pide_asesor(self, entrada):
        return any(palabra in entrada for palabra in PALABRAS_ASESOR)

    def _quiere_terminar(self, entrada):
        return any(palabra in entrada for palabra in PALABRAS_FIN)
