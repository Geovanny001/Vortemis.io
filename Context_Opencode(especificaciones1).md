# ESPECIFICACIÓN MAESTRA Y AUDITORÍA DE CIERRE: VORTEMIS.IO

**Nombre Oficial del Sistema:** **Vortemis.io**
*(Regla de Branding Inamovible: Queda estrictamente prohibido utilizar "Vortemis" a secas o "Vortemis SOC" en títulos, banners, encabezados de interfaz, TUI, logs o documentación. Toda referencia visual al producto debe ser **Vortemis.io**).*

---

## 1. AUDITORÍA DE ESTADO ACTUAL (LO QUE EL AGENTE YA HIZO)

A partir de la revisión del estado actual del repositorio (commit `04aa936`, 49 tests en verde y `ruff` limpio), se certifica que los siguientes módulos ya están construidos y **deben preservarse**:

1. **Arquitectura Hexagonal Pura (`domain <- application <- infrastructure <- entrypoints`):**
   * `domain/` aislado sin dependencias externas (`IPAddress`, `Port`, `Protocol`, `Timestamp`, `NetworkFlow`).
   * Capa REST artificial eliminada (`api.py`, `security.py`, `FastAPI`/`JWT` removidos).
2. **Motor Probabilístico en PyTorch (`src/vortemis/application/use_cases/bayesian_pytorch_engine.py`):**
   * Red neuronal `TrafficAutoencoder` ($\mathbb{R}^6 \rightarrow \mathbb{R}^{16} \rightarrow \mathbb{R}^3 \rightarrow \mathbb{R}^{16} \rightarrow \mathbb{R}^6$ con `Linear`, `BatchNorm1d` y `GELU`).
   * Vector de $6$ características en `FlowNormalizerUseCase`:
     $$\mathbf{x} = \left[ \log_{1p}(\text{iat\_ms}), \log_{1p}(\text{orig\_bytes}), \log_{1p}(\text{resp\_bytes}), \log_{1p}(\text{duration}), \text{PCR}, \text{is\_failed\_conn} \right]$$
   * Estandarización Z-Score con $\mu$ y $\sigma$ aprendidos: $\mathbf{z} = (\mathbf{x} - \mu) / (\sigma + 10^{-8})$.
   * Cálculo del error de reconstrucción por flujo $E_i = \frac{1}{6}\sum_{j=1}^{6}(z_{i,j} - \hat{z}_{i,j})^2$ y transformación mediante sigmoide logística calibrada sobre el cuantil 95% ($\tau$):
     $$P(\text{Anomaly} \mid \mathbf{x}_i) = \frac{1}{1 + \exp\left(-k \cdot \frac{E_i - \tau}{\tau}\right)}$$
3. **Clasificador de 5 Reglas MITRE ATT&CK de Red (`classify_mitre_tactic`):**
   * Evaluado cuando $P(\text{Anomaly} \mid \mathbf{x}_i) \ge \epsilon$ (por defecto $\epsilon = 0.70$):
     * `TA0010` (*Exfiltration*): `conn_state == "SF"`, $\text{PCR} > 0.60$, $\text{orig\_bytes} \ge 25000$.
     * `TA0008` (*Lateral Movement*): IP origen y destino privadas (RFC 1918) hacia puertos administrativos $\{22, 135, 139, 445, 3389, 5985\}$.
     * `TA0040` (*Impact / DoS*): $\text{iat\_ms} < 2.0\text{ ms}$ y estado abrupto $\{\text{S0}, \text{RSTO}, \text{RSTR}, \text{SH}, \text{OTH}\}$.
     * `TA0043` (*Reconnaissance*): estado `S0` o `REJ`, $\text{resp\_bytes} = 0$, $\text{duration} < 0.05\text{ s}$.
     * `TA0011` (*Command and Control*): $\text{iat\_ms} < 50.0\text{ ms}$ y $\text{orig\_bytes} < 1500$, o puertos C2 $\{53, 80, 443, 8080, 8443\}$.
4. **Esquema en Estrella OLAP en PostgreSQL 16 (`src/vortemis/infrastructure/persistence/`):**
   * Tablas `fact_network_flows`, `dim_protocols`, `dim_conn_states` y `dim_mitre_tactics` operativas.
5. **Scripts de Entrenamiento y Semilla (`scripts/train_gpu.py`, `scripts/generate_zeek_traffic.py`):**
   * Listos para entrenamiento e inyección inicial.

