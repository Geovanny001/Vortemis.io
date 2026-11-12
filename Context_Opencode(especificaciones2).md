# ESPECIFICACIÓN MAESTRA DE INGENIERÍA, DISEÑO UI/TUI Y BLINDAJE QA: VORTEMIS.IO

**Nombre Oficial del Producto:** **Vortemis.io**
*(Regla de Branding Inamovible: Todo título visible, banner ASCII, encabezado web, consola TUI, reporte exportado y documentación debe usar exclusivamente **"Vortemis.io"**. Queda prohibido mostrar "Vortemis" a secas o "Vortemis SOC" en la interfaz. El identificador técnico del paquete Python `vortemis` se conserva únicamente en imports internos y `pyproject.toml`).*

---

## 1. RESPUESTAS DIRECTAS A LAS 4 PREGUNTAS DEL AGENTE + AMPLIACIÓN DE ALCANCE PARA QA

1. **Orden de Ejecución (`Cadena Completa A -> H`):**
   * **Aprobado ejecutar todas las tareas de corrido sin pausas intermedias.** Además de las tareas `A -> F`, se agregan las tareas **`G` (Blindaje Anti-QA y Herramienta de Inyección en Vivo)** y **`H` (Expansión Masiva de Suite de Pruebas a 80+ Tests)**. Solo detente al final cuando `ruff check .` y `pytest` estén 100% en verde.
2. **Branding (`Tarea A`):**
   * **Banner ASCII:** Regenera el arte ASCII en `src/vortemis/banner.py` para que diga imponentemente **`VORTEMIS.IO`**.
   * **Créditos:** Usa exactamente **`"Contributors: The Vortemis.io Team"`**.
   * **Paquete Técnico:** Conserva `vortemis` en imports y `pyproject.toml`.
3. **Sensor `tshark` (`Tarea C`):**
   * Implementa `src/vortemis/infrastructure/zeek/live_sensor.py` con soporte para captura real vía subproceso asíncrono `tshark` y tests unitarios completos usando mocks (`AsyncMock`) para que pasen en verde sin requerir el binario `tshark` instalado en el contenedor de pruebas.
4. **Protección del Modelo Entrenado en GPU (`models/vortemis_ae.pt`):**
   * **REGLA CRÍTICA:** El archivo **`models/vortemis_ae.pt` (8.7 KB, 18 tensores, $\tau = 0.7455$) YA FUE ENTRENADO EN LA GPU RTX 5050 Y YA ESTÁ EN EL REPOSITORIO**.
   * **Prohibido sobrescribirlo o borrarlo.** El entrenamiento automático en CPU solo debe ejecutarse como *fallback* de emergencia si `not Path(settings.model_path).exists()`.
   * Adicionalmente, mejora `scripts/train_gpu.py` agregando el argumento opcional `--log-file <path>` para que, cuando se capture un archivo real de Zeek/tshark en la laptop, pueda reentrenarse directamente desde tráfico real además del modo base.

---

## 2. ESPECIFICACIÓN DE INTERFAZ GRÁFICA PREMIUM (STREAMLIT SIEM NIVEL ENTERPRISE)

El archivo `src/vortemis/entrypoints/dashboard.py` no puede verse como un formulario básico de Streamlit. Debe lucir como un **SIEM/UEBA de grado comercial** (inspirado en CrowdStrike Falcon, ManageEngine Log360 y Splunk Enterprise Security):

### 2.1. Sistema de Diseño Visual y CSS Inyectado (`<style>`)
* **Paleta de Colores Oscura Obsidian:**
  * Fondo principal: `#0b0f19`
  * Superficie de tarjetas y contenedores: `#111827` con gradiente sutil `linear-gradient(145deg, #111827 0%, #161f33 100%)`
  * Bordes técnicos: `1px solid #1f2937` con acento superior de `3px solid` según criticidad (`#10b981` Esmeralda para tráfico sano, `#f59e0b` Ámbar para sospechoso, `#ef4444` Carmesí para anomalías críticas, `#06b6d4` Cian para telemetría general).
  * Tipografía monoespaciada (`JetBrains Mono`, `Fira Code`, `monospace`) para direcciones IP, puertos, probabilidades, hashes y códigos MITRE ATT&CK.
