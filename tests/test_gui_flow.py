"""Prueba del flujo de calibracion unica, barrido y autodeteccion con un backend falso (sin hardware ni pantalla)."""

import math
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from fra_app.gui.main_window import MainWindow  # noqa: E402
from fra_app.serial_backend import SerialBackend  # noqa: E402

_app = QApplication.instance() or QApplication([])

# la configuracion del usuario (p. ej. "sombrear zona poco confiable") no debe influir en las pruebas ni ensuciarse
import os as _os  # noqa: E402
import tempfile  # noqa: E402

import fra_app.gui.main_window as _mw  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402

_settings_file = _os.path.join(tempfile.mkdtemp(prefix="fra_test_settings_"), "fra.ini")
_mw._open_settings = lambda: QSettings(_settings_file, QSettings.Format.IniFormat)
DELAY_NS = 6.4
OFFSET_DEG = 1.9


def instrument_phase_error(f):
    """Error de fase que el instrumento suma aun con el puente (nulo a 1 MHz, como deja CAL)."""
    return OFFSET_DEG - 360.0 * (f - 1e6) * DELAY_NS * 1e-9


def lowpass(f, fc=2800.0):
    return -10 * math.log10(1 + (f / fc) ** 2), -math.degrees(math.atan(f / fc))


class FakeInstrument(SerialBackend):
    """Emula el ESP32: responde a CAL y START emitiendo las mismas senales que el backend real."""

    def __init__(self):
        super().__init__("FAKE")
        self.dut = "bridge"          # "bridge" o "lowpass"
        self.calls = []
        self.fail_cal = False

    def run(self):  # no abre ningun puerto
        pass

    def stop(self):
        pass

    def send_calibrate(self):
        self.calls.append("CAL")
        if self.fail_cal:
            self.error.emit("Calibracion fallida: excursion de fase baja (DUT puenteado?)")
        else:
            self.calibration_done.emit(0.0, -1.65)

    def send_stop(self):
        self.calls.append("STOP")

    def send_start(self, f0, f1, n, log):
        self.calls.append(("START", f0, f1, n, log))
        self.sweep_started.emit(n)
        for i in range(n):
            f = f0 * (f1 / f0) ** (i / (n - 1)) if log else f0 + (f1 - f0) * i / (n - 1)
            db, ph = (0.0, 0.0) if self.dut == "bridge" else lowpass(f)
            ph = ((ph + instrument_phase_error(f)) + 180.0) % 360.0 - 180.0
            self.data_point.emit(i, f, db, ph)
        self.sweep_done.emit()


def set_stop_mhz(win, mhz):
    win.f_stop.unit_combo.setCurrentText("MHz")
    win.f_stop.spin.setValue(mhz)


def make_window():
    win = MainWindow()
    fake = FakeInstrument()
    win._attach_backend(fake)
    win._set_connected_state(True)
    return win, fake


def lowpass_win():
    win, fake = make_window()
    win._on_calibrate_clicked()
    fake.dut = "lowpass"
    return win, fake


