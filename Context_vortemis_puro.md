# ESPECIFICACIÓN TÉCNICA Y PLAN MAESTRO DE EJECUCIÓN: PROYECTO VORTEMIS (ARQUITECTURA ORIGINAL PURA)

**Título Oficial:** Análisis Probabilístico de Tráfico de Red para Detección de Anomalías (Enfoque SOC Pasivo)  
**Naturaleza del Sistema:** Motor Analítico Fuera de Banda (*Out-of-Band*), Ingesta Asíncrona por *Streaming*, Vectorización en Pandas/NumPy, Inferencia Estocástica en Tensores con **PyTorch**, Clasificación de Tácticas de Red **MITRE ATT&CK** y Almacenamiento OLAP en **PostgreSQL 16**.

---

## 0. Reglas Inquebrantables para el Agente de Desarrollo

Cualquier agente de IA o desarrollador que intervenga en este repositorio debe cumplir de forma estricta las siguientes directivas:

1. **Regla 7 (Strict English Only in Codebase):** Todo el código fuente, nombres de archivos, clases, métodos, variables, tablas SQL, logs y textos de la interfaz en Streamlit deben estar **100% en inglés**.
2. **Zero Comments Rule:** Está estrictamente prohibido escribir comentarios (`#`) o bloques de texto explicativos innecesarios dentro de los archivos `.py` o `.sql`. El código debe ser autodocumentado mediante tipado estricto y nombres semánticos.
3. **Python 3.14+ & Tipado Estricto:** Uso obligatorio de anotaciones de tipo modernas (`list[T]`, `dict[K, V]`, `T | None`, `AsyncIterator`, `Mapped[T]`, `mapped_column`).
4. **Arquitectura Hexagonal Pura (Sin API REST Intermedia):** El sistema **NO utiliza FastAPI, ni Flask, ni endpoints HTTP/REST, ni JWT web**. Toda la comunicación ocurre por *streams* asíncronos de archivos, tensores en memoria y conexiones binarias directas a PostgreSQL mediante `asyncpg`.

---

## 1. Filosofía y Naturaleza Real del Sistema

1. **CERO API REST / CERO HTTP Intermedio:** En un SOC pasivo que procesa decenas de miles de flujos de red, serializar paquetes en JSON sobre HTTP local introduce una latencia inaceptable. El motor analítico lee directamente los logs de captura pasiva (`conn.log` de Zeek) y escribe por lotes en PostgreSQL; el Dashboard en Streamlit lee directamente de PostgreSQL.
2. **Procesamiento Real Fuera de Banda (*Out-of-Band*):** El sistema no simula ataques con botones falsos ni bloquea tráfico en línea (no es un IPS/Firewall activo). Opera leyendo telemetría real de capa 3 y 4 exportada por sensores pasivos (`Zeek` / `tshark`), descartando la carga útil (*payload*) cifrada por TLS 1.3/HTTPS.
3. **Estrategia Híbrida de Hardware para PyTorch (Entrenamiento en GPU RTX 5050 vs. Inferencia en Contenedor):**
   * **Entrenamiento Local en GPU (`CUDA`):** El entrenamiento del modelo neuronal probabilístico se ejecuta en la estación de trabajo principal (equipada con GPU **NVIDIA RTX 5050 de 8 GB VRAM**) mediante un script dedicado (`scripts/train_gpu.py`). Este proceso aprovecha los núcleos CUDA para entrenar un **Autoencoder Profundo de Reconstrucción de Tráfico** en segundos y exporta los pesos y parámetros de normalización a un artefacto ligero (`models/vortemis_ae.pt`).
   * **Inferencia en Contenedor (`CPU`):** Para garantizar que `docker-compose.yml` sea portable para todo el equipo sin requerir el *NVIDIA Container Toolkit* ni descargar 4 GB de imágenes CUDA, el contenedor instala `torch` en su variante ligera de CPU y carga `models/vortemis_ae.pt` en modo evaluación (`model.eval()` y `torch.no_grad()`), logrando inferencia vectorial en menos de $2\text{ ms}$ por lote de $5,000$ flujos.
4. **Seguridad por Segregación a Nivel de Base de Datos:** El motor de ingesta/inferencia posee permisos de escritura (`INSERT`/`SELECT`), mientras que el Dashboard en Streamlit opera bajo un enfoque estrictamente de solo lectura (`READ ONLY`) para preservar la cadena de custodia forense.

