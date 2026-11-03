"""Protocolo serie PC <-> ESP32. Ver PROTOCOL.md en la raiz del repo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

BAUDRATE = 115200


@dataclass
class DataPoint:
    index: int
    freq_hz: float
    db: float
    phase_deg: float


@dataclass
class SweepStart:
    n_points: int


@dataclass
class SweepDone:
    pass


@dataclass
class SweepAborted:
    pass


@dataclass
class DeviceId:
    version: str


@dataclass
class DeviceError:
    message: str


@dataclass
class CalibrationDone:
    phase_offset_deg: float
    db_offset: float


Message = Union[DataPoint, SweepStart, SweepDone, SweepAborted, DeviceId, DeviceError, CalibrationDone]


def build_id_query() -> str:
    return "ID?\n"


def build_calibrate() -> str:
    return "CAL\n"


def build_start(f_start_hz: float, f_stop_hz: float, n_points: int, log_scale: bool) -> str:
    escala = "LOG" if log_scale else "LIN"
    return f"START,{f_start_hz},{f_stop_hz},{n_points},{escala}\n"


def build_stop() -> str:
    return "STOP\n"


def parse_line(line: str) -> Optional[Message]:
    """Parsea una linea recibida del ESP32. Devuelve None si no matchea el protocolo."""
    line = line.strip()
    if not line:
        return None

    parts = line.split(",")
    tag = parts[0]

    try:
        if tag == "DATA" and len(parts) == 5:
            return DataPoint(
                index=int(parts[1]),
                freq_hz=float(parts[2]),
                db=float(parts[3]),
                phase_deg=float(parts[4]),
            )
        if tag == "SWEEP_START" and len(parts) == 2:
            return SweepStart(n_points=int(parts[1]))
        if tag == "SWEEP_DONE":
            return SweepDone()
        if tag == "SWEEP_ABORTED":
            return SweepAborted()
        if tag == "ID" and len(parts) >= 3:
            return DeviceId(version=parts[2])
        if tag == "CAL_DONE" and len(parts) == 3:
            return CalibrationDone(phase_offset_deg=float(parts[1]), db_offset=float(parts[2]))
        if tag == "ERR":
            return DeviceError(message=",".join(parts[1:]))
    except ValueError:
        return None

    return None
