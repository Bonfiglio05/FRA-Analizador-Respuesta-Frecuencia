"""Analisis de la curva de Bode: frecuencias de corte, ancho de banda y Q."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


def reference_level(dbs: list[float], reliable: list[bool] | None = None) -> float:
    """Nivel de la meseta / pico para medir los -3 dB.

    Mediana del 15 % de puntos mas altos entre los confiables (al menos 3): no depende de
    un unico punto aislado, p. ej. los ~+0.4 dB que el instrumento lee a 100 Hz en un DUT plano.
    """
    values = list(dbs) if reliable is None else [d for d, ok in zip(dbs, reliable) if ok]
    if not values:
        values = list(dbs)
    values.sort(reverse=True)
    top = values[: max(3, int(round(0.15 * len(values))))]
    top.sort()
    return top[len(top) // 2]


def find_cutoff_frequencies(freqs: list[float], dbs: list[float], reference: float | None = None) -> list[float]:
    """Frecuencias donde la magnitud cruza (referencia - 3 dB), interpolando en escala log.

    Sin `reference` usa el maximo del barrido (comportamiento original)."""
    if len(freqs) < 2:
        return []

    threshold = (max(dbs) if reference is None else reference) - 3.0
    crossings: list[float] = []

    for i in range(1, len(freqs)):
        d0, d1 = dbs[i - 1], dbs[i]
        f0, f1 = freqs[i - 1], freqs[i]

        if d0 == threshold:
            crossings.append(f0)
        elif (d0 - threshold) * (d1 - threshold) < 0:
            frac = (threshold - d0) / (d1 - d0)
            log_f = math.log10(f0) + frac * (math.log10(f1) - math.log10(f0))
            crossings.append(10**log_f)

    return crossings


def cutoff_is_reliable(freqs: list[float], reliable: list[bool], freq: float) -> bool:
    """True si el punto medido mas cercano a `freq` y sus vecinos son confiables."""
    if not freqs or not reliable or freq <= 0:
        return True
    idx = min(range(len(freqs)), key=lambda i: abs(math.log10(freqs[i]) - math.log10(freq)))
    return all(reliable[max(0, idx - 1): idx + 2])


@dataclass
class BandwidthResult:
    f_low: float
    f_high: float
    bandwidth_hz: float
    f_center: float
    q: float


def compute_bandwidth(cutoffs: list[float]) -> Optional[BandwidthResult]:
    """Ancho de banda y Q a partir de exactamente dos frecuencias de corte."""
    if len(cutoffs) != 2:
        return None

    f_low, f_high = min(cutoffs), max(cutoffs)
    bandwidth = f_high - f_low
    f_center = math.sqrt(f_low * f_high)
    q = f_center / bandwidth if bandwidth > 0 else math.inf
    return BandwidthResult(f_low, f_high, bandwidth, f_center, q)
