"""Widget compuesto: un campo numerico + selector de unidad (Hz/kHz/MHz)."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QWidget

_UNITS = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6}


def _best_unit(value_hz: float) -> str:
    if value_hz >= 1e6:
        return "MHz"
    if value_hz >= 1e3:
        return "kHz"
    return "Hz"


class FrequencyInput(QWidget):
    def __init__(self, min_hz: float, max_hz: float, default_hz: float, parent: QWidget | None = None):
        super().__init__(parent)
        self._min_hz = min_hz
        self._max_hz = max_hz

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(3)
        layout.addWidget(self.spin)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(list(_UNITS.keys()))
        self.unit_combo.setFixedWidth(80)         # mismo ancho para Hz/kHz/MHz: los campos quedan alineados
        layout.addWidget(self.unit_combo)

        initial_unit = _best_unit(default_hz)
        self._last_factor = _UNITS[initial_unit]
        self.unit_combo.setCurrentText(initial_unit)
        self._apply_unit_range(initial_unit)
        self.spin.setValue(default_hz / self._last_factor)

        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)

    def _apply_unit_range(self, unit: str) -> None:
        factor = _UNITS[unit]
        self.spin.setRange(self._min_hz / factor, self._max_hz / factor)

    def _on_unit_changed(self, unit: str) -> None:
        current_hz = self.spin.value() * self._last_factor
        self._last_factor = _UNITS[unit]
        self._apply_unit_range(unit)
        self.spin.setValue(current_hz / self._last_factor)

    def value_hz(self) -> float:
        return self.spin.value() * self._last_factor
