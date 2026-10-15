# La Ciudad que cambió de ritmo
### Flujo vehicular de Buenos Aires, 2019–2025 — Proyecto 1 (ITBA)

**Autor:** Santiago Minoyetti · **Entregable:** informe interactivo autocontenido (`index.html`).

Un informe de datos que reconstruye cómo cambió el comportamiento del conductor porteño
entre 2019 y 2025, cruzando el **flujo vehicular por radares de AUSA/GCBA** (~1,9 millones de
registros horarios) con seis capas de contexto: peajes, precio de la nafta, transporte público
(SUBE), movilidad de Google, siniestros viales y el calendario del Mundial 2022.

📄 **Informe publicado:** https://santiagominoyetti.github.io/Proyecto1/ (o abrir `index.html`).

---

## Qué muestra

14 gráficos Plotly interactivos + 1 explorador granular, organizados como una narrativa:

| # | Gráfico | Idea |
|---|---|---|
| 1 | El pulso semanal de la Ciudad | Heatmap día×hora, una semana promedio por año |
| 2 | Pocos corredores concentran el tránsito | Participación por autopista (filtrable por año) |
| 3 | Cuánto y por cuánto se vació la Ciudad | Índice mensual, 3 fuentes (radar, peajes, Google) |
| 4 | ¿El volumen recuperó su nivel previo? | Índice anual del radar + peajes |
| 5 | La semana tipo de 2019 | El "latido" de base: ingresos y egresos |
| 6 | Seis años, autopista por autopista | Serie mensual por corredor |
| 7 | La pandemia, en una semana | 2019 vs 2020 |
| 8 | Año contra año: la forma | Cómo cambió el perfil semanal |
| 9 | ¿La nafta frena el tránsito? | Elasticidad precio–flujo |
| 10 | ¿Se sustituye el auto por el transporte público? | Flujo vs SUBE (índice feb-2020=100) |
| 11 | Mundial 2022: la Ciudad miró el partido | Caída del tránsito durante los partidos |
| 12 | ¿Menos autos = menos víctimas? | Flujo vs siniestros (índice 2019=100) |
| 13 | El riesgo por viaje durante la parálisis | Víctimas por unidad de tránsito |
| 14 | El ritmo de la Ciudad, radar por radar | Mapa animado mensual |
| — | Explorador | Perfil horario por fecha / autopista / sentido |

---

## Estructura del repositorio

```
├── index.html                     ← informe publicado (copia de construir_html.py)
├── construir_html.py              ← ensambla el informe desde los extractos
│
├── tableau_extracts/              ← EXTRACTOS compactos (versionados): 01–08 + explorador.json
├── contexto/procesado/            ← capas de contexto mensuales (versionadas)
│
├── unificar_datasets.py           ← 7 CSV anuales → unificado
├── EDA_saneamiento.ipynb          ← unificado → limpio (EDA + saneamiento)
├── storytelling.ipynb             ← limpio → extractos 01–06
├── procesar_explorador.py         ← limpio → extractos 07, 08, explorador.json
├── procesar_peajes.py             ← peajes crudos → peajes_mensual/anual
├── procesar_contexto.py           ← nafta/SUBE/mobility/siniestros → contexto_mensual
│
├── MEMORIA_datos.md               ← memoria técnica: pipeline, fuentes, decisiones, limitaciones
├── CLAUDE.md                      ← contexto para agentes (cómo está hecho y cómo seguir)
├── Modificaciones.md              ← pedidos de estilo/narrativa del profesor
└── requirements.txt
```

> **Datos crudos no versionados.** Los 7 CSV anuales de radares, el unificado, el limpio y la
> carpeta `contexto/` cruda (~2 GB) quedan fuera del repo por tamaño. Sus fuentes públicas están
> listadas en [`MEMORIA_datos.md`](MEMORIA_datos.md) §3. Con los extractos versionados alcanza
> para regenerar el informe.

---

## Cómo regenerar el informe

```bash
pip install -r requirements.txt
```

**Camino rápido** (desde los extractos ya versionados — no requiere los datos crudos):

```bash
python construir_html.py      # genera informe_flujo_vehicular.html
```

**Camino completo** (desde los datos crudos, si se consiguen las fuentes de MEMORIA §3):

```bash
python unificar_datasets.py        # 1. 7 CSV → unificado
# 2. ejecutar EDA_saneamiento.ipynb  → flujo-vehicular-limpio.csv
# 3. ejecutar storytelling.ipynb     → extractos 01–06
python procesar_explorador.py      # 4. extractos 07, 08, explorador.json
python procesar_peajes.py          # 5. peajes_mensual/anual
python procesar_contexto.py        # 6. contexto_mensual y capas
python construir_html.py           # 7. informe final
```

> ⚠️ Los scripts usan una ruta base **absoluta** (`C:\Users\santi\...`). Antes de correrlos en
> otra máquina hay que ajustar la constante `BASE` al tope de cada `.py`. Ver [`CLAUDE.md`](CLAUDE.md).

---

## Metodología en una línea

Como el número de radares cambia año a año (4 autopistas en 2019, 9 en 2025), **no se usan
totales absolutos** sino una **métrica relativa** —vehículos por radar-hora sobre un **panel
estable** de sensores presentes los 7 años— indexada a **base 2019 = 100**. El detalle, las
fuentes y todas las limitaciones conocidas están en [`MEMORIA_datos.md`](MEMORIA_datos.md).
