"""Pruebas de analysis: frecuencias de corte y su confiabilidad."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fra_app import analysis  # noqa: E402


def log_grid(f0=100.0, f1=1e7, n=100):
    return [f0 * (f1 / f0) ** (i / (n - 1)) for i in range(n)]


class CutoffTests(unittest.TestCase):
    def test_lowpass_cutoff_is_found_against_the_plateau(self):
        f = log_grid()
        db = [-10 * math.log10(1 + (x / 1800.0) ** 2) + 0.4 for x in f]     # meseta desplazada +0,4 dB
        ref = analysis.reference_level(db, [d > -20 for d in db])
        (fc,) = analysis.find_cutoff_frequencies(f, db, reference=ref)
        self.assertAlmostEqual(fc, 1800.0, delta=60.0)

    def test_cutoff_reliability_follows_the_neighbouring_points(self):
        f = log_grid()
        reliable = [x < 5000 for x in f]
        self.assertTrue(analysis.cutoff_is_reliable(f, reliable, 1000.0))
        self.assertFalse(analysis.cutoff_is_reliable(f, reliable, 5000.0))
        self.assertFalse(analysis.cutoff_is_reliable(f, reliable, 20000.0))


if __name__ == "__main__":
    unittest.main()