### Respuesta Oficial a la Pregunta Pendiente del Agente (Refactor Opcional)
* **Pregunta del Agente:** *"Lo único opcional que queda es el refactor de estructura (`infrastructure/ingestion/`, `database.py`), que solo renombra directorios/imports. ¿Lo hacemos o lo dejamos así?"*
* **Directiva Definitiva:** **DEJARLO ASÍ (NO EJECUTAR ESE REFACTOR).** La estructura actual (`infrastructure/zeek/` e `infrastructure/persistence/`) ya respeta al 100% la Arquitectura Hexagonal y tiene 49 pruebas en verde. Renombrar paquetes ahora solo introduce riesgo innecesario en los imports sin aportar valor funcional.

---

## 2. LO QUE FALTA POR HACER (TAREAS OBLIGATORIAS PARA EL AGENTE)

Para que **Vortemis.io** quede 100% terminado, autónomo (sin depender de botones de ingesta simulada), con interfaz web bien estructurada, versión de terminal (**TUI**) y cumpliendo todos los criterios de calificación de la rúbrica, el agente debe implementar las siguientes **6 tareas obligatorias**:

### Tarea A: Rebranding Global a `Vortemis.io`
1. Actualizar `src/vortemis/banner.py`, `src/vortemis/entrypoints/dashboard.py`, `src/vortemis/entrypoints/cli.py`, `src/vortemis/entrypoints/tui.py` y `README.md`.
2. Reemplazar cualquier aparición de `"Vortemis SOC"` o `"Vortemis"` en títulos visibles por **`"Vortemis.io"`**.
3. El subtítulo oficial en las consolas será: **`Vortemis.io — Autonomous Passive Network Anomaly & MITRE ATT&CK Platform`**.

### Tarea B: Autenticación Nativa y Roles (RBAC) directo en PostgreSQL
**Justificación:** La rúbrica de evaluación exige autenticación, contraseñas con hash, usuarios de prueba en base de datos y control de acceso por roles (vale $2.5$ puntos de la nota), y el diseño arquitectónico exige proteger la configuración del sistema bajo el principio de menor privilegio. Se implementará directo contra PostgreSQL sin usar API REST:
1. En `src/vortemis/infrastructure/persistence/models.py`, añadir el modelo ORM `SocOperator` (`tablename = "soc_operators"`):
   * `operator_id`: `Mapped[int]` (Primary Key, autoincrement).
   * `username`: `Mapped[str]` (`String(50)`, unique, not null).
   * `password_hash`: `Mapped[str]` (`String(256)`, not null).
   * `role`: `Mapped[str]` (`String(20)`, not null: `"admin"` o `"analyst"`).
2. Crear `src/vortemis/infrastructure/persistence/auth.py`:
   * Implementar funciones `hash_password(password: str) -> str` y `verify_password(password: str, stored_hash: str) -> bool` utilizando exclusivamente `hashlib.pbkdf2_hmac("sha256", ...)` y `secrets.token_hex(16)` de la librería estándar de Python.
   * Implementar `seed_default_operators(session: AsyncSession)` que inserte de forma idempotente dos operadores iniciales:
     * Usuario 1: `admin_carles` | Contraseña: `VortemisAdmin2026!` | Rol: `admin`
     * Usuario 2: `soc_analyst` | Contraseña: `VortemisAnalyst2026!` | Rol: `analyst`
   * Implementar `authenticate_operator(session: AsyncSession, username: str, password: str) -> SocOperator | None`.

### Tarea C: Autonomía Real (Sensor en Vivo con `tshark` + Demonio Continuo `Tail`)
**Objetivo:** Eliminar la dependencia de botones de simulación. **Vortemis.io** debe escuchar tráfico real de la interfaz de red y procesarlo automáticamente en segundo plano.
1. **Sensor de Captura Real (`src/vortemis/infrastructure/zeek/live_sensor.py`):**
   * Crear la clase `LiveTsharkSensor` que ejecute asíncronamente `tshark -i <INTERFACE> -l -n -T fields -E separator=/t` extrayendo los campos de Capa 3 y Capa 4:
     `frame.time_epoch`, `ip.src`, `tcp.srcport`, `udp.srcport`, `ip.dst`, `tcp.dstport`, `udp.dstport`, `ip.proto`, `frame.len`, `tcp.flags.syn`, `tcp.flags.ack`, `tcp.flags.reset`, `tcp.flags.fin`.
   * Agrupar los paquetes en memoria en ventanas de $2.0$ segundos por tupla de 5 elementos `(src_ip, src_port, dst_ip, dst_port, proto)`, calculando `duration`, `orig_bytes`, `resp_bytes` y deduciendo el estado Zeek (`SF`, `S0`, `REJ`, `RSTO`, `OTH`).
   * Escribir continuamente cada flujo en formato TSV estricto de Zeek al final del archivo indicado en `LOG_FILE` (creando el encabezado de 8 líneas de Zeek si el archivo no existe).
   * Incluir manejo limpio de errores si el binario `tshark` no está instalado o carece de permisos en un entorno de CI/test, registrando el aviso sin colapsar el contenedor.
