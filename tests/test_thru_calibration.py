"""Pruebas del modulo thru_calibration (python -m unittest)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fra_app.thru_calibration import ThruProfile, wrap180  # noqa: E402


def logspace(f0, f1, n):
    return [f0 * (f1 / f0) ** (i / (n - 1)) for i in range(n)]


def instrument_error_phase(f, offset=1.9, delay_ns=6.4):
    """Error de fase del puente: residuo fijo + retardo, nulo a 1 MHz como deja la calibracion del firmware."""
    return offset - 360.0 * (f - 1e6) * delay_ns * 1e-9


class ThruTests(unittest.TestCase):
    def setUp(self):
        self.f = logspace(100.0, 1e7, 150)
        self.err_ph = [instrument_error_phase(f) for f in self.f]
        self.err_db = [0.3 if f < 200 else 0.0 for f in self.f]
        self.profile = ThruProfile(self.f, self.err_db, self.err_ph)

    def test_corrects_a_measurement_on_a_different_grid(self):
        # DUT pasa-bajos ideal medido con el error del instrumento sumado, en otra grilla de frecuencias
        fc = 2800.0
        grid = logspace(150.0, 8e6, 97)
        true_db = [-10 * math.log10(1 + (f / fc) ** 2) for f in grid]
        true_ph = [-math.degrees(math.atan(f / fc)) for f in grid]
        meas_db = [d + (0.3 if f < 200 else 0.0) for d, f in zip(true_db, grid)]
        meas_ph = [wrap180(p + instrument_error_phase(f)) for p, f in zip(true_ph, grid)]
        cdb, cph = self.profile.apply(grid, meas_db, meas_ph)
        worst_db = max(abs(a - b) for a, b in zip(cdb, true_db))
        worst_ph = max(abs(wrap180(a - b)) for a, b in zip(cph, true_ph))
        self.assertLess(worst_db, 0.15)
        self.assertLess(worst_ph, 0.8)
        # sin la correccion el error de fase llegaba a mas de 10 grados a 8 MHz
        self.assertGreater(max(abs(wrap180(a - b)) for a, b in zip(meas_ph, true_ph)), 10.0)

    def test_clamps_outside_the_profile_range(self):
        lo = self.profile.correction_at(10.0)
        hi = self.profile.correction_at(5e7)
        self.assertEqual(lo, (self.profile.dbs[0], self.profile.phases[0]))
        self.assertEqual(hi, (self.profile.dbs[-1], self.profile.phases[-1]))

    def test_unsorted_input_is_sorted(self):
        p = ThruProfile([1e3, 1e2, 1e4], [0.1, 0.2, 0.3], [1.0, 2.0, 3.0])
        self.assertEqual(p.freqs, [1e2, 1e3, 1e4])
        self.assertEqual(p.phases, [2.0, 1.0, 3.0])

    def test_empty_profile_is_neutral(self):
        p = ThruProfile([], [], [])
        self.assertEqual(p.correction_at(1e3), (0.0, 0.0))

    def test_phase_correction_wraps_around_180(self):
        p = ThruProfile([1e2, 1e7], [0.0, 0.0], [2.0, 2.0])
        _, ph = p.apply([1e3], [0.0], [-179.0])
        self.assertAlmostEqual(ph[0], 179.0, places=6)


if __name__ == "__main__":
    unittest.main()
