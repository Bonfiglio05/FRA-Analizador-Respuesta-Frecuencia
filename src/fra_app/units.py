"""Formateo de frecuencias para mostrar en la UI."""

from __future__ import annotations


def format_freq(hz: float) -> str:
    if hz >= 1e6:
        return f"{hz / 1e6:.3f} MHz"
    if hz >= 1e3:
        return f"{hz / 1e3:.3f} kHz"
    return f"{hz:.2f} Hz"