* **Cabecera Superior de Estado Operativo (Top Status Bar):**
  * Banner horizontal personalizado en HTML/CSS mostrando:
    * Logo y título: **`VORTEMIS.IO // AUTONOMOUS PASSIVE NETWORK ANOMALY & MITRE ATT&CK ENGINE`**
    * Badges de estado en tiempo real con punto pulsante CSS (`@keyframes pulse`):
      * `SENSOR: PASSIVE OUT-OF-BAND (ACTIVE)`
      * `ENGINE: PYTORCH AUTOENCODER (R^6 -> R^3 -> R^6 | tau=0.7455)`
      * `STORAGE: POSTGRESQL 16 STAR-SCHEMA`
      * `OPERATOR: <username> [ROLE: ADMIN | ANALYST]`

### 2.2. Portal de Login Empresarial y Control RBAC
* **Vista de Login (cuando no hay sesión activa):**
  * Tarjeta central estilizada con el emblema de **Vortemis.io**, subtítulo técnico *"Zero-Trust Telemetry & Stochastic Threat Hunting Console"*, campos validados de `Username` y `Password`, y mensaje de error claro si las credenciales fallan o están vacías.
  * Autenticación directa contra la tabla `soc_operators` en PostgreSQL verificando el hash `PBKDF2-HMAC-SHA256` mediante comparación en tiempo constante (`hmac.compare_digest`).
* **Control de Acceso Basado en Roles (RBAC) en la Sesión:**
  * **`admin` (`admin_carles`):** Puede modificar el slider `Probabilistic Threshold (epsilon)` ($\epsilon \in [0.10, 0.99]$), ejecutar purga/reset de telemetría de prueba o inyección de prueba desde el panel de diagnóstico y exportar reportes.
  * **`analyst` (`soc_analyst`):** Tiene el slider `Probabilistic Threshold (epsilon)` bloqueado (`disabled=True`) con un aviso visual `Read-Only Policy: Threshold locked by SOC Administrator`.

### 2.3. Arquitectura de 4 Pestañas Forenses (`st.tabs`)
Organiza el área principal debajo de las 5 tarjetas KPI superiores en **4 pestañas especializadas**:

1. **Pestaña 1: `Live SOC Overview & Threat Telemetry`**
   * **Gráfico 1 (Izquierda):** *MITRE ATT&CK Network Tactics Breakdown* (Gráfico de barras horizontales en Plotly con colores por táctica: `TA0010` Rojo, `TA0008` Naranja, `TA0040` Púrpura, `TA0043` Ámbar, `TA0011` Cian).
   * **Gráfico 2 (Derecha):** *Posterior Probability Distribution $P(\text{Anomaly} \mid \mathbf{x})$* (Histograma de alta precisión con línea vertical discontinua en el umbral activo $\epsilon$ y sombreado de la zona crítica $P \ge \epsilon$).
   * **Gráfico 3 (Ancho Completo):** *Real-Time Network Anomaly Timeline* (Serie temporal apilada comparando flujos legítimos vs. flujos anómalos e intensidad de bytes transmitidos).
   * **Ranking de Host de Riesgo:** Tabla ejecutiva *Top Offending Source IPs* con conteo de flujos, probabilidad máxima registrada, volumen de bytes y táctica MITRE predominante.

2. **Pestaña 2: `Deep Flow Forensic Inspector`**
   * Tabla interactiva avanzada (`st.dataframe` con `column_config` de Streamlit: `ProgressColumn` para `anomaly_probability`, `NumberColumn` formateado para `iat_ms`, `orig_bytes`, `resp_bytes`).
   * **Inspector Individual de Flujo (Deep-Dive):** Selector de un `flow_id` de la tabla que despliega una tarjeta de autopsia matemática mostrando:
     * Las 6 dimensiones exactas del vector $\mathbf{x} = [\log_{1p}(\text{iat\_ms}), \log_{1p}(\text{orig\_bytes}), \log_{1p}(\text{resp\_bytes}), \log_{1p}(\text{duration}), \text{PCR}, \text{is\_failed\_conn}]$.
     * Gráfico de radar o barras comparando el vector $\mathbf{z}$ del flujo contra la media normal $\boldsymbol{\mu}$ del modelo PyTorch (mostrando visualmente qué característica disparó la anomalía).
     * Explicación textual automática de por qué se activó la regla MITRE ATT&CK correspondiente.

