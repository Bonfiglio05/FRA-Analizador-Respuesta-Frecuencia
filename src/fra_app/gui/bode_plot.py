"""Widget de grafico de Bode: magnitud (dB) y fase (grados) vs frecuencia (log).

Incluye dos cursores tipo osciloscopio (click izquierdo / click derecho) y, a pedido del usuario,
la deteccion de las frecuencias de corte a -3 dB con calculo de ancho de banda y Q.
"""

from __future__ import annotations

import bisect
import math

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .. import analysis, phase_repair
from ..units import format_freq

_CUTOFF_COLOR = "#2a9d57"
# distintos de los de las curvas (azul = magnitud, naranja = fase) y del verde de los cortes
_CURSOR_COLORS = ("#d62728", "#8e44ad")
_DELTA_COLOR = "#0b7285"
_HINT_COLOR = "#777777"
_REF_COLOR = "#9a9a9a"
_SHADE_COLOR = "#9e9e9e"
_READOUT_STYLE = "font-family: Consolas, 'Courier New', monospace; font-size: 14px; font-weight: 600; color: {};"
_SIDE_WIDTH = 360      # ancho del panel (controles y lecturas) a la derecha del grafico


class BodePlot(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.freqs: list[float] = []
        self.dbs: list[float] = []
        self.phases: list[float] = []        # fase mostrada (con el signo reparado al terminar el barrido)
        self.raw_dbs: list[float] = []       # magnitud tal como la entrega el instrumento
        self.raw_phases: list[float] = []    # fase tal como la entrega el instrumento
        self.reliable: list[bool] = []       # True: punto confiable (ver phase_repair.reliability)

        self._cursor_data: list[tuple[float, float, float] | None] = [None, None]
        self._cursor_artists: list[list] = [[], []]
        self._cutoff_artists: list = []
        self._detected = False               # el usuario pidio marcar las frecuencias de corte

        figure = Figure(figsize=(6, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(figure)
        self.ax_mag = figure.add_subplot(211)
        self.ax_phase = figure.add_subplot(212, sharex=self.ax_mag)

        self._setup_axes()

        (self.line_mag,) = self.ax_mag.plot([], [], "o-", color="#2a6fdb", markersize=3)
        (self.line_phase,) = self.ax_phase.plot([], [], "o-", color="#db6f2a", markersize=3)
        # puntos poco confiables: circulos huecos sobre la misma curva
        (self.unrel_mag,) = self.ax_mag.plot([], [], "o", color="#2a6fdb", markerfacecolor="white",
                                             markersize=4.5, linestyle="none", zorder=4)
        (self.unrel_phase,) = self.ax_phase.plot([], [], "o", color="#db6f2a", markerfacecolor="white",
                                                 markersize=4.5, linestyle="none", zorder=4)

        # curva de referencia (gris, debajo de la medicion): ver set_reference()
        (self.ref_mag,) = self.ax_mag.plot([], [], "-", color=_REF_COLOR, linewidth=1.5, zorder=1)
        (self.ref_phase,) = self.ax_phase.plot([], [], "-", color=_REF_COLOR, linewidth=1.5, zorder=1)
        self.reference: tuple[list[float], list[float], list[float]] | None = None

        self._shade = False                  # sombrear los tramos poco confiables (opcion del usuario)
        self._shade_artists: list = []
        self._spans: list[tuple[float, float, tuple[str, ...]]] = []   # tramos poco confiables y su motivo
        self._hover_span: int | None = None
        self._pan: dict | None = None

        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("button_press_event", self._on_pan_start)
        self.canvas.mpl_connect("motion_notify_event", self._on_pan_move)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.canvas.mpl_connect("button_release_event", self._on_pan_end)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)

        # El grafico ocupa todo el alto disponible; las lecturas van en un panel a la derecha (en una
        # pantalla baja, apilarlas debajo del grafico lo dejaba muy chico).
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas, stretch=1)

        # panel lateral con barra de desplazamiento por si la pantalla es muy baja; la ventana principal
        # le agrega arriba los controles (self.side_layout)
        side = QWidget()
        side_layout = self.side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(4, 0, 4, 0)
        self.side_scroll = QScrollArea()
        self.side_scroll.setWidget(side)
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.side_scroll.setFixedWidth(_SIDE_WIDTH)
        layout.addWidget(self.side_scroll)

        # un renglon por cursor y uno para la diferencia, cada uno con su color
        readouts = QVBoxLayout()
        readouts.setSpacing(1)
        self.cursor_labels = [QLabel() for _ in range(3)]       # cursor 1, cursor 2, diferencia
        for lab in self.cursor_labels:
            readouts.addWidget(lab)
        side_layout.addLayout(readouts)
        self.clear_cursors_btn = QPushButton("Limpiar cursores")
        self.clear_cursors_btn.clicked.connect(self.clear_cursors)
        side_layout.addWidget(self.clear_cursors_btn)

        side_layout.addSpacing(10)
        self.detect_btn = QPushButton("Detectar banda / fc")
        self.detect_btn.setToolTip("Analiza el barrido que ya esta en pantalla y marca la frecuencia de corte "
                                   "(-3 dB) o la banda, con su ancho de banda y Q.")
        self.detect_btn.setEnabled(False)
        self.detect_btn.clicked.connect(self.detect_cutoffs)
        side_layout.addWidget(self.detect_btn)
        self.analysis_label = QLabel()
        self.analysis_label.setWordWrap(True)
        self.analysis_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.analysis_label.setStyleSheet("font-size: 13px;")
        side_layout.addWidget(self.analysis_label, stretch=1)

        self._update_cursor_readout()
        self._update_analysis_readout(None)

    def _setup_axes(self) -> None:
        self.ax_mag.set_xscale("log")
        self.ax_mag.set_ylabel("Magnitud (dB)")
        self.ax_mag.grid(True, which="both", alpha=0.3)

        self.ax_phase.set_xscale("log")
        self.ax_phase.set_xlabel("Frecuencia (Hz)")
        self.ax_phase.set_ylabel("Fase (grados)")
        self.ax_phase.grid(True, which="both", alpha=0.3)

    # ------------------------------------------------------------- Datos --
    def clear(self) -> None:
        self.freqs.clear()
        self.dbs.clear()
        self.phases.clear()
        self.raw_dbs.clear()
        self.raw_phases.clear()
        self.reliable.clear()
        self.line_mag.set_data([], [])
        self.line_phase.set_data([], [])
        self.unrel_mag.set_data([], [])
        self.unrel_phase.set_data([], [])
        self.clear_cursors()
        self.clear_cutoffs()
        self._update_shading()
        self._detected = False
        self.detect_btn.setEnabled(False)
        self._update_analysis_readout(None)
        self.reset_view()

    @property
    def has_data(self) -> bool:
        return bool(self.freqs)

    # ------------------------------------------------- Referencia / vista --
    def set_reference(self, freqs: list[float], dbs: list[float], phases: list[float]) -> None:
        """Deja una curva gris de fondo para comparar con las mediciones que siguen."""
        self.reference = (list(freqs), list(dbs), list(phases))
        self.ref_mag.set_data(freqs, dbs)
        self.ref_phase.set_data(freqs, phases)
        self._update_legend()
        self.reset_view()

    def set_reference_from_current(self) -> bool:
        if not self.has_data:
            return False
        self.set_reference(self.freqs, self.dbs, self.phases)
        return True

    def clear_reference(self) -> None:
        self.reference = None
        self.ref_mag.set_data([], [])
        self.ref_phase.set_data([], [])
        self._update_legend()
        self.reset_view()

    def _update_legend(self) -> None:
        old = self.ax_mag.get_legend()
        if old is not None:
            old.remove()
        if self.reference is not None:
            self.ax_mag.legend([self.line_mag, self.ref_mag], ["Medicion", "Referencia"],
                               loc="lower left", fontsize=8, framealpha=0.85)

    def set_shade_unreliable(self, on: bool) -> None:
        self._shade = on
        self._update_shading()
        self.canvas.draw_idle()

    def _unreliable_spans(self) -> list[tuple[float, float]]:
        """Tramos de frecuencia con puntos poco confiables seguidos, con los bordes a mitad de camino (log)."""
        n = len(self.reliable)
        spans, i = [], 0
        while i < n:
            if self.reliable[i]:
                i += 1
                continue
            j = i
            while j + 1 < n and not self.reliable[j + 1]:
                j += 1
            lo = math.sqrt(self.freqs[i - 1] * self.freqs[i]) if i > 0 else self.freqs[i]
            hi = math.sqrt(self.freqs[j] * self.freqs[j + 1]) if j + 1 < n else self.freqs[j]
            if hi <= lo:
                lo, hi = lo / 1.02, hi * 1.02
            reasons = {phase_repair.unreliable_reason(self.freqs[k], self.dbs[k]) for k in range(i, j + 1)}
            reasons = tuple(r for r in (phase_repair.REASON_FLOOR, phase_repair.REASON_LF) if r in reasons)
            spans.append((lo, hi, reasons))
            i = j + 1
        return spans

    def _on_hover(self, event) -> None:
        """Al pasar sobre un tramo poco confiable, explica por que (tooltip)."""
        span_idx = None
        if self._pan is None and event.inaxes in (self.ax_mag, self.ax_phase) and event.xdata is not None \
                and self.reliable and len(self.reliable) == len(self.freqs):
            for k, (lo, hi, _) in enumerate(self._spans):
                if lo <= event.xdata <= hi:
                    span_idx = k
                    break
            if span_idx is not None and not self._shade:
                # sin sombreado, solo cuando el puntero esta sobre uno de los circulos huecos
                i = self._nearest_index(event.xdata)
                if i is None or self.reliable[i] or \
                        abs(event.inaxes.transData.transform((self.freqs[i], 0.0))[0] - event.x) > 12:
                    span_idx = None
        if span_idx == self._hover_span:
            return
        self._hover_span = span_idx
        if span_idx is None:
            QToolTip.hideText()
            return
        reasons = self._spans[span_idx][2]
        QToolTip.showText(QCursor.pos(), "\n\n".join(phase_repair.REASON_TEXT[r] for r in reasons), self.canvas)

    def _update_shading(self) -> None:
        for artist in self._shade_artists:
            artist.remove()
        self._shade_artists = []
        self._spans = self._unreliable_spans() if self.reliable and len(self.reliable) == len(self.freqs) else []
        self._hover_span = None
        if not self._shade or not self._spans:
            return
        for lo, hi, _ in self._spans:
            for ax in (self.ax_mag, self.ax_phase):
                self._shade_artists.append(ax.axvspan(lo, hi, color=_SHADE_COLOR, alpha=0.2, linewidth=0, zorder=0))

    def reset_view(self) -> None:
        """Vuelve al encuadre automatico (despues de hacer zoom o desplazar)."""
        for ax in (self.ax_mag, self.ax_phase):
            ax.autoscale(True)
            ax.relim()
            ax.autoscale_view()
        self.canvas.draw_idle()

    def _on_scroll(self, event) -> None:
        """Rueda: zoom en frecuencia alrededor del puntero. Con Ctrl: zoom vertical del grafico bajo el puntero."""
        ax = event.inaxes
        if ax not in (self.ax_mag, self.ax_phase) or event.xdata is None or event.ydata is None:
            return
        step = 0.8 if event.button == "up" else 1.25          # < 1 acerca
        if event.key == "control":
            lo, hi = ax.get_ylim()
            y = event.ydata
            ax.set_ylim(y + (lo - y) * step, y + (hi - y) * step)
        else:
            lo, hi = ax.get_xlim()
            x = event.xdata
            ax.set_xlim(x * (lo / x) ** step, x * (hi / x) ** step)
            self._fit_y_to_visible()
        self.canvas.draw_idle()

    def _fit_y_to_visible(self) -> None:
        """Ajusta magnitud y fase a los puntos que quedaron a la vista (medicion y referencia)."""
        lo, hi = self.ax_mag.get_xlim()
        series = ((self.ax_mag, [(self.freqs, self.dbs), self.reference and (self.reference[0], self.reference[1])], 1.0),
                  (self.ax_phase, [(self.freqs, self.phases), self.reference and (self.reference[0], self.reference[2])], 5.0))
        for ax, curves, min_span in series:
            ys = [y for c in curves if c for f, y in zip(*c) if lo <= f <= hi]
            if len(ys) < 2:
                continue                      # zoom entre puntos: no hay nada que ajustar
            ymin, ymax = min(ys), max(ys)
            pad = max(0.08 * (ymax - ymin), 0.5 * min_span)
            ax.set_ylim(ymin - pad, ymax + pad)

    def _on_pan_start(self, event) -> None:
        if event.button == 2 and event.inaxes in (self.ax_mag, self.ax_phase):
            ax = event.inaxes
            self._pan = dict(ax=ax, x=event.x, y=event.y, xlim=ax.get_xlim(), ylim=ax.get_ylim())

    def _on_pan_move(self, event) -> None:
        p = self._pan
        if p is None or event.x is None:
            return
        ax = p["ax"]
        lo, hi = math.log10(p["xlim"][0]), math.log10(p["xlim"][1])
        dx = (p["x"] - event.x) / ax.bbox.width * (hi - lo)
        ax.set_xlim(10 ** (lo + dx), 10 ** (hi + dx))
        ylo, yhi = p["ylim"]
        dy = (p["y"] - event.y) / ax.bbox.height * (yhi - ylo)
        ax.set_ylim(ylo + dy, yhi + dy)
        self.canvas.draw_idle()

    def _on_pan_end(self, event) -> None:
        self._pan = None

    def export_figure(self, path: str) -> None:
        """Guarda el grafico (PNG o PDF segun la extension) con un tamano apto para un informe."""
        figure = self.canvas.figure
        old = figure.get_size_inches().copy()
        figure.set_size_inches(9.0, 6.5, forward=False)
        try:
            figure.savefig(path, dpi=200, facecolor="white")
        finally:
            figure.set_size_inches(*old, forward=False)
            self.canvas.draw_idle()

    def add_point(self, freq_hz: float, db: float, phase_deg: float) -> None:
        self.freqs.append(freq_hz)
        self.dbs.append(db)
        self.phases.append(phase_deg)

        self.line_mag.set_data(self.freqs, self.dbs)
        self.line_phase.set_data(self.freqs, self.phases)

        for ax in (self.ax_mag, self.ax_phase):
            ax.relim()
            ax.autoscale_view()

        self.canvas.draw_idle()

    def finalize_sweep(self, thru=None) -> None:
        """Llamar cuando termina un barrido completo.

        Guarda los datos crudos, repara el signo de la fase con el barrido a la vista, aplica
        (si se da) la calibracion de puente `thru`, marca los puntos poco confiables y calcula
        las frecuencias de corte contra la meseta (no contra un punto aislado).
        """
        if not self.freqs:
            return
        self.raw_dbs = list(self.dbs)
        self.raw_phases = list(self.phases)
        self._process(thru)

    def reprocess(self, thru=None) -> None:
        """Vuelve a procesar el ultimo barrido desde los datos crudos (p. ej. al activar/desactivar el puente)."""
        if not self.raw_phases or len(self.raw_phases) != len(self.freqs):
            return
        self._process(thru)

    def _process(self, thru) -> None:
        repaired = phase_repair.repair_phase(self.raw_dbs, self.raw_phases)
        if thru is not None:
            dbs, phases = thru.apply(self.freqs, self.raw_dbs, repaired)
        else:
            dbs, phases = list(self.raw_dbs), repaired
        self.dbs[:] = dbs
        self.phases[:] = phases
        self.reliable = phase_repair.reliability(self.freqs, self.dbs)
        self._show_processed()

    def load_measurement(self, freqs: list[float], dbs: list[float], phases: list[float],
                         reliable: list[bool] | None = None) -> None:
        """Muestra una medicion guardada (CSV exportado) como si acabara de medirse.

        Los datos del archivo ya estan reparados y corregidos: se muestran tal cual, sin volver a procesarlos
        (por eso no hay datos crudos y la correccion de cero ya no se puede activar o desactivar sobre ella).
        """
        self.clear()
        self.freqs[:] = freqs
        self.dbs[:] = dbs
        self.phases[:] = phases
        if reliable is None or len(reliable) != len(freqs):
            reliable = phase_repair.reliability(freqs, dbs)
        self.reliable = list(reliable)
        self._show_processed()

    def _show_processed(self) -> None:
        """Dibuja self.freqs/dbs/phases con sus puntos poco confiables y deja listo el analisis."""
        self.line_mag.set_data(self.freqs, self.dbs)
        self.line_phase.set_data(self.freqs, self.phases)
        bad = [i for i, ok in enumerate(self.reliable) if not ok]
        self.unrel_mag.set_data([self.freqs[i] for i in bad], [self.dbs[i] for i in bad])
        self.unrel_phase.set_data([self.freqs[i] for i in bad], [self.phases[i] for i in bad])
        self._update_shading()
        for ax in (self.ax_mag, self.ax_phase):
            ax.relim()
            ax.autoscale_view()

        self.detect_btn.setEnabled(True)
        if self._detected:              # el usuario ya pidio el analisis: se actualiza con los datos reprocesados
            self.detect_cutoffs()
        else:
            self._mark_cutoffs([])
            self._update_analysis_readout(None, n_unreliable=len(bad))

    def detect_cutoffs(self) -> None:
        """Analiza los puntos ya medidos: marca las frecuencias de corte (-3 dB), el ancho de banda y Q."""
        if not self.freqs:
            return
        self._detected = True
        ref = analysis.reference_level(self.dbs, self.reliable or None)
        cutoffs = analysis.find_cutoff_frequencies(self.freqs, self.dbs, reference=ref)
        self._mark_cutoffs(cutoffs)
        self._update_analysis_readout(cutoffs, ref, n_unreliable=sum(1 for ok in self.reliable if not ok))

    def _cutoff_is_reliable(self, freq: float) -> bool:
        return analysis.cutoff_is_reliable(self.freqs, self.reliable, freq)

    # ----------------------------------------------------------- Cursores --
    def _nearest_index(self, x_click: float) -> int | None:
        if not self.freqs or x_click <= 0:
            return None

        pos = bisect.bisect_left(self.freqs, x_click)
        candidates = [i for i in (pos - 1, pos) if 0 <= i < len(self.freqs)]
        if not candidates:
            return None

        def log_distance(i: int) -> float:
            f = self.freqs[i]
            if f <= 0:
                return math.inf
            return abs(math.log10(f) - math.log10(x_click))

        return min(candidates, key=log_distance)

    def _on_click(self, event) -> None:
        if event.inaxes not in (self.ax_mag, self.ax_phase) or event.xdata is None:
            return
        if event.button not in (1, 3):
            return

        idx = self._nearest_index(event.xdata)
        if idx is None:
            return

        slot = 0 if event.button == 1 else 1
        self._set_cursor(slot, idx)

    def _set_cursor(self, slot: int, idx: int) -> None:
        for artist in self._cursor_artists[slot]:
            artist.remove()
        self._cursor_artists[slot] = []

        freq, db, phase = self.freqs[idx], self.dbs[idx], self.phases[idx]
        self._cursor_data[slot] = (freq, db, phase)

        color = _CURSOR_COLORS[slot]
        line_mag = self.ax_mag.axvline(freq, color=color, linestyle=":", linewidth=1.2)
        line_phase = self.ax_phase.axvline(freq, color=color, linestyle=":", linewidth=1.2)
        tag = self.ax_mag.text(freq, 0.96, f" {slot + 1}", transform=self.ax_mag.get_xaxis_transform(),
                               color=color, fontsize=11, fontweight="bold", va="top", ha="left", clip_on=True)
        self._cursor_artists[slot] = [line_mag, line_phase, tag]

        self._update_cursor_readout()
        self.canvas.draw_idle()

    def clear_cursors(self) -> None:
        for slot in (0, 1):
            for artist in self._cursor_artists[slot]:
                artist.remove()
            self._cursor_artists[slot] = []
            self._cursor_data[slot] = None
        self._update_cursor_readout()
        self.canvas.draw_idle()

    def _update_cursor_readout(self) -> None:
        c0, c1 = self._cursor_data
        hints = ("Cursor 1: click izquierdo", "Cursor 2: click derecho",
                 "Diferencia: con los dos cursores")
        colors = (*_CURSOR_COLORS, _DELTA_COLOR)
        rows = [None, None, None]
        for slot, c in enumerate((c0, c1)):
            if c is not None:
                rows[slot] = self._readout_row(f"Cursor {slot + 1}", format_freq(c[0]), f"{c[1]:.2f} dB", f"{c[2]:.1f}°")
        if c0 is not None and c1 is not None:
            rows[2] = self._readout_row("Diferencia", format_freq(abs(c1[0] - c0[0])),
                                        f"{c1[1] - c0[1]:+.2f} dB", f"{c1[2] - c0[2]:+.1f}°")
        for i, lab in enumerate(self.cursor_labels):
            lab.setText(rows[i] if rows[i] is not None else hints[i])
            lab.setStyleSheet(_READOUT_STYLE.format(colors[i] if rows[i] is not None else _HINT_COLOR)
                              if rows[i] is not None else f"font-size: 13px; color: {_HINT_COLOR};")

    @staticmethod
    def _readout_row(name: str, freq: str, db: str, phase: str) -> str:
        # columnas de ancho fijo (letra monoespaciada) para que los tres renglones queden alineados
        return f"{name:<10}{freq:>11}{db:>10}{phase:>8}"

    # -------------------------------------------------------- Frec. corte --
    def _mark_cutoffs(self, cutoffs: list[float]) -> None:
        self.clear_cutoffs()

        trans = self.ax_mag.get_xaxis_transform()
        for freq in cutoffs:
            line_mag = self.ax_mag.axvline(freq, color=_CUTOFF_COLOR, linestyle="--", linewidth=1)
            line_phase = self.ax_phase.axvline(freq, color=_CUTOFF_COLOR, linestyle="--", linewidth=1)
            # dentro del eje y recortado a el: fuera del eje, al hacer zoom el diseno se reacomodaba y achicaba
            label = self.ax_mag.text(
                freq,
                0.03,
                format_freq(freq) + " ",
                transform=trans,
                rotation=90,
                va="bottom",
                ha="right",
                fontsize=8.5,
                color=_CUTOFF_COLOR,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=1),
                clip_on=True,
            )
            self._cutoff_artists.extend([line_mag, line_phase, label])

        self.canvas.draw_idle()

    def clear_cutoffs(self) -> None:
        for artist in self._cutoff_artists:
            artist.remove()
        self._cutoff_artists = []
        self.canvas.draw_idle()

    def _update_analysis_readout(self, cutoffs: list[float] | None, reference: float | None = None,
                                 n_unreliable: int = 0) -> None:
        if not cutoffs:
            if cutoffs is None:
                text = "Frecuencia de corte: apreta «Detectar banda / fc» para analizar este barrido"
            else:
                text = ("No se encontro un cruce de -3 dB en este barrido (respuesta plana, o el corte queda "
                        "fuera del rango medido)")
            if n_unreliable:
                text += f" | {n_unreliable} puntos poco confiables (circulos huecos: pasa el mouse para ver el motivo)"
            self.analysis_label.setText(text)
            return

        any_bad = False
        shown = []
        for f in cutoffs:
            ok = self._cutoff_is_reliable(f)
            any_bad |= not ok
            shown.append(format_freq(f) + ("" if ok else "*"))
        ref_txt = f" (ref. {reference:+.1f} dB)" if reference is not None else ""
        text = f"Frecuencias de corte (-3 dB){ref_txt}: {', '.join(shown)}"
        bw = analysis.compute_bandwidth(cutoffs)
        if bw is not None:
            text += f" | BW = {format_freq(bw.bandwidth_hz)} · Q = {bw.q:.2f} (fc = {format_freq(bw.f_center)})"
            if any_bad:
                text += " (Q y BW poco confiables)"
        if any_bad:
            text += " | * en zona poco confiable"
        if n_unreliable:
            text += f" | {n_unreliable} puntos poco confiables (circulos huecos: pasa el mouse para ver el motivo)"
        self.analysis_label.setText(text)