2. **Modo Demonio Continuo en `ZeekTelemetrySource` y `cli.py`:**
   * Añadir el parámetro `follow: bool = False` a `ZeekTelemetrySource`. Cuando `follow=True`, al llegar al final del archivo (`EOF`), no debe cerrar el generador: debe conservar el offset del archivo, hacer `await asyncio.sleep(1.5)` y leer las nuevas líneas apenas se escriban.
   * Actualizar `src/vortemis/entrypoints/cli.py` para que soporte `CONTINUOUS_MODE=true` (configurable por variable de entorno):
     * Al arrancar, inicializa las tablas en PostgreSQL, siembra el catálogo MITRE y los operadores (`seed_default_operators`).
     * Si el archivo `models/vortemis_ae.pt` no existe aún, invoca automáticamente la rutina de entrenamiento base en CPU/CUDA para garantizar que `models/vortemis_ae.pt` exista siempre.
     * Procesa los flujos iniciales y, si `CONTINUOUS_MODE=true`, permanece en un bucle asíncrono infinito leyendo lotes nuevos desde `ZeekTelemetrySource(follow=True)`, ejecutando `FlowNormalizerUseCase` + `BayesianPyTorchEngine` y persistiendo en PostgreSQL cada $1.5$ segundos.

### Tarea D: Rediseño Estructurado del Dashboard Web `Vortemis.io` (`src/vortemis/entrypoints/dashboard.py`)
1. **Pantalla de Login Nativa:**
   * Si `st.session_state.get("operator")` es `None`, renderizar una tarjeta central de inicio de sesión con el título **`Vortemis.io — Autonomous Network Anomaly Platform`**, validando usuario y contraseña contra `soc_operators` en PostgreSQL y mostrando mensajes claros de error si las credenciales fallan.
2. **Control de Acceso por Rol (RBAC) y Validación de Formularios en Sidebar:**
   * Mostrar en la parte superior del Sidebar: operador autenticado, insignia de rol (`ADMIN` o `ANALYST`), estado del sensor (`AUTONOMOUS ENGINE: ONLINE`) y botón `Sign Out`.
   * **Toggle de Autonomía:** `Live Autonomous Refresh (3s)` activado para refrescar las consultas automáticamente sin intervención manual.
   * **Eliminación de Simulación:** Quitar el botón `"Ingest New Zeek Batch"` de la interfaz principal para que toda ingesta provenga del demonio autónomo.
   * **Restricción RBAC:** El slider `Probabilistic Threshold (ε)` ($0.10$ a $0.99$, valor por defecto $0.70$) debe estar **habilitado únicamente para el rol `admin`** y bloqueado (`disabled=True`) para el rol `analyst`.
   * **Validación Estricta de Entradas:** En los filtros `Source IP` y `Destination Port`, validar con `ipaddress.ip_address` y rango numérico $1 \le \text{port} \le 65535$. Si el usuario escribe una IP o puerto inválido, mostrar un `st.error(...)` descriptivo y no ejecutar la consulta corrupta.
3. **Maquetación SIEM en 4 Niveles (Dark Mode `#0d1117` y Tarjetas `#161b22`):**
   * **Nivel 1 (5 KPI Cards en `st.columns(5)`):**
     1. *Total Flows Analyzed*
     2. *Confirmed Anomalies ($P \ge \epsilon$)*
     3. *Exfiltration (`TA0010`)*
     4. *Recon & Lateral (`TA0043` / `TA0008`)*
     5. *C2 & Impact (`TA0011` / `TA0040`)*
   * **Nivel 2 (3 Paneles Analíticos en `st.columns([1.2, 1.8, 1.8])`):**
     * Columna 1: *Top Risk Source Hosts* (ranking de IPs origen con mayor probabilidad máxima de anomalía).
     * Columna 2: *MITRE ATT&CK Tactics Breakdown* (gráfico de barras horizontales en Plotly con fondo transparente).
     * Columna 3: *Posterior Probability Distribution $P(\text{Anomaly} \mid \mathbf{x})$* (histograma en Plotly con línea vertical punteada en $\epsilon$).
   * **Nivel 3:** *Autonomous Telemetry & Anomaly Timeline* (serie temporal en Plotly comparando flujos normales y anómalos).
   * **Nivel 4:** *Forensic Flow Inspector* (`st.dataframe` de ancho completo con botón `Export Forensic Report (CSV)`).

