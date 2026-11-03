"""Interfaz comun para las fuentes de datos (hoy, el ESP32 real por serie)."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class Backend(QThread):
    """Clase base. Emite los mismos eventos sin importar el origen de los datos."""

    connected = Signal()
    disconnected = Signal()
    device_id = Signal(str)
    calibration_done = Signal(float, float)  # phase_offset_deg, db_offset
    sweep_started = Signal(int)
    data_point = Signal(int, float, float, float)  # index, freq_hz, db, phase_deg
    sweep_done = Signal()
    sweep_aborted = Signal()
    error = Signal(str)
    log = Signal(str)

    def send_calibrate(self) -> None:
        raise NotImplementedError

    def send_start(self, f_start_hz: float, f_stop_hz: float, n_points: int, log_scale: bool) -> None:
        raise NotImplementedError

    def send_stop(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        """Corta el hilo y cierra la conexion."""
        raise NotImplementedError