3. **Pestaña 3: `MITRE ATT&CK Network Matrix`**
   * Cuadrícula visual de las 5 tácticas de red monitoreadas (`TA0010 Exfiltration`, `TA0008 Lateral Movement`, `TA0040 Impact`, `TA0043 Reconnaissance`, `TA0011 Command and Control`).
   * Cada tarjeta de táctica muestra: código oficial MITRE, fórmula matemática exacta de detección en Capa 3/4, cantidad de eventos detectados en la ventana actual, porcentaje del total de alertas y las últimas 3 direcciones IP origen que dispararon esa táctica.

4. **Pestaña 4: `PyTorch Engine & Sensor Diagnostics`**
   * Muestra los metadatos reales leídos desde `models/vortemis_ae.pt`: arquitectura de las capas (`6 -> 16 -> 3 -> 16 -> 6`), valor exacto de $\tau$, vectores $\boldsymbol{\mu}$ y $\boldsymbol{\sigma}$ por cada una de las 6 características, estado del archivo `LOG_FILE` (tamaño en KB, última modificación) y botón para descargar el reporte forense completo en CSV o JSON.

---

## 3. ESPECIFICACIÓN DE `VORTEMIS.IO TUI` (CONSOLA TERMINAL EN TEXTUAL)

El archivo `src/vortemis/entrypoints/tui.py` debe ofrecer una experiencia de centro de operaciones por terminal rápida, estable y visualmente impecable:

* **Layout Estructurado con CSS de Textual (`DEFAULT_CSS`):**
  * **Header Superior:** `Vortemis.io — Autonomous Passive Network Anomaly & MITRE ATT&CK TUI` con reloj activo.
  * **Barra de Estado Operativa:** Muestra ruta del modelo `.pt`, valor actual de $\epsilon$, filtro activo (`ALL FLOWS` vs `ANOMALIES ONLY`), estado de la base de datos y contador de refresco ($2.0\text{ s}$).
  * **Fila de 5 Tarjetas KPI:** Cajas con bordes estilizados (`heavy` o `tall`) para *Total Flows*, *Anomalies ($P \ge \epsilon$)*, *TA0010 Exfil*, *TA0043/TA0008 Recon & Lateral*, *TA0011/TA0040 C2 & Impact*.
  * **Cuerpo Principal Dividido (Horizontal):**
    * **Panel Izquierdo (32% ancho):** *Top Risk Source Hosts* + barras de progreso ASCII/Unicode con el desglose de tácticas MITRE ATT&CK.
    * **Panel Derecho (68% ancho):** `DataTable` con cursor por fila (`cursor_type="row"`) mostrando los flujos más recientes con colores por severidad (`bold red` si $P \ge \epsilon$, `yellow` si $0.50 \le P < \epsilon$, `green` si $P < 0.50$).
  * **Panel Inferior de Inspección Forense:** Al seleccionar cualquier fila en la `DataTable`, el panel inferior muestra instantáneamente los detalles completos de ese flujo (UUID, IPs, puertos, $\text{PCR}$, $\text{IAT}$, $P(\text{Anomaly})$ y descripción de la táctica MITRE).
* **Atajos de Teclado (`BINDINGS`):**
  * `a`: Alternar filtro *Only Anomalies*.
  * `+` / `=`: Subir umbral $\epsilon$ en $+0.05$.
  * `-`: Bajar umbral $\epsilon$ en $-0.05$.
  * `r`: Refrescar telemetría inmediatamente.
  * `q`: Salir limpiamente de `Vortemis.io TUI`.

---

## 4. BLINDAJE ANTI-QA Y CASOS BORDE (QA HARDENING CHECKLIST)

Un ingeniero de QA intentará romper el sistema con entradas inválidas, bases de datos vacías o archivos corruptos. El agente **DEBE** implementar estas defensas en todo el código:

1. **Tolerancia Cero a Caídas por Base de Datos Vacía (`Empty State Resilience`):**
   * Si `fact_network_flows` tiene `0` registros o si una combinación de filtros devuelve un `DataFrame` vacío, ni el Dashboard de Streamlit ni la TUI pueden lanzar `KeyError`, `IndexError` o `ZeroDivisionError`. Deben mostrar todos los KPIs en `0` y un banner informativo limpio: *"No network flows match the current filter criteria"*.
2. **Validación Estricta de Entradas de Usuario en Filtros (Anti-QA):**
   * **Filtro `Source IP`:** Validar con `ipaddress.ip_address()` (o prefijo CIDR válido con `ipaddress.ip_network()`). Si el usuario escribe texto basura como `"abc"`, `"999.999.999.999"` o `"'; DROP TABLE--"`, bloquear la consulta y mostrar un mensaje de validación claro (`Invalid IPv4/IPv6 address format`).
   * **Filtro `Destination Port`:** Validar que sea un entero estrictamente entre $1$ y $65535$. Si ingresan `0`, `-5`, `70000` o letras, mostrar error de validación inmediatamente.
   * **Filtro de Fechas:** Si `start_date > end_date`, mostrar alerta de validación sin romper la consulta SQL.
3. **Resiliencia en Streaming de Archivos en Vivo (`Partial Line Protection`):**
   * Cuando `live_sensor.py` o `tshark` escribe en vivo sobre `conn.log` mientras `ZeekTelemetrySource(follow=True)` está leyendo, puede leerse una línea aún incompleta (sin el `\n` final).
   * `ZeekTelemetrySource` en modo `follow=True` **solo debe emitir una línea cuando termine en `\n`**. Si lee una línea parcial sin `\n` al final del archivo, debe retroceder el puntero (`await f.seek(last_pos)`) y esperar al siguiente ciclo de `asyncio.sleep()` para leerla completa.
4. **Inyector de Ataques en Tiempo Real para Demostración y QA (`scripts/live_attack_injector.py`):**
   * Además de `live_sensor.py` (que usa `tshark`), crea el script `scripts/live_attack_injector.py` que escribe flujos en vivo línea por línea al final del archivo `LOG_FILE` (a razón de $N$ flujos por segundo o disparando una campaña específica bajo demanda: `--attack TA0010`, `--attack TA0008`, `--attack TA0040`, `--attack TA0043`, `--attack TA0011`, o `--mixed`).
   * Esto garantiza que, incluso si en el salón de clases el router Wi-Fi tiene *AP Isolation* o se prueba sin privilegios `root`, el usuario o el evaluador de QA pueda disparar ataques en vivo desde otra terminal y ver cómo el demonio continuo los detecta en tiempo real.
5. **Reentrenamiento desde Tráfico Real en `scripts/train_gpu.py`:**
   * Agrega soporte CLI (`argparse`) a `scripts/train_gpu.py` con `--from-log <ruta_conn_log>` para que pueda entrenar el `TrafficAutoencoder` directamente a partir de un archivo TSV real de Zeek/tshark usando exactamente la vectorización de 6 dimensiones del proyecto, manteniendo la generación sintética si no se pasa `--from-log`. **Recuerda: NO sobrescribas el `models/vortemis_ae.pt` actual durante las pruebas.**

---

## 5. SUITE DE PRUEBAS EXHAUSTIVA DE GRADO QA (META: 80+ TESTS EN VERDE)

El agente debe expandir la carpeta `tests/` para cubrir todos los escenarios que QA va a auditar:

1. `tests/test_auth_rbac.py`:
   * Hashing `PBKDF2-HMAC-SHA256` genera salts únicos por cada llamada.
   * Verificación exitosa e inválida de contraseñas con `hmac.compare_digest`.
   * Seed idempotente de `admin_carles` (`admin`) y `soc_analyst` (`analyst`) sin duplicar usuarios al ejecutarse múltiples veces.
   * Verificación de permisos RBAC (solo `admin` puede alterar el umbral $\epsilon$).
