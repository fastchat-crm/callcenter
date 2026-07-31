"""Configuracion del proyecto callcenter.

Todo lo sensible o dependiente del servidor vive en `credenciales.json`
(ver `credenciales_template.json`). El archivo real nunca se versiona.
"""
import json
import os
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ruta_credenciales = os.path.join(BASE_DIR, 'credenciales.json')
if not os.path.exists(_ruta_credenciales):
    _ruta_credenciales = os.path.join(BASE_DIR, 'credenciales_template.json')

with open(_ruta_credenciales, encoding='utf-8') as _archivo:
    data = json.load(_archivo)

# --- Base de datos PostgreSQL ---
POSTGRES_DBNAME = data.get('POSTGRES_DBNAME', 'callcenter')
POSTGRES_USER = data.get('POSTGRES_USER', 'callcenter')
POSTGRES_PASSWORD = data.get('POSTGRES_PASSWORD', 'callcenter')
POSTGRES_HOST = data.get('POSTGRES_HOST', '127.0.0.1')
POSTGRES_PORT = data.get('POSTGRES_PORT', '5432')

# --- Nucleo Django ---
SECRET_KEY = data.get('SECRET_KEY', 'cambiame-en-produccion')
DEBUG = bool(data.get('DEBUG', True))
IP_PUBLICA = data.get('IP_PUBLICA', '127.0.0.1')
DOMINIO_GENERAL = data.get('DOMINIO_GENERAL', '') or IP_PUBLICA
USE_SSL = bool(data.get('USE_SSL', False))
URL_GENERAL = ('https://' if USE_SSL else 'http://') + DOMINIO_GENERAL

ALLOWED_HOSTS = data.get('ALLOWED_HOSTS') or ['*']
if DEBUG and 'testserver' not in ALLOWED_HOSTS and '*' not in ALLOWED_HOSTS:
    # El cliente de pruebas de Django usa este host.
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, 'testserver']
CSRF_TRUSTED_ORIGINS = data.get('CSRF_TRUSTED_ORIGINS') or [
    URL_GENERAL,
    f'http://{IP_PUBLICA}',
    f'https://{IP_PUBLICA}',
]

SECURE_SSL_REDIRECT = USE_SSL and not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'

# --- Redis (channel layer + cache) ---
REDIS_HOST = data.get('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(data.get('REDIS_PORT', 6379) or 6379)
USAR_REDIS = bool(data.get('USAR_REDIS', True))

# --- Voz: host publico para las URL wss:// que recibe el carrier ---
VOZ_PUBLIC_HOST = data.get('VOZ_PUBLIC_HOST', '') or DOMINIO_GENERAL
VOZ_WS_ESQUEMA = 'wss' if USE_SSL else 'ws'

# --- Motor de voz (100% servicios gratuitos / auto-hospedados) ---
VOZ_STT_MOTOR = data.get('VOZ_STT_MOTOR', 'faster_whisper')
VOZ_WHISPER_SIZE = data.get('VOZ_WHISPER_SIZE', 'small')
VOZ_WHISPER_DEVICE = data.get('VOZ_WHISPER_DEVICE', 'cpu')
VOZ_WHISPER_COMPUTE = data.get('VOZ_WHISPER_COMPUTE', 'int8')
VOZ_TTS_MOTOR = data.get('VOZ_TTS_MOTOR', 'piper')
VOZ_PIPER_MODELO = data.get('VOZ_PIPER_MODELO', 'media/piper/es_MX-claude-high.onnx')
VOZ_EDGE_TTS_VOZ = data.get('VOZ_EDGE_TTS_VOZ', 'es-EC-LuisNeural')
VOZ_UMBRAL_SILENCIO = int(data.get('VOZ_UMBRAL_SILENCIO', 500) or 500)
VOZ_MS_SILENCIO_FIN_TURNO = int(data.get('VOZ_MS_SILENCIO_FIN_TURNO', 800) or 800)
VOZ_GRABAR_LLAMADAS = bool(data.get('VOZ_GRABAR_LLAMADAS', True))

# AudioSocket: el puente con Asterisk auto-hospedado. Escucha solo en loopback
# porque Asterisk corre en el mismo servidor; exponerlo sería dejar el audio de
# las llamadas abierto a internet sin autenticación.
AUDIOSOCKET_HOST = data.get('AUDIOSOCKET_HOST', '127.0.0.1')
AUDIOSOCKET_PUERTO = int(data.get('AUDIOSOCKET_PUERTO', 8090) or 8090)

# --- Embeddings locales para el RAG (sin costo de API) ---
RAG_MODELO_EMBEDDINGS = data.get('RAG_MODELO_EMBEDDINGS', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
RAG_DIRECTORIO_VECTORSTORE = data.get('RAG_DIRECTORIO_VECTORSTORE', 'vectorstore')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'daphne',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # APPS LOCALES
    'core.apps.CoreConfig',
    'clientes.apps.ClientesConfig',
    'autenticacion.apps.AutenticacionConfig',
    'seguridad.apps.SeguridadConfig',
    'panel.apps.PanelConfig',
    'telefonia.apps.TelefoniaConfig',
    'ivr.apps.IvrConfig',
    'llamadas.apps.LlamadasConfig',
    'agentes_ia.apps.AgentesIaConfig',
    'voz.apps.VozConfig',
    # PAQUETES
    'channels',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.custom_middleware.RequestMiddleware',
    'core.custom_middleware.DatosInicialesApp',
]

ROOT_URLCONF = 'callcenterdj.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.datos_sistema',
                'core.context_processors.cliente_panel',
                'core.context_processors.guia_pantalla',
            ],
        },
    },
]

WSGI_APPLICATION = 'callcenterdj.wsgi.application'
ASGI_APPLICATION = 'callcenterdj.asgi.application'

CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
if USAR_REDIS:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [(REDIS_HOST, REDIS_PORT)]},
        },
    }
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/1',
        },
    }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': POSTGRES_DBNAME,
        'USER': POSTGRES_USER,
        'PASSWORD': POSTGRES_PASSWORD,
        'HOST': POSTGRES_HOST,
        'PORT': POSTGRES_PORT,
        'ATOMIC_REQUESTS': True,
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'autenticacion.Usuario'
LOGIN_URL = '/login/'

LANGUAGE_CODE = 'es-ec'
TIME_ZONE = data.get('TIME_ZONE', 'America/Guayaquil')
USE_I18N = True
USE_L10N = True
USE_TZ = False

STATIC_URL = '/static/'
if DEBUG:
    STATIC_ROOT = ''
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
else:
    STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
SITE_STORAGE = Path(BASE_DIR) / 'media'

DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440 * 10
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
X_FRAME_OPTIONS = 'SAMEORIGIN'
DEFAULT_CHARSET = 'utf-8'

NOMBRE_SISTEMA = data.get('NOMBRE_SISTEMA', 'Callcenter IA')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'loggers': {
        'voz': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'ivr': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'telefonia': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'agentes_ia': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}