### Tarea E: Creación de `Vortemis.io TUI` (Consola en Terminal) (`src/vortemis/entrypoints/tui.py`)
1. Añadir `textual>=0.80.0` y `rich>=13.7.0` a las dependencias en `pyproject.toml`.
2. Construir `src/vortemis/entrypoints/tui.py` implementando la aplicación `VortemisTUI(App)`:
   * **Header Oficial:** `Vortemis.io TUI — Passive Network Anomaly & MITRE ATT&CK Monitor`.
   * **Barra de Estado Superior (5 Cajas KPI):** *Total Flows*, *Anomalies ($P \ge \epsilon$)*, *TA0010 Exfiltration*, *TA0043/TA0008 Recon/Lateral*, *TA0011/TA0040 C2/Impact*.
   * **Cuerpo Dividido en 2 Paneles:**
     * Panel Izquierdo: *Top Risk Source IPs* y conteo en vivo por táctica MITRE ATT&CK.
     * Panel Derecho: `DataTable` actualizada automáticamente cada $2.0$ segundos desde PostgreSQL con las columnas `Timestamp`, `Src IP`, `Dst IP`, `Dst Port`, `Proto`, `State`, `IAT (ms)`, `Orig Bytes`, `P(Anomaly)` y `MITRE Tactic`.
   * **Atajos de Teclado en el Footer:**
     * `a`: Alternar filtro *Only Anomalies*.
     * `+` / `-`: Subir o bajar el umbral $\epsilon$ en pasos de $0.05$.
     * `r`: Refrescar datos inmediatamente.
     * `q`: Salir de `Vortemis.io TUI`.

### Tarea F: Suite de Pruebas para las Nuevas Funciones
1. Añadir pruebas en `tests/` que verifiquen:
   * Hashing y verificación de contraseñas en `auth.py`, creación y autenticación de `admin_carles` y `soc_analyst`.
   * Lectura incremental (`follow=True`) en `ZeekTelemetrySource` cuando se agregan nuevas líneas a un archivo temporal.
   * Parseo de líneas de `tshark` a registros TSV de Zeek en `live_sensor.py`.
   * Instanciación y configuración de `VortemisTUI` y validación de filtros del Dashboard.
2. Verificar que `ruff check .` no arroje ningún error y que el 100% de `pytest` pase en verde.

---

## 3. GUÍA PARA EL USUARIO: ENTRENAMIENTO DE PYTORCH EN TU PC (RTX 5050)

### 3.1. ¿Cómo funciona el entrenamiento en tu PC de escritorio?
Tu PC de escritorio cuenta con una GPU **NVIDIA RTX 5050 (8 GB VRAM)**. El script `scripts/train_gpu.py` genera en memoria $50,000$ vectores sintéticos de tráfico legítimo de red y entrena la red neuronal `TrafficAutoencoder` para comprimir y reconstruir esos vectores.

### 3.2. Pasos exactos que debes ejecutar en tu PC con GPU
1. Abre una terminal en tu PC de escritorio dentro de la carpeta del repositorio.
2. Asegúrate de tener instalado PyTorch con CUDA y ejecuta:
~~~bash
uv run python scripts/train_gpu.py
~~~
3. El script detectará automáticamente `cuda`, entrenará el modelo en menos de 4 segundos y escribirá en disco el archivo:
~~~text
models/vortemis_ae.pt
~~~

### 3.3. ¿Qué es `models/vortemis_ae.pt` y cómo lo pasas a tu laptop?
* **Qué recibes:** Un único archivo binario compacto (`models/vortemis_ae.pt`, de ~25 KB) que contiene el diccionario de tensores de PyTorch:
  * `model_state_dict`: Los pesos entrenados de las capas neuronales.
  * `mu` y `sigma`: Los vectores de media y desviación estándar de las $6$ características.
  * `tau`: El umbral del cuantil 95% del error de reconstrucción.
* **Cómo lo incluyes en el proyecto de tu laptop:**
  * Simplemente copia el archivo `models/vortemis_ae.pt` desde tu PC de escritorio (por Git o USB) y pégalo dentro de la carpeta `models/vortemis_ae.pt` en tu laptop.
  * Al levantar Docker (`docker compose up --build`), el contenedor usa PyTorch CPU para leer ese archivo `models/vortemis_ae.pt` y evaluar miles de flujos en un par de milisegundos sin consumir la memoria RAM de tu laptop.
  * **Nota de seguridad:** Con la Tarea C configurada arriba, si decides probar el sistema en tu laptop *antes* de pasar el archivo desde tu PC de escritorio, el script `train_gpu.py` generará automáticamente una versión inicial en CPU de `models/vortemis_ae.pt` en 5 segundos para que nada falle.

