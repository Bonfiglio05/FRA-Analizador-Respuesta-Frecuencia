"""Backend que habla con el ESP32 real por un puerto serie (COM virtual del CH340)."""

from __future__ import annotations

import serial
import serial.tools.list_ports

from . import protocol
from .backend import Backend


def list_ports() -> list[str]:
    return [p.device for p in serial.tools.list_ports.comports()]


class SerialBackend(Backend):
    def __init__(self, port: str, baudrate: int = protocol.BAUDRATE):
        super().__init__()
        self._port_name = port
        self._baudrate = baudrate
        self._serial: serial.Serial | None = None
        self._running = False

    def run(self) -> None:
        try:
            self._serial = serial.Serial(self._port_name, self._baudrate, timeout=0.5)
        except serial.SerialException as exc:
            self.error.emit(f"No se pudo abrir {self._port_name}: {exc}")
            return

        self._running = True
        self.connected.emit()
        self._write(protocol.build_id_query())

        while self._running:
            try:
                raw = self._serial.readline()
            except serial.SerialException as exc:
                self.error.emit(f"Error de lectura serie: {exc}")
                break

            if not raw:
                continue

            line = raw.decode("ascii", errors="replace")
            self.log.emit(line.strip())
            self._dispatch(protocol.parse_line(line))

        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self.disconnected.emit()

    def _dispatch(self, msg: protocol.Message | None) -> None:
        if msg is None:
            return
        if isinstance(msg, protocol.DataPoint):
            self.data_point.emit(msg.index, msg.freq_hz, msg.db, msg.phase_deg)
        elif isinstance(msg, protocol.SweepStart):
            self.sweep_started.emit(msg.n_points)
        elif isinstance(msg, protocol.SweepDone):
            self.sweep_done.emit()
        elif isinstance(msg, protocol.SweepAborted):
            self.sweep_aborted.emit()
        elif isinstance(msg, protocol.DeviceId):
            self.device_id.emit(msg.version)
        elif isinstance(msg, protocol.CalibrationDone):
            self.calibration_done.emit(msg.phase_offset_deg, msg.db_offset)
        elif isinstance(msg, protocol.DeviceError):
            self.error.emit(msg.message)

    def _write(self, text: str) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.write(text.encode("ascii"))

    def send_calibrate(self) -> None:
        self._write(protocol.build_calibrate())

    def send_start(self, f_start_hz: float, f_stop_hz: float, n_points: int, log_scale: bool) -> None:
        self._write(protocol.build_start(f_start_hz, f_stop_hz, n_points, log_scale))

    def send_stop(self) -> None:
        self._write(protocol.build_stop())

    def stop(self) -> None:
        self._running = False
        self.wait(2000)