---

## 2. Stack Tecnológico Oficial

| Capa del Sistema | Tecnología / Biblioteca | Rol Exacto en Vortemis |
| :--- | :--- | :--- |
| **Lenguaje Núcleo** | **Python 3.14.6+** | Ejecución asíncrona (`asyncio`), tipado estricto y manejo eficiente de memoria. |
| **Captura Pasiva** | **Zeek (NSM) & tshark** | Extracción fuera de banda de metadatos de Capa 3 (Red) y Capa 4 (Transporte) en formato TSV (`conn.log`). |
| **Ingesta Asíncrona** | **`asyncio` + `aiofiles`** | Lectura no bloqueante mediante generadores (`AsyncIterator`) con memoria acotada por lotes (*batching*). |
| **Limpieza y Vectorización** | **Pandas 3.x & NumPy 2.x** | Saneamiento vectorial de nulos, ordenamiento temporal y cálculo matricial de $IAT$, ratio de asimetría de bytes ($PCR$) y entropía de puertos. |
| **Motor Matemático y Tensores** | **PyTorch (`torch` 2.x)** | Conversión sin copia de arreglos NumPy a `torch.Tensor` (cumpliendo **HU-02**), ejecución del Autoencoder Probabilístico y cálculo vectorial de $P(\text{Anomalía} \mid \text{Metadatos})$. |
| **Persistencia OLAP** | **PostgreSQL 16 + SQLAlchemy 2.x (`asyncpg`)** | Esquema en Estrella (*Star Schema*), control de concurrencia multiversión (**MVCC**) e índices **B-Tree**. |
| **Visualización SOC** | **Streamlit + Plotly** | Consola analítica en modo oscuro (*Dark Mode*) conectada a PostgreSQL para monitoreo de amenazas MITRE, ajuste de umbral $\epsilon$ y exportación forense. |
| **Infraestructura** | **Docker & Docker Compose** | Orquestación reproducible del clúster PostgreSQL, el motor analítico y la interfaz de visualización. |

---

## 3. Arquitectura Hexagonal y Flujo de Datos

```text
+-----------------------------------------------------------------------------------+
|                      CAPA DE INFRAESTRUCTURA (Adaptadores)                        |
|                                                                                   |
|  [Logs Reales Zeek: conn.log]                      [PostgreSQL 16 (Star Schema)]  |
|               |                                                   ^               |
|               v                                                   |               |
|     (ZeekTelemetrySource)                             (PostgresFlowRepository)    |
+---------------|---------------------------------------------------|---------------+
                | Implementa                                        | Implementa
                v                                                   |
+-----------------------------------------------------------------------------------+
|                        CAPA DE APLICACIÓN (Casos de Uso)                          |
|                                                                                   |
|  <<Driving Port>>                                               <<Driven Port>>   |
|  TelemetrySource ---> [ FlowNormalizer ] ---> [ BayesianPyTorchEngine ] ----------+
|                       (Pandas / NumPy)        (torch.Tensor + Reglas MITRE Red)   |
+-------------------------------------------------------------------|---------------+
                                                                    | Instancia
                                                                    v
+-----------------------------------------------------------------------------------+
|                         CAPA DE DOMINIO (Núcleo Puro)                             |
|                                                                                   |
|   Entidades Inmutables: NetworkFlow                                               |
|   Value Objects: IPAddress (IPv4/IPv6), Port (1-65535), Protocol, MitreTactic     |
+-----------------------------------------------------------------------------------+
```

---

## 4. Pipeline Matemático y Reglas MITRE ATT&CK de Red

### Etapa 1: Ingesta Asíncrona de Telemetría Cruda (`HU-01`)
El adaptador `ZeekTelemetrySource` lee el archivo `conn.log` (formato TSV oficial de Zeek con sus 8 líneas de directiva `#separator`, `#fields`, `#types`, etc.) empleando `aiofiles`. Emite lotes (`batch_size`) de diccionarios crudos sin cargar el archivo completo en la memoria RAM.

