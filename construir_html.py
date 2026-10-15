"""
Construye el informe interactivo en un único HTML autocontenido:
"La Ciudad que cambió de ritmo" — estética editorial (tipo La Nación / Tableau),
5 actos con gráficos Plotly filtrables y un mapa animado con heatmap temporal.

Incorpora el dataset de PEAJES (AUSA) como fuente independiente para:
  · corroborar la caída COVID y la recuperación, y
  · COMPENSAR el hueco del radar en 2022 (faltan mar-sep).

Salida: informe_flujo_vehicular.html
"""
import sys
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from plotly.io import to_html
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = Path(r"C:\Users\santi\OneDrive\Documents\itba\Proyecto1")
EXT = BASE / "tableau_extracts"
CTX = BASE / "contexto" / "procesado"
OUT = BASE / "informe_flujo_vehicular.html"

# ── Paleta editorial / Tableau (clara) ──
C_FLUJO = "#3a6ea5"   # azul radar
C_PEAJE = "#2a9d8f"   # teal peajes
C_NAFTA = "#d1495b"   # rojo
C_SUBE = "#5b8c5a"    # verde
C_MOB = "#9b6a9e"     # violeta
C_SIN = "#e08e3c"     # naranja
INK = "#22272e"
INK2 = "#5a6572"
GRID = "#e8eaed"
ACCENT = "#b3001b"    # acento editorial (rojo La Nación-ish)
FONT_UI = "Georgia, 'Times New Roman', serif"  # titulares
FONT_CHART = "Helvetica Neue, Arial, sans-serif"

CONFIG = {"displayModeBar": True, "displaylogo": False, "responsive": True,
          "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def idx_base2019_m(serie: pd.Series) -> pd.Series:
    base = serie[serie.index.year == 2019].mean()
    return serie / base * 100 if base and not np.isnan(base) else serie


def style(fig, h=460, legend=True):
    fig.update_layout(
        template="plotly_white", height=h,
        font=dict(family=FONT_CHART, color=INK, size=13),
        title=None, paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=58, r=24, t=16, b=46),
        hoverlabel=dict(font_family=FONT_CHART),
        colorway=[C_FLUJO, C_NAFTA, C_SUBE, C_MOB, C_SIN, C_PEAJE],
        legend=(dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                     bgcolor="rgba(0,0,0,0)") if legend else dict()))
    fig.update_xaxes(showgrid=False, linecolor="#c7ccd1", ticks="outside",
                     tickcolor="#c7ccd1")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)")
    return fig


def fig_block(num, titulo, dek, fig, fuente, h=460, legend=True, mapa=False):
    if mapa:
        inner = to_html(fig, include_plotlyjs=False, full_html=False, config=CONFIG)
    else:
        style(fig, h, legend)
        inner = to_html(fig, include_plotlyjs=False, full_html=False, config=CONFIG)
    return f"""
<figure class="chart">
  <div class="fig-head">
    <span class="fig-num">Gráfico {num}</span>
    <h3>{titulo}</h3>
    <p class="dek">{dek}</p>
  </div>
  {inner}
  <figcaption>Fuente: {fuente}</figcaption>
</figure>"""


# ─────────────────────────── Cargar datos ───────────────────────────
print("Cargando extractos...")
idx_anual = pd.read_csv(EXT / "01_indice_anual_base2019.csv")
serie_m = pd.read_csv(EXT / "02_serie_mensual.csv", parse_dates=["mes"]).set_index("mes").sort_index()
perfil = pd.read_csv(EXT / "03_perfil_hora_dia_anio.csv")
share = pd.read_csv(EXT / "04_share_autopistas.csv").sort_values("share_pct")
radares = pd.read_csv(EXT / "05_radares_coords.csv")
radar_m = pd.read_csv(EXT / "06_flujo_radar_mensual.csv")
sem07 = pd.read_csv(EXT / "07_semana_autopista.csv")
men08 = pd.read_csv(EXT / "08_mensual_autopista.csv")
expl_json = (EXT / "explorador.json").read_text(encoding="utf-8")

# Paleta de 9 colores para las autopistas (Tableau 10)
PAL9 = ['#4e79a7', '#f28e2b', '#59a14f', '#e15759', '#76b7b2',
        '#edc948', '#b07aa1', '#ff9da7', '#9c755f']
AUTOS9 = sorted(sem07["autopista_nombre"].unique())
COL9 = {a: PAL9[i % len(PAL9)] for i, a in enumerate(AUTOS9)}
DAY_TICKS = [d * 24 + 12 for d in range(7)]
DAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

ctx = pd.read_csv(CTX / "contexto_mensual.csv", parse_dates=["mes"]).set_index("mes")
mundial = pd.read_csv(CTX / "mundial_2022.csv", parse_dates=["fecha"])
peaje_m = pd.read_csv(CTX / "peajes_mensual.csv", parse_dates=["mes"]).set_index("mes")
peaje_a = pd.read_csv(CTX / "peajes_anual.csv")

# Anular meses con radar corrupto (oct-dic 2022: mismos radares pero conteos ~1/3).
# Evita el falso "bajón" en las series mensuales y el falso pico de riesgo.
CORRUPTOS = [(2022, 10), (2022, 11), (2022, 12)]
for a, m in CORRUPTOS:
    ts = pd.Timestamp(a, m, 1)
    if ts in serie_m.index:
        serie_m.loc[ts, "veh_radar_hora"] = np.nan

# Imputación de julio-2024: el dataset publicado de origen solo trae las horas 11–23
# para ese mes (faltan las 00–10, las de menor tránsito), por lo que el promedio
# mensual queda sesgado ~20% hacia arriba (falso pico en G3/G6/G10). Se corrige
# multiplicando el valor publicado por el "factor de descuento nocturno" —el cociente
# media-24h / media-11a23— observado en los julios completos 2019, 2021, 2023 y 2025
# (0,8195 · 0,7945 · 0,8155 · 0,8013 → promedio 0,8077). Es una estimación modelada,
# no un dato de origen; se aclara con una nota al pie en los gráficos afectados.
JUL24 = pd.Timestamp(2024, 7, 1)
FACTOR_NOCTURNO = np.mean([0.8195, 0.7945, 0.8155, 0.8013])
if JUL24 in serie_m.index:
    jul_orig = serie_m.loc[JUL24, "veh_radar_hora"]
    serie_m.loc[JUL24, "veh_radar_hora"] = jul_orig * FACTOR_NOCTURNO
    # Propagar la corrección a los demás extractos que agregan julio-2024:
    # (a) Índice ANUAL 2024 (G4): baja en proporción a la caída de julio, que pesa 1/12 del año.
    y24 = serie_m.index.year == 2024
    mean_corr = serie_m.loc[y24, "veh_radar_hora"].mean()
    mean_orig = mean_corr + jul_orig * (1 - FACTOR_NOCTURNO) / 12
    ratio24 = mean_corr / mean_orig
    idx_anual.loc[idx_anual["anio"] == 2024, "veh_radar_hora"] *= ratio24
    base19 = idx_anual.loc[idx_anual["anio"] == 2019, "veh_radar_hora"].iloc[0]
    idx_anual["indice_base2019"] = idx_anual["veh_radar_hora"] / base19 * 100
    # (b) Mapa animado por radar (G14): escala directa de las celdas de julio-2024.
    radar_m.loc[radar_m["mes"] == "2024-07", "cantidad"] *= FACTOR_NOCTURNO

serie_m["flujo_idx"] = idx_base2019_m(serie_m["veh_radar_hora"])
maestro = ctx.join(serie_m, how="outer").join(peaje_m[["pasos_idx"]], how="outer").sort_index()
maestro = maestro[(maestro.index.year >= 2019) & (maestro.index.year <= 2025)]
maestro = maestro.rename(columns={"pasos_idx": "peaje_idx"})

figs = {}

