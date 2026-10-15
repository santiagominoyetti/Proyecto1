# CLAUDE.md — contexto para agentes

Guía para que otro agente (u otra sesión) entienda y siga trabajando este proyecto **sin perder
el hilo de las decisiones ya tomadas**. Léela entera antes de tocar código o texto.

Complementos:
- [`MEMORIA_datos.md`](MEMORIA_datos.md) — memoria técnica canónica del pipeline de datos (fuentes,
  unificación, saneamiento, metodología, limitaciones). **Es la fuente de verdad sobre los datos.**
- [`Modificaciones.md`](Modificaciones.md) — pedidos de estilo y narrativa del profesor.
- [`README.md`](README.md) — presentación del repo para humanos.

---

## 1. Qué es esto

Informe de datos interactivo **autocontenido** (`index.html` / `informe_flujo_vehicular.html`) que
narra cómo cambió el flujo vehicular de Buenos Aires entre 2019 y 2025. Lo ensambla un único
script, **`construir_html.py`**, a partir de extractos compactos. El texto está en **español
rioplatense**, con voz de divulgación periodística.

## 2. Mapa del repo: qué se versiona y qué no

| Versionado (en el repo) | No versionado (local, ~2 GB) |
|---|---|
| `construir_html.py` y los 5 scripts de pipeline | `flujo-vehicular-por-radares-2019..2025.csv` |
| `tableau_extracts/` (01–08 + `explorador.json`, ~3 MB) | `flujo-vehicular-unificado.csv`, `flujo-vehicular-limpio.csv` |
| `contexto/procesado/` (capas mensuales, ~1 MB) | `contexto/` cruda (nafta ~772 MB, peajes, SUBE, mobility, siniestros) |
| `index.html` (informe publicado), notebooks, PDFs, `.md` | `informe_flujo_vehicular.html` (se regenera) |

Las fuentes públicas de los datos crudos están en `MEMORIA_datos.md §3`. **Con lo versionado
alcanza para regenerar el informe** (`construir_html.py` solo lee de `tableau_extracts/` y
`contexto/procesado/`).

## 3. Cómo reconstruir

```bash
pip install -r requirements.txt
python construir_html.py        # extractos → informe_flujo_vehicular.html (~2,3 MB)
```
Para publicar: copiar `informe_flujo_vehicular.html` sobre `index.html`.

El camino completo desde datos crudos (7 pasos) está en `README.md` y `MEMORIA_datos.md §12`.

> ⚠️ **Rutas absolutas.** Cada `.py` define `BASE = Path(r"C:\Users\santi\...")`. En otra máquina
> hay que cambiarla (en `construir_html.py` son las líneas ~27–29: `BASE`, `EXT`, `CTX`). No está
> parametrizada por diseño del autor; no la "arregles" sin avisar.

## 4. `construir_html.py` — convenciones y trampas (IMPORTANTE)

Este archivo (~900 líneas) genera los 14 gráficos. Cosas con las que **te vas a tropezar**:

- **`fig_block(num, titulo, dek, fig, fuente, h=460, legend=True, mapa=False)`** arma cada bloque.
  Los gráficos van en el dict `figs[...]`; `num` es el número visible (1–14).
- **`style(fig, h, legend)`** se aplica DESPUÉS de cada figura y, si `legend=True`, **pisa** la
  config de leyenda por-figura (fuerza `orientation="h"`, arriba). Si una leyenda no te queda donde
  la pusiste, es por esto.
- **`idx_base2019_m(serie)`** indexa una serie mensual a base 2019=100 (devuelve la serie sin tocar
  si no hay datos 2019 — p. ej. SUBE).
- **Selectores de año (`updatemenus`)**: deben ir a la **izquierda** (`x=0.0, xanchor="left"`).
  La barra de herramientas (modebar) de Plotly vive arriba a la derecha; si el dropdown se pone a
  la derecha, el modebar lo tapa y **los clics no funcionan** (bug real ya corregido en G1, G2, G11).
- **Plotly se carga por CDN** (`cdn.plot.ly/plotly-2.35.2.min.js`, línea ~588). El informe **no
  funciona sin internet**. Si se pide robustez offline, hay que inlinear plotly.js.
- El mapa (G14) usa `px.density_mapbox` → tira un `DeprecationWarning` inofensivo.

## 5. Datos: anulaciones e imputaciones ya aplicadas

Dos defectos de origen se corrigen **dentro de `construir_html.py`** (los extractos crudos quedan
intactos; la corrección vive en código y está documentada con nota al pie + bullet de limitaciones):

- **`CORRUPTOS = [(2022,10),(2022,11),(2022,12)]`** → se anulan (NaN). Oct–dic 2022 traen los mismos
  radares pero conteos a ⅓ de lo normal. Además falta mar–sep 2022. El **nivel** de 2022 se
  complementa con peajes (fuente independiente). Las curvas puentean el hueco con `connectgaps`.