class GuiFlowTests(unittest.TestCase):
    def test_calibration_measures_the_bridge_and_corrects_a_later_sweep(self):
        win, fake = make_window()
        win._on_calibrate_clicked()
        self.assertEqual(fake.calls[0], "CAL")
        self.assertEqual(fake.calls[1][0], "START")
        self.assertTrue(win.calibrated)
        self.assertEqual(len(win.plot.freqs), 0, "el barrido del puente no debe dibujarse")
        self.assertTrue(win.thru_check.isEnabled() and win.thru_check.isChecked())
        self.assertTrue(win.calibrate_btn.isEnabled() and win.start_btn.isEnabled())
        self.assertIn("Calibrado", win.calibration_status.text())

        fake.dut = "lowpass"
        set_stop_mhz(win, 8.0)
        win._on_start_clicked()
        self.assertGreater(len(win.plot.freqs), 10)
        self.assertGreater(max(win.plot.freqs), 7e6)
        worst = 0.0
        # compara con la teoria en las frecuencias medidas
        for f, d, p in zip(win.plot.freqs, win.plot.dbs, win.plot.phases):
            _, ph_true = lowpass(f)
            if d > -20:
                worst = max(worst, abs((p - ph_true + 180) % 360 - 180))
        self.assertLess(worst, 1.0, "con la correccion de cero la fase debe coincidir con la teoria")

    def test_without_correction_the_instrument_error_is_visible(self):
        win, fake = lowpass_win()
        set_stop_mhz(win, 8.0)
        win.thru_check.setChecked(False)
        win._on_start_clicked()
        worst = 0.0
        for f, d, p in zip(win.plot.freqs, win.plot.dbs, win.plot.phases):
            _, ph_true = lowpass(f)
            if d > -20:
                worst = max(worst, abs((p - ph_true + 180) % 360 - 180))
        self.assertGreater(worst, 1.5)

    def test_toggle_reprocesses_current_plot(self):
        win, fake = lowpass_win()
        set_stop_mhz(win, 8.0)
        win._on_start_clicked()
        corrected = list(win.plot.phases)
        win.thru_check.setChecked(False)
        raw_view = list(win.plot.phases)
        self.assertIn("SIN correccion", win.calibration_status.text())
        win.thru_check.setChecked(True)
        again = list(win.plot.phases)
        self.assertNotEqual(corrected, raw_view)
        for a, b in zip(corrected, again):
            self.assertAlmostEqual(a, b, places=6)

    def test_measuring_without_calibration_asks_first(self):
        import fra_app.gui.main_window as mw
        win, fake = make_window()
        original = mw.QMessageBox.question
        try:
            mw.QMessageBox.question = staticmethod(lambda *a, **k: mw.QMessageBox.StandardButton.No)
            win._on_start_clicked()
            self.assertEqual(fake.calls, [], "si el usuario dice que no, no se mide")
            mw.QMessageBox.question = staticmethod(lambda *a, **k: mw.QMessageBox.StandardButton.Yes)
            win._on_start_clicked()
            self.assertEqual(fake.calls[0][0], "START")
        finally:
            mw.QMessageBox.question = original

    def test_failed_calibration_unblocks_the_buttons(self):
        win, fake = make_window()
        fake.fail_cal = True
        # QMessageBox.critical bloquearia la prueba: se reemplaza
        import fra_app.gui.main_window as mw
        original = mw.QMessageBox.critical
        mw.QMessageBox.critical = staticmethod(lambda *a, **k: None)
        try:
            win._on_calibrate_clicked()
        finally:
            mw.QMessageBox.critical = original
        self.assertFalse(win.calibrated)
        self.assertTrue(win.calibrate_btn.isEnabled() and win.start_btn.isEnabled())
        self.assertIn("fallida", win.calibration_status.text())

    def test_cutoffs_are_not_marked_until_the_user_asks(self):
        win, fake = lowpass_win()
        win._on_start_clicked()
        plot = win.plot
        self.assertTrue(plot.detect_btn.isEnabled())
        self.assertEqual(plot._cutoff_artists, [], "al terminar el barrido no se marca nada solo")
        self.assertIn("Detectar", plot.analysis_label.text())
        plot.detect_btn.click()
        self.assertTrue(plot._cutoff_artists)
        self.assertIn("2.799 kHz", plot.analysis_label.text())     # fc = 2,8 kHz del pasa-bajos de prueba
        # al activar/desactivar la correccion el analisis se actualiza solo (ya fue pedido)
        win.thru_check.setChecked(False)
        self.assertTrue(plot._cutoff_artists)
        # un barrido nuevo empieza sin marcas y con el boton apagado hasta que termine
        win.plot.clear()
        self.assertFalse(plot.detect_btn.isEnabled())
        self.assertEqual(plot._cutoff_artists, [])

    def test_detect_on_a_flat_response_says_there_is_no_cutoff(self):
        win, fake = make_window()
        win._on_calibrate_clicked()
        win._on_start_clicked()                                     # DUT puenteado: plano
        win.plot.detect_btn.click()
        self.assertIn("No se encontro", win.plot.analysis_label.text())
    def test_cursor_readout_has_one_colored_line_per_cursor_and_one_for_the_difference(self):
        win, fake = lowpass_win()
        win._on_start_clicked()
        plot = win.plot
        plot._set_cursor(0, 10)
        plot._set_cursor(1, 40)
        texts = [lab.text() for lab in plot.cursor_labels]
        self.assertTrue(texts[0].startswith("Cursor 1") and texts[1].startswith("Cursor 2"))
        self.assertTrue(texts[2].startswith("Diferencia"))
        styles = {lab.styleSheet().split("color:")[-1].strip(" ;") for lab in plot.cursor_labels}
        self.assertEqual(len(styles), 3, "cursor 1, cursor 2 y diferencia con tres colores distintos")
        plot.clear_cursors()
        self.assertTrue(plot.cursor_labels[0].text().startswith("Cursor 1:"))


