"""Calibracion de puente por barrido completo ("thru").

El firmware calibra a una sola frecuencia (1 MHz): ahi fase y dB quedan en 0 con el DUT
puenteado, pero en el resto del rango el propio instrumento deja errores fijos que se
miden con el puente puesto: un residuo de ~+2 grados de fase a media frecuencia, un
retardo de camino de ~6 ns (-23 grados a 10 MHz) y ~+0.3 dB a 100-200 Hz. Ademas, el
retardo de los cables propios del montaje.

Este modulo guarda el barrido del puente y lo resta de las mediciones posteriores
(magnitud y fase), llevando el plano de referencia a los bornes del DUT, como la
calibracion "thru" de un analizador vectorial. No corrige el error que depende del nivel
de la senal (DUT que atenua o amplifica): eso no se mide con un puente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

THRU_START_HZ = 100.0
THRU_STOP_HZ = 10_000_000.0
THRU_POINTS = 150


def wrap180(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


@dataclass
class ThruProfile:
    freqs: list[float]
    dbs: list[float]
    phases: list[float]

    def __post_init__(self) -> None:
        order = sorted(range(len(self.freqs)), key=self.freqs.__getitem__)
        self.freqs = [self.freqs[i] for i in order]
        self.dbs = [self.dbs[i] for i in order]
        self.phases = [self.phases[i] for i in order]
        self._logf = [math.log10(f) for f in self.freqs]

    def correction_at(self, freq_hz: float) -> tuple[float, float]:
        """(dB, fase en grados) que midio el puente a esa frecuencia (interpolacion en log f)."""
        n = len(self.freqs)
        if n == 0:
            return 0.0, 0.0
        x = math.log10(max(freq_hz, 1e-9))
        if x <= self._logf[0]:
            return self.dbs[0], self.phases[0]
        if x >= self._logf[-1]:
            return self.dbs[-1], self.phases[-1]
        lo, hi = 0, n - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self._logf[mid] <= x:
                lo = mid
            else:
                hi = mid
        t = (x - self._logf[lo]) / (self._logf[hi] - self._logf[lo])
        return (self.dbs[lo] + t * (self.dbs[hi] - self.dbs[lo]),
                self.phases[lo] + t * (self.phases[hi] - self.phases[lo]))

    def apply(self, freqs: list[float], dbs: list[float], phases: list[float]) -> tuple[list[float], list[float]]:
        out_db, out_ph = [], []
        for f, d, p in zip(freqs, dbs, phases):
            cd, cp = self.correction_at(f)
            out_db.append(d - cd)
            out_ph.append(wrap180(p - cp))
        return out_db, out_ph

    def summary(self) -> str:
        if not self.freqs:
            return "perfil vacio"
        return (f"{len(self.freqs)} puntos, {self.freqs[0]:.0f} Hz - {self.freqs[-1] / 1e6:.0f} MHz; "
                f"fase {min(self.phases):+.1f}° a {max(self.phases):+.1f}°, magnitud {min(self.dbs):+.2f} a {max(self.dbs):+.2f} dB")
