# P1 — Baseline CICIDS2017 y diagnóstico del modelo

- Fecha: 2026-11-14
- Rama: `feat/p1-cicids2017-calibration`
- Dataset: CICIDS2017, versión `MachineLearningCSV` convertida a Parquet
- Fuente: `https://huggingface.co/datasets/bvsam/cic-ids-2017`
- Checkpoint original: `models/vortemis_ae.pt` (intacto)
- Checkpoint experimental: `models/vortemis_ae_cicids.pt` (local, no versionado)

## 1. Dataset preparado

El adaptador `scripts/prepare_cicids2017.py` convierte las columnas de CICIDS2017 a las 6 features de Vortemis:

| Feature Vortemis | Columna CICIDS2017 | Transformación |
|---|---|---|
| `iat_ms` | Flow IAT Mean | µs → ms |
| `orig_bytes` | Total Length of Fwd Packets | directo |
| `resp_bytes` | Total Length of Bwd Packets | directo |
| `duration` | Flow Duration | µs → s |
| `pcr` | — | `(orig - resp) / (orig + resp + 1)` |
| `is_failed_conn` | RST/SYN/ACK/FIN Flag Count | estado derivado |

Totales:

```text
rows=2830743
benign=2273097
attacks=557646
```

Distribución de tácticas:

| Táctica | Flujos |
|---|---:|
| TA0040 Impact | 380699 |
| TA0043 Reconnaissance | 158930 |
| TA0008 Lateral Movement | 16015 |
| TA0011 Command and Control | 1966 |
| TA0010 Exfiltration | 36 |

Mapeo de etiquetas:

| Etiqueta CICIDS2017 | Táctica |
|---|---|
| PortScan | TA0043 |
| DDoS, DoS Hulk, DoS GoldenEye, DoS slowloris, DoS Slowhttptest, Heartbleed | TA0040 |
| FTP-Patator, SSH-Patator, Web Attack - Brute Force/XSS/Sql Injection | TA0008 |
| Bot | TA0011 |
| Infiltration | TA0010 |
| BENIGN | Ninguna |

## 2. Resultados con el checkpoint original

`models/vortemis_ae.pt` sobre 200 000 benignos y 557 646 ataques:

| Métrica | Valor |
|---|---:|
| ROC-AUC | 0.6944 |
| Precision @ ε=0.70 | 0.7779 |
| Recall @ ε=0.70 | 0.8551 |
| F1 @ ε=0.70 | 0.8147 |
| FPR @ ε=0.70 | 0.6809 |
| Recall con FPR ≤5% | 0.00 |

Incluso con umbral 0.99 el FPR se queda en 59.6% porque las probabilidades están saturadas. El modelo original no es utilizable sobre CICIDS2017.

Recall por táctica a ε=0.70:

| Táctica | Recall |
|---|---:|
| TA0010 | 1.0000 |
| TA0040 | 0.9972 |
| TA0008 | 0.9333 |
| TA0011 | 0.6612 |
| TA0043 | 0.5094 |

El recall alto viene acompañado de un FPR del 68%.

## 3. Checkpoint entrenado con benignos CICIDS2017

Arquitectura actual `6 → 16 → 3 → 16 → 6`, entrenada con 300 000 benignos:

| Métrica | Valor |
|---|---:|
| ROC-AUC | 0.6988 |
| Precision @ ε=0.70 | 0.9092 |
| Recall @ ε=0.70 | 0.1125 |
| F1 @ ε=0.70 | 0.2002 |
| FPR @ ε=0.70 | 0.0313 |
| Umbral seleccionado | 0.65 |
| Recall @ umbral seleccionado | 0.1121 |
| FPR @ umbral seleccionado | 0.0330 |

Recall por táctica a ε=0.65:

| Táctica | Recall |
|---|---:|
| TA0010 | 0.9091 |
| TA0040 | 0.1641 |
| TA0011 | 0.0345 |
| TA0008 | 0.0000 |
| TA0043 | 0.0003 |

El FPR baja a 3.3%, pero el recall cae a 11.2%. No es aceptable.

## 4. Diagnóstico: ¿features o modelo?

Prueba supervisada con exactamente las mismas 6 features (`HistGradientBoostingClassifier`, 200 000 benignos + 200 000 ataques):

```text
supervised_auc=0.9977
```

Esto demuestra que las 6 features sí contienen señal suficiente para separar ataques y benignos. El cuello de botella es el autoencoder actual, no los datos.

Comparativa de alternativas no supervisadas:

| Modelo | ROC-AUC | Recall con FPR 5% |
|---|---:|---:|
| Autoencoder actual 6→16→3→16→6 | 0.694 | 0.112 |
| Isolation Forest | 0.782 | 0.120 |
| Mahalanobis | 0.820 | 0.169 |
| Autoencoder 6→32→8→32→6 | 0.868 | 0.560 |
| Supervisado (diagnóstico) | 0.998 | — |

## 5. Conclusión

1. El checkpoint original no generaliza a tráfico real: FPR 68%.
2. Entrenar el autoencoder actual con benignos reales reduce el FPR, pero el recall cae a 11%.
3. Las features sí separan: un modelo supervisado alcanza AUC 0.998.
4. El autoencoder más grande mejora mucho (AUC 0.868, recall 56% con FPR 5%), pero sigue lejos de un sistema fiable.
5. El problema principal es la capacidad/objetivo del modelo y la ausencia de features de comportamiento (paquetes, flags, puertos, tasas), no el dataset.

## 6. Opciones para continuar P1

1. **Autoencoder configurable más grande** (`6→32→8→32→6`) como checkpoint experimental. Es el cambio más cercano al diseño actual y multiplica por 5 el recall con FPR 5%.
2. **Expandir features**: añadir packet counts, flags, puertos, protocolo, bytes por paquete y tasas. Mantiene el enfoque no supervisado y probablemente sube el AUC.
3. **Modelo híbrido**: autoencoder para anomalías desconocidas + clasificador supervisado para las 5 tácticas conocidas. Es la opción con mejor rendimiento potencial, pero cambia la naturaleza del motor.

Recomendación: probar primero 1 + 2, con objetivo AUC ≥0.95 y recall ≥0.80 con FPR ≤5%. Si no se alcanza, pasar a 3.

Estado: baseline completado. Las mejoras de modelo quedan como trabajo futuro; el foco actual es UI/ops.

## 7. Reproducción

```powershell
# Preparar el dataset (fuera del repo)
python -m uv run python scripts/prepare_cicids2017.py `
  --input-dir E:\Vortemis\datasets\CICIDS2017\raw `
  --output E:\Vortemis\datasets\CICIDS2017\prepared.parquet

# Entrenar el checkpoint experimental
python -m uv run python scripts/train_cicids2017.py `
  --dataset E:\Vortemis\datasets\CICIDS2017\prepared.parquet `
  --output E:\Vortemis.io\models\vortemis_ae_cicids.pt

# Evaluar
python -m uv run python scripts/evaluate_cicids2017.py `
  --dataset E:\Vortemis\datasets\CICIDS2017\prepared.parquet `
  --model E:\Vortemis.io\models\vortemis_ae_cicids.pt `
  --max-benign 200000 --select-threshold --max-fpr 0.05 `
  --output E:\Vortemis\datasets\CICIDS2017\metrics.json
```

El dataset y el checkpoint experimental no se versionan. El checkpoint original `models/vortemis_ae.pt` no se modificó.
