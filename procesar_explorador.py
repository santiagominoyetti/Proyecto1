"""
Genera extractos para los gráficos nuevos del informe:
  07_semana_autopista.csv  — semana promedio (dow×hora) por autopista y año
  08_mensual_autopista.csv — tránsito mensual por autopista y año
  explorador.json          — cubo (fecha, autopista, sentido) → 24 valores horarios
                             para el gráfico explorador filtrable por año/mes/día/sentido

Métrica: veh por radar-hora (media sobre radares) → respeta la multiplicidad de radares.
"""
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = Path(r"C:\Users\santi\OneDrive\Documents\itba\Proyecto1")
SRC = BASE / "flujo-vehicular-limpio.csv"
EXT = BASE / "tableau_extracts"
EXT.mkdir(exist_ok=True)

print("Leyendo flujo limpio...")
cols = ["fecha", "anio", "hora", "autopista_nombre", "seccion_sentido", "cantidad"]
df = pd.read_csv(SRC, usecols=cols)
df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
df = df[df["fecha"].notna()]
df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
df = df[df["cantidad"].notna()]
df["hora"] = pd.to_numeric(df["hora"], errors="coerce").astype("Int64")
df = df[df["hora"].between(0, 23)]
df["dow"] = df["fecha"].dt.dayofweek
df["mes"] = df["fecha"].dt.month
print(f"  {len(df):,} filas válidas")

# Meses con valores de radar corruptos (mismos radares/filas pero conteos ~1/3
# de lo normal; defecto de la fuente). Se excluyen de las agregaciones de forma.
CORRUPTOS = {(2022, 10), (2022, 11), (2022, 12)}
clean = df[~df.set_index(["anio", "mes"]).index.isin(CORRUPTOS)]
print(f"  {len(df) - len(clean):,} filas en meses corruptos excluidas de 07/08")

# ── 07 semana promedio por autopista y año ──
print("07 semana_autopista...")
sem = (clean.groupby(["anio", "autopista_nombre", "dow", "hora"])["cantidad"]
         .mean().reset_index().rename(columns={"cantidad": "veh_radar_hora"}))
sem["hw"] = sem["dow"] * 24 + sem["hora"]   # hora de la semana 0..167
sem.to_csv(EXT / "07_semana_autopista.csv", index=False)
print(f"  {len(sem):,} filas, {sem['anio'].nunique()} años, {sem['autopista_nombre'].nunique()} autopistas")

# ── 08 mensual por autopista y año ──
print("08 mensual_autopista...")
men = (clean.groupby(["anio", "mes", "autopista_nombre"])["cantidad"]
         .mean().reset_index().rename(columns={"cantidad": "veh_radar_hora"}))
men["periodo"] = pd.to_datetime(dict(year=men["anio"], month=men["mes"], day=1)).dt.strftime("%Y-%m")
men.to_csv(EXT / "08_mensual_autopista.csv", index=False)
print(f"  {len(men):,} filas")

# ── explorador.json — cubo (fecha, autopista, sentido)→[24 horas] ──
print("explorador.json (puede tardar)...")
ex = df[df["seccion_sentido"].isin(["A", "B"])].copy()
ex["fstr"] = ex["fecha"].dt.strftime("%Y-%m-%d")
autos = sorted(ex["autopista_nombre"].unique())
auto_idx = {a: i for i, a in enumerate(autos)}
sent_code = {"A": 0, "B": 1}

# media por (fecha, autopista, sentido, hora)
g = (ex.groupby(["fstr", "autopista_nombre", "seccion_sentido", "hora"])["cantidad"]
       .mean().round().astype(int))

data = {}  # fecha -> list of [autoIdx, sentCode, v0..v23]
for (fstr, auto, sent), sub in g.groupby(level=[0, 1, 2]):
    arr = [0] * 24
    for h, v in sub.droplevel([0, 1, 2]).items():
        arr[int(h)] = int(v)
    data.setdefault(fstr, []).append([auto_idx[auto], sent_code[sent]] + arr)

payload = {"autos": autos, "data": data}
out = EXT / "explorador.json"
out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
print(f"  {len(data):,} fechas, {out.stat().st_size/1024/1024:.1f} MB")
print("Listo.")