### Etapa 2: Limpieza, Vectorización y Puente a Tensores (`HU-02`)
`FlowNormalizer` recibe el lote crudo y ejecuta transformaciones matriciales con **Pandas** y **NumPy**:
1. **Imputación Vectorial:** Reemplaza marcadores vacíos de Zeek (`-` y `(empty)`) por `np.nan`. Imputa `orig_bytes = 0`, `resp_bytes = 0` y `duration = 0.0` cuando están ausentes (típico en paquetes `S0` o `REJ`).
2. **Cálculo del *Inter-Arrival Time* ($IAT$ en milisegundos):**
   Agrupa por `src_ip` y ordena por `ts_start`. Calcula la diferencia vectorial entre paquetes consecutivos:
   $$\text{iat\_ms}_i = (ts_i - ts_{i-1}) \times 1000.0$$
   *(El primer flujo de cada IP origen conserva `None` / `NULL` en la base de datos y se imputa a un valor neutral durante la estandarización del tensor).*
3. **Cálculo de Características Derivadas de Red para el Tensor:**
   Para cada flujo del lote se construye un vector numérico de $6$ dimensiones:
   $$\mathbf{x} = \begin{bmatrix} \log_{1p}(\text{iat\_ms}) & \log_{1p}(\text{orig\_bytes}) & \log_{1p}(\text{resp\_bytes}) & \log_{1p}(\text{duration}) & PCR & \text{is\_failed\_conn} \end{bmatrix}$$
   Donde el **Ratio Productor-Consumidor ($PCR$)** mide la asimetría direccional de bytes en la red:
   $$PCR = \frac{\text{orig\_bytes} - \text{resp\_bytes}}{\text{orig\_bytes} + \text{resp\_bytes} + 1.0} \in [-1.0, +1.0]$$
   Y $\text{is\_failed\_conn} \in \{0.0, 1.0\}$ vale $1.0$ si `conn_state` pertenece a estados fallidos o de escaneo (`S0`, `REJ`, `RSTO`, `RSTR`).
4. **Estandarización Z-Score y Conversión a `torch.Tensor`:**
   Usando la media $\boldsymbol{\mu}$ y desviación estándar $\boldsymbol{\sigma}$ aprendidas durante el entrenamiento:
   $$\mathbf{z} = \frac{\mathbf{x} - \boldsymbol{\mu}}{\boldsymbol{\sigma} + 10^{-8}}$$
   La matriz de NumPy (`np.ndarray` de tipo `float32`) se transforma directamente en un tensor de PyTorch mediante `tensor_batch = torch.from_numpy(z_matrix)`.

### Etapa 3: Inferencia Probabilística en PyTorch (`BayesianPyTorchEngine`)
El modelo en PyTorch (`TrafficAutoencoder`) es una red neuronal simétrica con capas lineales, normalización por lotes y activaciones `GELU`:
$$\mathbb{R}^6 \xrightarrow{\text{Encoder}} \mathbb{R}^{16} \xrightarrow{\text{Bottleneck}} \mathbb{R}^3 \xrightarrow{\text{Decoder}} \mathbb{R}^{16} \xrightarrow{\text{Output}} \mathbb{R}^6$$
1. **Error de Reconstrucción Por Flujo:**
   Dado un lote de tensores $\mathbf{Z}$, el modelo produce la reconstrucción $\hat{\mathbf{Z}}$. El error cuadrático medio por fila es:
   $$E_i = \frac{1}{6} \sum_{j=1}^{6} \left( Z_{i,j} - \hat{Z}_{i,j} \right)^2$$
2. **Conversión a Probabilidad Posterior $P(\text{Anomalía} \mid \text{Metadatos})$:**
   Para mapear el error $E_i \in [0, \infty)$ a una distribución de probabilidad calibrada en $(0.0, 1.0)$, se aplica una transformación logística centrada en el cuantil $95\%$ del error de entrenamiento ($\tau$):
   $$P(\text{Anomalía} \mid \mathbf{z}_i) = \frac{1}{1 + \exp\left( -k \cdot \frac{E_i - \tau}{\tau} \right)}$$
   Si $P(\text{Anomalía} \mid \mathbf{z}_i) > \epsilon$ (donde $\epsilon$ es el umbral de sensibilidad configurable, por defecto $\epsilon = 0.70$), el flujo se declara **Anomalía Confirmada**.

