"""Genera icono.ico (el icono del ejecutable y del instalador) con el mismo dibujo que usa la ventana.

Solo hace falta volver a ejecutarlo si se cambia el dibujo en src/fra_app/icon.py:
    python generar_icono.py
"""

import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from fra_app.icon import SIZES, render_image  # noqa: E402


def png_bytes(size: int) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    render_image(size).save(buf, "PNG")
    return bytes(data)


def main() -> None:
    app = QGuiApplication([])  # noqa: F841 (necesario para dibujar)
    imagenes = [(s, png_bytes(s)) for s in SIZES]
    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))      # .ico con imagenes PNG
    offset = 6 + 16 * len(imagenes)
    entradas, datos = b"", b""
    for size, png in imagenes:
        lado = 0 if size >= 256 else size                    # 0 = 256 px
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), offset + len(datos))
        datos += png
    destino = os.path.join(AQUI, "icono.ico")
    with open(destino, "wb") as f:
        f.write(cabecera + entradas + datos)
    print(f"{destino}: {len(imagenes)} tamanos ({', '.join(str(s) for s in SIZES)})")


if __name__ == "__main__":
    main()
