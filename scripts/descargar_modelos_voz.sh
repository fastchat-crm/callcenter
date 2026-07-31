#!/usr/bin/env bash
# Descarga los modelos de voz gratuitos (Piper en español) y precarga Whisper.
#   bash scripts/descargar_modelos_voz.sh [voz]
# Voces disponibles en https://huggingface.co/rhasspy/piper-voices
set -euo pipefail

RAIZ="/home/callcenter"
DESTINO="$RAIZ/media/piper"
VOZ="${1:-es_MX-claude-high}"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/es"

declare -A RUTAS=(
    ["es_MX-claude-high"]="es_MX/claude/high/es_MX-claude-high"
    ["es_ES-davefx-medium"]="es_ES/davefx/medium/es_ES-davefx-medium"
    ["es_ES-sharvard-medium"]="es_ES/sharvard/medium/es_ES-sharvard-medium"
    ["es_AR-daniela-high"]="es_AR/daniela/high/es_AR-daniela-high"
)

RUTA="${RUTAS[$VOZ]:-}"
if [ -z "$RUTA" ]; then
    echo "Voz desconocida: $VOZ"
    echo "Opciones: ${!RUTAS[*]}"
    exit 1
fi

mkdir -p "$DESTINO"
echo "→ Descargando voz Piper: $VOZ"
curl -fL --progress-bar "${BASE}/${RUTA}.onnx"      -o "${DESTINO}/${VOZ}.onnx"
curl -fL --progress-bar "${BASE}/${RUTA}.onnx.json" -o "${DESTINO}/${VOZ}.onnx.json"
echo "  guardado en ${DESTINO}/${VOZ}.onnx"

echo "→ Recuerda dejar esta ruta en credenciales.json:"
echo "    \"VOZ_PIPER_MODELO\": \"media/piper/${VOZ}.onnx\""

echo "→ Precargando modelo Whisper (se descarga una sola vez)"
"$RAIZ/venv/bin/python" - <<'PY' || echo "  faster-whisper aún no está instalado; se descargará en la primera llamada."
from faster_whisper import WhisperModel
import os
tamano = os.getenv('VOZ_WHISPER_SIZE', 'small')
WhisperModel(tamano, device='cpu', compute_type='int8')
print(f'  modelo Whisper {tamano} listo')
PY

echo "Listo."
