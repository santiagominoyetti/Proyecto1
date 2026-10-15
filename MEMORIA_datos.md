# Memoria de manejo y transformación de datos
### Proyecto: "La Ciudad que cambió de ritmo" — Flujo vehicular de Buenos Aires (2019–2025)
**Autor:** Santiago Minoyetti · Proyecto 1 — ITBA
**Entregable analizado:** `informe_flujo_vehicular.html` (informe interactivo autocontenido)

---

## 1. Resumen ejecutivo

El proyecto reconstruye, limpia, unifica y cruza varias bases públicas para contar cómo
cambió el comportamiento del conductor porteño entre 2019 y 2025. El dato base es el
**flujo vehicular por radares de AUSA/GCBA** (7 archivos anuales, formatos heterogéneos),
al que se suman seis capas de contexto (peajes, nafta, SUBE, movilidad de Google,
siniestros viales y calendario del Mundial 2022).

El pipeline va de **~1,9 millones de registros horarios crudos** a un conjunto de
**extractos compactos** (CSV + JSON) que alimentan directamente los 15 gráficos interactivos
del informe. La decisión metodológica central es comparar "peras con peras": como la cantidad
de radares y autopistas cambia año a año, no se usan totales absolutos sino una **métrica
relativa** (vehículos por radar-hora) sobre un **panel estable** de sensores presentes en los
siete años, indexada a **base 2019 = 100**.

---

## 2. Arquitectura del pipeline

```
                       FUENTE BASE (radares)                    CAPAS DE CONTEXTO
                       ────────────────────                     ─────────────────
  flujo-vehicular-por-radares-2019..2025.csv      peajes/ · nafta · sube · mobility · siniestros · mundial
        │  (7 archivos, formatos distintos)                       │
        ▼                                                         ▼
  unificar_datasets.py ─► flujo-vehicular-unificado.csv    procesar_peajes.py   ─► peajes_mensual / peajes_anual
        │                                                  procesar_contexto.py ─► contexto_mensual / sube_diario /
        ▼                                                                          feriados / mundial_2022
  EDA_saneamiento.ipynb ─► flujo-vehicular-limpio.csv
        │
        ├─► storytelling.ipynb     ─► tableau_extracts/01..05  (índice anual, serie mensual, perfil, share, coords)
        ├─► (derivado)             ─► tableau_extracts/06_flujo_radar_mensual.csv  (mapa animado)
        └─► procesar_explorador.py ─► tableau_extracts/07, 08 + explorador.json
                                                          │
                                                          ▼
                                              construir_html.py ─► informe_flujo_vehicular.html
```

| Script / Notebook | Entrada | Salida | Rol |
|---|---|---|---|
| `unificar_datasets.py` | 7 CSV anuales | `flujo-vehicular-unificado.csv` | Concatenación + normalización estructural |
| `EDA_saneamiento.ipynb` | unificado | `flujo-vehicular-limpio.csv` | EDA, control de calidad y saneamiento |
| `storytelling.ipynb` | limpio | extractos `01`–`05` | Panel estable, métrica, índices, visuales núcleo |
| `procesar_explorador.py` | limpio | extractos `07`, `08`, `explorador.json` | Semana/mes por autopista y cubo horario |
| `procesar_peajes.py` | `contexto/peajes/*` | `peajes_mensual/anual.csv` | Fuente independiente para compensar 2022 |
| `procesar_contexto.py` | nafta, SUBE, mobility, siniestros, feriados | `contexto_mensual.csv` y otros | Capas de contexto mensuales alineadas |
| `construir_html.py` | todos los extractos | `informe_flujo_vehicular.html` | Ensamble final del informe interactivo |

> Nota histórica: existe además `TP3_Minoyetti_pipeline.ipynb`, una pipeline de normalización
> en streaming pensada para carga en PostgreSQL (Colab, ~1.971.485 filas hasta 2026-01-31). La
> versión **canónica para este informe** es la pipeline local descrita arriba, que cubre
> 2019–2025.

---

## 3. Fuentes de datos

### 3.1 Base — Flujo vehicular por radares (AUSA / GCBA)
Siete archivos anuales (`flujo-vehicular-por-radares-2019…2025.csv`). Cada fila es una medición
**(radar, fecha, hora)** con la cantidad de vehículos contados. Columnas relevantes: fecha, hora,
autopista, nombre del dispositivo, ubicación (km), sentido de circulación, latitud, longitud y
cantidad.

