# Contrato HTTP `/v1`

- Base: `http://<host>:8000`
- Versión: `1.0.0`
- Formato: JSON en UTF-8
- Fechas: ISO 8601 en UTC
- Autorización: bearer token en la cabecera `Authorization`

## 1. Arranque

```text
python -m uv run uvicorn vortemis.entrypoints.api:app --host 0.0.0.0 --port 8000
```

Variables:

| Variable | Uso |
|---|---|
| `DATABASE_URL` | PostgreSQL del motor |
| `MODEL_PATH` | Checkpoint para `/v1/engine/metadata` |
| `VORTEMIS_CORS_ORIGINS` | Orígenes permitidos, separados por coma |
| `VORTEMIS_ACCESS_TTL_MINUTES` | Vida del access token, 15 por defecto |
| `VORTEMIS_REFRESH_TTL_DAYS` | Vida del refresh token, 30 por defecto |

OpenAPI: `GET /openapi.json` y `GET /docs`.

## 2. Autenticación

```text
POST /v1/auth/login
{ "username": "admin_carles", "password": "..." }
```

Respuesta `200`:

```json
{
  "access_token": "oX2...",
  "refresh_token": "rT9...",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_expires_in": 2592000,
  "role": "admin"
}
```

- Access token opaco de 32 bytes; en la base solo se guarda su SHA-256.
- Vida del access token: 15 minutos (`VORTEMIS_ACCESS_TTL_MINUTES`).
- Vida del refresh token: 30 días (`VORTEMIS_REFRESH_TTL_DAYS`).
- Códigos: `401` credenciales inválidas, `429` demasiados intentos.
- El rate limit de login se guarda en base de datos: cinco intentos fallidos por usuario bloquean cinco minutos, incluso con varias instancias de la API.

```text
POST /v1/auth/refresh
{ "refresh_token": "rT9..." }
```

- Devuelve un par nuevo y rota ambos tokens.
- El access token anterior queda inválido al instante.
- Si se reutiliza un refresh ya rotado, se revoca la sesión completa y se devuelve `401`.

```text
POST /v1/auth/logout   -> 204
GET  /v1/auth/me       -> { "username": "...", "role": "..." }
```

## 3. Flujos

```text
GET /v1/flows
```

| Parámetro | Tipo | Notas |
|---|---|---|
| `since`, `until` | ISO 8601 | Con zona horaria |
| `src_ip`, `dst_ip` | texto | Coincidencia exacta |
| `src_port`, `dst_port` | 1-65535 | |
| `protocol` | `tcp`, `udp`, `icmp` | |
| `tactic` | `TA0010`, `TA0008`, ... | |
| `min_probability` | 0.0-1.0 | Umbral de anomalía |
| `limit` | 1-500 | 100 por defecto |
| `cursor` | texto | Opaco; viene de `next_cursor` |

Respuesta `200`:

```json
{
  "records": [
    {
      "ts": "2026-11-16T12:00:00+00:00",
      "flow_id": "6f3c...",
      "src_ip": "192.168.1.10",
      "dst_ip": "10.0.0.5",
      "src_port": 50000,
      "dst_port": 443,
      "protocol": "tcp",
      "conn_state": "SF",
      "iat_ms": 12.5,
      "orig_bytes": 1200,
      "resp_bytes": 800,
      "duration": 0.4,
      "anomaly_probability": 0.93,
      "is_anomaly": true,
      "mitre_tactic": "TA0010"
    }
  ],
  "next_cursor": "2026-11-16T12:00:00+00:00|6f3c..."
}
```

`next_cursor` es `null` en la última página. El orden es `ts` descendente, con `flow_id` como desempate.

## 4. Estadísticas

```text
GET /v1/stats/summary
```

Filtros iguales a `/v1/flows` más `threshold` (0.0-1.0, 0.70 por defecto).

```json
{
  "total_flows": 5000,
  "anomalies": 4852,
  "by_tactic": { "TA0010": 12, "TA0011": 3400 }
}
```

```text
GET /v1/stats/top-sources?threshold=0.7&limit=10
```

```json
[{ "src_ip": "192.168.1.252", "flows": 13, "anomalies": 12 }]
```

```text
GET /v1/stats/timeline?threshold=0.7&bucket_seconds=60
```

```json
[{ "bucket_start": "2026-11-16T12:00:00+00:00", "flows": 42, "anomalies": 7 }]
```

`bucket_seconds` va de 10 a 86400.

## 5. Motor

```text
GET /v1/engine/metadata
```

```json
{
  "architecture": "6 -> 16 -> 3 -> 16 -> 6",
  "feature_dim": 6,
  "tau": 0.7455,
  "mean": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
  "std": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
}
```

`404` si no hay checkpoint.

## 6. Administración

Requieren rol `admin`. Cualquier otro rol recibe `403`.

```text
POST /v1/admin/purge                          -> 204
PUT  /v1/admin/operators/{username}/password  -> 204
```

Purga:

- Trunca `fact_network_flows`, borra `ingestion_state` y reescribe el log con la cabecera Zeek.
- Es irreversible: la telemetría anterior no se puede recuperar.
- No toca dimensiones ni operadores.

Rotación de contraseña:

```json
{ "password": "NuevaClave2026!", "role": "analyst" }
```

- `password`: mínimo 12 caracteres.
- `role`: opcional; si se omite, el rol actual no cambia.
- Si el operador no existe, se crea.

## 7. Salud

```text
GET /v1/health   (sin autenticación)
```

```json
{ "status": "ok", "database": "ok" }
```

`503` si la base de datos no responde.

## 8. Errores

```json
{ "detail": "mensaje" }
```

| Código | Cuándo |
|---|---|
| 400 | Cursor inválido |
| 401 | Token ausente, inválido, expirado o revocado |
| 403 | Rol insuficiente |
| 404 | Recurso inexistente |
| 422 | Filtros fuera de rango |
| 429 | Rate limit de login |
| 503 | Base de datos no disponible |

## 9. Reglas del contrato

- `/v1` es aditivo: no se renombran ni se quitan campos dentro de la versión.
- Cualquier cambio incompatible abre `/v2`.
- El frontend fija una versión y copia `openapi.json`.
- La API no conoce PostgreSQL ni el motor; solo `TelemetryReadService`.
- El motor autentica; la API aplica los roles. La purga solo se expondrá a `admin`.

## 10. CORS

- Allowlist explícita por entorno.
- Sin `*` y sin cookies.
- Métodos: `GET` y `POST`.
- Cabeceras: `Authorization`, `Content-Type`.