---

## 4. CÓMO VALIDAR EL SISTEMA EN VIVO CON TU CELULAR (SIN SIMULACIONES)

Para demostrar que **Vortemis.io** detecta tráfico real de red en tu laptop de 8 GB de RAM:

1. **Levantar la plataforma:**
~~~bash
docker compose up --build -d
~~~
2. **Iniciar el sensor de red en vivo en tu laptop (Arch Linux):**
   Conecta tu laptop y tu celular a la misma red (por ejemplo, el Hotspot Wi-Fi de tu celular) y ejecuta el sensor apuntando a tu interfaz Wi-Fi (`wlan0`):
~~~bash
sudo uv run python -m vortemis.infrastructure.zeek.live_sensor --interface wlan0
~~~
3. **Abrir las interfaces de `Vortemis.io`:**
   * **Web SIEM:** Abre `http://localhost:8501` e inicia sesión con `admin_carles` / `VortemisAdmin2026!`.
   * **Terminal TUI:** En otra pestaña de tu terminal Ghostty, ejecuta:
~~~bash
uv run python -m vortemis.entrypoints.tui
~~~
4. **Lanzar ataques reales desde tu celular (Termux):**
   Averigua la IP de tu laptop (`ip -4 addr`) y ejecuta desde tu teléfono:
   * **Disparar `TA0043` (Reconnaissance):**
     `nmap -T4 -F <IP_LAPTOP>`
   * **Disparar `TA0008` (Lateral Movement):**
     `nmap -p 22,445,3389 <IP_LAPTOP>`
   * **Disparar `TA0040` (Impact / Burst):**
     `nmap -p 80 --min-rate 1000 -Pn <IP_LAPTOP>`
   En menos de 3 segundos verás aparecer la IP real de tu teléfono tanto en **Vortemis.io Web** como en **Vortemis.io TUI** clasificada por el Autoencoder de PyTorch.

---

## 5. PROMPT DIRECTO PARA EL AGENTE (COPIAR Y PEGAR)

~~~text
Lee el archivo de especificacion maestra actualizado (vortemis_arquitectura_original_pura.md) y ejecuta todas las tareas de la Seccion 2 (Tareas A, B, C, D, E y F) para cerrar el proyecto Vortemis.io:

1. NO realices el refactor opcional de renombrar infrastructure/zeek/ ni database.py; conserva los paquetes actuales que ya tienen 49 tests en verde.
2. Aplica la Tarea A: Rebranding total a "Vortemis.io" en banner.py, dashboard.py, cli.py, tui.py y README.md (prohibido usar "Vortemis SOC" o "Vortemis" a secas).
3. Aplica la Tarea B: Agrega el modelo SocOperator en models.py y crea src/vortemis/infrastructure/persistence/auth.py con hashing PBKDF2-SHA256 nativo y seed automatico de los usuarios admin_carles (rol admin) y soc_analyst (rol analyst).
4. Aplica la Tarea C: Crea el sensor de captura real con tshark en src/vortemis/infrastructure/zeek/live_sensor.py, agrega soporte de lectura continua (follow=True) en ZeekTelemetrySource y modo demonio continuo (CONTINUOUS_MODE=true) en cli.py, asegurando ademas que models/vortemis_ae.pt se autogenere si no existe.
5. Aplica la Tarea D: Actualiza el Dashboard de Streamlit (dashboard.py) con Login nativo contra PostgreSQL, control RBAC en el sidebar (analyst no puede mover el slider de epsilon, admin si puede), validacion estricta de IP y Puerto con mensajes de error, auto-refresco autonomo y eliminacion del boton de ingesta simulada.
6. Aplica la Tarea E: Agrega textual y rich a pyproject.toml y construye la consola de terminal interactiva "Vortemis.io TUI" en src/vortemis/entrypoints/tui.py con los 5 KPIs, tabla en vivo y atajos de teclado (a, +, -, r, q).
7. Aplica la Tarea F: Agrega los tests unitarios e integracion para auth, modo follow, live_sensor y TUI. Ejecuta ruff check . y pytest hasta que el 100% de la suite este en verde. Recuerda mantener la Regla 7 (todo en ingles) y cero comentarios con numeral (#).
~~~