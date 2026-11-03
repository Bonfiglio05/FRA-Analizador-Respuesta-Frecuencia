"""Icono de la aplicacion, dibujado por codigo: una curva de Bode (magnitud arriba, fase abajo).

Se usa para la ventana y, a traves de Instalador/construccion/generar_icono.py, para el .ico del ejecutable.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

SIZES = (16, 24, 32, 48, 64, 128, 256)

_MAG_COLOR = QColor("#5aa0ff")      # azul, como la curva de magnitud de la aplicacion
_PHASE_COLOR = QColor("#ff9f45")    # naranja, como la de fase


def _curve(y_of, x0: float = 38.0, x1: float = 218.0, n: int = 60) -> QPainterPath:
    """Curva de un pasa-bajos de 1.er orden entre 0,06 fc y 16 fc (eje de frecuencia logaritmico)."""
    path = QPainterPath()
    for i in range(n + 1):
        t = i / n
        f = 10 ** (-1.2 + 2.4 * t)
        pt = QPointF(x0 + (x1 - x0) * t, y_of(f))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    return path


def _draw(p: QPainter, size: int) -> None:
    """Dibuja el icono en un lienzo virtual de 256 x 256 escalado a `size`."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 256.0, size / 256.0)

    fondo = QLinearGradient(0, 0, 0, 256)
    fondo.setColorAt(0.0, QColor("#2b3d52"))
    fondo.setColorAt(1.0, QColor("#141d29"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fondo)
    p.drawRoundedRect(QRectF(6, 6, 244, 244), 52, 52)

    # separador entre las dos graficas
    p.setPen(QPen(QColor(255, 255, 255, 45), 4))
    p.drawLine(QPointF(34, 128), QPointF(222, 128))

    ancho = 20 if size <= 48 else 15      # mas gruesa en tamanos chicos para que se lea
    mag = _curve(lambda f: 52 + (10 * math.log10(1 + f * f)) / 21 * 58)
    fase = _curve(lambda f: 148 + math.degrees(math.atan(f)) / 90 * 72)
    for path, color in ((mag, _MAG_COLOR), (fase, _PHASE_COLOR)):
        pen = QPen(color, ancho)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


def render_image(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    _draw(p, size)
    p.end()
    return image


def app_icon() -> QIcon:
    """QIcon con varios tamanos (requiere que exista una QApplication)."""
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(QPixmap.fromImage(render_image(size)))
    return icon