# ─────────────── ACTO 1 — heatmap hora×día filtrable por año ───────────────
print("Acto 1...")
dias_ord = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
perfil["dia"] = perfil["dow"].map(dict(enumerate(dias_ord)))
anios = sorted(perfil["anio"].unique())
fig1 = go.Figure()
for a in anios:
    piv = perfil[perfil["anio"] == a].pivot_table(index="dia", columns="hora",
                                                   values="cantidad", aggfunc="mean").reindex(dias_ord)
    fig1.add_trace(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index,
                              colorscale="YlOrRd", visible=(a == 2019),
                              colorbar=dict(title="veh/h", thickness=12, len=0.9),
                              hovertemplate="%{y} · %{x}h<br>%{z:.0f} veh/h<extra></extra>"))
buttons = [dict(label=str(a), method="update",
                args=[{"visible": [j == i for j in range(len(anios))]}])
           for i, a in enumerate(anios)]
fig1.update_layout(xaxis_title="Hora del día", yaxis_title="",
                   updatemenus=[dict(buttons=buttons, x=0.0, xanchor="left", y=1.14,
                                     direction="down", showactive=True,
                                     bgcolor="#f3f4f6", bordercolor="#d0d0d0")])
figs["heatmap_semana"] = fig_block(
    1, "El pulso semanal de la Ciudad",
    "Este gráfico muestra una semana promedio para el año elegido. El color indica el flujo de vehículos por hora (más oscuro, más tránsito); las horas del día están en el eje inferior y los días de la semana, a la izquierda. Así se aprecia, a grandes rasgos, el comportamiento de los conductores. Cambiá el año en el selector.",
    fig1, "Flujo vehicular por radares (AUSA/GCBA), panel estable.", legend=False)

# Participación de cada autopista, filtrable por año (+ Total de todos los años).
sem_tot = sem07.groupby(["anio", "autopista_nombre"])["veh_radar_hora"].sum().reset_index()
share_years = sorted(sem_tot["anio"].unique())


def _mk_share(df_sub):
    t = df_sub["veh_radar_hora"].sum()
    s = df_sub.copy()
    s["pct"] = s["veh_radar_hora"] / t * 100
    return s.sort_values("pct")


tot_share = _mk_share(sem_tot.groupby("autopista_nombre")["veh_radar_hora"].sum().reset_index())
share_opts = [("Total (2019-2025)", tot_share)]
share_opts += [(str(a), _mk_share(sem_tot[sem_tot["anio"] == a])) for a in share_years]

fig1b = go.Figure()
for i, (lbl, s) in enumerate(share_opts):
    fig1b.add_trace(go.Bar(x=s["pct"], y=s["autopista_nombre"], orientation="h",
                           marker_color=C_FLUJO, visible=(i == 0),
                           text=s["pct"].round(1).astype(str) + "%", textposition="outside",
                           hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
btn_share = [dict(label=lbl, method="update",
                  args=[{"visible": [j == i for j in range(len(share_opts))]}])
             for i, (lbl, s) in enumerate(share_opts)]
fig1b.update_layout(xaxis_title="% del flujo total", yaxis_title="",
                    updatemenus=[dict(buttons=btn_share, x=0.0, xanchor="left", y=1.16,
                                      direction="down", showactive=True,
                                      bgcolor="#f3f4f6", bordercolor="#d0d0d0")])
figs["ranking_au"] = fig_block(
    2, "Pocos corredores concentran el grueso del tránsito",
    "Cada barra muestra qué porción del flujo total aporta cada autopista. Con el selector podés ver un año puntual o el promedio de todo el período (Total). En casi todos los años, Lugones y Cantilo solas explican más de la mitad del tránsito medido: <b>56,4%</b> del flujo total de la red en el promedio 2019-2025.",
    fig1b, "Flujo vehicular por radares (AUSA/GCBA), panel estable. Participación = veh/radar-hora de cada autopista sobre el total de la red en el año elegido.", h=420, legend=False)

# ─────────────── ACTO 2 — shock COVID + corroboración peajes ───────────────
print("Acto 2...")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=maestro.index, y=maestro["flujo_idx"], name="Flujo radares (índice 2019=100)",
                          line=dict(color=C_FLUJO, width=3),
                          hovertemplate="%{x|%b %Y}: %{y:.0f}<extra></extra>"))
fig2.add_trace(go.Scatter(x=maestro.index, y=maestro["peaje_idx"], name="Flujo peajes (índice 2019=100)",
                          line=dict(color=C_PEAJE, width=2, dash="solid"),
                          hovertemplate="%{x|%b %Y}: %{y:.0f}<extra></extra>"))
fig2.add_trace(go.Scatter(x=maestro.index, y=maestro["mob_trabajo"], name="Movilidad de trabajo (% vs base)",
                          line=dict(color=C_MOB, width=1.5, dash="dot"),
                          hovertemplate="%{x|%b %Y}: %{y:.0f}%<extra></extra>"))
abr20 = pd.Timestamp("2020-04-01")
if abr20 in maestro.index:
    fig2.add_annotation(x=abr20, y=maestro.loc[abr20, "flujo_idx"],
                        text="ASPO abril 2020<br>−72%", showarrow=True, arrowhead=2, ay=-55,
                        font=dict(color=ACCENT, size=12), arrowcolor=ACCENT)
fig2.add_hline(y=100, line_dash="dash", line_color="#b0b6bd")
fig2.update_layout(yaxis_title="Índice / % cambio", hovermode="x unified")
figs["shock"] = fig_block(
    3, "Cuánto y por cuánto tiempo se vació la Ciudad",
    "El eje vertical es un índice base 2019=100: cada punto dice qué porcentaje del nivel normal de 2019 se registró ese mes. Tres curvas miden lo mismo desde fuentes distintas: el flujo por radares, el flujo por peajes de AUSA y la movilidad hacia lugares de trabajo de Google. Cuando las curvas se cortan es porque faltan datos en la base pública de origen, no porque el tránsito haya desaparecido.",
    fig2, "Radares y peajes AUSA/GCBA; Google COVID-19 Community Mobility. Índices base 2019=100. Julio 2024 imputado por un faltante de origen (ver «Cómo leer estos datos»).", h=480)

# ─────────────── ACTO 3 — recuperación + COMPENSACIÓN 2022 ───────────────
print("Acto 3...")
# barras radar + línea peajes anual (rellena el 2022 incompleto del radar)
fig3 = go.Figure()
colors = []
for v, a in zip(idx_anual["indice_base2019"], idx_anual["anio"]):
    if a == 2022:
        colors.append("#c9d6e3")   # 2022 radar atenuado (incompleto)
    else:
        colors.append(C_FLUJO if v >= 100 else "#7ea3c9")
fig3.add_trace(go.Bar(x=idx_anual["anio"], y=idx_anual["indice_base2019"],
                      name="Radares (índice anual)", marker_color=colors,
                      text=idx_anual["indice_base2019"].round(0).astype(int), textposition="outside",
                      hovertemplate="%{x}: %{y:.0f}<extra></extra>"))
fig3.add_trace(go.Scatter(x=peaje_a["anio"], y=peaje_a["pasos_idx"],
                          name="Peajes (índice anual, fuente independiente)",
                          mode="lines+markers", line=dict(color=C_PEAJE, width=3),
                          marker=dict(size=9),
                          hovertemplate="%{x}: %{y:.0f}<extra></extra>"))
fig3.add_hline(y=100, line_dash="dash", line_color="#9aa0a6",
               annotation_text="Nivel 2019", annotation_position="top left")
p22 = peaje_a.loc[peaje_a["anio"] == 2022, "pasos_idx"].iloc[0]
fig3.add_annotation(x=2022, y=p22 + 6,
                    text=f"Radar 2022 incompleto (faltan mar–sep).<br>Los peajes estiman ≈{p22:.0f}",
                    showarrow=True, arrowhead=2, ax=70, ay=-30,
                    font=dict(color=C_PEAJE, size=11), arrowcolor=C_PEAJE)
