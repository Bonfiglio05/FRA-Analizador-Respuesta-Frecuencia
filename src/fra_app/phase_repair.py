"""Reparacion del signo de la fase y marcado de puntos poco confiables.

El instrumento mide |fase| con buena exactitud, pero el SIGNO se decide con una
segunda lectura que se vuelve ambigua cerca de +-90 grados y cuando la senal esta
cerca del piso del detector (~ -25 dB). Un error de signo es un salto de 2*|fase|
entre puntos vecinos. Un salto de fase REAL de 180 grados solo puede ocurrir en un
cero de transmision (un minimo profundo de la magnitud, p. ej. un notch).

Por eso el signo se elige sobre el barrido completo (Viterbi de dos estados por punto):
se busca el camino mas suave posible, penalizando apartarse del signo crudo, y los
saltos se "abaratan" casi a cero en los minimos de magnitud y en el piso del detector,
donde ahi si se confia en el signo crudo. Funciona sobre el barrido ya terminado; el
firmware (v1.4 en adelante) entrega la fase cruda.
"""

from __future__ import annotations

FLOOR_DB = -22.0        # por debajo de este nivel la lectura esta en el piso del detector
UNRELIABLE_DB = -20.0   # por debajo la fase (y la magnitud) dejan de ser confiables
LF_LIMIT_HZ = 700.0     # por debajo, con nivel distinto del de referencia, hay error de baja frecuencia
LF_LEVEL_DB = 3.0       # "nivel distinto": |magnitud| mayor que esto
DIP_DEPTH_DB = 8.0      # un minimo cuenta como cero de transmision si hay >= 8 dB de cada lado
DIP_WINDOW = 12         # puntos a cada lado para buscar ese minimo

KAPPA = 25.0            # costo (grados) de apartarse del signo crudo
LAMBDA = 1.0            # costo por grado de salto entre puntos vecinos
LAMBDA_FREE = 0.03      # idem, en minimos de magnitud / piso (alli el salto real es posible)


def wrap180(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def free_flags(dbs: list[float]) -> list[bool]:
    """Puntos donde se permite un salto real de fase: piso del detector o minimo profundo de |H|."""
    n = len(dbs)
    free = [db < FLOOR_DB for db in dbs]
    for i in range(n):
        lo, hi = max(0, i - DIP_WINDOW), min(n, i + DIP_WINDOW + 1)
        if dbs[i] > min(dbs[lo:hi]) + 1e-9:
            continue
        left = max(dbs[lo:i], default=dbs[i])
        right = max(dbs[i + 1:hi], default=dbs[i])
        if left - dbs[i] >= DIP_DEPTH_DB and right - dbs[i] >= DIP_DEPTH_DB:
            for j in range(max(0, i - 2), min(n, i + 3)):
                free[j] = True
    return free


def repair_phase(dbs: list[float], phases: list[float]) -> list[float]:
    """Devuelve las fases con el signo reparado (mismo largo que la entrada)."""
    n = len(phases)
    if n < 3 or len(dbs) != n:
        return list(phases)

    free = free_flags(dbs)
    mag = [abs(p) for p in phases]
    # estado 0: +|fase|, estado 1: -|fase|
    cand = [(m, -m) for m in mag]

    unary = []
    for i in range(n):
        weight = min(1.0, mag[i] / 60.0)  # cerca de 0 grados el signo importa poco
        raw_state = 0 if phases[i] >= 0.0 else 1
        cost = [0.0, 0.0]
        cost[1 - raw_state] = KAPPA * weight
        unary.append(cost)

    total = [list(unary[0])]
    back = [[0, 0]]
    for i in range(1, n):
        lam = LAMBDA_FREE if (free[i] or free[i - 1]) else LAMBDA
        row = [0.0, 0.0]
        brow = [0, 0]
        for s in (0, 1):
            best_cost, best_prev = None, 0
            for r in (0, 1):
                c = total[i - 1][r] + lam * abs(wrap180(cand[i][s] - cand[i - 1][r])) + unary[i][s]
                if best_cost is None or c < best_cost:
                    best_cost, best_prev = c, r
            row[s], brow[s] = best_cost, best_prev
        total.append(row)
        back.append(brow)

    state = 0 if total[-1][0] <= total[-1][1] else 1
    out = [0.0] * n
    for i in range(n - 1, -1, -1):
        out[i] = wrap180(cand[i][state])
        state = back[i][state]
    return out


REASON_FLOOR = "floor"
REASON_LF = "lf"

REASON_TEXT = {
    REASON_FLOOR: "Nivel bajo: por debajo de −20 dB el detector se acerca a su piso (≈ −25 dB) y la fase "
                  "deja de ser confiable.",
    REASON_LF: "Baja frecuencia con atenuación: por debajo de 700 Hz, con más de 3 dB de diferencia de nivel, "
               "el instrumento la exagera (error de décimas de dB y unos grados).",
}


def unreliable_reason(freq: float, db: float) -> str | None:
    """Motivo por el que el punto no es confiable (REASON_FLOOR / REASON_LF), o None si lo es."""
    if db < UNRELIABLE_DB:
        return REASON_FLOOR
    if freq < LF_LIMIT_HZ and abs(db) > LF_LEVEL_DB:
        return REASON_LF
    return None


def reliability(freqs: list[float], dbs: list[float]) -> list[bool]:
    """True para los puntos confiables.

    No confiable: magnitud por debajo de UNRELIABLE_DB (piso del detector) o, a baja
    frecuencia, magnitud que se aparta mas de LF_LEVEL_DB del nivel de referencia (el
    instrumento exagera la diferencia de nivel entre sus dos canales por debajo de ~700 Hz).
    """
    return [unreliable_reason(f, db) is None for f, db in zip(freqs, dbs)]