> **Dataset saneado en Drive.** El archivo `flujo-vehicular-limpio.csv` (~157 MB), resultado del
> saneamiento (§5) y entrada de todos los extractos, está publicado en:
> https://drive.google.com/file/d/1TQPrWjawV7rnMDBaJb87vC2unefO-Ryw/view?usp=sharing
> Los 7 CSV anuales crudos no se publican; se obtienen de las fuentes públicas de origen.

### 3.2 Capas de contexto
| Capa | Fuente | Granularidad original | Uso en el informe |
|---|---|---|---|
| Peajes | Flujo por unidades de peaje AUSA (BA Data) | diaria / mensual | Compensar el hueco del radar 2022 (G4, G8) |
| Nafta | Precios en surtidor, Res. 314/2016 (Sec. Energía) | por estación | Elasticidad precio-flujo (G9) |
| SUBE | Transacciones de la tarjeta SUBE (Min. Transporte) | diaria | Sustitución auto ↔ transporte público (G10) |
| Movilidad | Google COVID-19 Community Mobility | diaria | Corroborar la caída de 2020 (G3) |
| Siniestros | Víctimas en siniestros viales OMSV-GCBA | por hecho | Riesgo por viaje (G12, G13) |
| Mundial | Calendario Qatar 2022 (elaboración propia) | por partido | Efecto de los partidos en el tránsito (G11) |
| Feriados | nager.at + argentinadatos | por fecha | Control / contexto de calendario |

---

## 4. Unificación estructural (`unificar_datasets.py`)

Los siete archivos venían con **formatos incompatibles** que hubo que homogeneizar por posición
de columna (los encabezados eran "sucios" pero el orden era fijo):

- **Separador:** 2019–2020 usan coma; 2021–2025 usan punto y coma.
- **Fechas:** se normaliza cualquier variante (`YYYY-MM-DD`, `YYYY/MM/DD`, `YY-MM-DD`,
  `D/M/YYYY`, `M/D/YYYY`, timestamps con hora) a ISO `YYYY-MM-DD`.
- **Coordenadas:** coma decimal → punto; y reconstrucción de longitudes rotas con falsos
  separadores de miles (p. ej. `-58.459.669.999.999.900` → coordenada decimal válida con dos
  dígitos enteros).
- **Enteros:** `cantidad` y `hora` se parsean de forma tolerante (`float`→`int`, vacío si falla).
- **Salida:** un único `flujo-vehicular-unificado.csv` con esquema fijo de 10 columnas
  (≈**1.895.607 filas**, 160 MB).

---

## 5. EDA y saneamiento (`EDA_saneamiento.ipynb`)

Antes de tocar nada se hizo un **análisis exploratorio y de calidad** completo, y recién después
el saneamiento.

### 5.1 Diagnóstico
- **Valores faltantes** por columna y por año (mapa de calor).
- **Continuidad temporal:** rango de fechas, días únicos vs. esperados por año, días sin ningún
  registro y coherencia entre `fecha.year` y la columna `anio`.
- **Variable objetivo `cantidad`:** distribución, ceros, negativos, outliers extremos (p99.95)
  y serie diaria total para detectar anomalías globales.
- **`hora`:** verificación de rango [0, 23] y perfiles horarios por sentido.
- **Categóricas:** autopistas (variantes de nombre), sentidos, dispositivos (altas/bajas por año).
- **Geográficas:** conversión a numérico, *bounding box* del AMBA, dispositivos con más de una
  coordenada y mapa de dispersión.
- **Reporte de calidad por año** con % de nulos por columna.

### 5.2 Saneamiento (pasos aplicados)
1. **Descartar filas sin fecha válida.**
2. **Re-derivar `anio`** desde la fecha (consistencia).
3. **Normalizar texto** (trim, colapsar espacios) en autopista/dispositivo/sentido; unificar
   variantes de nombre de autopista.
4. **Sentido:** sólo `A`, `B`, `R` son válidos; el resto → `NaN`.
5. **Coordenadas:** usar las numéricas; invalidar las que caen fuera del AMBA
   (lat ∉ [-35,0; -34,2] o long ∉ [-59,0; -57,5]); **imputar** las faltantes (todo 2021 venía sin
   latitud) con la **coordenada modal del mismo dispositivo** en otros años.
