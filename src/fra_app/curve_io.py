"""Lectura y escritura de curvas CSV (columnas freq_hz, db, phase_deg y, opcional, confiable).

Es el formato de "Exportar datos (CSV)": los datos que guarda ya estan reparados y corregidos, por lo que al
abrirlos se muestran tal cual, sin volver a procesarlos.
"""

from __future__ import annotations

import csv

HEADER = ["freq_hz", "db", "phase_deg", "confiable"]


def save_measurement_csv(path: str, freqs: list[float], dbs: list[float], phases: list[float],
                         reliable: list[bool] | None = None) -> None:
    """confiable = 0 marca los puntos poco confiables (ver phase_repair.reliability)."""
    if not reliable or len(reliable) != len(freqs):
        reliable = [True] * len(freqs)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows((fr, d, p, int(r)) for fr, d, p, r in zip(freqs, dbs, phases, reliable))


def load_measurement_csv(path: str) -> tuple[list[float], list[float], list[float], list[bool] | None]:
    """Devuelve (frecuencias, dB, fase, confiable) ordenadas por frecuencia.

    `confiable` es None si el archivo no tiene esa columna (CSV de versiones anteriores).
    Lanza ValueError con un mensaje legible si el archivo no sirve.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            has_flag = "confiable" in (reader.fieldnames or [])
            rows = [(float(r["freq_hz"]), float(r["db"]), float(r["phase_deg"]),
                     bool(int(float(r["confiable"]))) if has_flag else True) for r in reader]
    except (KeyError, TypeError, ValueError):
        raise ValueError("El archivo no es una curva valida: hacen falta las columnas freq_hz, db y phase_deg "
                         "con valores numericos.") from None
    rows = sorted(p for p in rows if p[0] > 0)
    if len(rows) < 2:
        raise ValueError("El archivo tiene menos de 2 puntos validos.")
    reliable = [p[3] for p in rows] if has_flag else None
    return [p[0] for p in rows], [p[1] for p in rows], [p[2] for p in rows], reliable


def load_curve_csv(path: str) -> tuple[list[float], list[float], list[float]]:
    """Solo (frecuencias, dB, fase): para usar el archivo como curva de referencia."""
    freqs, dbs, phases, _ = load_measurement_csv(path)
    return freqs, dbs, phases
