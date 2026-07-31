"""Costeo del consumo de IA.

Tarifas públicas por cada 1.000 tokens (entrada, salida). Es un **estimado** para
el tablero: el cobro real lo hace el proveedor. Los modelos auto-hospedados valen
cero. Un modelo no listado cae al precio de su familia y, si tampoco coincide, a
un valor conservador para no subestimar el gasto.
"""
from decimal import Decimal

PRECIO_USD_POR_1K_TOKENS = {
    # Google
    'gemini-2.5-flash': (0.00030, 0.00250),
    'gemini-2.5-flash-lite': (0.00010, 0.00040),
    'gemini-2.5-pro': (0.00125, 0.01000),
    'gemini-1.5-flash': (0.000075, 0.00030),
    'gemini-1.5-pro': (0.00125, 0.00500),
    # OpenAI
    'gpt-4o-mini': (0.00015, 0.00060),
    'gpt-4o': (0.00250, 0.01000),
    'gpt-4.1-mini': (0.00040, 0.00160),
    'gpt-4.1-nano': (0.00010, 0.00040),
    # Groq — capa gratuita; se costea en cero mientras no se pase al plan pago
    'llama-3.3-70b-versatile': (0.0, 0.0),
    'llama-3.1-8b-instant': (0.0, 0.0),
    # DeepSeek
    'deepseek-chat': (0.00027, 0.00110),
    'deepseek-reasoner': (0.00055, 0.00219),
}

_PRECIO_POR_PREFIJO = (
    ('gemini-', (0.00030, 0.00250)),
    ('gpt-4', (0.00050, 0.00200)),
    ('claude-', (0.00300, 0.01500)),
    ('deepseek', (0.00055, 0.00219)),
)

# Modelos abiertos servidos en la nube (Ollama Cloud y similares): no publican
# tarifa por token, así que se estima con el promedio del mercado para modelos
# abiertos de tamaño medio. Sirve para comparar agentes entre sí, no para pagar.
_PRECIO_MODELO_ABIERTO_NUBE = (0.00020, 0.00060)
_PREFIJOS_MODELO_ABIERTO = ('qwen', 'llama', 'mistral', 'gemma', 'phi', 'gpt-oss',
                            'kimi', 'glm', 'minimax', 'deepseek-r1')

_PRECIO_DEFECTO = (0.00100, 0.00400)

# Proveedores que hoy no facturan por token: auto-hospedados y capas gratuitas.
PROVEEDORES_SIN_COSTO = ('ollama_local', 'groq', 'openrouter')


def precio_modelo(modelo: str, proveedor: str = '') -> tuple:
    """(USD entrada, USD salida) por cada 1.000 tokens."""
    if proveedor in PROVEEDORES_SIN_COSTO:
        return (0.0, 0.0)

    nombre = (modelo or '').strip()
    if nombre in PRECIO_USD_POR_1K_TOKENS:
        return PRECIO_USD_POR_1K_TOKENS[nombre]

    minuscula = nombre.lower()
    for prefijo, precio in _PRECIO_POR_PREFIJO:
        if minuscula.startswith(prefijo):
            return precio
    if any(minuscula.startswith(prefijo) for prefijo in _PREFIJOS_MODELO_ABIERTO):
        return _PRECIO_MODELO_ABIERTO_NUBE
    return _PRECIO_DEFECTO


def costo_usd(modelo: str, tokens_entrada: int, tokens_salida: int, proveedor: str = '') -> Decimal:
    entrada, salida = precio_modelo(modelo, proveedor)
    total = (tokens_entrada or 0) / 1000.0 * entrada + (tokens_salida or 0) / 1000.0 * salida
    return Decimal(str(round(total, 6)))


def resumen_por_modelo(consulta):
    """Agrega un queryset de ConsumoIA por modelo, con costo estimado."""
    from django.db.models import Avg, Count, Sum

    filas = consulta.values('modelo', 'proveedor').annotate(
        turnos=Count('id'),
        entrada=Sum('tokens_entrada'),
        salida=Sum('tokens_salida'),
        costo=Sum('costo_usd'),
        latencia=Avg('latencia_ms'),
    )
    resultado = []
    for fila in filas:
        resultado.append({
            'modelo': fila['modelo'] or '(sin modelo)',
            'proveedor': fila['proveedor'] or '—',
            'turnos': fila['turnos'],
            'entrada': fila['entrada'] or 0,
            'salida': fila['salida'] or 0,
            'total': (fila['entrada'] or 0) + (fila['salida'] or 0),
            'costo_usd': float(fila['costo'] or 0),
            'latencia_ms': int(fila['latencia'] or 0),
        })
    resultado.sort(key=lambda item: item['costo_usd'], reverse=True)
    return resultado


def resumen_por_agente(consulta):
    from django.db.models import Avg, Count, Sum

    filas = consulta.values('agente__nombre').annotate(
        turnos=Count('id'),
        entrada=Sum('tokens_entrada'),
        salida=Sum('tokens_salida'),
        costo=Sum('costo_usd'),
        latencia=Avg('latencia_ms'),
    ).order_by('-costo')
    return [
        {
            'agente': fila['agente__nombre'] or '(sin agente)',
            'turnos': fila['turnos'],
            'total': (fila['entrada'] or 0) + (fila['salida'] or 0),
            'costo_usd': float(fila['costo'] or 0),
            'latencia_ms': int(fila['latencia'] or 0),
        }
        for fila in filas
    ]


def totales(consulta):
    from django.db.models import Avg, Count, Sum

    datos = consulta.aggregate(
        turnos=Count('id'),
        entrada=Sum('tokens_entrada'),
        salida=Sum('tokens_salida'),
        costo=Sum('costo_usd'),
        latencia=Avg('latencia_ms'),
        fallidos=Count('id', filter=~models_q_error_vacio()),
    )
    entrada = datos['entrada'] or 0
    salida = datos['salida'] or 0
    return {
        'turnos': datos['turnos'] or 0,
        'tokens_entrada': entrada,
        'tokens_salida': salida,
        'tokens_total': entrada + salida,
        'costo_usd': round(float(datos['costo'] or 0), 4),
        'latencia_ms': int(datos['latencia'] or 0),
        'fallidos': datos['fallidos'] or 0,
    }


def models_q_error_vacio():
    from django.db.models import Q

    return Q(error__isnull=True) | Q(error='')


def costo_por_llamada(llamada):
    """Costo de IA de una llamada concreta."""
    from django.db.models import Sum

    from agentes_ia.models import ConsumoIA

    total = ConsumoIA.objects.filter(llamada=llamada).aggregate(t=Sum('costo_usd'))['t']
    return round(float(total or 0), 6)
