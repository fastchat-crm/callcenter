# Base de datos — PostgreSQL

El proyecto usa PostgreSQL como única base. No hay soporte para SQLite: el modelo de
llamadas usa `JSONField` e índices compuestos que conviene mantener en un motor real.

## 1. Instalación

```bash
sudo apt install -y postgresql postgresql-contrib libpq-dev
sudo systemctl enable --now postgresql
psql --version    # 14 o superior
```

## 2. Usuario y base

```bash
sudo -u postgres psql <<'SQL'
CREATE USER callcenter WITH PASSWORD 'una-clave-larga-y-aleatoria';
CREATE DATABASE callcenter OWNER callcenter ENCODING 'UTF8' TEMPLATE template0;
GRANT ALL PRIVILEGES ON DATABASE callcenter TO callcenter;
ALTER ROLE callcenter SET client_encoding TO 'utf8';
ALTER ROLE callcenter SET default_transaction_isolation TO 'read committed';
ALTER ROLE callcenter SET timezone TO 'America/Guayaquil';
SQL
```

Verifica la conexión con el usuario de la aplicación:

```bash
PGPASSWORD='una-clave-larga-y-aleatoria' psql -h 127.0.0.1 -U callcenter -d callcenter -c '\conninfo'
```

## 3. Configuración en el proyecto

En `credenciales.json`:

```json
{
  "POSTGRES_DBNAME": "callcenter",
  "POSTGRES_USER": "callcenter",
  "POSTGRES_PASSWORD": "una-clave-larga-y-aleatoria",
  "POSTGRES_HOST": "127.0.0.1",
  "POSTGRES_PORT": "5432"
}
```

`callcenterdj/settings.py` activa `ATOMIC_REQUESTS`: cada request corre dentro de una
transacción, así que un error a mitad de un guardado no deja registros a medias.

## 4. Migraciones

```bash
./venv/bin/python manage.py migrate
```

Al cambiar modelos:

```bash
./venv/bin/python manage.py makemigrations <app>
./venv/bin/python manage.py migrate
```

Nunca edites una migración ya aplicada: crea una nueva.

## 5. Modelo de datos

### Telefonía

| Tabla | Campos clave |
|---|---|
| `telefonia_proveedortelefonia` | `driver` (asterisk, twilio, telnyx…), credenciales de API, costo por minuto |
| `telefonia_troncalsip` | host, puerto, transporte, contexto del dialplan |
| `telefonia_numerotelefonico` | `numero` **único** en E.164, `pais_iso`, `flujo`, `idioma`, `concurrencia_maxima` |
| `telefonia_asesorhumano` | destino de transferencia, horario y prioridad |

### Motor IVR

| Tabla | Campos clave |
|---|---|
| `ivr_flujovoz` | saludo, despedida, agente IA, asesor de respaldo, reintentos |
| `ivr_pasovoz` | `tipo`, `texto`, `variable`, `validacion`, `paso_siguiente`, `paso_error`. Único por (`flujo`, `codigo`) |
| `ivr_opcionpaso` | `tecla` DTMF y `frases` de voz que llevan a otro paso |

### Llamadas

| Tabla | Campos clave |
|---|---|
| `llamadas_llamada` | `call_id`, `stream_sid`, números, `estado`, `resultado`, `datos_capturados` (JSONB), `transcripcion` |
| `llamadas_turnollamada` | cada intervención con latencias STT/LLM/TTS separadas |
| `llamadas_transferenciallamada` | motivo, destino y estado del escalamiento |
| `llamadas_grabacionllamada` | archivo, formato y backend de almacenamiento |

Índices creados por la migración inicial: `(estado, -fecha_inicio)` y `(numero_origen)` sobre
`llamadas_llamada` — son los dos filtros del panel y del monitor.

### Agentes IA

| Tabla | Campos clave |
|---|---|
| `agentes_ia_apikeyia` | proveedor, clave, modelo, `base_url`, consumo acumulado |
| `agentes_ia_agenteia` | prompt del sistema, tono, temperatura, tope de oraciones, colección RAG |
| `agentes_ia_coleccionconocimiento` | `slug` (nombre de la carpeta del vectorstore), fragmentos indexados |
| `agentes_ia_consumoia` | tokens y latencia por turno, para costeo |

Todos los modelos heredan de `core.custom_models.ModeloBase`: `usuario_creacion`,
`fecha_registro`, `usuario_modificacion`, `fecha_modificacion` y `status`.
**`status = False` es el borrado lógico** — nunca se ejecuta `DELETE`.

## 6. Consultas útiles

```sql
-- Minutos consumidos por mes
SELECT date_trunc('month', fecha_inicio) AS mes,
       count(*) AS llamadas,
       round(sum(duracion_segundos) / 60.0, 1) AS minutos
FROM llamadas_llamada
WHERE status
GROUP BY 1 ORDER BY 1 DESC;

-- Motivos de escalamiento a humano
SELECT motivo, count(*) FROM llamadas_transferenciallamada
WHERE status GROUP BY 1 ORDER BY 2 DESC;

-- Llamadas por país
SELECT pais_iso, count(*), round(avg(duracion_segundos)) AS seg_promedio
FROM llamadas_llamada WHERE status AND pais_iso <> '' GROUP BY 1 ORDER BY 2 DESC;

-- Latencia de los últimos 500 turnos de la IA
SELECT round(avg(latencia_ms)) AS ms_promedio, max(latencia_ms) AS ms_peor
FROM (SELECT latencia_ms FROM llamadas_turnollamada
      WHERE rol = 'ia' ORDER BY id DESC LIMIT 500) t;
```

## 7. Respaldos

```bash
# Respaldo diario comprimido
sudo -u postgres pg_dump -Fc callcenter > /var/backups/callcenter_$(date +%F).dump

# Restauración
sudo -u postgres pg_restore -d callcenter --clean --if-exists /var/backups/callcenter_2026-07-31.dump
```

Cron sugerido (`crontab -e`):

```cron
30 3 * * * sudo -u postgres pg_dump -Fc callcenter > /var/backups/callcenter_$(date +\%F).dump && find /var/backups -name 'callcenter_*.dump' -mtime +14 -delete
```

Las grabaciones viven en `media/grabaciones/`: respáldalas aparte con `rsync` o súbelas a un
bucket compatible con S3.

## 8. Afinado

Para un VPS de 4 GB, en `/etc/postgresql/*/main/postgresql.conf`:

```conf
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 16MB
maintenance_work_mem = 256MB
max_connections = 100
random_page_cost = 1.1          # discos SSD/NVMe
```

Reinicia con `sudo systemctl restart postgresql`.

Si el servidor de base está en otra máquina, abre `listen_addresses` y agrega la línea
correspondiente en `pg_hba.conf` con `scram-sha-256`; nunca `trust`.

## 9. Retención

Las transcripciones crecen rápido. Para conservar 12 meses:

```sql
DELETE FROM llamadas_turnollamada
WHERE llamada_id IN (SELECT id FROM llamadas_llamada
                     WHERE fecha_inicio < now() - interval '12 months');
```

Si el cliente maneja datos sensibles (salud, financieros), revisa antes qué exige la
normativa local sobre conservación y sobre sacar audio del país.
