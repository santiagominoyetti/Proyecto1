"""
Unifica los CSVs de flujo vehicular por radares (2019–2025).

Columnas de salida:
  fecha, hora, anio, autopista_nombre, disp_nombre,
  disp_ubicacion, seccion_sentido, lat, long, cantidad
"""

import csv
import re
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\santi\OneDrive\Documents\itba\Proyecto1")
OUTPUT = BASE / "flujo-vehicular-unificado.csv"
YEARS = list(range(2019, 2026))


def parse_date(raw: str) -> str:
    """Normaliza cualquier formato de fecha a YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError(f"Fecha no reconocida: {raw!r}")


def fix_coord(raw: str) -> str:
    """
    Convierte coordenadas al formato float con punto decimal.
    Casos: '', '-34,56336', '-34.56336', '-58.459.669.999.999.900'
    """
    raw = raw.strip()
    if not raw:
        return ""
    # Reemplaza coma decimal por punto
    raw = raw.replace(",", ".")
    # Corrige longitudes/latitudes con múltiples puntos:
    # '-58.459.669.999.999.900' → quitar puntos sobrantes preservando el signo
    # El primer punto (separador decimal real) se queda; el resto se eliminan
    if raw.count(".") > 1:
        # Reconstruir: mantener signo + dígitos + primer punto + resto sin puntos
        negative = raw.startswith("-")
        digits = raw.lstrip("-").replace(".", "")
        # Reintroducimos el punto en la posición correcta (2 dígitos enteros para coords arg)
        # Determinamos cuántos dígitos enteros hay buscando cuándo la secuencia tiene sentido
        # Para longitudes ~-58 o latitudes ~-34: 2 dígitos enteros
        # Simplemente tomamos los primeros 2 dígitos como parte entera
        int_digits = 2
        reconstructed = digits[:int_digits] + "." + digits[int_digits:]
        raw = ("-" if negative else "") + reconstructed
    try:
        float(raw)
        return raw
    except ValueError:
        return ""


def safe_int(raw: str) -> str:
    raw = raw.strip()
    try:
        return str(int(float(raw)))
    except (ValueError, TypeError):
        return ""


OUTFIELDS = [
    "fecha", "hora", "anio",
    "autopista_nombre", "disp_nombre", "disp_ubicacion",
    "seccion_sentido", "lat", "long", "cantidad",
]


def process_2019_2020(year: int, rows_written: list) -> int:
    """Formato: comma-separated, headers: fecha,hora,autopista_nombre,disp_nombre,
    disp_ubicacion,seccion_sentido,lat,long,cantidad"""
    path = BASE / f"flujo-vehicular-por-radares-{year}.csv"
    count = 0
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fecha = parse_date(row["fecha"])
            rows_written.append({
                "fecha": fecha,
                "hora": safe_int(row["hora"]),
                "anio": str(year),
                "autopista_nombre": row["autopista_nombre"].strip(),
                "disp_nombre": row["disp_nombre"].strip(),
                "disp_ubicacion": row["disp_ubicacion"].strip().replace(",", "."),
                "seccion_sentido": row["seccion_sentido"].strip(),
                "lat": fix_coord(row["lat"]),
                "long": fix_coord(row["long"]),
                "cantidad": safe_int(row["cantidad"]),
            })
            count += 1
    return count


def process_semicolon(year: int, rows_written: list) -> int:
    """
    Formato semicolon 2021-2025.
    Columnas (con nombres sucios): fecha;hora;aut_nombre;disp_nombre;
    disp_ubicacion;seccion_sentido;lat;lng;cantidad  [+extras en 2021]
    """
    path = BASE / f"flujo-vehicular-por-radares-{year}.csv"
    count = 0
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        # Normalizamos índices por posición (los headers son sucios pero el orden es fijo)
        # Pos: 0=fecha, 1=hora, 2=aut_nombre, 3=disp_nombre, 4=disp_ubicacion,
        #      5=seccion_sentido, 6=lat, 7=lng, 8=cantidad
        IDX = {"fecha": 0, "hora": 1, "aut": 2, "disp_n": 3, "disp_u": 4,
               "sentido": 5, "lat": 6, "lng": 7, "cant": 8}

        for row in reader:
            if len(row) < 9:
                continue
            try:
                fecha = parse_date(row[IDX["fecha"]])
            except ValueError:
                continue
            rows_written.append({
                "fecha": fecha,
                "hora": safe_int(row[IDX["hora"]]),
                "anio": str(year),
                "autopista_nombre": row[IDX["aut"]].strip(),
                "disp_nombre": row[IDX["disp_n"]].strip(),
                "disp_ubicacion": row[IDX["disp_u"]].strip().replace(",", "."),
                "seccion_sentido": row[IDX["sentido"]].strip(),
                "lat": fix_coord(row[IDX["lat"]]),
                "long": fix_coord(row[IDX["lng"]]),
                "cantidad": safe_int(row[IDX["cant"]]),
            })
            count += 1
    return count


def main():
    all_rows = []
    for year in YEARS:
        if year in (2019, 2020):
            n = process_2019_2020(year, all_rows)
        else:
            n = process_semicolon(year, all_rows)
        print(f"{year}: {n:,} filas procesadas")

    print(f"\nTotal: {len(all_rows):,} filas — escribiendo {OUTPUT.name} ...")
    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTFIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    print("Listo.")


if __name__ == "__main__":
    main()
