"""
Procesa el flujo vehicular por unidades de peaje AUSA (2019-2024) a serie
mensual de pasos totales. Sirve para COMPENSAR el hueco del radar en 2022
(que no tiene marzo-septiembre) con una fuente independiente y completa.

Esquemas heterogéneos por año:
  2019: CSV grande, col 'fecha' (YYYY-MM-DD), 'cantidad_pasos'
  2020: CSV grande, col 'fecha' (YYYY-MM-DD HH:MM:SS), 'cantidad_pasos'
  2021: CSV grande, 'Año de Fecha Operativa'=2021, 'Mes de Fecha Operativa'=nombre, 'Pasos'
  2022-2024: ZIP con un CSV por mes, 'Año de Fecha Operativa'=fecha d/m/Y, 'Pasos'

Salida: contexto/procesado/peajes_mensual.csv  (mes, pasos, pasos_idx)
"""
import sys
import zipfile
import calendar
import pandas as pd
import numpy as np
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PJ = Path(r"C:\Users\santi\OneDrive\Documents\itba\Proyecto1\contexto\peajes")
OUT = Path(r"C:\Users\santi\OneDrive\Documents\itba\Proyecto1\contexto\procesado")

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

monthly = {}  # (anio, mes) -> pasos


def add(anio, mes, pasos):
    monthly[(anio, mes)] = monthly.get((anio, mes), 0) + pasos


# ── 2019 ──
print("Peajes 2019...")
for ch in pd.read_csv(PJ / "peaje_2019.csv", usecols=["fecha", "cantidad_pasos"],
                      chunksize=500_000):
    ch["fecha"] = pd.to_datetime(ch["fecha"], errors="coerce")
    ch = ch.dropna(subset=["fecha"])
    ch["cantidad_pasos"] = pd.to_numeric(ch["cantidad_pasos"], errors="coerce").fillna(0)
    g = ch.groupby([ch["fecha"].dt.year, ch["fecha"].dt.month])["cantidad_pasos"].sum()
    for (a, m), v in g.items():
        add(int(a), int(m), v)

# ── 2020 ──
print("Peajes 2020...")
for ch in pd.read_csv(PJ / "peaje_2020.csv", usecols=["fecha", "cantidad_pasos"],
                      chunksize=500_000):
    ch["fecha"] = pd.to_datetime(ch["fecha"], errors="coerce")
    ch = ch.dropna(subset=["fecha"])
    ch["cantidad_pasos"] = pd.to_numeric(ch["cantidad_pasos"], errors="coerce").fillna(0)
    g = ch.groupby([ch["fecha"].dt.year, ch["fecha"].dt.month])["cantidad_pasos"].sum()
    for (a, m), v in g.items():
        add(int(a), int(m), v)

# ── 2021 (mes por nombre, dedup filas duplicadas y descartar 'total') ──
print("Peajes 2021...")
df21 = pd.read_csv(PJ / "peaje_2021.csv", sep=None, engine="python")
df21 = df21.drop_duplicates()
mes_col = [c for c in df21.columns if "Mes de Fecha Operativa" in c][0]
pasos_col = [c for c in df21.columns if c.strip().lower() == "pasos"][0]
df21["m"] = df21[mes_col].astype(str).str.strip().str.lower().map(MESES_ES)
df21["pasos"] = pd.to_numeric(df21[pasos_col], errors="coerce").fillna(0)
df21 = df21.dropna(subset=["m"])  # descarta filas 'total'
for m, v in df21.groupby("m")["pasos"].sum().items():
    add(2021, int(m), v)


def mes_desde_nombre(fname: str):
    """Devuelve lista de meses (1-12) presentes en el nombre del archivo."""
    low = fname.lower()
    return [num for nom, num in MESES_ES.items() if nom in low]


# ── 2022-2024 (ZIP): el mes se deriva del NOMBRE del archivo
#    (las columnas de fecha mezclan 3 formatos distintos e irreparables) ──
for y in (2022, 2023, 2024):
    print(f"Peajes {y}...")
    z = zipfile.ZipFile(PJ / f"peaje_{y}.zip")
    for name in z.namelist():
        if not name.lower().endswith(".csv"):
            continue
        df = None
        for sep in (None, ";", ","):
            with z.open(name) as f:
                tmp_df = pd.read_csv(f, sep=sep, engine="python", encoding="latin-1")
            if any(c.strip().lower() == "pasos" for c in tmp_df.columns):
                df = tmp_df
                break
        if df is None:
            print(f"  ! sin columna Pasos en {name}, salteado")
            continue
        col_pasos = [c for c in df.columns if c.strip().lower() == "pasos"][0]
        pasos = pd.to_numeric(df[col_pasos], errors="coerce").fillna(0)
        meses = mes_desde_nombre(name)
        if len(meses) == 1:
            add(y, meses[0], pasos.sum())
        else:
            # archivo combinado (ej. Enero-Febrero): repartir por fecha ISO
            col_fecha = [c for c in df.columns if "Fecha Operativa" in c][0]
            fechas = pd.to_datetime(df[col_fecha], errors="coerce", dayfirst=False)
            tmp = pd.DataFrame({"f": fechas, "p": pasos}).dropna(subset=["f"])
            for (a, m), v in tmp.groupby([tmp["f"].dt.year, tmp["f"].dt.month])["p"].sum().items():
                add(int(a), int(m), v)

# ── Ensamble ──
ser = pd.Series(monthly).sort_index()
ser.index = pd.to_datetime([f"{a}-{m:02d}-01" for a, m in ser.index])
ser = ser.sort_index()
ser = ser[(ser.index.year >= 2019) & (ser.index.year <= 2025)]

base = ser[ser.index.year == 2019].mean()
out = pd.DataFrame({"pasos": ser, "pasos_idx": ser / base * 100})
# Filtro de sanidad: meses con índice implausible (>150 o <30) son errores
# de la fuente (archivos mensuales duplicados o truncados). Se anulan.
anomalos = out[(out["pasos_idx"] > 150) | (out["pasos_idx"] < 30)]
if len(anomalos):
    print("\nMeses anómalos anulados (error de fuente):")
    for mes, r in anomalos.iterrows():
        print(f"  {mes:%Y-%m}: idx {r['pasos_idx']:.0f}")
    out.loc[anomalos.index, ["pasos", "pasos_idx"]] = np.nan
out.index.name = "mes"
OUT.mkdir(exist_ok=True)
out.to_csv(OUT / "peajes_mensual.csv")

# anual (sobre la serie ya filtrada)
ser_ok = out["pasos"].dropna()
anual = ser_ok.groupby(ser_ok.index.year).mean()
anual_idx = anual / anual[2019] * 100
anual.to_frame("pasos").assign(pasos_idx=anual_idx).rename_axis("anio") \
    .to_csv(OUT / "peajes_anual.csv")
print("\nÍndice anual peajes (base 2019=100):")
for a, v in anual_idx.items():
    print(f"  {a}: {v:5.1f}   (meses válidos: {(ser_ok.index.year==a).sum()})")
print(f"\nGuardado: {OUT / 'peajes_mensual.csv'}  ({len(out)} meses)")
