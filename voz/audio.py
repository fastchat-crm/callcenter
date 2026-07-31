"""Conversiones de audio para telefonia.

Usa `audioop` cuando existe (Python <= 3.12). En Python 3.13+ el modulo salio de
la biblioteca estandar, asi que se implementan las mismas operaciones en Python
puro: mu-law, A-law, RMS y remuestreo lineal. El resto del codigo llama siempre
a estas funciones y no le importa cual camino se usa.
"""
from __future__ import annotations

import array
import math

try:  # Python <= 3.12 o paquete audioop-lts instalado
    import audioop  # type: ignore
except ImportError:  # pragma: no cover - depende de la version de Python
    audioop = None

TAMANO_MUESTRA = 2  # PCM 16 bits


# --- Tablas mu-law (G.711) ---
def _pcm_a_ulaw_muestra(muestra: int) -> int:
    SIGNO_BIT = 0x80
    CLIP = 32635
    signo = SIGNO_BIT if muestra < 0 else 0
    if muestra < 0:
        muestra = -muestra
    muestra = min(muestra, CLIP) + 0x84
    exponente = 7
    mascara = 0x4000
    while exponente > 0 and not muestra & mascara:
        exponente -= 1
        mascara >>= 1
    mantisa = (muestra >> (exponente + 3)) & 0x0F
    return ~(signo | (exponente << 4) | mantisa) & 0xFF


def _ulaw_a_pcm_muestra(byte: int) -> int:
    byte = ~byte & 0xFF
    signo = byte & 0x80
    exponente = (byte >> 4) & 0x07
    mantisa = byte & 0x0F
    muestra = ((mantisa << 3) + 0x84) << exponente
    muestra -= 0x84
    return -muestra if signo else muestra


_TABLA_ULAW_A_PCM = [_ulaw_a_pcm_muestra(valor) for valor in range(256)]


def pcm_a_ulaw(pcm: bytes) -> bytes:
    if audioop is not None:
        return audioop.lin2ulaw(pcm, TAMANO_MUESTRA)
    muestras = array.array('h')
    muestras.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    return bytes(_pcm_a_ulaw_muestra(muestra) for muestra in muestras)


def ulaw_a_pcm(ulaw: bytes) -> bytes:
    if audioop is not None:
        return audioop.ulaw2lin(ulaw, TAMANO_MUESTRA)
    muestras = array.array('h', (_TABLA_ULAW_A_PCM[byte] for byte in ulaw))
    return muestras.tobytes()


def rms(pcm: bytes) -> int:
    if len(pcm) < 2:
        return 0
    if audioop is not None:
        return audioop.rms(pcm, TAMANO_MUESTRA)
    muestras = array.array('h')
    muestras.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not muestras:
        return 0
    total = sum(muestra * muestra for muestra in muestras)
    return int(math.sqrt(total / len(muestras)))


def remuestrear(pcm: bytes, origen: int, destino: int) -> bytes:
    """Cambia el sample rate de PCM 16-bit mono."""
    if origen == destino or not pcm:
        return pcm
    if audioop is not None:
        convertido, _ = audioop.ratecv(pcm, TAMANO_MUESTRA, 1, origen, destino, None)
        return convertido

    entrada = array.array('h')
    entrada.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not entrada:
        return b''
    proporcion = destino / origen
    total_salida = int(len(entrada) * proporcion)
    salida = array.array('h', [0] * total_salida)
    for indice in range(total_salida):
        posicion = indice / proporcion
        izquierda = int(posicion)
        derecha = min(izquierda + 1, len(entrada) - 1)
        peso = posicion - izquierda
        salida[indice] = int(entrada[izquierda] * (1 - peso) + entrada[derecha] * peso)
    return salida.tobytes()


def ancho_a_16bits(pcm: bytes, ancho_origen: int) -> bytes:
    if ancho_origen == TAMANO_MUESTRA:
        return pcm
    if audioop is not None:
        return audioop.lin2lin(pcm, ancho_origen, TAMANO_MUESTRA)
    if ancho_origen == 1:
        muestras = array.array('h', ((byte - 128) << 8 for byte in pcm))
        return muestras.tobytes()
    raise ValueError(f'Ancho de muestra no soportado sin audioop: {ancho_origen}')


def duracion_ms(pcm: bytes, sample_rate: int) -> float:
    return (len(pcm) / TAMANO_MUESTRA) * 1000 / max(sample_rate, 1)


def pcm_a_wav(pcm: bytes, sample_rate: int) -> bytes:
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(TAMANO_MUESTRA)
        archivo.setframerate(sample_rate)
        archivo.writeframes(pcm)
    return buffer.getvalue()
