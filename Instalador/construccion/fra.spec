# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para la app del FRA. Se usa desde construir.bat (no hace falta tocarla).

import os

# Carpeta de la app (donde estan run.py y src/). construir.bat la pasa en FRA_APP_DIR; por defecto, dos niveles
# arriba (Instalador/construccion dentro de la carpeta App del proyecto).
APP = os.path.abspath(os.environ.get("FRA_APP_DIR") or os.path.join(SPECPATH, "..", ".."))

# Qt: la app solo usa QtCore / QtGui / QtWidgets. Se excluye el resto para que el instalador pese menos.
EXCLUIR = [
    "tkinter",
    "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_tk",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuick3D", "PySide6.QtQml",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors", "PySide6.QtWebSockets", "PySide6.QtWebChannel",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtHelp",     # QtSvg lo necesita matplotlib
    "PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtRemoteObjects",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech", "PySide6.QtSpatialAudio", "PySide6.QtHttpServer", "PySide6.QtGraphs",
]

a = Analysis(
    [os.path.join(APP, "run.py")],
    pathex=[os.path.join(APP, "src")],
    # matplotlib carga los backends de exportacion por nombre (savefig .pdf / .png): PyInstaller no los ve solo
    hiddenimports=["matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_agg",
                   "matplotlib.backends.backend_pdf"],
    excludes=EXCLUIR,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FRA",
    console=False,          # app de ventana: sin consola negra
    icon=os.path.join(SPECPATH, "icono.ico"),
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FRA",
)