### Etapa 4: Clasificador Vectorial de Reglas MITRE ATT&CK de Red
Dado que Vortemis es un analizador pasivo de tráfico de red (Capa 3 y Capa 4), únicamente evalúa **Tácticas MITRE ATT&CK de Red**. Para todo flujo donde $P(\text{Anomalía} \mid \mathbf{z}_i) > \epsilon$, el motor evalúa en orden de especificidad las siguientes firmas matemáticas sobre los metadatos del flujo para asignarle su `tactic_id`:

| Código MITRE | Nombre de la Táctica | Regla Matemática y Firma de Red (Capa 3 / Capa 4) |
| :--- | :--- | :--- |
| **`TA0010`** | **Exfiltration** (Exfiltración de Datos) | Flujo establecido (`conn_state == 'SF'`) con fuerte asimetría de subida ($PCR > 0.60$, es decir, $\text{orig\_bytes} > 4 \times \text{resp\_bytes}$) y volumen saliente elevado ($\text{orig\_bytes} \ge 25,000\text{ bytes}$). |
| **`TA0008`** | **Lateral Movement** (Movimiento Lateral) | Tanto `src_ip` como `dst_ip` son direcciones IP privadas (RFC 1918: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) y el puerto destino `dst_port` pertenece a servicios de administración interna: `{22 (SSH), 135 (RPC), 139 (NetBIOS), 445 (SMB), 3389 (RDP), 5985 (WinRM)}`. |
| **`TA0040`** | **Impact** (DoS / Inundación de Paquetes) | Ráfaga de alta frecuencia desde el mismo host con tiempo entre llegadas crítico ($\text{iat\_ms} \neq \text{NULL}$ y $\text{iat\_ms} < 2.0\text{ ms}$) acompañado de estados de conexión incompletos o abruptos (`S0`, `RSTO`, `RSTR`, `SH`, `OTH`). |
| **`TA0043`** | **Reconnaissance** (Escaneo Activo de Puertos) | Conexión sin respuesta o rechazada (`conn_state` en `{'S0', 'REJ'}`), transferencia nula del servidor ($\text{resp\_bytes} == 0$) y duración fugaz ($\text{duration} < 0.05\text{ s}$). |
| **`TA0011`** | **Command and Control** (C2 Beaconing) | Conexiones anómalas que no caen en las categorías anteriores, caracterizadas por latidos rápidos o periódicos ($\text{iat\_ms} < 50.0\text{ ms}$), cargas útiles pequeñas de control ($\text{orig\_bytes} < 1,500\text{ bytes}$) o dirigidas a puertos típicos de túneles C2 (`53`, `80`, `443`, `8080`, `8443`). |

*(Si $P(\text{Anomalía} \mid \mathbf{z}_i) \le \epsilon$, el flujo se clasifica como Tráfico Normal y su `tactic_id` permanece en `NULL`, cumpliendo el Diccionario de Datos de la Tabla 3).*

---

## 5. Diseño Físico de Base de Datos (Esquema en Estrella en PostgreSQL 16)

El archivo `src/vortemis/infrastructure/persistence/models.py` debe implementar exactamente el esquema relacional de la **Figura 7** y las **Tablas 3 y 4**, añadiendo el puntaje de probabilidad calculado por PyTorch para permitir la recalibración dinámica del umbral $\epsilon$ en el Dashboard:

1. **`dim_protocols`:**
   * `protocol_id` (`SERIAL`, PK)
   * `protocol_name` (`VARCHAR(10)`, UNIQUE, NOT NULL — ej. `tcp`, `udp`, `icmp`)
   * `description` (`VARCHAR(50)`, NOT NULL)
2. **`dim_conn_states`:**
   * `state_id` (`SERIAL`, PK)
   * `state_code` (`VARCHAR(10)`, UNIQUE, NOT NULL — ej. `S0`, `SF`, `REJ`, `RSTO`)
   * `description` (`VARCHAR(100)`, NOT NULL)
3. **`dim_mitre_tactics`:**
   * `tactic_id` (`SERIAL`, PK)
   * `mitre_id` (`VARCHAR(15)`, UNIQUE, NOT NULL — `TA0010`, `TA0008`, `TA0040`, `TA0043`, `TA0011`)
   * `tactic_name` (`VARCHAR(50)`, NOT NULL — `Exfiltration`, `Lateral Movement`, `Impact`, `Reconnaissance`, `Command and Control`)
