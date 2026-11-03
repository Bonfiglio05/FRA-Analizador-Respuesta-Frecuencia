import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow
from .icon import app_icon


def main() -> None:
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
