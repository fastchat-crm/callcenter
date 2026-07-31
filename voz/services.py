"""Pipeline de voz con servicios gratuitos: STT → LLM → TTS.

  STT  faster-whisper local (por defecto) o Vosk local
  LLM  agentes_ia (Gemini free / Groq free / Ollama local)
  TTS  Piper local (por defecto), espeak-ng local o edge-tts (gratuito, nube)

Los modelos se cargan de forma perezosa y quedan en memoria: Whisper y Piper
tardan segundos en inicializar y compartirlos entre llamadas es la diferencia
entre 3 segundos y 300 milisegundos por turno.
"""
from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
import wave

from django.conf import settings

from voz import audio as audio_utils

logger = logging.getLogger('voz')

SAMPLE_RATE_TELEFONICO = 8000
SAMPLE_RATE_NAVEGADOR = 16000

_stt = None
_tts_piper = None


# =====================================================================
# STT — reconocimiento de voz
# =====================================================================
def _cargar_whisper():
    global _stt
    if _stt is not None:
        return _stt
    from faster_whisper import WhisperModel

    tamano = settings.VOZ_WHISPER_SIZE
    dispositivo = settings.VOZ_WHISPER_DEVICE
    computo = settings.VOZ_WHISPER_COMPUTE
    logger.info('[voz] cargando faster-whisper %s (%s/%s)', tamano, dispositivo, computo)
    _stt = WhisperModel(tamano, device=dispositivo, compute_type=computo)
    return _stt


def _cargar_vosk():
    global _stt
    if _stt is not None:
        return _stt
    from vosk import Model

    ruta = os.path.join(settings.MEDIA_ROOT, 'vosk', 'es')
    logger.info('[voz] cargando Vosk desde %s', ruta)
    _stt = Model(ruta)
    return _stt


def transcribir_pcm(pcm: bytes, sample_rate: int = SAMPLE_RATE_TELEFONICO, idioma: str = 'es') -> str:
    """PCM 16-bit mono → texto. Devuelve cadena vacía si no se entendió nada."""
    if not pcm:
        return ''
    motor = settings.VOZ_STT_MOTOR
    try:
        if motor == 'vosk':
            return _transcribir_vosk(pcm, sample_rate)
        return _transcribir_whisper(pcm, sample_rate, idioma)
    except Exception:
        logger.exception('[voz] falló la transcripción con motor %s', motor)
        return ''


def _transcribir_whisper(pcm, sample_rate, idioma):
    modelo = _cargar_whisper()
    buffer = io.BytesIO(audio_utils.pcm_a_wav(pcm, sample_rate))
    segmentos, _ = modelo.transcribe(buffer, language=idioma, beam_size=1, vad_filter=True)
    return ' '.join(segmento.text for segmento in segmentos).strip()


def _transcribir_vosk(pcm, sample_rate):
    import json

    from vosk import KaldiRecognizer

    modelo = _cargar_vosk()
    if sample_rate != 16000:
        pcm = audio_utils.remuestrear(pcm, sample_rate, 16000)
    reconocedor = KaldiRecognizer(modelo, 16000)
    reconocedor.AcceptWaveform(pcm)
    return (json.loads(reconocedor.FinalResult()) or {}).get('text', '').strip()


# =====================================================================
# TTS — sintesis de voz
# =====================================================================
def _cargar_piper():
    global _tts_piper
    if _tts_piper is not None:
        return _tts_piper
    try:
        from piper import PiperVoice
    except ImportError:
        logger.warning('[voz] piper-tts no está instalado (pip install piper-tts)')
        return None

    ruta = settings.VOZ_PIPER_MODELO
    if not os.path.isabs(ruta):
        ruta = os.path.join(settings.BASE_DIR, ruta)
    if not os.path.exists(ruta):
        logger.warning('[voz] no existe el modelo Piper en %s — ejecuta scripts/descargar_modelos_voz.sh', ruta)
        return None
    logger.info('[voz] cargando Piper %s', ruta)
    _tts_piper = PiperVoice.load(ruta)
    return _tts_piper