6. **`disp_ubicacion`** → numérico.
7. **`cantidad`:** negativos → `NaN`; **cap de outliers** en p99.99 por (año × autopista) para
   neutralizar picos de sensor; `hora` fuera de rango → `NaN`.
8. **Reordenar columnas** y exportar `flujo-vehicular-limpio.csv` (163 MB), con validación
   post-saneamiento (re-lectura, recuento de nulos, totales por año).

---

## 6. Metodología analítica (`storytelling.ipynb`)

El núcleo conceptual del proyecto. Tres decisiones, justificadas por el hecho de que el número de
sensores **no es comparable entre años** (4 autopistas en 2019, 9 en 2025):

1. **Panel estable.** Sólo entran al análisis las **autopistas y radares presentes en los 7 años**
   (Lugones, Cantilo, 9 de Julio Sur y Dellepiane). Esto neutraliza el sesgo de altas/bajas de
   sensores.
2. **Métrica relativa.** Se usa **vehículos promedio por radar-hora** (la media de `cantidad`
   sobre el conjunto de filas), no la suma cruda. Respeta la multiplicidad de radares.
3. **Índice base 2019 = 100.** Toda serie se expresa relativa a 2019 para que dialoguen en un
   mismo eje.

Resultado del índice anual del radar (extracto `01`):

| Año | veh/radar-hora | Índice (2019=100) |
|---|---|---|
| 2019 | 3.013 | 100 |
| 2020 | 1.989 | 66 |
| 2021 | 2.541 | 84 |
| 2022 | 1.616 | 54 ⚠️ (datos incompletos/corruptos) |
| 2023 | 3.096 | 103 |
| 2024 | 3.005 | 100 |
| 2025 | 2.734 | 91 |

### Extractos generados
| Archivo | Contenido | Alimenta |
|---|---|---|
| `01_indice_anual_base2019.csv` | índice anual | G4 (recuperación) |
| `02_serie_mensual.csv` | serie mensual veh/radar-hora | G3, G4, G9, G10, G12 |
| `03_perfil_hora_dia_anio.csv` | perfil hora × día × año | G1 (heatmap) |
| `04_share_autopistas.csv` | participación por autopista | G2 (ranking) |
| `05_radares_coords.csv` | coordenadas de radares | mapa |
| `06_flujo_radar_mensual.csv` | flujo mensual por radar + coords | G14 (mapa animado) |
| `07_semana_autopista.csv` | semana promedio (día×hora) por autopista y año | G5, G7, G8, G2 (por año) |
| `08_mensual_autopista.csv` | tránsito mensual por autopista y año | G6 |
| `explorador.json` | cubo (fecha, autopista, sentido) → 24 horas | G11 (Mundial) y G15 (explorador) |

---

## 7. Capas de contexto (`procesar_contexto.py`)

Todas las capas se reducen a **series mensuales alineadas** y, donde hay 2019, indexadas a base
2019 = 100. Salida principal: `contexto_mensual.csv`.

- **Nafta:** lectura por *chunks* (archivo de ~772 MB); se filtra Capital Federal y el producto
  "Nafta súper" (idproducto = 2); promedio mensual de precio.
- **SUBE:** se filtran transacciones del AMBA, se agregan a mensual; no hay 2019 (sin índice
  base). Se guarda además la serie diaria.
- **Google Mobility:** se aísla CABA (ciudad), promedio mensual de tres indicadores
  (trabajo, transporte, hogar). Disponible sólo entre feb-2020 y oct-2022.
- **Siniestros:** desde el Excel del OMSV, conteo mensual de hechos, víctimas y mortales.
- **Feriados:** unificación de dos fuentes con formatos JSON distintos (2019–2020 vs 2021–2025).
- **Mundial 2022:** tabla manual de los 7 partidos de Argentina con fecha, hora (UTC-3) y resultado.

---

## 8. Compensación del hueco de 2022 con peajes (`procesar_peajes.py`)

El dataset de radares de 2022 está **incompleto y, en parte, corrupto** (ver §9). Para no contar
una historia falsa, se incorporó una **segunda fuente independiente y completa**: el flujo por
unidades de peaje de AUSA.