- **`FACTOR_NOCTURNO ≈ 0,808`** → imputación de **julio-2024**. El dataset publicado de origen solo
  trae las horas **11–23** de ese mes (faltan 00–10, las de menor tránsito), lo que inflaba el
  promedio mensual ~20% y generaba un pico falso. Se multiplica el valor por el cociente
  media-24h / media-11a23 observado en los julios completos (2019, 2021, 2023, 2025). **Es una
  estimación modelada, no dato de origen.** Se propaga a: `serie_m` (G3, G9, G10, G12, G13),
  `idx_anual` 2024 (G4 y KPI de recuperación, que bajó de 100% a 98%), `men08` (G6) y `radar_m`
  (mapa G14). Cada gráfico afectado lleva una nota al pie que apunta al bullet de "Cómo leer estos
  datos".

Otros quiebres de serie (todos declarados en el panel de limitaciones del informe):
- **SUBE** no tiene 2019 → G10 usa base común **feb-2020 = 100** (no 2019=100).
- **Google Mobility** solo existe feb-2020 → oct-2022.
- Los extractos `01`–`06` salen de `storytelling.ipynb` (no de un `.py`); el `02_serie_mensual`
  usa una ponderación por radares del panel estable, levemente distinta de un promedio crudo del
  CSV limpio. No intentes reproducir `02` como `mean(cantidad)`: no da igual.

## 6. Reglas de estilo del autor (de `Modificaciones.md`) — RESPETALAS

- **No usar el carácter "—" (raya/em dash) en el texto narrativo**: el autor lo considera "muy IA".
  Usar coma, paréntesis o dos puntos. *(Nota: en correcciones recientes se colaron algunas rayas;
  conviene barrerlas si se vuelve a editar prosa.)*
- Secciones numeradas, **sin la palabra "Acto"**.
- Sin "Generado el ..." en el pie.
- El título se renderiza más ancho que el cuerpo del texto.
- Cada gráfico debe tener una **interpretación** (no solo describir, contar lo relevante a la
  narrativa).

## 7. Regla de integridad de datos (del autor, NO negociable)

**Nunca inventar ni estimar números.** Antes de escribir un número en el texto:
1. calcularlo desde los datos reales (mostrar el cálculo),
2. si un dato no se puede calcular con lo disponible, **decirlo** en vez de aproximar,
3. presentar el cálculo/opciones **antes** de tocar el texto o los datos, y esperar el visto bueno.

La imputación de julio-2024 (§5) se hizo así: se evaluó el método, se mostró el rango de resultados
y recién con el OK se aplicó, siempre declarada como estimación.

## 8. Historial de correcciones (sesiones recientes, 2026)

Sobre la base descrita en `MEMORIA_datos.md`, se aplicaron:

1. **Auditoría de riesgo (G12/G13):** se quitó el doble eje; ambas series a índice 2019=100 en un
   solo eje desde cero. G13 = índice víctimas / índice flujo × 100 (riesgo por viaje). Se reescribió
   que durante la cuarentena el riesgo por viaje **baja** (no se dispara).
2. **Números concretos** reemplazando afirmaciones cualitativas (todos calculados de los datos):
   - G2: los dos corredores principales concentran **56,4%** del flujo (promedio del período).
   - G9 (nafta): índice de precio máximo **3.784** vs flujo **86** ese mismo mes (elasticidad baja).
   - Conclusión (martes/jueves): redactada con **pico horario** real — 2019 pico miér 4.870 / vie
     4.830 (martes era el más flojo, 4.540); 2025 martes 4.190 / jueves 4.170 encabezan.
3. **G10 (SUBE):** de doble eje a **base común feb-2020=100**; se eliminó el falso "cruce
   definitivo" (era artefacto del doble eje). Dek reescrito con números reales (abril-2020 SUBE 20
   vs flujo 29; dic-2025 90 vs 92).
4. **Técnicas:** período "2019–2025" en el encabezado; selectores de año corregidos (modebar, §4);
   imputación de julio-2024 (§5).

## 9. Pendientes y decisiones abiertas

- **Vistas de perfil (G1 heatmap, G8 semana-por-año, G2 shares)** se dejaron **con dato crudo** para
  julio-2024: al ser promedios por (día×hora) o ratios entre corredores, el faltante no genera un
  pico visible ni sesgo relevante. Imputarlas agregaría ruido sin beneficio. *(Decisión consciente,
  no olvido.)*
- **Explorador (G15)** muestra el dato diario real; si se elige una fecha de julio-2024 se ve el
  hueco nocturno. Es coherente con "la fuente no publicó esas horas".
- **Rutas absolutas** (§3) y **Plotly por CDN** (§4): mejoras de portabilidad/robustez pendientes;
  no tocar sin pedido explícito.

## 10. Stack

Python 3.13 · pandas, numpy, plotly (informe) · matplotlib, seaborn (solo EDA) · openpyxl (xlsx de
siniestros). Codificación UTF-8. Índices base 2019 = 100 (salvo SUBE, feb-2020=100).