def sintetizar_pcm(texto: str, sample_rate: int = SAMPLE_RATE_NAVEGADOR) -> bytes:
    """Texto → PCM 16-bit mono al sample rate pedido."""
    texto = (texto or '').strip()
    if not texto:
        return b''

    motor = settings.VOZ_TTS_MOTOR
    generadores = {
        'piper': _tts_piper_pcm,
        'espeak': _tts_espeak_pcm,
        'edge': _tts_edge_pcm,
    }
    orden = [motor] + [nombre for nombre in ('piper', 'espeak', 'edge') if nombre != motor]
    for nombre in orden:
        generador = generadores.get(nombre)
        if generador is None:
            continue
        try:
            pcm, rate_origen = generador(texto)
            if pcm:
                if nombre != motor:
                    logger.info('[voz] TTS resuelto con motor alterno: %s', nombre)
                return audio_utils.remuestrear(pcm, rate_origen, sample_rate)
        except Exception:
            logger.exception('[voz] falló el motor TTS %s', nombre)
    logger.error('[voz] ningún motor TTS disponible — revisa docs/SERVICIOS_GRATUITOS.md')
    return b''


def sintetizar_ulaw(texto: str) -> bytes:
    """Texto → mu-law 8 kHz, el formato que consumen los Media Streams."""
    pcm = sintetizar_pcm(texto, SAMPLE_RATE_TELEFONICO)
    return audio_utils.pcm_a_ulaw(pcm) if pcm else b''


def _tts_piper_pcm(texto):
    voz = _cargar_piper()
    if voz is None:
        return b'', SAMPLE_RATE_NAVEGADOR
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as archivo:
        voz.synthesize(texto, archivo)
    buffer.seek(0)
    return _leer_wav(buffer)


def _tts_espeak_pcm(texto):
    """espeak-ng: instalado con `apt install espeak-ng`, voz robótica pero gratuita."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temporal:
        ruta = temporal.name
    try:
        subprocess.run(
            ['espeak-ng', '-v', 'es-419', '-s', '150', '-w', ruta, texto],
            check=True, capture_output=True, timeout=30,
        )
        with open(ruta, 'rb') as archivo:
            return _leer_wav(io.BytesIO(archivo.read()))
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def _tts_edge_pcm(texto):
    """edge-tts: voces neuronales de Microsoft, gratuitas y sin API key."""
    import asyncio

    import edge_tts

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temporal:
        ruta_mp3 = temporal.name
    ruta_wav = ruta_mp3.replace('.mp3', '.wav')
    try:
        async def generar():
            comunicador = edge_tts.Communicate(texto, settings.VOZ_EDGE_TTS_VOZ)
            await comunicador.save(ruta_mp3)

        asyncio.run(generar())
        subprocess.run(
            ['ffmpeg', '-y', '-i', ruta_mp3, '-ar', '16000', '-ac', '1', ruta_wav],
            check=True, capture_output=True, timeout=30,
        )
        with open(ruta_wav, 'rb') as archivo:
            return _leer_wav(io.BytesIO(archivo.read()))
    finally:
        for ruta in (ruta_mp3, ruta_wav):
            if os.path.exists(ruta):
                os.remove(ruta)


def _leer_wav(buffer):
    buffer.seek(0)
    with wave.open(buffer, 'rb') as archivo:
        rate = archivo.getframerate()
        ancho = archivo.getsampwidth()
        pcm = archivo.readframes(archivo.getnframes())
    return audio_utils.ancho_a_16bits(pcm, ancho), rate


# =====================================================================
# Diagnostico
# =====================================================================
def estado_motores() -> dict:
    """Resumen para el panel: qué componentes del pipeline están listos."""
    estado = {
        'stt_motor': settings.VOZ_STT_MOTOR,
        'stt_listo': False,
        'tts_motor': settings.VOZ_TTS_MOTOR,
        'tts_listo': False,
        'llm_listo': False,
        'detalle': [],
    }
    try:
        if settings.VOZ_STT_MOTOR == 'vosk':
            import vosk  # noqa: F401
        else:
            import faster_whisper  # noqa: F401
        estado['stt_listo'] = True
    except ImportError as ex:
        estado['detalle'].append(f'STT no disponible: {ex}')

    ruta_piper = settings.VOZ_PIPER_MODELO
    if not os.path.isabs(ruta_piper):
        ruta_piper = os.path.join(settings.BASE_DIR, ruta_piper)
    if os.path.exists(ruta_piper):
        estado['tts_listo'] = True
    else:
        estado['detalle'].append('Modelo Piper no descargado; se usará espeak-ng o edge-tts.')
        estado['tts_listo'] = _hay_comando('espeak-ng')

    try:
        from agentes_ia.models import AgenteIA
        estado['llm_listo'] = AgenteIA.objects.filter(status=True, activo=True).exists()
        if not estado['llm_listo']:
            estado['detalle'].append('No hay agentes IA activos configurados.')
    except Exception as ex:
        estado['detalle'].append(f'No se pudo consultar agentes: {ex}')
    return estado


def _hay_comando(comando):
    from shutil import which
    return which(comando) is not None
