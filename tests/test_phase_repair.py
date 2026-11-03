"""Pruebas del modulo phase_repair (sin dependencias externas: python -m unittest)."""

import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fra_app import phase_repair as pr  # noqa: E402


def sign_agreement(true, got, dbs, min_db=-22.0, min_phase=20.0):
    idx = [i for i in range(len(true)) if abs(true[i]) > min_phase and dbs[i] > min_db]
    ok = sum(1 for i in idx if (true[i] > 0) == (got[i] > 0))
    return 100.0 * ok / len(idx)


def firmware_v13_rule(phases, limit=100.0, min_mag=60.0):
    out = []
    for p in phases:
        if out:
            prev = out[-1]
            d = abs(pr.wrap180(p - prev))
            if d > limit and abs(p) > min_mag and abs(prev) > min_mag and abs(pr.wrap180(-p - prev)) < d:
                p = -p
        out.append(p)
    return out


def notch_case(seed, n=200):
    """Notch ideal: la fase baja de -10 a -85 hasta el notch, salta a +85 y vuelve a bajar a +30."""
    rng = random.Random(seed)
    k = n // 2
    dbs, true = [], []
    for i in range(n):
        x = i / (n - 1)
        if i < k:
            true.append(-10.0 - 75.0 * (i / k))
            dbs.append(-2.0 - 24.5 * (i / k) ** 2)
        else:
            true.append(85.0 - 55.0 * ((i - k) / (n - k)))
            dbs.append(-26.5 + 24.5 * (((i - k) / (n - k)) ** 0.5))
    dbs = [max(d, -26.5) for d in dbs]
    raw = list(true)
    for i in range(n):
        if dbs[i] < -22.0:  # en el piso el instrumento no distingue el signo
            raw[i] = abs(raw[i]) * rng.choice([-1.0, 1.0])
    candidates = [i for i in range(n) if abs(true[i]) > 60 and dbs[i] > -22.0]
    for i in rng.sample(candidates, max(1, int(0.06 * len(candidates)))):
        raw[i] = -raw[i]
    return dbs, true, raw


def bandpass_case(seed, n=400):
    """Pasabanda: la fase baja de +80 a -80 con un maximo de magnitud en el medio; bloque de signos falsos."""
    rng = random.Random(seed)
    true = [80.0 - 160.0 * i / (n - 1) for i in range(n)]
    dbs = [-3.0 - 18.0 * abs(i / (n - 1) - 0.5) ** 1.0 * 2.0 for i in range(n)]
    raw = list(true)
    candidates = [i for i in range(n) if abs(true[i]) > 60 and dbs[i] > -20.0]
    k = rng.randint(3, 10)
    start = rng.randint(0, len(candidates) - k - 1)
    block = candidates[start:start + k]
    for i in block:
        raw[i] = -raw[i]
    others = [i for i in candidates if i not in block]
    for i in rng.sample(others, max(1, int(0.05 * len(others)))):
        raw[i] = -raw[i]
    return dbs, true, raw


class RepairTests(unittest.TestCase):
    def test_notch_real_jump_is_kept(self):
        for seed in range(20):
            dbs, true, raw = notch_case(seed)
            got = pr.repair_phase(dbs, raw)
            self.assertGreaterEqual(sign_agreement(true, got, dbs), 99.0, f"semilla {seed}")

    def test_current_firmware_rule_breaks_notch(self):
        """Documenta el defecto de la regla secuencial de la v1.3."""
        dbs, true, raw = notch_case(1)
        self.assertLess(sign_agreement(true, firmware_v13_rule(raw), dbs), 90.0)

    def test_false_sign_blocks_without_dip_are_corrected(self):
        scores = []
        for seed in range(40):
            dbs, true, raw = bandpass_case(seed)
            got = pr.repair_phase(dbs, raw)
            scores.append(sign_agreement(true, got, dbs, min_db=-20.0))
        self.assertGreaterEqual(min(scores), 97.0)
        self.assertGreaterEqual(sum(scores) / len(scores), 99.0)

    def test_phase_near_plus_minus_180_is_not_disturbed(self):
        # inversor: fase ~ +-180 con el pliegue normal
        phases = [-179.3, -179.1, -178.9, -179.5, 179.9, 179.6, 179.2, 178.8, 178.0, 177.0, 175.0, 170.0]
        dbs = [7.2] * len(phases)
        got = pr.repair_phase(dbs, phases)
        for a, b in zip(phases, got):
            self.assertLess(abs(pr.wrap180(a - b)), 0.01)

    def test_short_input_returned_unchanged(self):
        self.assertEqual(pr.repair_phase([0.0, 0.0], [10.0, -10.0]), [10.0, -10.0])

    def test_reliability_flags(self):
        freqs = [100.0, 500.0, 1000.0, 1e4, 1e5, 1e6]
        dbs = [0.4, -8.0, -3.0, -19.0, -21.0, -24.0]
        self.assertEqual(pr.reliability(freqs, dbs), [True, False, True, True, False, False])


if __name__ == "__main__":
    unittest.main()