4. **`fact_network_flows`:**
   * `flow_id` (`UUID`, PK)
   * `ts_start` (`TIMESTAMPTZ`, NOT NULL, Índice B-Tree `ix_fact_flows_ts_start`)
   * `src_ip` (`INET`, NOT NULL)
   * `dst_ip` (`INET`, NOT NULL, Índice B-Tree `ix_fact_flows_dst_ip`)
   * `src_port` (`INTEGER`, NOT NULL, Check $1 \le \text{src\_port} \le 65535$)
   * `dst_port` (`INTEGER`, NOT NULL, Check $1 \le \text{dst\_port} \le 65535$)
   * `protocol_id` (`INTEGER`, FK $\rightarrow$ `dim_protocols.protocol_id`, NOT NULL)
   * `state_id` (`INTEGER`, FK $\rightarrow$ `dim_conn_states.state_id`, NOT NULL)
   * `tactic_id` (`INTEGER`, FK $\rightarrow$ `dim_mitre_tactics.tactic_id`, NULLABLE)
   * `iat_ms` (`FLOAT8`, NULLABLE)
   * `orig_bytes` (`BIGINT`, NOT NULL, Check $\text{orig\_bytes} \ge 0$)
   * `resp_bytes` (`BIGINT`, NOT NULL, Check $\text{resp\_bytes} \ge 0$)
   * `anomaly_probability` (`FLOAT8`, NOT NULL, Default $0.0$ — almacena $P(\text{Anomalía} \mid \text{Metadatos}) \in [0.0, 1.0]$)

---

## 6. Diseño de la Consola Analítica en Streamlit (`AlertDashboardUI`)

El archivo `src/vortemis/entrypoints/dashboard.py` materializa el **Wireframe de la Figura 8** con una estética profesional **Dark Mode SIEM** (inspirada en consolas corporativas de detección de anomalías), conectándose directamente a PostgreSQL:

1. **Estilizado CSS Dark Mode:** Tarjetas superiores con fondo oscuro (`#161b22`), bordes sutiles (`#30363d`), tipografía limpia y acentos semánticos (rojo para amenazas críticas, ámbar para advertencias, azul/cian para telemetría general).
2. **Panel Lateral Izquierdo (`Sidebar` - Controles y Casos de Uso del Analista):**
   * **Caso de Uso "Ajustar umbral probabilístico":** Slider interactivo `Probabilistic Threshold (ε)` de $0.10$ a $0.99$ (por defecto $0.70$). Al moverlo, recalcula en vivo qué flujos superan $P(\text{Anomalía}) > \epsilon$.
   * **Filtros Forenses:**
     * Rango de Fechas (`Date Range`).
     * Búsqueda por `Source IP` y `Destination Port`.
     * Selector múltiple de `Protocol` (`tcp`, `udp`, `icmp`).
     * Selector múltiple de `MITRE Tactic` (`TA0010`, `TA0011`, `TA0043`, `TA0040`, `TA0008`).
     * Checkbox `Only Anomalies (P > ε)`.
     * Botón `Apply Filters` con indicador de estado (`st.spinner`).
   * **Caso de Uso "Generar reporte forense":** Botón `Export Forensic Report (CSV)` (`st.download_button`) que exporta los vectores anómalos filtrados con su táctica MITRE y probabilidad asociada.