fig3.update_layout(yaxis_title="Índice (base 2019=100)", xaxis_title="")
figs["recup"] = fig_block(
    4, "¿El volumen recuperó su nivel previo?",
    "Las barras son el índice anual del radar y la línea, el flujo por peajes. Siguiendo el hilo de la caída, acá se ve la otra mitad: tras tocar fondo en 2020, el volumen sube año a año hasta rozar el nivel 2019 en 2024. El radar marca un 2022 demasiado bajo por meses faltantes; los peajes, una fuente completa, confirman que para entonces la recuperación ya estaba en marcha. Pero recuperar el volumen no es lo mismo que recuperar la forma, y ahí está lo que viene.",
    fig3, "Radares (panel estable) y flujo por peajes AUSA. Índices base 2019=100. Julio 2024 imputado por un faltante de origen (ver «Cómo leer estos datos»).")

hab = perfil[perfil["dow"] < 5]

# ── G5 — semana promedio 2019, una línea por autopista (la base) ──
s2019 = sem07[sem07["anio"] == 2019].sort_values("hw")
figB = go.Figure()
for a in AUTOS9:
    sub = s2019[s2019["autopista_nombre"] == a]
    figB.add_trace(go.Scatter(x=sub["hw"], y=sub["veh_radar_hora"], name=a,
                              line=dict(color=COL9[a], width=1.8),
                              hovertemplate=a + "<br>%{y:.0f} veh/radar-h<extra></extra>"))
figB.update_xaxes(tickvals=DAY_TICKS, ticktext=DAY_LABELS)
figB.update_layout(xaxis_title="Semana promedio (2019)", yaxis_title="veh/radar-hora")
figs["semana_2019"] = fig_block(
    5, "La semana tipo de 2019: el latido de base",
    "Cada línea es una autopista a lo largo de una semana promedio. Se ven cinco latidos, uno por día hábil, y un fin de semana mucho más bajo. Dentro de cada día hábil hay dos picos: el de la mañana corresponde al ingreso, cuando la Ciudad se llena para trabajar, y el de la tarde al egreso, cuando se vacía de vuelta hacia la provincia. Ese doble pulso diario, repetido de lunes a viernes, es el patrón que la pandemia vino a romper.",
    figB, "Flujo vehicular por radares (AUSA/GCBA), panel estable.", h=480)

# ── G6 — tránsito mensual por autopista (el cráter de la pandemia) ──
men08 = men08.copy()
men08["periodo_dt"] = pd.to_datetime(men08["periodo"] + "-01")
# Misma corrección de julio-2024 que en la serie general: la base de origen no publicó
# las horas 00–10 de ese mes, así que cada corredor queda sesgado ~20% hacia arriba.
men08.loc[men08["periodo"] == "2024-07", "veh_radar_hora"] *= FACTOR_NOCTURNO
figC = go.Figure()
for a in AUTOS9:
    sub = men08[men08["autopista_nombre"] == a].sort_values("periodo_dt")
    figC.add_trace(go.Scatter(x=sub["periodo_dt"], y=sub["veh_radar_hora"], name=a,
                              line=dict(color=COL9[a], width=1.6),
                              hovertemplate=a + "<br>%{x|%b %Y}: %{y:.0f}<extra></extra>"))
figC.update_layout(xaxis_title="", yaxis_title="veh/radar-hora (promedio mensual)")
figs["mensual_au"] = fig_block(
    6, "Seis años, autopista por autopista",
    "El mismo dato agregado por mes deja ver el desplome de 2020, un cráter común a todos los corredores, y la pendiente despareja con que cada autopista fue recuperando su tránsito.",
    figC, "Flujo vehicular por radares (AUSA/GCBA), panel estable. Julio 2024 imputado por un faltante de origen (ver «Cómo leer estos datos»).", h=480)

# ── G7 — la pandemia: semana promedio 2019 vs 2020 (red completa) ──
net = sem07.groupby(["anio", "hw"])["veh_radar_hora"].mean().reset_index()
figD = go.Figure()
for yr, colr, nm in [(2019, C_FLUJO, "2019 · pre-pandemia"),
                     (2020, ACCENT, "2020 · pandemia")]:
    sub = net[net["anio"] == yr].sort_values("hw")
    figD.add_trace(go.Scatter(x=sub["hw"], y=sub["veh_radar_hora"], name=nm,
                              line=dict(color=colr, width=2.6),
                              hovertemplate=nm + "<br>%{y:.0f} veh/radar-h<extra></extra>"))
figD.update_xaxes(tickvals=DAY_TICKS, ticktext=DAY_LABELS)
figD.update_layout(xaxis_title="Semana promedio", yaxis_title="veh/radar-hora (red completa)")
figs["pandemia"] = fig_block(
    7, "La pandemia, en una semana",
    "La misma semana promedio de toda la red, antes y durante. La curva azul de 2019 dibuja con nitidez los cinco latidos hábiles y sus picos de ingreso y egreso. La curva roja de 2020 hace dos cosas a la vez: baja de nivel, porque hay muchos menos autos, y se aplana, porque desaparecen los picos de la hora pico. La Ciudad no solo se vació: perdió su forma.",
    figD, "Flujo vehicular por radares (AUSA/GCBA), panel estable.")

# ── G8 — semana promedio de cada año superpuesta, filtrable ──
# 2022: el radar solo tiene meses limpios (ene-feb); su forma promedio se reescala
# al NIVEL que indican los peajes (fuente independiente y completa) para que sea
# comparable con el resto de los años.
ref2019 = net[net["anio"] == 2019]["veh_radar_hora"].mean()
ratio22 = peaje_a.loc[peaje_a["anio"] == 2022, "pasos_idx"].iloc[0] / 100.0
m22 = net["anio"] == 2022
if m22.any():
    cur22 = net.loc[m22, "veh_radar_hora"].mean()
    net.loc[m22, "veh_radar_hora"] *= (ref2019 * ratio22) / cur22

YR_PAL = {2019: '#4e79a7', 2020: '#e15759', 2021: '#f28e2b', 2022: '#76b7b2',
          2023: '#59a14f', 2024: '#b07aa1', 2025: '#9c755f'}
figE = go.Figure()
for yr in sorted(net["anio"].unique()):
    sub = net[net["anio"] == yr].sort_values("hw")
    nm = "2022 (forma real · nivel por peajes)" if yr == 2022 else str(yr)
    figE.add_trace(go.Scatter(x=sub["hw"], y=sub["veh_radar_hora"], name=nm,
                              line=dict(color=YR_PAL.get(int(yr)), width=2,
                                        dash=("dash" if yr == 2022 else "solid")),
                              visible=(True if yr in (2019, 2020, 2024) else "legendonly"),
                              hovertemplate=nm + " · %{y:.0f} veh/radar-h<extra></extra>"))
figE.update_xaxes(tickvals=DAY_TICKS, ticktext=DAY_LABELS)
figE.update_layout(xaxis_title="Semana promedio", yaxis_title="veh/radar-hora (red completa)")
figs["semana_anios"] = fig_block(
    8, "Año contra año: la recuperación de la forma",
    f"Hacé clic en los años de la leyenda para sumarlos o quitarlos. Lo más revelador es comparar la semana laboral con el fin de semana. De lunes a viernes, el latido cambió de forma: los picos de hora pico se aplanaron y se corrieron, y la diferencia entre días se reacomodó respecto de 2019. El fin de semana, en cambio, conservó una silueta muy parecida a la de antes de la pandemia. Es decir: lo que cambió fue cómo trabajamos, no cómo descansamos. La línea de <b>2022</b> es punteada porque su nivel se estima con peajes (≈{ratio22*100:.0f}% de 2019); ver la nota al pie.",
    figE, "Flujo por radares (AUSA/GCBA), panel estable. La forma de 2022 sale de los meses limpios del radar y su nivel se ajusta a los peajes AUSA, porque al radar le faltan o están corruptos casi todos los meses de ese año.", h=480)

