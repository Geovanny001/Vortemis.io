# Demo: simulador guionado para la feria

- Fecha: 2026-11-19
- Rama: `feat/demo-simulator`
- Base: `develop` en `ae1a3ec`
- Objetivo: alimentar una demostración en vivo con tráfico creíble (benigno +
  ataques guionados) para que la consola muestre actividad en tiempo real.

## 1. Problema

La demo dependía del seed estático (5000 flujos de 2023, ~97% marcados como
anomalía) y del inyector `live_attack_injector.py`, que solo emite ataques
sueltos sin tráfico benigno ni narrativa. La consola no mostraba una secuencia
creíble ni la tasa de anomalía esperada.

## 2. Cambios

Nuevo `scripts/demo_simulator.py`, standalone (solo stdlib):

- Tráfico benigno continuo desde dos hosts privados fijos, con valores cercanos
  a `mu` del modelo para que el autoencoder los puntúe por debajo de `epsilon`.
- Ciclo de ataque guionado: Reconocimiento → Movimiento lateral → C2 →
  Exfiltración → Impacto, con firmas que disparan cada regla MITRE.
- Timestamps actuales (`time.time()`), por lo que la timeline arranca en "ahora".
- Los ataques que requieren IAT pequeño emiten un par de líneas con delta de
  milisegundos; el resto usa valores extremos (bytes, duración, PCR, estado).
- Flags: `--log-file`, `--cycle-seconds`, `--benign-interval`, `--once`.

## 3. Validación

```text
$ python -m uvx ruff check scripts/demo_simulator.py
All checks passed!
```

Runtime contra el stack en vivo (purge previo, 20 s de simulación):

```text
total 139  anomalies 8  benign 131
by_tactic {'TA0043': 4, 'TA0010': 1, 'TA0008': 1, 'TA0011': 1, 'TA0040': 1}
benign-host detections: 2 (flujos de warm-up de reconocimiento)
```

Lectura:

- Las cinco tácticas aparecen en un solo ciclo.
- El tráfico benigno se queda por debajo de `epsilon` (sin falsos positivos
  reales entre los 131 flujos benignos).
- Tasa de anomalía ~6%, creíble para una demo.

## 4. Comando de reproducción

```text
docker compose up -d
# purgar telemetría (admin) y luego:
python scripts/demo_simulator.py --log-file data/samples/conn_massive.log \
  --cycle-seconds 40 --benign-interval 0.15
```

## 5. Riesgos residuales

- El modelo no está calibrado; si cambia el checkpoint, hay que reajustar los
  valores del simulador para mantener las firmas por encima de `epsilon`.
- El primer flujo por host no tiene IAT previo; los warm-up de reconocimiento
  producen dos detecciones iniciales que se desplazan fuera de la ventana.