Desafíos resueltos:
- **Esquemas heterogéneos por año:** 2019–2020 CSV grandes con `fecha`; 2021 con mes por nombre;
  2022–2024 en ZIP con un CSV por mes y formatos de fecha mezclados e irreparables.
- Cuando la columna de fecha no era confiable, el **mes se deriva del nombre del archivo**.
- **Filtro de sanidad:** meses con índice implausible (>150 o <30 respecto de 2019) son errores
  de origen (archivos duplicados/truncados) y se anulan.

Índice anual de peajes (base 2019 = 100): 2020 ≈ 74, 2021 ≈ 91, **2022 ≈ 78**, 2023 ≈ 75,
2024 ≈ 92. El valor de 2022 (≈78, completo) es el que se usa para reescalar la forma del radar.

---

## 9. Problemas de datos detectados y cómo se resolvieron

| Problema | Diagnóstico | Solución |
|---|---|---|
| Formatos de fecha/decimal incompatibles entre años | 6 variantes de fecha; coma vs punto decimal | Normalización por reglas en la unificación |
| Longitud "rota" en 2021 (`-58.459.669…`) y latitud vacía | Falsos separadores de miles; lat ausente en la fuente | Reconstrucción de la coordenada + imputación por dispositivo modal |
| Coordenadas fuera del AMBA | *Bounding box* | Invalidar → `NaN` |
| Outliers de sensor en `cantidad` | p99.99 por año×autopista | *Capping* |
| Variantes de nombre de autopista (`AU Perito Moreno2025`) | 1 fila desalineada | Unificación a nombre canónico |
| **2022 del radar: faltan ~mar–sep** | Cobertura parcial hunde el índice anual | Complementar el **nivel** con peajes |
| **2022 del radar: oct–dic corruptos** | Mismos radares y nº de registros, pero conteos a ⅓ de lo normal (dic ≈ 799 vs ene-2023 ≈ 2.644) | **Anular** esos meses en las series; **excluirlos** de los extractos 07/08 |
| Falso "bajón" en 2023 y falso "pico de riesgo" en 2022 | Eran artefactos del denominador deflactado por los meses corruptos | Al anular oct–dic 2022 desaparecen; se verificó con datos del OMSV (111 víctimas fatales en 2022, tasa normal) |
| Peajes: 5 meses con valores duplicados | Índice implausible | Anulados por filtro de sanidad |

---

## 10. Salida final (`construir_html.py`)

Ensambla un **único HTML autocontenido** con 15 gráficos Plotly interactivos, un mapa animado y
un explorador granular (cubo horario embebido como JSON inline para funcionar sin servidor). Aplica:
- anulación de los meses corruptos de 2022 (las series puentean el hueco con `connectgaps`);
- reescalado de la forma de la semana 2022 al nivel de los peajes (G8);
- un panel de **caveats** que documenta de forma transparente todas las limitaciones del dato.

---

## 11. Limitaciones conocidas (declaradas en el informe)

- **Métrica relativa**, no totales absolutos (no comparables entre años).
- **2022 del radar:** faltan mar–sep y oct–dic son corruptos; el nivel se complementa con peajes.
- **Sin velocidad ni tipo de vehículo:** el riesgo (Acto 5) se infiere de siniestros, no de
  velocidad medida.
- **Movilidad de Google:** sólo disponible feb-2020 a oct-2022.
- **SUBE:** sin datos de 2019 (no se indexa a base 2019).

---

## 12. Reproducibilidad

Orden de ejecución para regenerar el informe desde cero:

```
1. python unificar_datasets.py            # 7 CSV → unificado
2. ejecutar EDA_saneamiento.ipynb         # unificado → limpio
3. ejecutar storytelling.ipynb            # limpio → extractos 01–05 (y 06)
4. python procesar_explorador.py          # limpio → 07, 08, explorador.json
5. python procesar_peajes.py              # peajes → peajes_mensual/anual
6. python procesar_contexto.py            # contexto → contexto_mensual y otros
7. python construir_html.py               # todo → informe_flujo_vehicular.html
```

**Stack:** Python (pandas, numpy, plotly, matplotlib/seaborn para EDA). Codificación UTF-8;
índices base 2019 = 100.
