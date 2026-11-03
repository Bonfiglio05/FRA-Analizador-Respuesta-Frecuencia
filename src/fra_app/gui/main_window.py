"""Ventana principal de la app del Analizador de Respuesta en Frecuencia."""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..backend import Backend
from ..curve_io import load_curve_csv, load_measurement_csv, save_measurement_csv
from ..serial_backend import SerialBackend, list_ports
from ..thru_calibration import THRU_POINTS, THRU_START_HZ, THRU_STOP_HZ, ThruProfile
from .bode_plot import BodePlot
from .frequency_input import FrequencyInput

_SETTINGS_ORG = "UTN"
_SETTINGS_APP = "FRA"
_SHADE_KEY = "ver/sombrear_poco_confiable"


def _open_settings() -> QSettings:
    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)

MIN_FREQ_HZ = 100
MAX_FREQ_HZ = 10_000_000

_CORRECTION_TIP = (
    "Con el DUT puenteado el instrumento deberia leer 0 dB y 0°: lo que lee en cambio es su error "
    "sistematico (retardo de los cables, desfase propio). Esa lectura de cero, tomada al calibrar, se resta "
    "de cada medicion (correccion de cero). Desmarcala para ver la medicion sin compensar."
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Analizador de Respuesta en Frecuencia")
        self.resize(1000, 750)

        self.backend: Backend | None = None
        self._connected = False

        # Calibracion unica: CAL a 1 MHz + barrido del puente 100 Hz - 10 MHz ("cero" del instrumento).
        self.thru_profile: ThruProfile | None = None
        self._thru_state: str | None = None          # None | "cal" | "sweep"
        self._thru_points: list[tuple[float, float, float]] = []
        self._plot_profile: ThruProfile | None = None  # perfil con el que se midio el grafico actual

        self._sweeping = False                       # barrido del usuario en curso

        self._build_log_dialog()
        self._build_ui()
        self._refresh_ports()
        self._set_connected_state(False)

    # ---------------------------------------------------------------- UI --
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)


        self.plot = BodePlot()
        root.addWidget(self.plot, stretch=1)
        # los controles van en el panel lateral del grafico, arriba de las lecturas (aprovecha ese espacio)
        self.plot.side_layout.insertWidget(0, self._build_instrument_box())
        self.plot.side_layout.insertWidget(1, self._build_sweep_box())

        self.progress = QProgressBar()
        root.addWidget(self.progress)

        self._build_menus()
        self.statusBar().showMessage("Desconectado")

    def _build_menus(self) -> None:
        """Archivo: exportar. Ver: opciones avanzadas (zoom, referencia, zona poco confiable, registro)."""
        file_menu = self.menuBar().addMenu("Archivo")
        file_menu.addAction("Abrir medicion (CSV)...", self._open_measurement_csv)
        file_menu.addSeparator()
        self.export_csv_action = file_menu.addAction("Exportar datos (CSV)...", self._export_csv)
        self.export_png_action = file_menu.addAction("Exportar grafico (PNG)...", lambda: self._export_figure("png"))
        self.export_pdf_action = file_menu.addAction("Exportar grafico (PDF)...", lambda: self._export_figure("pdf"))
        file_menu.addSeparator()
        file_menu.addAction("Salir", self.close)

        view_menu = self.menuBar().addMenu("Ver")
        self.shade_action = QAction("Sombrear zona poco confiable", self, checkable=True)
        self.shade_action.setToolTip("Marca en gris los tramos donde la medicion no es confiable.")
        self.shade_action.setChecked(self._read_setting(_SHADE_KEY))
        self.shade_action.toggled.connect(self._on_shade_toggled)
        view_menu.addAction(self.shade_action)
        self.plot.set_shade_unreliable(self.shade_action.isChecked())
        view_menu.addAction("Restablecer zoom", self.plot.reset_view)

        ref_menu = view_menu.addMenu("Curva de referencia")
        self.ref_set_action = ref_menu.addAction("Usar el barrido actual como referencia", self._set_reference_current)
        ref_menu.addAction("Abrir CSV como referencia...", self._open_reference_csv)
        self.ref_clear_action = ref_menu.addAction("Quitar referencia", self.plot.clear_reference)

        view_menu.addSeparator()
        view_menu.addAction("Registro de comunicacion...", self.log_dialog.show)

        file_menu.aboutToShow.connect(self._update_menus)
        ref_menu.aboutToShow.connect(self._update_menus)

    def _update_menus(self) -> None:
        has_data = self.plot.has_data
        for action in (self.export_csv_action, self.export_png_action, self.export_pdf_action, self.ref_set_action):
            action.setEnabled(has_data)
        self.ref_clear_action.setEnabled(self.plot.reference is not None)

    @staticmethod
    def _read_setting(key: str) -> bool:
        return _open_settings().value(key, False, type=bool)

    def _on_shade_toggled(self, checked: bool) -> None:
        self.plot.set_shade_unreliable(checked)
        _open_settings().setValue(_SHADE_KEY, checked)

    def _set_reference_current(self) -> None:
        if self.plot.set_reference_from_current():
            self.statusBar().showMessage("Referencia fijada: el proximo barrido se dibuja sobre ella")

    def _open_reference_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir CSV como referencia", "", "CSV (*.csv)")
        if not path:
            return
        try:
            freqs, dbs, phases = load_curve_csv(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "No se pudo abrir la referencia", str(exc))
            return
        self.plot.set_reference(freqs, dbs, phases)
        self.statusBar().showMessage(f"Referencia: {os.path.basename(path)}")

    def _build_log_dialog(self) -> None:
        """El registro serie ya no ocupa la ventana: queda a un click por si hay que depurar."""
        self.log_dialog = QDialog(self)
        self.log_dialog.setWindowTitle("Registro de comunicacion")
        self.log_dialog.resize(600, 300)
        layout = QVBoxLayout(self.log_dialog)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

    def _log(self, line: str) -> None:
        if not line.startswith("DATA"):      # un renglon por punto no aporta nada al usuario
            self.log_view.append(line)

    def _build_instrument_box(self) -> QGroupBox:
        """Conexion y calibracion (van en el panel lateral, apiladas)."""
        box = QGroupBox("Instrumento")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Puerto:"))
        self.port_combo = QComboBox()
        row.addWidget(self.port_combo, stretch=1)
        self.refresh_btn = QPushButton("Actualizar")
        self.refresh_btn.clicked.connect(self._refresh_ports)
        row.addWidget(self.refresh_btn)
        layout.addLayout(row)

        row = QHBoxLayout()
        self.connect_btn = QPushButton("Conectar")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        row.addWidget(self.connect_btn)
        self.calibrate_btn = QPushButton("Calibrar")
        self.calibrate_btn.setToolTip(
            "Puentea la entrada y la salida del DUT con los mismos cables de la medicion. "
            "Calibra fase y dB a 1 MHz y mide el puente de 100 Hz a 10 MHz (unos 50 s)."
        )
        self.calibrate_btn.clicked.connect(self._on_calibrate_clicked)
        row.addWidget(self.calibrate_btn)
        layout.addLayout(row)

        self.thru_check = QCheckBox("Correccion de cero")
        self.thru_check.setToolTip(_CORRECTION_TIP)
        self.thru_check.setChecked(True)
        self.thru_check.setEnabled(False)
        self.thru_check.toggled.connect(self._on_thru_toggled)
        layout.addWidget(self.thru_check)

        self.calibration_status = QLabel()
        self.calibration_status.setWordWrap(True)
        layout.addWidget(self.calibration_status)

        return box

    def _build_sweep_box(self) -> QGroupBox:
        box = QGroupBox("Barrido")
        grid = QGridLayout(box)

        grid.addWidget(QLabel("Desde:"), 0, 0)
        self.f_start = FrequencyInput(MIN_FREQ_HZ, MAX_FREQ_HZ, default_hz=100)
        grid.addWidget(self.f_start, 0, 1)

        grid.addWidget(QLabel("Hasta:"), 1, 0)
        self.f_stop = FrequencyInput(MIN_FREQ_HZ, MAX_FREQ_HZ, default_hz=100_000)
        grid.addWidget(self.f_stop, 1, 1)

        grid.addWidget(QLabel("Puntos:"), 2, 0)
        self.n_points = QSpinBox()
        self.n_points.setRange(2, 2000)
        self.n_points.setValue(101)
        grid.addWidget(self.n_points, 2, 1)

        grid.addWidget(QLabel("Escala:"), 3, 0)
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["Logaritmica", "Lineal"])
        grid.addWidget(self.scale_combo, 3, 1)

        buttons = QHBoxLayout()
        self.start_btn = QPushButton("Iniciar barrido")
        self.start_btn.clicked.connect(self._on_start_clicked)
        buttons.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Detener")
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        buttons.addWidget(self.stop_btn)
        grid.addLayout(buttons, 4, 0, 1, 2)

        return box
    # ------------------------------------------------------------ Estado --
    @property
    def calibrated(self) -> bool:
        return self.thru_profile is not None

    def _busy(self) -> bool:
        """Hay una calibracion en curso."""
        return self._thru_state is not None

    def _refresh_buttons(self) -> None:
        idle = self._connected and not self._busy() and not self._sweeping
        self.calibrate_btn.setEnabled(idle)
        self.start_btn.setEnabled(idle)
        self.stop_btn.setEnabled(self._connected and (self._sweeping or self._thru_state == "sweep"))
        self.thru_check.setEnabled(self.calibrated and not self._busy())

    def _set_connected_state(self, connected: bool) -> None:
        self._connected = connected
        self.connect_btn.setText("Desconectar" if connected else "Conectar")
        self.port_combo.setEnabled(not connected)
        self.refresh_btn.setEnabled(not connected)
        if not connected:
            self._thru_state = None
            self._sweeping = False
            self.thru_profile = None
            self.calibration_status.setText("Conecta el instrumento")
        elif not self.calibrated:
            self.calibration_status.setText("Sin calibrar: puentea y apreta Calibrar")
        self._refresh_buttons()

    def _refresh_ports(self) -> None:
        self.port_combo.clear()
        self.port_combo.addItems(list_ports())

    # -------------------------------------------------------- Conexion --
    def _on_connect_clicked(self) -> None:
        if self.backend is not None:
            self._disconnect()
            return

        port = self.port_combo.currentText()
        if not port:
            QMessageBox.warning(self, "Sin puerto", "Selecciona un puerto serie primero.")
            return
        backend = SerialBackend(port)

        self._attach_backend(backend)
        backend.start()

    def _attach_backend(self, backend: Backend) -> None:
        """Guarda el backend y conecta sus senales (separado para poder probarlo con un backend falso)."""
        self.backend = b = backend
        b.connected.connect(self._on_backend_connected)
        b.disconnected.connect(self._on_backend_disconnected)
        b.device_id.connect(lambda v: self.statusBar().showMessage(f"Conectado - dispositivo {v}"))
        b.calibration_done.connect(self._on_calibration_done)
        b.sweep_started.connect(self._on_sweep_started)
        b.data_point.connect(self._on_data_point)
        b.sweep_done.connect(self._on_sweep_done)
        b.sweep_aborted.connect(self._on_sweep_aborted)
        b.error.connect(self._on_backend_error)
        b.log.connect(self._log)

    def _disconnect(self) -> None:
        if self.backend is not None:
            self.backend.stop()
            self.backend = None
        self._set_connected_state(False)
        self.statusBar().showMessage("Desconectado")

    def _on_backend_connected(self) -> None:
        self._set_connected_state(True)
        self.statusBar().showMessage("Conectado")

    def _on_backend_disconnected(self) -> None:
        self._set_connected_state(False)
        self.statusBar().showMessage("Desconectado")

    def _on_backend_error(self, message: str) -> None:
        self.log_view.append(f"[ERROR] {message}")
        if self._thru_state is not None:
            self.calibration_status.setText("Calibracion fallida: revisa el puente y los cables")
        self._thru_state = None
        self._sweeping = False
        self._refresh_buttons()
        QMessageBox.critical(self, "Error", message)

    # -------------------------------------------------------- Calibracion --
    def _on_calibrate_clicked(self) -> None:
        """Calibracion unica: CAL a 1 MHz y, a continuacion, barrido del puente (el "cero" del instrumento)."""
        if self.backend is None:
            return
        self.thru_profile = None          # cada CAL deja residuos distintos: el cero anterior ya no vale
        self._thru_state = "cal"
        self._thru_points = []
        self.calibration_status.setText("Calibrando (1/2)...")
        self._refresh_buttons()
        self.backend.send_calibrate()

    def _on_calibration_done(self, phase_offset_deg: float, db_offset: float) -> None:
        self.log_view.append(f"Calibrado a 1 MHz (fase ref.: {phase_offset_deg:.2f}°, offset dB: {db_offset:.3f})")
        if self._thru_state != "cal":
            return
        self._thru_state = "sweep"
        self.calibration_status.setText("Midiendo el puente (2/2)...")
        self.progress.setValue(0)
        self._refresh_buttons()
        self.backend.send_start(THRU_START_HZ, THRU_STOP_HZ, THRU_POINTS, True)

    def _on_thru_toggled(self, checked: bool) -> None:
        # solo se reprocesa el grafico si se midio con esta misma calibracion
        if self.plot.freqs and self._plot_profile is self.thru_profile and self.thru_profile is not None:
            self.plot.reprocess(self.thru_profile if checked else None)
        self._update_calibration_status()

    def _active_thru(self) -> ThruProfile | None:
        return self.thru_profile if (self.calibrated and self.thru_check.isChecked()) else None

    def _update_calibration_status(self) -> None:
        if not self.calibrated:
            return
        if self.thru_check.isChecked():
            self.calibration_status.setText("Calibrado - correccion de cero aplicada")
        else:
            self.calibration_status.setText("Calibrado - mostrando la medicion SIN correccion de cero")

    def _confirm_calibrated(self) -> bool:
        if self.calibrated:
            return True
        answer = QMessageBox.question(
            self, "Sin calibrar",
            "Todavia no calibraste: sin calibrar, la fase y la magnitud pueden tener errores de varios grados y "
            "decimas de dB.\n\nMedir igual?",
        )
        return answer == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------ Barrido --
    def _on_start_clicked(self) -> None:
        if self.backend is None:
            return
        if self.f_start.value_hz() >= self.f_stop.value_hz():
            QMessageBox.warning(self, "Rango invalido", "La frecuencia inicial debe ser menor a la final.")
            return
        if not self._confirm_calibrated():
            return
        self._start_sweep(self.f_start.value_hz(), self.f_stop.value_hz(), self.n_points.value(),
                          self.scale_combo.currentText() == "Logaritmica")

    def _start_sweep(self, f_start: float, f_stop: float, n_points: int, log_scale: bool) -> None:
        self.plot.clear()
        self._sweeping = True
        self._refresh_buttons()
        self.backend.send_start(f_start, f_stop, n_points, log_scale)

    def _on_stop_clicked(self) -> None:
        if self.backend is not None:
            self.backend.send_stop()

    def _on_sweep_started(self, n_points: int) -> None:
        self.progress.setMaximum(n_points)
        self.progress.setValue(0)

    def _on_data_point(self, index: int, freq_hz: float, db: float, phase_deg: float) -> None:
        self.progress.setValue(index + 1)
        if self._thru_state == "sweep":
            self._thru_points.append((freq_hz, db, phase_deg))  # barrido del puente: no va al grafico
            return
        self.plot.add_point(freq_hz, db, phase_deg)

    def _on_sweep_finished(self, message: str) -> None:
        self._sweeping = False
        self._refresh_buttons()
        self.statusBar().showMessage(message)

    def _on_sweep_done(self) -> None:
        if self._thru_state == "sweep":
            self._finish_thru()
            return
        self._plot_profile = self.thru_profile       # con que calibracion se midio este grafico
        self.plot.finalize_sweep(self._active_thru())
        self._on_sweep_finished("Barrido completo")

    def _on_sweep_aborted(self) -> None:
        if self._thru_state == "sweep":
            self._thru_state = None
            self.calibration_status.setText("Calibracion cancelada: falta el barrido del puente")
            self._refresh_buttons()
            self.statusBar().showMessage("Calibracion cancelada")
            return
        self._on_sweep_finished("Barrido detenido")

    def _finish_thru(self) -> None:
        pts = self._thru_points
        self._thru_state = None
        if len(pts) < 10:
            self.calibration_status.setText("Calibracion fallida (llegaron pocos puntos)")
            self._refresh_buttons()
            return
        self.thru_profile = ThruProfile([p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts])
        self.log_view.append("Perfil de puente: " + self.thru_profile.summary())
        self.thru_check.blockSignals(True)
        self.thru_check.setChecked(True)
        self.thru_check.blockSignals(False)
        self._update_calibration_status()
        self._refresh_buttons()
        self.statusBar().showMessage("Calibracion lista")

    # ------------------------------------------------------------- Datos --
    def _export_figure(self, ext: str) -> None:
        if not self.plot.has_data:
            QMessageBox.information(self, "Sin datos", "Todavia no hay datos para exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(self, f"Exportar grafico ({ext.upper()})", f"bode.{ext}",
                                              f"{ext.upper()} (*.{ext})")
        if not path:
            return
        try:
            self.plot.export_figure(path)
        except OSError as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return
        self.statusBar().showMessage(f"Exportado a {path}")

    def _export_csv(self) -> None:
        if not self.plot.freqs:
            QMessageBox.information(self, "Sin datos", "Todavia no hay datos para exportar.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "bode.csv", "CSV (*.csv)")
        if not path:
            return

        try:
            save_measurement_csv(path, self.plot.freqs, self.plot.dbs, self.plot.phases, self.plot.reliable)
        except OSError as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        self.statusBar().showMessage(f"Exportado a {path}")

    def _open_measurement_csv(self) -> None:
        """Abre un CSV exportado y lo muestra como una medicion: cursores y deteccion de banda funcionan igual."""
        if self._sweeping or self._busy():
            QMessageBox.information(self, "Medicion en curso", "Espera a que termine el barrido o la calibracion.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Abrir medicion (CSV)", "", "CSV (*.csv)")
        if not path:
            return
        try:
            freqs, dbs, phases, reliable = load_measurement_csv(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "No se pudo abrir el archivo", str(exc))
            return
        self._plot_profile = None            # no corresponde a ninguna calibracion de esta sesion
        self.plot.load_measurement(freqs, dbs, phases, reliable)
        self.statusBar().showMessage(f"Abierto: {os.path.basename(path)} ({len(freqs)} puntos); se muestra tal como se guardo")

    # -------------------------------------------------------------- Qt --
    def closeEvent(self, event) -> None:  # noqa: N802 (nombre requerido por Qt)
        if self.backend is not None:
            self.backend.stop()
        super().closeEvent(event)