2. `tests/test_continuous_streaming_and_sensor.py`:
   * `ZeekTelemetrySource(follow=True)` lee líneas iniciales y detecta nuevas líneas añadidas dinámicamente en caliente.
   * Protección contra líneas parciales/truncadas (sin `\n` final) esperando a que se completen.
   * `live_sensor.py` con subproceso `tshark` mockeado traduce paquetes TCP/UDP a líneas TSV de Zeek válidas y deduce estados `SF`, `S0`, `REJ`, `RSTO`.
3. `tests/test_qa_edge_cases.py`:
   * Validación de filtros de interfaz (IPs malformadas, inyecciones SQL en campos de texto, puertos fuera de rango $<1$ o $>65535$, rangos de fechas invertidos).
   * Comportamiento seguro con lote vacío (`[]`), flujos con `orig_bytes = 0` y `resp_bytes = 0` (sin división por cero en $\text{PCR}$), timestamps idénticos ($\text{iat\_ms} = 0.0$).
   * Verificación de integridad del archivo real `models/vortemis_ae.pt` presente en el repositorio (comprobando que carga en CPU, contiene las 4 claves `model_state_dict`, `mu`, `sigma`, `tau` y produce probabilidades en $[0.0, 1.0]$).
4. `tests/test_tui_and_banner.py`:
   * Verificación de que `banner.py` contiene `VORTEMIS.IO` y `Contributors: The Vortemis.io Team`.
   * Smoke tests asíncronos de `Vortemis.io TUI` verificando que instancia widgets y maneja estados vacíos y con datos sin errores.

---

## 6. PROMPT MAESTRO PARA COPIAR Y PEGAR AL AGENTE AHORA MISMO

Copia todo el bloque siguiente y pásaselo al agente para que trabaje a máxima capacidad:

