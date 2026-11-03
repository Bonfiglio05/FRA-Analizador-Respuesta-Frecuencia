# Protocolo de comunicación PC ↔ ESP32

UART simple sobre el puente USB-UART (CH340K), texto ASCII, una instrucción/dato por línea
terminada en `\n`. Pensado para poder debuggearse a mano con el monitor serie de Arduino/PlatformIO.

- **Baudrate:** `115200` 8N1
- **Codificación:** ASCII, campos separados por coma, línea terminada en `\n` (`\r\n` también se acepta)

Este documento es el contrato entre el firmware del ESP32 y la app de PC. Si el firmware
cambia el formato, actualizar `fra_app/protocol.py` (lado PC) junto con este archivo.
Versión del firmware que describe: **1.4**.

## PC → ESP32 (comandos)

| Comando | Formato | Descripción |
|---|---|---|
| Identificación | `ID?\n` | La PC lo manda al conectar. El ESP32 responde `ID,FRA,<version>\n` |
| Calibrar | `CAL\n` | Con el DUT puenteado (entrada=salida), busca la fase de referencia y el offset de dB que dejan la lectura en 0. Tarda unos 4-5 segundos. El ESP32 responde `CAL_DONE,<fase_offset_deg>,<db_offset>\n`, o `ERR,...` si no ve el puente |
| Iniciar barrido | `START,<f_start_hz>,<f_stop_hz>,<n_points>,<escala>\n` | `escala` es `LIN` o `LOG`. Ej: `START,10,100000,201,LOG\n` |
| Detener barrido | `STOP\n` | Aborta el barrido en curso |
| Continuidad de fase | `CONT,<0\|1>\n` / `CONT?\n` | Activa (`1`) o desactiva (`0`, valor por defecto) la regla de continuidad secuencial de la v1.3. Responde `CONT,<0\|1>\n`. La app **no** la usa: repara los signos ella misma (ver más abajo) |

Comandos de diagnóstico (solo si el firmware se compila con `FRA_TESTS 1`): `VT` (valida la medición de fase
emulando DUTs de ±180° con el corrimiento de los DDS) y `PWR` (prueba del apagado de los DDS).

## ESP32 → PC (respuestas / datos)

| Mensaje | Formato | Descripción |
|---|---|---|
| Identificación | `ID,FRA,<version>\n` | Respuesta a `ID?` |
| Calibración lista | `CAL_DONE,<fase_offset_deg>,<db_offset>\n` | Respuesta a `CAL`. Informativo, no hace falta que la app haga nada con los valores más que mostrarlos |
| Dato de un punto | `DATA,<indice>,<freq_hz>,<db>,<fase_deg>\n` | Uno por cada frecuencia medida durante el barrido. `indice` arranca en 0. La fase es **cruda** (ver más abajo) |
| Barrido iniciado | `SWEEP_START,<n_points>\n` | Confirma que arrancó, informa cuántos puntos van a llegar |
| Barrido terminado | `SWEEP_DONE\n` | Fin normal del barrido |
| Barrido abortado | `SWEEP_ABORTED\n` | Confirma que se detuvo por `STOP` |
| Estado de continuidad | `CONT,<0\|1>\n` | Respuesta a `CONT` / `CONT?` |
| Error | `ERR,<mensaje>\n` | Error genérico (parámetros inválidos, calibración fallida, etc.) |

## Calibración

La calibración NO se guarda en el ESP32 entre encendidos (a propósito - hay que puentear
entrada/salida del DUT y mandar `CAL` cada vez que se empieza a usar el equipo). Mientras se
calibra, el ESP32 prueba los 32 pasos de fase posibles del AD9850 (11.25° cada uno) a 1 MHz y
detecta los dos cruces por cero de la lectura (a ±90° de la superposición); el punto medio da la
fase de superposición con mejor resolución que un paso, y además se estiman la pendiente y el offset
vertical de la lectura. De paso mide el offset de dB. Todo queda aplicado automáticamente para los
`START` siguientes - no hace falta mandarlo de vuelta.

## Medición de fase

El AD8302 solo entrega el módulo del desfase, `|φ|`. En cada punto se hacen dos lecturas: A con los
DDS superpuestos (da `|φ|`) y B con el DDS de referencia corrido +90° (da `φ` con signo cuando
`|φ| < 90°`). El signo de B resuelve el signo de la fase. Convención: **fase negativa = el DUT atrasa**
respecto de la excitación. Tras el barrido (y tras `CAL`) los DDS se apagan (power-down).

**Desde la v1.4 el firmware envía la fase cruda**: no aplica ninguna regla de continuidad. El signo de B
es ambiguo cerca de ±90° y con la señal cerca del piso del detector (≈ −25 dB), y una regla que mire solo
el punto anterior no puede distinguir ese error de un salto real de 180° en un cero de transmisión (por
ejemplo un notch). La app de PC repara los signos con el barrido completo a la vista
(`fra_app/phase_repair.py`): elige el camino de fase más suave, y permite saltos de 180° solo en los
mínimos profundos de magnitud o en el piso del detector.

Puntos poco confiables (la app los dibuja con círculos huecos y los exporta con `confiable = 0`):
magnitud por debajo de −20 dB, o magnitud que se aparta más de 3 dB del nivel de referencia por debajo
de 700 Hz (el instrumento exagera la diferencia de nivel entre sus dos canales a baja frecuencia).

**Primer punto:** al empezar un barrido los DDS se encienden en la primera frecuencia, se esperan 1000 ms
y se descarta una lectura completa; así el primer punto informado ya es válido (la v1.3 lo informaba
0,3-0,4 dB corrido).

## Ejemplo de intercambio

```
PC   -> START,20,200000,101,LOG
ESP  -> SWEEP_START,101
ESP  -> DATA,0,20.0,-1.2,3.4
ESP  -> DATA,1,23.8,-1.3,3.9
...
ESP  -> DATA,100,200000.0,-42.1,-88.7
ESP  -> SWEEP_DONE
```

## Notas de implementación para el firmware

- Cada línea debe salir con `Serial.print(...); Serial.print(",");` ... `Serial.println(...)`
  para que termine en `\n`.
- Frecuencias en Hz (float), dB y fase en grados (float), con el punto decimal (no coma).
- Si el barrido es `LOG`, los puntos deben ir espaciados logarítmicamente entre `f_start` y `f_stop`.
- Ante un `STOP` en medio del barrido, dejar de mandar `DATA` y mandar `SWEEP_ABORTED` en vez de `SWEEP_DONE`.
- La app ignora las líneas que no reconoce (por ejemplo las de diagnóstico).