class ViewOptionTests(unittest.TestCase):
    def sweep_window(self):
        win, fake = lowpass_win()
        win._on_start_clicked()          # 100 Hz - 100 kHz: el tramo bajo -20 dB queda marcado como poco confiable
        return win

    def test_shading_is_optional_and_covers_only_the_unreliable_tail(self):
        win = self.sweep_window()
        plot = win.plot
        self.assertEqual(plot._shade_artists, [], "por defecto no se sombrea nada")
        plot.set_shade_unreliable(True)
        self.assertEqual(len(plot._shade_artists), 2)                 # un tramo, en magnitud y en fase
        spans = plot._unreliable_spans()
        self.assertEqual(len(spans), 1)
        self.assertGreater(spans[0][0], 20_000)                       # -20 dB del pasa-bajos de 2,8 kHz: ~28 kHz
        plot.set_shade_unreliable(False)
        self.assertEqual(plot._shade_artists, [])

    def test_unreliable_reasons_and_hover_tooltip(self):
        import fra_app.gui.bode_plot as bp
        from fra_app import phase_repair as pr
        self.assertEqual(pr.unreliable_reason(5000.0, -25.0), pr.REASON_FLOOR)
        self.assertEqual(pr.unreliable_reason(400.0, -5.0), pr.REASON_LF)
        self.assertEqual(pr.unreliable_reason(400.0, -1.0), None)
        self.assertEqual(pr.unreliable_reason(5000.0, -10.0), None)

        win = self.sweep_window()
        plot = win.plot
        win.show()
        plot.canvas.draw()
        shown = []
        original = bp.QToolTip.showText
        hidden = []
        bp.QToolTip.showText = staticmethod(lambda pos, text, widget=None: shown.append(text))
        original_hide = bp.QToolTip.hideText
        bp.QToolTip.hideText = staticmethod(lambda: hidden.append(True))
        try:
            lo, hi, reasons = plot._spans[0]
            self.assertEqual(reasons, (pr.REASON_FLOOR,))
            f_in = (lo * hi) ** 0.5
            px = plot.ax_mag.transData.transform((f_in, -25.0))

            class Ev:
                inaxes, xdata, x, y = plot.ax_mag, f_in, px[0], px[1]
            plot.set_shade_unreliable(True)
            plot._on_hover(Ev)
            self.assertEqual(len(shown), 1)
            self.assertIn("Nivel bajo", shown[0])
            plot._on_hover(Ev)
            self.assertEqual(len(shown), 1, "no repite el tooltip mientras sigue en el mismo tramo")
            Ev.xdata, Ev.x = 1000.0, plot.ax_mag.transData.transform((1000.0, 0))[0]
            plot._on_hover(Ev)
            self.assertTrue(hidden, "al salir del tramo se oculta")
            # sin sombreado y lejos de un circulo hueco, no molesta
            plot.set_shade_unreliable(False)
            n = len(shown)
            Ev.xdata, Ev.x = f_in, px[0] + 40
            plot._on_hover(Ev)
            self.assertEqual(len(shown), n)
        finally:
            bp.QToolTip.showText = original
            bp.QToolTip.hideText = original_hide

    def test_reference_curve_stays_while_new_sweeps_replace_the_measurement(self):
        win = self.sweep_window()
        plot = win.plot
        self.assertTrue(plot.set_reference_from_current())
        n_ref = len(plot.ref_mag.get_xdata())
        self.assertGreater(n_ref, 10)
        self.assertIsNotNone(plot.ax_mag.get_legend())
        win._on_start_clicked()                                       # nuevo barrido: la referencia no se borra
        self.assertEqual(len(plot.ref_mag.get_xdata()), n_ref)
        plot.clear_reference()
        self.assertEqual(len(plot.ref_mag.get_xdata()), 0)
        self.assertIsNone(plot.ax_mag.get_legend())

    def test_zoom_with_the_wheel_and_reset(self):
        win = self.sweep_window()
        plot = win.plot
        win.show()
        plot.canvas.draw()
        lo0, hi0 = plot.ax_mag.get_xlim()

        class Ev:                                                     # evento de rueda de matplotlib
            inaxes, xdata, ydata, button, key = plot.ax_mag, 1000.0, 0.0, "up", None
        plot._on_scroll(Ev)
        lo1, hi1 = plot.ax_mag.get_xlim()
        self.assertGreater(lo1, lo0)
        self.assertLess(hi1, hi0)
        self.assertEqual(plot.ax_phase.get_xlim(), (lo1, hi1), "los dos graficos comparten el eje de frecuencia")
        plot.reset_view()
        self.assertAlmostEqual(plot.ax_mag.get_xlim()[0], lo0, delta=lo0 * 1e-6)
        self.assertAlmostEqual(plot.ax_mag.get_xlim()[1], hi0, delta=hi0 * 1e-6)

    def test_zoom_fits_magnitude_and_phase_to_what_is_visible(self):
        win = self.sweep_window()
        plot = win.plot
        win.show()
        plot.canvas.draw()
        span0 = plot.ax_mag.get_ylim()[1] - plot.ax_mag.get_ylim()[0]

        class Ev:
            inaxes, xdata, ydata, button, key = plot.ax_mag, 200.0, 0.0, "up", None
        for _ in range(4):                    # acerca a la zona plana de 100-300 Hz
            plot._on_scroll(Ev)
        lo, hi = plot.ax_mag.get_xlim()
        visible = [d for f, d in zip(plot.freqs, plot.dbs) if lo <= f <= hi]
        ylo, yhi = plot.ax_mag.get_ylim()
        self.assertLess(yhi - ylo, span0 / 5, "la magnitud se ajusta a lo que se ve")
        self.assertTrue(ylo <= min(visible) and yhi >= max(visible))
        plo, phi = plot.ax_phase.get_ylim()
        vis_ph = [p for f, p in zip(plot.freqs, plot.phases) if lo <= f <= hi]
        self.assertTrue(plo <= min(vis_ph) and phi >= max(vis_ph))
        self.assertLess(phi - plo, 100)

    def test_zooming_away_from_the_cutoff_does_not_shrink_the_plot(self):
        win = self.sweep_window()
        plot = win.plot
        win.show()
        plot.detect_cutoffs()
        plot._set_cursor(0, 10)
        plot.canvas.draw()
        before = plot.ax_mag.get_position().bounds

        class Ev:                             # zoom hacia 60 kHz: la fc de 2,8 kHz y el cursor quedan fuera de la vista
            inaxes, xdata, ydata, button, key = plot.ax_mag, 60e3, 0.0, "up", None
        for _ in range(8):
            plot._on_scroll(Ev)
        plot.canvas.draw()
        after = plot.ax_mag.get_position().bounds
        for a, b in zip(before, after):       # solo cambia el ancho de los numeros del eje vertical (< 2 %)
            self.assertAlmostEqual(a, b, delta=0.02)
        texts = [t for t in plot.ax_mag.texts]
        self.assertTrue(texts and all(t.get_clip_on() for t in texts),
                        "las etiquetas de la fc y del cursor se recortan al eje: no condicionan el diseno")

    def test_export_figure_writes_png_and_pdf(self):
        import tempfile
        win = self.sweep_window()
        size_before = win.plot.canvas.figure.get_size_inches().copy()
        with tempfile.TemporaryDirectory() as d:
            for ext in ("png", "pdf"):
                path = os.path.join(d, f"bode.{ext}")
                win.plot.export_figure(path)
                self.assertGreater(os.path.getsize(path), 5000)
        self.assertEqual(list(win.plot.canvas.figure.get_size_inches()), list(size_before))

    def test_load_curve_csv(self):
        import tempfile
        from fra_app.curve_io import load_curve_csv
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "ok.csv")
            with open(good, "w", encoding="utf-8") as f:
                f.write("freq_hz,db,phase_deg,confiable\n1000,-3,-45,1\n100,0,-5,1\n")
            freqs, dbs, phases = load_curve_csv(good)
            self.assertEqual(freqs, [100.0, 1000.0])                  # queda ordenada por frecuencia
            bad = os.path.join(d, "bad.csv")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("a,b\n1,2\n")
            with self.assertRaises(ValueError):
                load_curve_csv(bad)

    def test_exported_csv_reopens_as_a_measurement(self):
        import tempfile
        import fra_app.gui.main_window as mw
        win = self.sweep_window()
        win.plot.detect_cutoffs()
        fc_original = win.plot.analysis_label.text()
        saved = (list(win.plot.freqs), list(win.plot.dbs), list(win.plot.phases), list(win.plot.reliable))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bode.csv")
            mw.save_measurement_csv(path, *saved)

            # otra sesion: sin calibrar y sin datos
            win2, _ = make_window()
            self.assertFalse(win2.calibrated)
            original = mw.QFileDialog.getOpenFileName
            mw.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (path, "CSV (*.csv)"))
            try:
                win2._open_measurement_csv()
            finally:
                mw.QFileDialog.getOpenFileName = original
        plot = win2.plot
        self.assertEqual(plot.freqs, saved[0])
        for a, b in zip(plot.dbs, saved[1]):
            self.assertAlmostEqual(a, b, places=9)
        for a, b in zip(plot.phases, saved[2]):
            self.assertAlmostEqual(a, b, places=9)       # tal cual: no se vuelve a reparar ni a corregir
        self.assertEqual(plot.reliable, saved[3])
        self.assertTrue(plot.detect_btn.isEnabled())
        self.assertEqual(plot.line_mag.get_xdata().tolist() if hasattr(plot.line_mag.get_xdata(), "tolist")
                         else list(plot.line_mag.get_xdata()), saved[0])
        plot._set_cursor(0, 10)
        plot._set_cursor(1, 40)
        self.assertTrue(plot.cursor_labels[2].text().startswith("Diferencia"))
        plot.detect_btn.click()
        self.assertEqual(plot.analysis_label.text(), fc_original, "la deteccion da lo mismo que sobre la medicion")
        self.assertTrue(win2.export_csv_action is not None)
        win2._update_menus()
        self.assertTrue(win2.export_csv_action.isEnabled())

    def test_csv_without_the_reliability_column_still_opens(self):
        import tempfile
        from fra_app.curve_io import load_measurement_csv
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "viejo.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("freq_hz,db,phase_deg\n100,0,-1\n1000,-3,-45\n10000,-22,-80\n")
            freqs, dbs, phases, reliable = load_measurement_csv(path)
        self.assertEqual(freqs, [100.0, 1000.0, 10000.0])
        self.assertIsNone(reliable)
        win, _ = make_window()
        win.plot.load_measurement(freqs, dbs, phases, reliable)
        self.assertEqual(win.plot.reliable, [True, True, False], "se calcula con la regla de confiabilidad")

    def test_opening_a_csv_is_refused_during_a_sweep(self):
        import fra_app.gui.main_window as mw
        win, _ = make_window()
        win._sweeping = True
        asked = []
        original_dialog, original_info = mw.QFileDialog.getOpenFileName, mw.QMessageBox.information
        mw.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: asked.append("dialogo") or ("", ""))
        mw.QMessageBox.information = staticmethod(lambda *a, **k: asked.append("aviso"))
        try:
            win._open_measurement_csv()
        finally:
            mw.QFileDialog.getOpenFileName, mw.QMessageBox.information = original_dialog, original_info
        self.assertEqual(asked, ["aviso"])

    def test_menus_enable_exports_only_with_data(self):
        win, fake = make_window()
        win._update_menus()
        self.assertFalse(win.export_csv_action.isEnabled() or win.ref_set_action.isEnabled())
        win._on_calibrate_clicked()
        win._on_start_clicked()
        win._update_menus()
        self.assertTrue(win.export_csv_action.isEnabled() and win.export_png_action.isEnabled()
                        and win.export_pdf_action.isEnabled() and win.ref_set_action.isEnabled())
        self.assertFalse(win.ref_clear_action.isEnabled())


if __name__ == "__main__":
    unittest.main()