3. **Cuerpo Principal del Dashboard:**
   * **Fila 1 - 5 Tarjetas de Métricas Superiores (KPIs estilo SIEM):**
     1. *Total Flows Analyzed* (Total de flujos en ventana).
     2. *Detected Anomalies ($P > \epsilon$)* (Total y porcentaje sobre el tráfico).
     3. *Data Exfiltration (`TA0010`)* (Conteo de alertas de exfiltración).
     4. *Recon & Lateral Mov (`TA0043` / `TA0008`)* (Escaneos y movimientos internos).
     5. *C2 & Impact Flood (`TA0011` / `TA0040`)* (Beaconing y DoS).
   * **Fila 2 - Visualizaciones Analíticas (`st.columns([1.2, 1.8, 1.8])`):**
     * **Columna 1 (*Top Risk Source Hosts*):** Ranking visual de las 10 direcciones `src_ip` con mayor probabilidad acumulada de riesgo y número de alertas MITRE.
     * **Columna 2 (*MITRE ATT&CK Network Tactics Breakdown*):** Gráfico de barras horizontales en Plotly mostrando la distribución de ataques detectados por código MITRE.
     * **Columna 3 (*Posterior Probability Distribution $P(\text{Anomaly} \mid E)$*):** Histograma en Plotly mostrando la separación entre tráfico legítimo y tráfico anómalo, con una línea vertical punteada roja indicando la posición actual del umbral $\epsilon$.
   * **Fila 3 - Serie Temporal de Anomalías (*Anomaly Trend Over Time*):**
     * Gráfico de línea temporal (Plotly) mostrando la evolución de flujos normales vs. anomalías a lo largo del tiempo (`ts_start`).
   * **Fila 4 - Tabla Forense Dinámica (*Latest Analyzed Network Flows*):**
     * `st.dataframe` de ancho completo mostrando `ts_start`, `src_ip`, `src_port`, `dst_ip`, `dst_port`, `protocol`, `conn_state`, `iat_ms`, `orig_bytes`, `resp_bytes`, `anomaly_probability` y `mitre_tactic`.

---

## 7. Estructura Exacta de Archivos del Proyecto

```text
Vortemis/
├── docker-compose.yml                         # Servicios: db (postgres:16-alpine), app (daemon/ingest), dashboard (streamlit)
├── Dockerfile                                 # Python 3.14-slim + torch (CPU) + pandas + numpy + sqlalchemy + streamlit
├── pyproject.toml                             # Dependencias puras del proyecto original
├── .env.example                               # Plantilla limpia de variables de entorno (sin secretos reales)
├── models/
│   └── vortemis_ae.pt                         # Pesos del Autoencoder PyTorch + vectores mu/sigma/tau entrenados
├── data/
│   └── samples/
│       ├── conn.log                           # Muestra pequeña para tests
│       └── conn_realistic.log                 # Captura Zeek realista con tráfico base y patrones MITRE inyectados
├── scripts/
│   ├── train_gpu.py                           # Script de entrenamiento PyTorch en CUDA (RTX 5050) + generador de dataset
│   └── generate_zeek_traffic.py               # Generador determinista de tráfico Zeek con los 5 vectores de ataque MITRE
├── src/
│   └── vortemis/
│       ├── config.py                          # Configuración tipada por variables de entorno
│       ├── banner.py                          # Banner ASCII oficial del equipo Vortemis
│       ├── domain/
│       │   ├── entities.py                    # NetworkFlow (incluye anomaly_probability y mitre_tactic)
│       │   ├── value_objects.py               # IPAddress, Port, Protocol, MitreTacticCode
│       │   └── exceptions.py                  # Excepciones de dominio
│       ├── application/
│       │   ├── ports/
│       │   │   ├── telemetry_source.py        # Driving Port: stream() -> AsyncIterator[RawRecord]
│       │   │   └── flow_repository.py         # Driven Port: save_batch(flows: list[NetworkFlow]) -> None
│       │   └── use_cases/
│       │       ├── flow_normalizer.py         # Limpieza Pandas/NumPy, cálculo IAT/PCR y puente a torch.Tensor
│       │       └── bayesian_pytorch_engine.py # Inferencia con TrafficAutoencoder (.pt) y reglas MITRE de red
│       ├── infrastructure/
│       │   ├── ingestion/
│       │   │   └── zeek_source.py             # Parser asíncrono TSV/JSON de Zeek con aiofiles
│       │   └── persistence/
│       │       ├── database.py                # Motor asíncrono SQLAlchemy (asyncpg)
│       │       ├── models.py                  # ORM Star Schema (FactNetworkFlow, DimProtocol, DimConnState, DimMitreTactic)
│       │       └── postgres_repository.py     # Inserción masiva con mapeo automático de dimensiones y tácticas MITRE
│       └── entrypoints/
│           ├── cli.py                         # Punto de entrada del motor: carga modelo PyTorch, procesa Zeek y persiste
│           └── dashboard.py                   # AlertDashboardUI en Streamlit (SIEM Dark Mode)
└── tests/
    ├── unit/
    │   ├── test_domain.py
    │   ├── test_normalizer.py
    │   └── test_pytorch_mitre_engine.py       # Valida tensores, probabilidades y las 5 reglas MITRE ATT&CK
    └── integration/
        └── test_pipeline_e2e.py
```

