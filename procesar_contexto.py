"""
Procesa las capas de contexto descargadas a series mensuales compactas,
todas alineadas e indexadas (base 2019=100 donde haya 2019).
Salida: contexto/procesado/*.csv
"""
import sys
import json
import glob
import pandas as pd
import numpy as np
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CTX = Path(r"C:\Users\santi\OneDrive\Documents\itba\Proyecto1\contexto")
OUT = CTX / "procesado"
OUT.mkdir(exist_ok=True)


def idx_base2019(serie: pd.Series) -> pd.Series:
    """Indexa a base 2019=100 usando el promedio de los meses de 2019."""
    base = serie[serie.index.year == 2019].mean()
    return serie / base * 100 if base and not np.isnan(base) else serie


# ────────────────────────────────────────────────────────────────────────────
# 1. NAFTA — precio súper promedio mensual en Capital Federal
# ────────────────────────────────────────────────────────────────────────────
print("Procesando NAFTA (772 MB en chunks)...")
acc = []
# idproducto==2 es "Nafta (súper) entre 92 y 95 Ron" (evita problemas de encoding del nombre)
cols = ["provincia", "idproducto", "precio", "anio", "mes"]
for chunk in pd.read_csv(CTX / "nafta_historico.csv", usecols=cols, chunksize=500_000):
    c = chunk[(chunk["provincia"] == "CAPITAL FEDERAL") &
              (chunk["idproducto"] == 2)]
    if len(c):
        acc.append(c[["anio", "mes", "precio"]])
naf = pd.concat(acc, ignore_index=True)
naf["precio"] = pd.to_numeric(naf["precio"], errors="coerce")
naf = naf[(naf["anio"] >= 2019) & (naf["anio"] <= 2025)]
naf_m = naf.groupby(["anio", "mes"])["precio"].mean()
naf_m.index = pd.to_datetime([f"{a}-{m:02d}-01" for a, m in naf_m.index])
naf_m = naf_m.sort_index()
nafta = pd.DataFrame({"nafta_super": naf_m, "nafta_idx": idx_base2019(naf_m)})
print(f"  Nafta: {len(nafta)} meses, {nafta.index.min():%Y-%m} a {nafta.index.max():%Y-%m}")


# ────────────────────────────────────────────────────────────────────────────
# 2. SUBE — transacciones diarias AMBA, agregadas a mensual
# ────────────────────────────────────────────────────────────────────────────
print("Procesando SUBE (2020-2025)...")
sube_daily = []
for f in sorted(glob.glob(str(CTX / "sube_*.csv"))):
    df = pd.read_csv(f, usecols=["DIA_TRANSPORTE", "AMBA", "CANTIDAD"])
    df = df[df["AMBA"].astype(str).str.upper().isin(["SI", "SÍ", "AMBA", "1", "TRUE"])]
    if df.empty:  # fallback: sin filtro AMBA, todo
        df = pd.read_csv(f, usecols=["DIA_TRANSPORTE", "CANTIDAD"])
    g = df.groupby("DIA_TRANSPORTE")["CANTIDAD"].sum()
    sube_daily.append(g)
sube_s = pd.concat(sube_daily)
sube_s.index = pd.to_datetime(sube_s.index, errors="coerce")
sube_s = sube_s[sube_s.index.notna()].sort_index()
sube_m = sube_s.resample("MS").sum()
sube_m = sube_m[(sube_m.index.year >= 2020) & (sube_m.index.year <= 2025)]
# Guardar también la serie diaria para anotaciones de saltos tarifarios
sube_s.rename("sube_usos").reset_index().rename(columns={"index": "fecha"}) \
    .to_csv(OUT / "sube_diario.csv", index=False)
sube = pd.DataFrame({"sube_usos": sube_m})
print(f"  SUBE: {len(sube)} meses (no hay 2019 → sin índice base)")


# ────────────────────────────────────────────────────────────────────────────
# 3. GOOGLE MOBILITY — CABA (ciudad), promedio mensual
# ────────────────────────────────────────────────────────────────────────────
print("Procesando Google Mobility (CABA)...")
mob_cols = {
    "workplaces_percent_change_from_baseline": "mob_trabajo",
    "transit_stations_percent_change_from_baseline": "mob_transporte",
    "residential_percent_change_from_baseline": "mob_hogar",
}
mob_acc = []
for f in sorted(glob.glob(str(CTX / "20*_AR_mobility.csv"))):
    df = pd.read_csv(f, usecols=["sub_region_1", "sub_region_2", "date", *mob_cols])
    caba = df[(df["sub_region_1"] == "Buenos Aires") & (df["sub_region_2"].isna())]
    mob_acc.append(caba)