# ─────────────── ACTO 4 — fuerzas: nafta, SUBE, mundial ───────────────
print("Acto 4...")
fig4 = go.Figure()
fig4.add_trace(go.Scatter(x=maestro.index, y=maestro["flujo_idx"], name="Flujo (índice 2019=100)",
                          line=dict(color=C_FLUJO, width=3), connectgaps=True,
                          hovertemplate="%{x|%b %Y}: %{y:.0f}<extra></extra>"))
fig4.add_trace(go.Scatter(x=maestro.index, y=maestro["nafta_idx"], name="Nafta súper (índice 2019=100)",
                          line=dict(color=C_NAFTA, width=2),
                          hovertemplate="%{x|%b %Y}: %{y:.0f}<extra></extra>"))
fig4.update_layout(yaxis_title="Índice", hovermode="x unified")
figs["nafta"] = fig_block(
    9, "¿La nafta frena el tránsito?",
    "Flujo y precio de la nafta súper, ambos en índice base 2019=100. La línea del combustible trepa muy por encima de la del flujo: hacia fines de 2025 el índice de precio toca su máximo, <b>3.784</b> (casi 38 veces el valor nominal de 2019, en pesos corrientes), mientras ese mismo mes el flujo se mantiene en <b>86</b>. El tránsito no sigue al precio hacia arriba ni hacia abajo: las subas, incluso fuertes, casi no mueven la cantidad de autos en la calle. Es la elasticidad baja de la nafta: para la mayoría, el auto es una necesidad, no un lujo que se recorta cuando sube el surtidor.",
    fig4, "Radares AUSA/GCBA; precios surtidor Res. 314/2016 (Sec. Energía). Julio 2024 del flujo imputado por un faltante de origen (ver «Cómo leer estos datos»).")

# Base común feb-2020=100: SUBE no tiene datos 2019; feb-2020 es el último mes
# normal prepandemia y el primero con ambas series, así las dos curvas son comparables.
base10 = pd.Timestamp(2020, 2, 1)
m10 = maestro.copy()
bf10 = m10.loc[base10, "veh_radar_hora"]
bs10 = m10.loc[base10, "sube_usos"]
m10["flujo_b20"] = m10["veh_radar_hora"] / bf10 * 100
m10["sube_b20"] = m10["sube_usos"] / bs10 * 100
fig4b = go.Figure()
fig4b.add_trace(go.Scatter(x=m10.index, y=m10["flujo_b20"], name="Flujo vehicular (índice feb-2020=100)",
                           line=dict(color=C_FLUJO, width=3), connectgaps=True,
                           hovertemplate="%{x|%b %Y}: %{y:.0f}<extra></extra>"))
fig4b.add_trace(go.Scatter(x=m10.index, y=m10["sube_b20"], name="Transporte público · SUBE (índice feb-2020=100)",
                           line=dict(color=C_SUBE, width=2),
                           hovertemplate="%{x|%b %Y}: %{y:.0f}<extra></extra>"))
fig4b.add_hline(y=100, line_dash="dash", line_color="#9aa0a6",
                annotation_text="Nivel feb-2020", annotation_position="top left")
fig4b.update_yaxes(title_text="Índice (feb-2020=100)", rangemode="tozero")
fig4b.update_layout(hovermode="x unified")
figs["sube"] = fig_block(
    10, "¿Se sustituye el auto por el transporte público?",
    "Flujo vehicular y transporte público (usos de la tarjeta SUBE en el AMBA), ambos llevados a un índice con base en febrero de 2020: el último mes normal antes de la cuarentena y el primero con datos de SUBE. Los valles tienen explicación: el mínimo absoluto de abril de 2020 es la cuarentena estricta, cuando el transporte público cayó incluso más fuerte que el auto (índice <b>20</b> frente a <b>29</b> del flujo); el bache de mayo de 2021 coincide con la segunda ola de COVID; y los pozos que se repiten cada enero y febrero son las vacaciones de verano. No hay un cruce definitivo entre las curvas: se recuperan casi en paralelo y se turnan por delante. Recién en 2025 el transporte público saca una ventaja transitoria (llega a estar <b>12</b> puntos por encima del flujo en octubre), pero para diciembre vuelve a quedar apenas por debajo: <b>90</b> contra <b>92</b>. El auto no fue reemplazado por el colectivo; seis años después, ambos se estacionaron cerca del 90% de su nivel prepandemia.",
    fig4b, "Radares AUSA/GCBA; SUBE (Min. Transporte). Julio 2024 del flujo imputado por un faltante de origen (ver «Cómo leer estos datos»).")

# El radar SÍ cubre dic-2022 (aunque con nivel deflactado): comparamos la forma
# horaria del día de cada partido de eliminación contra un día típico del mismo
# día de semana. Como ambas curvas vienen del mismo mes, el sesgo de nivel se cancela.
expl = json.loads(expl_json)


def net_dia(fch):
    rows = expl["data"].get(fch)
    if not rows:
        return None
    arr = np.zeros(24)
    for r in rows:
        arr += np.array(r[2:26], dtype=float)
    return arr


def baseline_dia(dias):
    arrs = [net_dia(f"2022-12-{d:02d}") for d in dias]
    arrs = [a for a in arrs if a is not None]
    return np.mean(arrs, axis=0) if arrs else None


# (etiqueta, fecha, resultado, hora_ini, hora_fin, días-base mismo weekday)
PARTIDOS = [
    ("Octavos", "2022-12-03", "Argentina 2–1 Australia", 16, 18, [10, 17, 24, 31]),
    ("Cuartos", "2022-12-09", "Países Bajos 2–2 Argentina (pen.)", 16, 19, [2, 16, 23, 30]),
    ("Semifinal", "2022-12-13", "Argentina 3–0 Croacia", 16, 18, [6, 20, 27]),
    ("FINAL", "2022-12-18", "Argentina 3–3 Francia (pen.)", 12, 15, [4, 11, 25]),
]
hrs = list(range(24))
fig4c = go.Figure()
for i, (lbl, fch, res, h0, h1, bdays) in enumerate(PARTIDOS):
    dprof, bprof = net_dia(fch), baseline_dia(bdays)
    fig4c.add_trace(go.Scatter(x=hrs, y=dprof, name="Día del partido",
                               visible=(i == 0), line=dict(color=ACCENT, width=3),
                               hovertemplate="%{x}:00 h · %{y:.0f}<extra></extra>"))
    fig4c.add_trace(go.Scatter(x=hrs, y=bprof, name="Día típico (mismo día de semana)",
                               visible=(i == 0), line=dict(color=INK2, width=2, dash="dot"),
                               hovertemplate="%{x}:00 h · %{y:.0f}<extra></extra>"))


def _mw(h0, h1, lbl, res):
    shapes = [dict(type="rect", xref="x", yref="paper", x0=h0, x1=h1, y0=0, y1=1,
                   fillcolor=ACCENT, opacity=0.10, line_width=0, layer="below")]
    anns = [dict(x=(h0 + h1) / 2, y=1.0, xref="x", yref="paper", showarrow=False,
                 text=f"⚽ {lbl} · {res}<br>{h0}:00 h", yanchor="bottom",
                 font=dict(color=ACCENT, size=12))]
    return shapes, anns


botones = []
n = len(PARTIDOS)
for i, (lbl, fch, res, h0, h1, bdays) in enumerate(PARTIDOS):
    vis = [False] * (2 * n)
    vis[2 * i] = vis[2 * i + 1] = True
    sh, an = _mw(h0, h1, lbl, res)
    botones.append(dict(label=f"{lbl} · {fch[8:10]}-dic", method="update",
                        args=[{"visible": vis}, {"shapes": sh, "annotations": an}]))
sh0, an0 = _mw(*PARTIDOS[0][3:5], PARTIDOS[0][0], PARTIDOS[0][2])
fig4c.update_layout(xaxis_title="Hora del día", yaxis_title="veh/radar-hora (red total)",
                    shapes=sh0, annotations=an0,
                    updatemenus=[dict(buttons=botones, x=0.0, xanchor="left", y=1.16,
                                      direction="down", showactive=True,
                                      bgcolor="#f3f4f6", bordercolor="#d0d0d0")])