---

## 8. Plan de Trabajo Secuencial para el Agente y el Desarrollador

### Paso 1: Orden para el Agente de IA
Pásale al agente la siguiente instrucción directa:
> *"Lee el archivo `vortemis_arquitectura_original_pura.md` de principio a fin. Implementa exactamente la arquitectura descrita en las Secciones 0 a la 7: actualiza las dependencias con `torch` (CPU wheel para Docker, soporte CUDA en scripts), crea el módulo `bayesian_pytorch_engine.py` con el `TrafficAutoencoder` y las 5 reglas MITRE ATT&CK de red (`TA0010`, `TA0008`, `TA0040`, `TA0043`, `TA0011`), actualiza el esquema en estrella en `models.py` y `postgres_repository.py` para incluir `dim_mitre_tactics` y `anomaly_probability`, crea los scripts `scripts/train_gpu.py` y `scripts/generate_zeek_traffic.py`, y rediseña `src/vortemis/entrypoints/dashboard.py` siguiendo la Sección 6. Asegúrate de que `ruff check .` y `pytest` pasen al 100% sin un solo comentario `#` en el código."*

### Paso 2: Entrenamiento en tu PC de Escritorio (RTX 5050 8 GB)
Una vez que el agente cree los archivos, abre tu terminal en tu entorno local con GPU NVIDIA y ejecuta:
```bash
python scripts/train_gpu.py
```
* Este script detectará automáticamente tu **RTX 5050 (`cuda:0`)**, entrenará el Autoencoder sobre $50,000$ vectores de tráfico legítimo en menos de $5$ segundos y guardará el modelo calibrado en `models/vortemis_ae.pt`.
* Acto seguido, ejecuta `python scripts/generate_zeek_traffic.py` para generar `data/samples/conn_realistic.log` con $10,000$ flujos de red que incluyen tráfico normal mezclado con campañas reales de Exfiltración (`TA0010`), Movimiento Lateral (`TA0008`), Escaneo de Puertos (`TA0043`), Beaconing C2 (`TA0011`) e Impacto DoS (`TA0040`).

### Paso 3: Despliegue del Ecosistema Completo en Docker
Con el modelo `.pt` ya entrenado por tu GPU y el log realista generado, levanta todo el SOC pasivo:
```bash
docker compose up --build
```
* El contenedor `db` levantará PostgreSQL 16.
* El contenedor `app` cargará `models/vortemis_ae.pt`, leerá los $10,000$ flujos con `aiofiles`, calculará el $IAT$ y el $PCR$ con Pandas/NumPy, ejecutará la inferencia en tensores de PyTorch, asignará las tácticas MITRE ATT&CK y los insertará en el Esquema en Estrella.
* El contenedor `dashboard` expondrá la consola SIEM en `http://localhost:8501` lista para tus pruebas interactivas y capturas de pantalla.

Recuerda usar skills para un mejor trabajo.
Recuerda estrictamente lo que me recomendaste para no perder el hilo, a pesar del reinicio de tokens:

Por qué "alucino" al reiniciar
No es que invente de la nada: es que toda mi memoria del proyecto vive en el contexto de esta sesión. Cuando se resetea, pierdo las decisiones, preferencias y el "por qué" de lo ya hecho. Si no hay nada escrito, reconstruyo mal y parezco alucinar.
La solución no es más contexto, es memoria externa: que todo lo importante quede en archivos del repo, y que cualquier sesión nueva (yo o un agente) empiece leyendo esos archivos antes de tocar nada.
Lo que recomiendo: un "kit de continuidad"
Antes de que se reinicie, dejar escritos (yo los creo ahora si autorizas):
1. OpenCode_context.md (ya existe) → expandirlo con: reglas, estado real (qué está hecho, qué falta), credenciales/aliases del equipo, y un apartado "cómo retomar".
2. docs/DECISIONS.md → log de decisiones (por qué Python 3.14, por qué sha256+salt, por qué emails noreply, por qué el volumen se reseteó, etc.). Evita que un agente nuevo "deshaga" una decisión por no saberla.
3. docs/ROADMAP.md → fases hechas + fases del mega upgrade, cada una con su spec.
4. docs/HANDOFF.md (opcional) → "estado en el último corte": qué se estaba haciendo, siguiente paso exacto.