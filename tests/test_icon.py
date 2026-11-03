"""El icono dibujado por codigo: todos los tamanos se generan y no quedan vacios."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from fra_app.icon import SIZES, app_icon, render_image  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])


class IconTests(unittest.TestCase):
    def test_every_size_renders_with_a_visible_drawing_and_transparent_corners(self):
        for size in SIZES:
            image = render_image(size)
            self.assertEqual((image.width(), image.height()), (size, size))
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0, "las esquinas son transparentes")
            opaque = sum(1 for x in range(size) for y in range(size) if image.pixelColor(x, y).alpha() > 200)
            self.assertGreater(opaque, size * size * 0.6, "el fondo del icono se dibuja")

    def test_app_icon_has_all_sizes(self):
        icon = app_icon()
        self.assertFalse(icon.isNull())
        self.assertGreaterEqual(len(icon.availableSizes()), len(SIZES))


if __name__ == "__main__":
    unittest.main()
