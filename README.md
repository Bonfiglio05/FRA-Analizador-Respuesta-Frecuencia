# Analizador de Respuesta en Frecuencia - App de PC

Aplicacion de escritorio (Python + PySide6) para el proyecto de Analizador de Respuesta en
Frecuencia (FRA). Recibe por USB (puerto serie virtual) los datos de frecuencia, magnitud (dB)
y fase que mide el ESP32, permite configurar el barrido (rango de frecuencias y cantidad de
puntos) y grafica el diagrama de Bode en tiempo real.

## Descargar e instalar (Windows)

Para usar la aplicación no hace falta instalar Python: descargá `FRA_Instalador_<versión>.exe` desde la sección
**Releases** de este repositorio y ejecutalo. Las instrucciones (driver del instrumento, primeros pasos,
aviso de Windows SmartScreen) están en [`Instalador/README.md`](Instalador/README.md).

## Ejecutar desde el código

Para modificar la aplicación o probarla sin el instalador. Requiere Python 3.10 o superior.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```bash
python run.py
```

O con doble click en **iniciar_app.bat**, que usa el Python de `.venv` si existe (no hace falta activar el
entorno). En Git Bash el entorno se activa con `source .venv/Scripts/activate` (barras normales).

- Elegi el puerto serie del ESP32 (aparece como puerto COM del conversor CH340) y apreta
  **Conectar**.
- **Calibrar** (una sola vez por montaje): puentea la entrada con la salida del DUT con los mismos
  cables que vas a usar y apreta **Calibrar** (unos 50 s).
- Configura el rango de frecuencias, la cantidad de puntos y la escala (lineal o logaritmica),
  y apreta **Iniciar barrido**.
- Con el barrido en pantalla, **Detectar banda / fc** analiza los puntos medidos y marca la frecuencia de corte
  (-3 dB) o la banda, con su ancho de banda y Q. No se marca nada solo.
- Cursores: click izquierdo = cursor 1 (rojo), click derecho = cursor 2 (violeta); la diferencia
  aparece en un tercer renglon (turquesa).
- **Archivo**: exporta los datos (CSV, columnas `freq_hz, db, phase_deg, confiable`) o el grafico (PNG o PDF).
  **Abrir medicion (CSV)** vuelve a cargar un CSV exportado como si fuera una medicion: se pueden usar los
  cursores, *Detectar banda / fc*, el zoom y exportarlo de nuevo. Los datos se muestran tal como se guardaron
  (ya llevan la correccion de cero y la reparacion de signo); los CSV sin columna `confiable` (versiones
  anteriores) marcan los puntos poco confiables con la regla actual.
- **Ver** (opciones avanzadas):
  - *Sombrear zona poco confiable*: marca en gris los tramos poco confiables (se recuerda entre sesiones).
  - *Restablecer zoom*. En el grafico, la rueda hace zoom en frecuencia alrededor del puntero, Ctrl + rueda
    hace zoom vertical y arrastrar con el boton del medio desplaza la vista.
  - *Curva de referencia*: deja el barrido actual (o un CSV exportado antes) en gris de fondo para comparar
    con las mediciones siguientes, p. ej. antes y despues de cambiar un componente.
  - *Registro de comunicacion*, para depurar.
### Calibracion

Calibrar hace dos cosas: ajusta fase y dB a 1 MHz (CAL del firmware) y mide el puente de 100 Hz a
10 MHz. Con el DUT puenteado el instrumento deberia leer 0 dB y 0°; lo que lee es su error
sistematico (residuo de fase de ~2°, retardo del camino de senal de ~6 ns, que a 10 MHz son ~23°, y el
retardo de tus cables). Esa lectura de cero se resta de cada medicion (**correccion de cero**). La casilla
permite ver la medicion sin compensar. Vuelve a calibrar si cambias los cables. No corrige el error que
depende del nivel de la senal (DUT que atenua o amplifica).
### Que confianza tiene cada punto

- La app **repara el signo de la fase** al terminar el barrido (`phase_repair.py`): los saltos reales de
  180° (p. ej. un notch) se respetan y los errores de signo aislados se corrigen.
- Los puntos dibujados como **circulos huecos** son poco confiables: magnitud por debajo de -20 dB (piso
  del detector, ~ -25 dB), o por debajo de 700 Hz cuando el DUT cambia el nivel mas de 3 dB.
- Las frecuencias de corte se miden respecto de la meseta; las que caen en una zona poco confiable van con `*`.

## Protocolo de comunicacion

El formato de los mensajes por UART entre la PC y el ESP32 esta definido en
[`PROTOCOL.md`](PROTOCOL.md). Firmware y app de PC deben respetar ese contrato.

## Estructura del proyecto

```
src/fra_app/
    protocol.py          # armado/parseo de los mensajes del protocolo
    backend.py            # interfaz comun (senales Qt) para las fuentes de datos
    serial_backend.py     # backend real: habla con el ESP32 por puerto serie
    analysis.py           # frecuencias de corte, ancho de banda, Q
    phase_repair.py       # reparacion del signo de la fase y marcado de puntos poco confiables
    thru_calibration.py   # calibracion de puente por barrido completo
    curve_io.py           # lectura de curvas CSV (referencia)
    gui/
        main_window.py     # ventana principal
        bode_plot.py        # grafico de Bode (magnitud + fase)
tests/                    # python -m unittest discover -s tests
Instalador/               # genera el instalador de Windows (ver Instalador/README.md)
```

## Licencia

Software libre bajo la licencia [MIT](LICENSE): podés usarlo, modificarlo y redistribuirlo conservando el aviso
de autoría.