```text
ORDEN DE EJECUCION TOTAL (CADENA A -> H SIN PAUSAS, NIVEL QA ENTERPRISE):

Lee el archivo de especificacion actualizado y ejecuta todo el trabajo de corrido de principio a fin sin detenerte a preguntar entre tareas. Quiero que consumas los recursos necesarios para dejar "Vortemis.io" visualmente impecable, 100% autonomo y blindado contra cualquier prueba de QA.

RESPUESTAS A TUS 4 PREGUNTAS PREVIAS:
1. Orden: Ejecuta toda la cadena completa de corrido y muestrame el reporte final cuando ruff check . y pytest esten 100% en verde.
2. Branding:
   - Regenera el banner ASCII en src/vortemis/banner.py para que diga "VORTEMIS.IO".
   - Cambia los creditos a "Contributors: The Vortemis.io Team".
   - Conserva el identificador tecnico del paquete Python (vortemis) en imports y pyproject.toml.
   - En toda la UI web, TUI, CLI y README usa exclusivamente el nombre "Vortemis.io" (nunca "Vortemis SOC" ni "Vortemis" a secas).
3. tshark: Implementa src/vortemis/infrastructure/zeek/live_sensor.py y sus tests usando mocks (AsyncMock) para que pytest pase en verde sin requerir el binario tshark instalado en tu entorno.
4. PROTECCION CRITICA DE models/vortemis_ae.pt: El archivo models/vortemis_ae.pt (8.7 KB, tau=0.7455) YA FUE ENTRENADO en mi GPU RTX 5050 y YA ESTA en el repositorio. PROHIBIDO sobrescribirlo o borrarlo. El entrenamiento en CPU solo debe ejecutarse como fallback si Path(model_path).exists() es False.

ADEMAS DE LAS TAREAS A -> F, EJECUTA ESTOS REQUERIMIENTOS DE NIVEL QA Y UI PREMIUM:

A. Dashboard Web SIEM Enterprise (src/vortemis/entrypoints/dashboard.py):
   - Inyecta CSS avanzado (Dark Obsidian #0b0f19 / #111827, bordes de acento por severidad, badges con indicador pulsante en vivo, tipografia monoespaciada para IPs/puertos/MITRE).
   - Cabecera superior "Vortemis.io — Autonomous Passive Network Anomaly & MITRE ATT&CK Platform" con estado en vivo del Sensor, Motor PyTorch (mostrando tau real cargado del .pt), PostgreSQL y Operador activo.
   - Login empresarial contra la tabla soc_operators en PostgreSQL (admin_carles / VortemisAdmin2026! con rol "admin", y soc_analyst / VortemisAnalyst2026! con rol "analyst").
   - RBAC estricto: el rol "admin" puede ajustar el slider Probabilistic Threshold (epsilon), mientras que "analyst" lo tiene bloqueado (disabled=True) con aviso de politica Read-Only.
   - Estructura el espacio de trabajo en 4 pestanas (st.tabs):
     * Tab 1 "Live SOC Overview & Threat Telemetry": 5 KPIs superiores, grafico de barras horizontales MITRE ATT&CK, histograma de P(Anomaly | x) con linea vertical en epsilon, timeline temporal de anomalias y tabla Top Offending Source IPs.
     * Tab 2 "Deep Flow Forensic Inspector": dataframe con barras de progreso de probabilidad + inspector individual de flujo que muestre el vector de 6 caracteristicas, comparativa z-score contra mu/sigma del modelo PyTorch y justificacion de la regla MITRE.
     * Tab 3 "MITRE ATT&CK Network Matrix": tarjetas de las 5 tacticas (TA0010, TA0008, TA0040, TA0043, TA0011) con su formula de red de Capa 3/4, conteo de alertas y ultimas IPs origen.
     * Tab 4 "PyTorch Engine & Sensor Diagnostics": metricas internas leidas en vivo desde models/vortemis_ae.pt (arquitectura 6->16->3->16->6, tau, vectores mu y sigma), estado del archivo de log y exportacion CSV/JSON.

B. Consola de Terminal Interactiva "Vortemis.io TUI" (src/vortemis/entrypoints/tui.py):
   - Construida con textual y rich con hoja de estilos CSS en modo oscuro.
   - Header oficial de Vortemis.io, barra de estado, 5 cajas de KPIs superiores, panel izquierdo con Top Risk IPs + barras Unicode de tacticas MITRE, panel derecho con DataTable interactiva coloreada por severidad, y panel inferior que inspecciona el vector matematico del flujo seleccionado.
   - Atajos de teclado: [a] solo anomalias, [+]/[-] ajustar epsilon, [r] refrescar, [q] salir.

C. Blindaje Anti-QA y Streaming en Vivo:
   - En ZeekTelemetrySource(follow=True), protege contra lineas parciales/truncadas cuando el sensor escribe en vivo: solo procesa una linea cuando termine en "\n"; si no termina en "\n", haz seek atras y espera al siguiente ciclo.
   - Crea funciones puras de validacion de filtros (validate_ip_filter, validate_port_filter, validate_date_range) y usalas en el dashboard para bloquear IPs invalidas, textos basura o puertos fuera de 1..65535 mostrando errores claros sin lanzar excepciones.
   - Asegura que tanto el Dashboard como la TUI funcionen sin errores cuando la base de datos tiene 0 filas o cuando un filtro devuelve 0 resultados.
   - Crea scripts/live_attack_injector.py para poder inyectar flujos en tiempo real linea por linea sobre LOG_FILE (soportando --attack TA0010, TA0008, TA0040, TA0043, TA0011 o --mixed) para pruebas de QA en vivo del demonio continuo.
   - En scripts/train_gpu.py agrega soporte opcional --from-log <path> para permitir reentrenar desde un conn.log real sin tocar el models/vortemis_ae.pt existente a menos que se invoque explicitamente.

D. Suite de Pruebas de Grado QA (80+ tests):
   - Agrega tests exhaustivos para autenticacion PBKDF2 y RBAC, streaming continuo con lineas parciales, sensor tshark con mocks, validaciones de entradas invalidas de QA, base de datos vacia, verificacion del checkpoint real models/vortemis_ae.pt y smoke tests de la TUI.
   - Recuerda respetar estrictamente: todo el codigo/UI en ingles, cero comentarios con numeral (#) y tipado moderno Python 3.14+.
   - Ejecuta ruff check . y pytest hasta que los 80+ tests pasen 100% en verde.
```