mob = pd.concat(mob_acc, ignore_index=True)
mob["date"] = pd.to_datetime(mob["date"])
mob = mob.rename(columns=mob_cols).set_index("date")[list(mob_cols.values())]
mob_m = mob.resample("MS").mean()
print(f"  Mobility: {len(mob_m)} meses, {mob_m.index.min():%Y-%m} a {mob_m.index.max():%Y-%m}")


# ────────────────────────────────────────────────────────────────────────────
# 4. SINIESTROS VIALES — conteo mensual de víctimas y mortales (CABA)
# ────────────────────────────────────────────────────────────────────────────
print("Procesando siniestros viales...")
sin = pd.read_excel(CTX / "siniestros_hechos.xlsx", sheet_name="HECHOS")
sin["fecha_siniestro"] = pd.to_datetime(sin["fecha_siniestro"], errors="coerce")
sin = sin[sin["fecha_siniestro"].notna()]
for col in ["numero_total_de_victimas", "numero_victimas_mortal_siniestro"]:
    sin[col] = pd.to_numeric(sin[col], errors="coerce").fillna(0)
sin_m = sin.set_index("fecha_siniestro").resample("MS").agg(
    hechos=("id_siniestro", "count"),
    victimas=("numero_total_de_victimas", "sum"),
    mortales=("numero_victimas_mortal_siniestro", "sum"),
)
sin_m = sin_m[(sin_m.index.year >= 2019) & (sin_m.index.year <= 2025)]
sin_m["victimas_idx"] = idx_base2019(sin_m["victimas"])
print(f"  Siniestros: {len(sin_m)} meses, {int(sin_m['victimas'].sum())} víctimas totales")


# ────────────────────────────────────────────────────────────────────────────
# 5. FERIADOS — unificar nager.at (2019-2020) + argentinadatos (2021-2025)
# ────────────────────────────────────────────────────────────────────────────
print("Procesando feriados...")
fer = []
for y in range(2019, 2026):
    data = json.load(open(CTX / f"feriados_{y}.json", encoding="utf-8"))
    for d in data:
        if "date" in d:           # formato nager.at
            fer.append({"fecha": d["date"], "nombre": d.get("localName", d.get("name"))})
        elif "fecha" in d:        # formato argentinadatos
            fer.append({"fecha": d["fecha"], "nombre": d.get("nombre"), "tipo": d.get("tipo")})
feriados = pd.DataFrame(fer)
feriados["fecha"] = pd.to_datetime(feriados["fecha"])
feriados = feriados.sort_values("fecha").drop_duplicates("fecha")
feriados.to_csv(OUT / "feriados.csv", index=False)
print(f"  Feriados: {len(feriados)} fechas")


# ────────────────────────────────────────────────────────────────────────────
# 6. MUNDIAL 2022 — fechas/horarios de los 7 partidos de Argentina (UTC-3)
# ────────────────────────────────────────────────────────────────────────────
mundial = pd.DataFrame([
    ("2022-11-22", "07:00", "Argentina 1–2 Arabia Saudita"),
    ("2022-11-26", "16:00", "Argentina 2–0 México"),
    ("2022-11-30", "16:00", "Polonia 0–2 Argentina"),
    ("2022-12-03", "16:00", "Argentina 2–1 Australia (8vos)"),
    ("2022-12-09", "16:00", "Países Bajos 2–2 Argentina (4tos, pen)"),
    ("2022-12-13", "16:00", "Argentina 3–0 Croacia (semi)"),
    ("2022-12-18", "12:00", "Argentina 3–3 Francia (FINAL, pen)"),
], columns=["fecha", "hora", "partido"])
mundial.to_csv(OUT / "mundial_2022.csv", index=False)


# ────────────────────────────────────────────────────────────────────────────
# Ensamble: tabla mensual maestra
# ────────────────────────────────────────────────────────────────────────────
maestro = pd.concat([
    nafta,
    sube,
    mob_m,
    sin_m[["hechos", "victimas", "mortales", "victimas_idx"]],
], axis=1).sort_index()
maestro = maestro[(maestro.index.year >= 2019) & (maestro.index.year <= 2025)]
maestro.index.name = "mes"
maestro.to_csv(OUT / "contexto_mensual.csv")
print(f"\nMaestro mensual: {maestro.shape[0]} meses × {maestro.shape[1]} columnas")
print("Columnas:", list(maestro.columns))
print("Guardado en", OUT / "contexto_mensual.csv")