fig4c.update_xaxes(dtick=2)
figs["mundial"] = fig_block(
    11, "Mundial 2022: la Ciudad miró el partido",
    "Elegí un partido de la fase eliminatoria. La franja sombreada marca el horario del encuentro: el tránsito se hunde mientras juega la Selección. En la final (domingo), tras el pitazo, explota en festejos.",
    fig4c, "Flujo vehicular por radares (AUSA/GCBA). Día del partido vs. promedio del mismo día de semana en diciembre 2022.", h=480)

# ─────────────── ACTO 5 — cierre: siniestros ───────────────
print("Acto 5...")
m5 = maestro.copy()
m5["victimas_idx"] = idx_base2019_m(m5["victimas"])
m5["riesgo_rel"] = m5["victimas_idx"] / m5["flujo_idx"] * 100
fig5 = go.Figure()
fig5.add_trace(go.Scatter(x=m5.index, y=m5["flujo_idx"], name="Flujo vehicular (índice 2019=100)",
                          line=dict(color=C_FLUJO, width=3), connectgaps=True))
fig5.add_trace(go.Scatter(x=m5.index, y=m5["victimas_idx"], name="Víctimas viales (índice 2019=100)",
                          line=dict(color=C_SIN, width=2)))
fig5.add_hline(y=100, line_dash="dash", line_color="#9aa0a6",
               annotation_text="Nivel 2019", annotation_position="top left")
fig5.update_yaxes(title_text="Índice (2019=100)", rangemode="tozero")
fig5.update_xaxes(title_text="")
fig5.update_layout(hovermode="x unified")
figs["siniestros"] = fig_block(
    12, "¿Menos autos significó menos víctimas?",
    "Para comparar las dos series sin distorsiones las llevamos a un mismo índice (promedio 2019 = 100) y a un único eje que arranca en cero, sin recortes que exageren una curva sobre otra. Así se ve la verdadera diferencia de pendientes. Durante el aislamiento estricto de abril de 2020 la reducción de víctimas fue drástica y más profunda que la caída del flujo vehicular en autopistas, con una contracción cercana al 80% frente a un 73% del tránsito. Es decir, las víctimas cayeron más rápido que la cantidad de autos, y al recuperarse el flujo no volvieron a treparse en la misma proporción. La cantidad de vehículos, por sí sola, no explica cuánta gente se lastima.",
    fig5, "Radares AUSA/GCBA; Víctimas en siniestros viales (OMSV-GCBA). Ambas series en índice base 2019=100. Julio 2024 del flujo imputado por un faltante de origen (ver «Cómo leer estos datos»).")

fig5b = go.Figure(go.Scatter(x=m5.index, y=m5["riesgo_rel"], mode="lines",
                             line=dict(color=C_SIN, width=2), connectgaps=True,
                             hovertemplate="%{x|%b %Y}: %{y:.0f}<extra></extra>"))
fig5b.add_hline(y=100, line_dash="dash", line_color="#9aa0a6",
                annotation_text="Riesgo 2019", annotation_position="top left")
fig5b.update_layout(yaxis_title="Índice de riesgo relativo", xaxis_title="")
figs["riesgo"] = fig_block(
    13, "El riesgo por viaje durante la parálisis",
    "Este índice divide las víctimas por el flujo (ambos en base 2019=100): mide cuántas víctimas hay por cada unidad de tránsito, no en total. Por encima de 100 cada viaje es más riesgoso que en 2019; por debajo, menos. Contra la intuición de que las calles vacías invitan a correr, el riesgo por viaje no se disparó durante el confinamiento: tocó pisos en abril de 2020 (alrededor de 80) y, sobre todo, en mayo de 2021 (cerca de 48), en plena segunda ola. La parálisis casi total no solo sacó autos de la calle, también apagó las interacciones complejas (cruces, maniobras, congestión) que producen la mayoría de los siniestros, y la siniestralidad por viaje bajó a mínimos históricos. Recién con la vida normalizada el índice vuelve a rondar 100, y hacia fines de 2024 sube por encima por un repunte real en el conteo de víctimas, no por un efecto del denominador.",
    fig5b, "Elaboración propia: OMSV-GCBA sobre flujo de radares (índice víctimas / índice flujo × 100). Julio 2024 del flujo imputado por un faltante de origen (ver «Cómo leer estos datos»).")

# ─────────────── MAPA ANIMADO ───────────────
print("Mapa animado...")
radar_m = radar_m.sort_values("mes")
center = dict(lat=radar_m["lat"].mean(), lon=radar_m["long"].mean())
mapfig = px.density_mapbox(
    radar_m, lat="lat", lon="long", z="cantidad", radius=26,
    center=center, zoom=10, mapbox_style="carto-positron",
    animation_frame="mes", color_continuous_scale="YlOrRd",
    range_color=(0, radar_m["cantidad"].quantile(0.98)), hover_name="disp_nombre",
    hover_data={"autopista_nombre": True, "cantidad": ":.0f", "lat": False, "long": False})
mapfig.update_layout(template="plotly_white", paper_bgcolor="white",
                     font=dict(color=INK, family=FONT_CHART),
                     margin=dict(l=0, r=0, t=10, b=0), height=560,
                     coloraxis_colorbar=dict(title="veh/h", thickness=12))
if mapfig.layout.updatemenus:
    mapfig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 400
figs["mapa"] = fig_block(
    14, "El ritmo de la Ciudad, radar por radar",
    "Heatmap temporal del flujo mensual por radar. Apretá ▶ para ver el vaciamiento de 2020 y la recuperación.",
    mapfig, "Flujo vehicular por radares (AUSA/GCBA), panel estable. Julio 2024 imputado por un faltante de origen (ver «Cómo leer estos datos»).", mapa=True)

# ─────────────── Explorador granular (JS + JSON inline) ───────────────
print("Explorador...")
explorer_js = r"""
<figure class="chart" id="explorador">
  <div class="fig-head">
    <span class="fig-num">Gráfico 15</span>
    <h3>Explorador: el tránsito hora por hora</h3>
    <p class="dek">Elegí <b>año</b>, <b>mes</b>, <b>día</b> y <b>sentido</b>. Cada línea es una autopista (veh/radar-hora, promedio de las fechas elegidas). Mirá un día puntual o un año entero.</p>
  </div>
  <div class="expl-controls">
    <label>Año <select id="ex-anio"></select></label>
    <label>Mes <select id="ex-mes"></select></label>
    <label>Día <select id="ex-dia"></select></label>
    <label>Sentido <select id="ex-sent">
      <option value="*">Ambos</option>
      <option value="A">Hacia Centro (A)</option>
      <option value="B">Hacia Provincia (B)</option>
    </select></label>
  </div>
  <div id="ex-chart" class="plotly-graph-div" style="height:480px"></div>
  <figcaption>Fuente: Flujo vehicular por radares (AUSA/GCBA). Promedio veh/radar-hora sobre las fechas seleccionadas.</figcaption>
</figure>
<script>
const EXPL = __EXPL_JSON__;
(function(){
  const PAL = ['#4e79a7','#f28e2b','#59a14f','#e15759','#76b7b2','#edc948','#b07aa1','#ff9da7','#9c755f'];
  const autos = EXPL.autos, data = EXPL.data;
  const keys = Object.keys(data);
  const years = [...new Set(keys.map(k=>k.slice(0,4)))].sort();
  const elA=document.getElementById('ex-anio'),elM=document.getElementById('ex-mes'),
        elD=document.getElementById('ex-dia'),elS=document.getElementById('ex-sent');
  function opt(el,val,txt){const o=document.createElement('option');o.value=val;o.textContent=txt;el.appendChild(o);}
  opt(elA,'*','Todos');years.forEach(y=>opt(elA,y,y));
  opt(elM,'*','Todos');const MN=['','Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  for(let m=1;m<=12;m++)opt(elM,m,MN[m]);
  opt(elD,'*','Todos');for(let d=1;d<=31;d++)opt(elD,d,d);
  elA.value = years.includes('2024')?'2024':years[years.length-1];
  const layout={height:480,
    font:{family:"Helvetica Neue, Arial, sans-serif",color:"#22272e",size:13},
    margin:{l:58,r:24,t:16,b:46},paper_bgcolor:'white',plot_bgcolor:'white',
    hovermode:'x unified',
    legend:{orientation:'h',yanchor:'bottom',y:1.0,x:0,bgcolor:'rgba(0,0,0,0)'},
    xaxis:{title:'Hora del día',dtick:2,showgrid:false,linecolor:'#c7ccd1',ticks:'outside',tickcolor:'#c7ccd1'},
    yaxis:{title:'veh/radar-hora',gridcolor:'#e8eaed',zeroline:false}};
  const cfg={displayModeBar:true,displaylogo:false,responsive:true,
    modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d']};
  function agg(){
    const yv=elA.value,mv=elM.value,dv=elD.value,sv=elS.value;
    const sums=autos.map(()=>new Array(24).fill(0));
    const cnts=autos.map(()=>0);
    for(const f in data){
      const Y=f.slice(0,4),M=+f.slice(5,7),D=+f.slice(8,10);
      if(yv!=='*'&&Y!==yv)continue;
      if(mv!=='*'&&M!==+mv)continue;
      if(dv!=='*'&&D!==+dv)continue;
      const rows=data[f],dayv={};
      for(const r of rows){
        const ai=r[0],sc=r[1];
        if(sv==='A'&&sc!==0)continue;
        if(sv==='B'&&sc!==1)continue;
        if(!dayv[ai])dayv[ai]=new Array(24).fill(0);
        for(let h=0;h<24;h++)dayv[ai][h]+=r[2+h];
      }
      for(const ai in dayv){for(let h=0;h<24;h++)sums[ai][h]+=dayv[ai][h];cnts[ai]++;}
    }
    const traces=[],hrs=[...Array(24).keys()];
    for(let i=0;i<autos.length;i++){
      if(cnts[i]===0)continue;
      traces.push({x:hrs,y:sums[i].map(v=>v/cnts[i]),name:autos[i],mode:'lines',
        line:{color:PAL[i%PAL.length],width:1.8},type:'scatter',
        hovertemplate:autos[i]+': %{y:.0f}<extra></extra>'});
    }
    return traces;
  }
  function draw(){
    const t=agg();
    if(!t.length){
      Plotly.react('ex-chart',[],Object.assign({},layout,{annotations:[{text:'Sin datos para esa combinación',xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:16,color:'#8a929b'}}]}),cfg);
      return;
    }
    Plotly.react('ex-chart',t,layout,cfg);
  }
  [elA,elM,elD,elS].forEach(e=>e.addEventListener('change',draw));
  draw();
})();
</script>
""".replace("__EXPL_JSON__", expl_json)

# ─────────────── Indicadores ───────────────
i2019 = idx_anual.loc[idx_anual["anio"] == 2019, "veh_radar_hora"].iloc[0]
i2024 = idx_anual.loc[idx_anual["anio"] == 2024, "veh_radar_hora"].iloc[0]
recup_pct = i2024 / i2019 * 100
pico_2019 = hab[hab["anio"] == 2019].groupby("hora")["cantidad"].mean().max()
pico_2024 = hab[hab["anio"] == 2024].groupby("hora")["cantidad"].mean().max()


def kpi(v, l, s=""):
    return f'<div class="kpi"><div class="kpi-val">{v}</div><div class="kpi-lbl">{l}</div><div class="kpi-sub">{s}</div></div>'


kpis = (kpi("−72%", "caída del flujo en abril 2020", "el momento más dramático") +
        kpi(f"{recup_pct:.0f}%", "del volumen 2019, recuperado en 2024", "el tránsito volvió") +
        kpi(f"{pico_2024/pico_2019*100:.0f}%", "del pico horario hábil de 2019", "pero la hora pico se aplanó"))

# ─────────────── HTML ───────────────
print("Ensamblando HTML...")
HOY = pd.Timestamp.now()
_MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
FECHA_ES = f"{HOY.day} de {_MESES_ES[HOY.month-1]} de {HOY.year}"

HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>La Ciudad que cambió de ritmo</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  :root {{ --ink:{INK}; --ink2:{INK2}; --accent:{ACCENT}; --line:#e2e5e9; }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{ margin:0; background:#fff; color:var(--ink);
         font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;
         font-size:18px; line-height:1.7; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:0 22px; }}
  .wide {{ max-width:1000px; margin:0 auto; padding:0 22px; }}

  /* Cabecera editorial */
  header.masthead {{ border-bottom:2px solid var(--ink); margin-bottom:0; }}
  .masthead-inner {{ max-width:1000px; margin:0 auto; padding:14px 22px;
        display:flex; justify-content:space-between; align-items:baseline;
        font-size:.78rem; letter-spacing:.12em; text-transform:uppercase; color:var(--ink2); }}
  .masthead-inner b {{ color:var(--ink); letter-spacing:.06em; }}

  .hero {{ max-width:1040px; margin:0 auto; padding:0 12px; }}
  .kicker {{ color:var(--accent); font-weight:700; letter-spacing:.14em;
        text-transform:uppercase; font-size:.8rem; margin:42px 0 12px; }}
  h1.title {{ font-family:{FONT_UI}; font-weight:700; font-size:4rem;
        line-height:1.06; letter-spacing:-1px; margin:0 0 12px; }}
  .standfirst {{ font-size:1.32rem; line-height:1.5; color:#333; font-weight:400;
        font-family:{FONT_UI}; margin:0 0 26px; }}
  .byline {{ font-size:.92rem; color:var(--ink2); border-top:1px solid var(--line);
        border-bottom:1px solid var(--line); padding:12px 0; margin:0 0 8px;
        display:flex; gap:16px; flex-wrap:wrap; }}
  .byline b {{ color:var(--ink); }}

  /* Cuerpo */
  section {{ padding:8px 0 26px; }}
  .act-divider {{ border:0; border-top:3px solid var(--ink); max-width:1000px;
        margin:46px auto 0; }}
  .act-num {{ font-family:{FONT_UI}; font-style:italic; color:var(--accent);
        font-size:1rem; margin:34px 0 2px; }}
  h2 {{ font-family:{FONT_UI}; font-weight:700; font-size:2rem; line-height:1.18;
        margin:4px 0 14px; letter-spacing:-.3px; }}
  p.body {{ margin:0 0 18px; }}
  p.body.lead::first-letter {{ font-family:{FONT_UI}; font-weight:700; float:left;
        font-size:3.4rem; line-height:.82; padding:6px 10px 0 0; color:var(--ink); }}
  em {{ font-style:italic; }}

  /* Pull quote / tesis */
  blockquote.thesis {{ font-family:{FONT_UI}; font-size:1.55rem; line-height:1.4;
        color:var(--ink); border-left:4px solid var(--accent); margin:30px 0;
        padding:6px 0 6px 26px; }}

  /* KPIs */
  .kpis {{ display:flex; gap:0; flex-wrap:wrap; max-width:1000px; margin:30px auto;
        padding:0 22px; border-top:1px solid var(--line); }}
  .kpi {{ flex:1; min-width:200px; padding:22px 20px; border-bottom:1px solid var(--line);
        border-right:1px solid var(--line); }}
  .kpi:first-child {{ border-left:1px solid var(--line); }}
  .kpi-val {{ font-family:{FONT_UI}; font-size:2.7rem; font-weight:700; color:var(--accent);
        line-height:1; }}
  .kpi-lbl {{ font-size:.98rem; color:var(--ink); margin-top:8px; font-weight:600; }}
  .kpi-sub {{ font-size:.85rem; color:var(--ink2); margin-top:3px; }}

  /* Gráficos */
  figure.chart {{ margin:26px auto; max-width:1000px; padding:0 22px; }}
  .fig-head {{ margin-bottom:6px; }}
  .fig-num {{ font-size:.72rem; letter-spacing:.12em; text-transform:uppercase;
        color:var(--accent); font-weight:700; }}
  .fig-head h3 {{ font-family:{FONT_UI}; font-size:1.32rem; margin:3px 0 4px; line-height:1.25; }}
  .dek {{ color:var(--ink2); font-size:.98rem; margin:0 0 10px; line-height:1.5; }}
  figure.chart .plotly-graph-div {{ border:1px solid var(--line); border-radius:4px;
        padding:6px; background:#fff; }}
  figcaption {{ font-size:.8rem; color:#8a929b; margin-top:8px;
        border-top:1px solid var(--line); padding-top:7px; }}

  /* Controles del explorador */
  .expl-controls {{ display:flex; gap:18px; flex-wrap:wrap; margin:4px 0 12px;
        padding:12px 14px; background:#f6f7f9; border:1px solid var(--line); border-radius:4px; }}
  .expl-controls label {{ font-size:.82rem; color:var(--ink2); font-weight:600;
        text-transform:uppercase; letter-spacing:.06em; display:flex; align-items:center; gap:7px; }}
  .expl-controls select {{ font-family:{FONT_CHART}; font-size:.95rem; color:var(--ink);
        padding:5px 9px; border:1px solid #c7ccd1; border-radius:3px; background:#fff;
        text-transform:none; letter-spacing:0; font-weight:400; cursor:pointer; }}

  /* Nota metodológica */
  .nota {{ max-width:760px; margin:8px auto; padding:0 22px; }}
  .nota .box {{ background:#f6f7f9; border:1px solid var(--line); border-left:4px solid {C_PEAJE};
        border-radius:4px; padding:18px 22px; font-size:.96rem; color:#3b424a; }}
  .caveats .box {{ border-left-color:#9aa0a6; }}
  .box h4 {{ margin:0 0 8px; font-family:{FONT_UI}; font-size:1.05rem; }}
  .box ul {{ margin:6px 0 0; padding-left:20px; }}
  .box li {{ margin:5px 0; }}

  footer {{ border-top:2px solid var(--ink); margin-top:50px; }}
  .foot-inner {{ max-width:1000px; margin:0 auto; padding:26px 22px 50px;
        font-size:.85rem; color:var(--ink2); line-height:1.6; }}
  a {{ color:var(--accent); }}
  @media (max-width:640px) {{ h1.title {{ font-size:2.2rem; }} body {{ font-size:16px; }} }}
</style>
</head>
<body>

<header class="masthead">
  <div class="masthead-inner">
    <span><b>PROYECTO 1 · ITBA</b> · Visualización de datos</span>
    <span>Buenos Aires · 2019–2025</span>
  </div>
</header>

<div class="hero">
  <div class="kicker">Análisis de datos · Movilidad urbana · 2019–2025</div>
  <h1 class="title">La Ciudad que cambió de ritmo</h1>
</div>
<div class="wrap">
  <p class="standfirst">La pandemia no solo vació las autopistas porteñas: cambió de forma
  permanente <em>cuándo</em> se mueve la Ciudad. Una lectura del flujo vehicular en seis años,
  cruzada con nafta, transporte público y siniestros.</p>
  <div class="byline">
    <span>Por <b>Santiago Minoyetti</b></span>
    <span>{FECHA_ES}</span>
    <span>Lectura: 8 min · 15 gráficos interactivos</span>
  </div>
</div>

<div class="kpis">{kpis}</div>

<div class="wrap">
  <blockquote class="thesis">"El tránsito volvió en volumen, pero perdió su forma rígida y dejó
  al conductor porteño mucho más sensible al contexto económico que antes."</blockquote>
</div>

<hr class="act-divider">
<div class="wrap">
  <section>
    <div class="act-num">1 · El pulso normal</div>
    <h2>¿Cómo latía la Ciudad antes de la pandemia?</h2>
    <p class="body lead">En 2019 el conductor porteño tenía una rutina previsible: dos jorobas de
    hora pico, una semana laboral rígida y tres corredores que concentraban el grueso del tránsito.
    Ese patrón es el punto de partida, y el contraste, de todo lo que vino después.</p>
  </section>
</div>
{figs['heatmap_semana']}
<div class="wrap"><section>
  <p class="body">Recorriendo los años se ve la transformación. En <b>2019</b> la semana laboral es
  un bloque casi monolítico, con una concentración cada vez más intensa sobre el final de la semana,
  de miércoles en adelante; el "arranque" es nítido a las 6 de la mañana y la vuelta aparece más
  repartida a lo largo de la tarde. En <b>2020</b> el patrón es prácticamente el mismo, pero la
  escala de color baja de golpe: la forma no cambia, lo que se desploma es el volumen. En los años
  siguientes, de <b>2021 a 2023</b>, se nota una caída del flujo los lunes y los viernes; en
  <b>2024</b> la semana parece emparejarse de nuevo, pero en <b>2025</b> los días más intensos pasan
  a ser claramente los jueves y los martes. Ese corrimiento de patrón es compatible con los nuevos
  hábitos de trabajo: la llegada del teletrabajo y su mayor flexibilidad. Lo mismo ocurre con las
  horas: en 2019 se distinguen con claridad el ingreso y el egreso, mientras que en la pospandemia
  ese patrón se vuelve difuso, lo que confirma la sensación de que hoy hay tránsito a cualquier hora.</p>
</section></div>
{figs['ranking_au']}
<div class="wrap"><section>
  <p class="body">La métrica protagonista es <em>vehículos por radar-hora</em> sobre un
  <b>panel estable</b> (las autopistas presentes todos los años: Lugones, Cantilo, 9 de Julio Sur
  y Dellepiane). Así se comparan peras con peras, sin que el alta de nuevos sensores infle los totales.</p>
</section></div>

<hr class="act-divider">
<div class="wrap">
  <section>
    <div class="act-num">2 · El shock</div>
    <h2>El día que se vació la Ciudad</h2>
    <p class="body lead">En abril de 2020 el flujo se desplomó un 72%. No fue un dato aislado:
    los radares, los peajes y la movilidad de Google cayeron al unísono. Cuando tres fuentes
    independientes cuentan la misma historia, el dato es sólido.</p>
  </section>
</div>
{figs['shock']}
<div class="wrap"><section>
  <p class="body">Que el tránsito bajó en la pandemia lo sabe todo el mundo; lo interesante es
  <em>cuánto</em> y <em>por cuánto tiempo</em>. En abril de 2020 el flujo se hundió alrededor de un
  72% respecto de 2019: de cada diez autos, quedaban menos de tres en la calle. Y la vuelta fue
  lenta: recién hacia 2024, casi cuatro años después, el volumen se reaproxima a los niveles previos.
  Las tres curvas vienen de orígenes independientes (los radares de las autopistas, los pasos de
  peaje de AUSA y los registros de movilidad de Google), y que cuenten la misma historia es lo que
  le da solidez al dato.</p>
</section></div>

<hr class="act-divider">
<div class="wrap">
  <section>
    <div class="act-num">3 · La recuperación incompleta</div>
    <h2>Volvió… pero no volvió igual</h2>
    <p class="body lead">Hacia 2024 el volumen casi recupera el nivel de 2019. Pero la pregunta
    no es solo cuánto, sino con qué forma: la hora pico de los días hábiles se aplanó, señal de
    una semana más híbrida.</p>
  </section>
</div>
{figs['recup']}
<div class="nota"><div class="box">
  <h4>Compensar el hueco de 2022 con una segunda fuente</h4>
  Al dataset de radares le faltan los meses de <b>marzo a septiembre de 2022</b>, lo que hunde
  artificialmente su índice anual. Para no contar una historia falsa, sumamos el
  <b>flujo por unidades de peaje de AUSA</b> (una fuente independiente y completa) que muestra que
  2022 ya estaba en plena recuperación (≈{p22:.0f} sobre 100). Cinco meses con valores corruptos en
  el origen de los peajes (duplicados) fueron detectados y anulados.
</div></div>

<div class="wrap"><section>
  <p class="body">Pero el volumen anual esconde lo más interesante: <em>la forma</em>. Para verla,
  bajamos a la semana tipo (el promedio de cada hora de cada día) autopista por autopista.
  Empezamos por 2019, la línea de base contra la que se mide todo lo demás.</p>
</section></div>
{figs['semana_2019']}
{figs['mensual_au']}
<div class="wrap"><section>
  <p class="body">Y entonces, 2020. La semana promedio no solo baja de nivel: <b>pierde su silueta</b>.
  Las dos jorobas de la hora pico se desdibujan hasta casi desaparecer.</p>
</section></div>
{figs['pandemia']}
{figs['semana_anios']}

<hr class="act-divider">
<div class="wrap">
  <section>
    <div class="act-num">4 · Las fuerzas que tiran del volante</div>
    <h2>Qué mueve hoy al conductor porteño</h2>
    <p class="body lead">El tránsito post-pandemia dejó de ser pura inercia: responde al precio
    de la nafta, a las tarifas del transporte público y hasta a un partido de fútbol. La Ciudad
    se volvió más elástica al contexto.</p>
  </section>
</div>
{figs['nafta']}
{figs['sube']}
{figs['mundial']}

<hr class="act-divider">
<div class="wrap">
  <section>
    <div class="act-num">5 · El cierre</div>
    <h2>Menos autos, ¿menos víctimas?</h2>
    <p class="body lead">El cierre mira la otra cara del tránsito: los siniestros. Cuando la Ciudad
    se paralizó, las víctimas no solo bajaron, cayeron más rápido que la cantidad de autos, y el
    riesgo <em>por viaje</em> tocó mínimos históricos. La relación entre volumen y seguridad no
    es lineal.</p>
  </section>
</div>
{figs['siniestros']}
{figs['riesgo']}

<hr class="act-divider">
<div class="wrap">
  <section>
    <div class="act-num">Conclusión</div>
    <h2>Cómo cambió el conductor porteño</h2>
    <p class="body lead">El recorrido deja una idea de fondo: el tránsito de la Ciudad recuperó
    su volumen, pero no volvió a ser el de antes. Lo que cambió es el patrón de comportamiento de
    quienes manejan.</p>
    <p class="body">La rutina rígida de 2019, con dos picos diarios filosos y una semana laboral
    pareja de lunes a viernes, se aflojó. Hoy la hora pico está más aplanada, el ingreso y el egreso
    se reparten a lo largo del día y aparecen días "fuertes" que antes no lo eran. En 2019, la hora
    pico más cargada caía miércoles y viernes (unos <b>4.870</b> y <b>4.830</b> vehículos por hora en
    su momento más intenso) y el martes era el día laboral más flojo (<b>4.540</b>). En 2025 el orden
    se dio vuelta: el martes y el jueves pasaron a encabezar la semana (<b>4.190</b> y <b>4.170</b>
    veh/h en el pico), mientras que el lunes y el viernes se descolgaron hacia el fondo (<b>3.960</b>
    y <b>4.010</b>). Es la huella del teletrabajo y de una semana más flexible, donde ya no todos
    entran a la misma hora ni los mismos días. El fin de semana, en cambio, casi no se movió: cambiamos la forma en que trabajamos, no la
    forma en que descansamos.</p>
    <p class="body">Al mismo tiempo, el conductor quedó más expuesto al contexto. El precio de la
    nafta sube y el tránsito apenas lo acusa, el transporte público se recuperó casi a la par del auto, la
    siniestralidad sigue su propia lógica (cuando la Ciudad se paralizó, el riesgo por viaje cayó a
    mínimos históricos) y hasta un partido de la Selección puede apagar la Ciudad por noventa
    minutos. El auto sigue siendo una necesidad, pero el modo en que lo
    usamos se volvió más sensible, más repartido y menos previsible que antes de la pandemia.</p>
  </section>
</div>

<hr class="act-divider">
<div class="wide"><section>
  <div class="act-num">Mapa</div>
  <h2>El pulso de la Ciudad, radar por radar</h2>
</section></div>
{figs['mapa']}

<div class="nota caveats"><div class="box">
  <h4>Cómo leer estos datos (limitaciones)</h4>
  <ul>
    <li><b>Panel estable:</b> solo radares presentes todos los años, para neutralizar altas/bajas de sensores.</li>
    <li><b>Métrica relativa:</b> veh/radar-hora, no totales absolutos (no comparables entre años).</li>
    <li><b>2022 del radar:</b> faltan mar–sep y, además, oct–dic traen valores corruptos
    (mismos radares y registros, pero conteos a ⅓ de lo normal). Esos meses se anulan y el
    nivel de 2022 se complementa con peajes.</li>
    <li><b>Julio 2024 imputado:</b> el dataset publicado de origen solo trae las horas 11 a 23 de
    ese mes (faltan las 00 a 10, las de menor tránsito), lo que inflaba el promedio mensual cerca de
    un 20% y generaba un pico artificial. Se corrigió multiplicando el valor por el <i>factor de
    descuento nocturno</i> —el cociente entre la media de 24 horas y la de 11 a 23— observado en los
    julios completos de 2019, 2021, 2023 y 2025 (promedio 0,808). Es una estimación modelada, no un
    dato de origen, y afecta a los Gráficos 3, 4, 6, 9, 10, 12, 13 y al mapa.</li>
    <li><b>Peajes:</b> 5 meses con errores de origen (valores duplicados) fueron anulados.</li>
    <li><b>Universos geográficos distintos:</b> el índice de riesgo relativo debe interpretarse con
    cautela. El denominador (flujo) se mide estrictamente en un panel de autopistas controladas por
    AUSA, mientras que el numerador (víctimas) abarca todos los siniestros de la CABA, incluidas
    calles barriales, avenidas y cruces peatonales. En confinamientos localizados, la movilidad de
    cercanía y la de autopista se mueven a ritmos distintos, lo que puede sobredimensionar las
    variaciones del cociente.</li>
    <li><b>Meses sin flujo:</b> el riesgo no se calcula para 2022 (mar–sep faltantes y oct–dic
    corruptos en el radar), por eso la curva del Gráfico 13 se interrumpe ese año.</li>
    <li><b>Sin velocidad medida:</b> el riesgo del cierre se infiere de la relación víctimas/flujo,
    no de velocidades observadas.</li>
    <li><b>Movilidad Google:</b> disponible solo entre feb-2020 y oct-2022.</li>
  </ul>
</div></div>

<hr class="act-divider">
<div class="wide"><section>
  <div class="act-num">Explorá vos</div>
  <h2>El dataset completo, en tus manos</h2>
</section></div>
<div class="wrap"><section>
  <p class="body">Hasta acá contamos nuestra historia. Pero los datos admiten muchas más.
  Este último gráfico abre el cubo entero: elegí cualquier año, mes, día y sentido de
  circulación, y compará el perfil horario de las nueve autopistas. Desde un martes
  cualquiera hasta el promedio de un año entero.</p>
</section></div>
{explorer_js}

<footer>
  <div class="foot-inner">
    <b>Fuentes:</b> Flujo vehicular por radares y por peajes AUSA (BA Data) ·
    Víctimas en siniestros viales OMSV-GCBA · Precios en surtidor Res. 314/2016 (Sec. Energía) ·
    SUBE (Min. Transporte) · Google COVID-19 Community Mobility · calendario Qatar 2022.<br><br>
    Procesamiento y visualización: Python (pandas, Plotly). Índices base 2019=100.
  </div>
</footer>

</body>
</html>"""

OUT.write_text(HTML, encoding="utf-8")
print(f"\nListo: {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
print(f"  Recuperación 2024 vs 2019 (radar): {recup_pct:.0f}%")
print(f"  2022 — radar: {idx_anual.loc[idx_anual.anio==2022,'indice_base2019'].iloc[0]:.0f} | peajes: {p22:.0f}")
