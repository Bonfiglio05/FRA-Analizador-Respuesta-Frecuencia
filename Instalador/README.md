# FRA - Instalador de la aplicación de PC

Aplicación de escritorio para el **Analizador de Respuesta en Frecuencia (FRA)**: se conecta al instrumento por USB,
barre un rango de frecuencias y grafica el diagrama de Bode (magnitud y fase) del circuito que estés midiendo.

Este instalador no requiere tener Python ni instalar nada más.

## Instalación

**Requisitos:** Windows 10 u 11 de 64 bits. No hace falta ser administrador.

1. Descargá `FRA_Instalador_<versión>.exe` (el de la versión más reciente) desde la sección **Releases** de este repositorio.
2. Ejecutalo y seguí el asistente. Se instala solo para tu usuario y puede crear un acceso directo en el escritorio.
3. Abrí **FRA** desde el menú Inicio (o el escritorio).

Para desinstalarlo: *Configuración > Aplicaciones > FRA*.

### Si Windows muestra "Windows protegió su PC"

El instalador no está firmado digitalmente (la firma tiene costo), así que Windows SmartScreen puede advertirlo.
Hacé click en **Más información** y después en **Ejecutar de todas formas**.

### Driver del instrumento (una sola vez)

El instrumento se conecta por USB-C y aparece como un puerto COM (conversor CH340). Windows 10 y 11 suelen instalar
el driver solos al enchufarlo. Si en la aplicación no aparece ningún puerto, instalá el driver **CH340 / CH341SER**
del fabricante (WCH) y apretá **Actualizar** en la aplicación.

## Primeros pasos

1. Conectá el instrumento, elegí el puerto en la aplicación y apretá **Conectar**.
2. **Calibrar:** puenteá la entrada con la salida del DUT con **los mismos cables** que vas a usar en la medición y
   apretá **Calibrar** (tarda unos 50 s). Con **Corrección de cero** marcada se compensan los cables y el propio
   instrumento; si cambiás los cables, volvé a calibrar.
3. Conectá tu circuito, elegí **Desde**, **Hasta**, los **Puntos** y la **Escala**, y apretá **Iniciar barrido**.
4. Sobre el gráfico:
   - **Cursores:** click izquierdo (cursor 1) y click derecho (cursor 2); la diferencia aparece abajo.
   - **Detectar banda / fc:** marca la frecuencia de corte (−3 dB) o la banda, con su ancho de banda y Q.
   - **Zoom:** rueda del mouse (Ctrl + rueda para el eje vertical); el botón del medio desplaza.
5. **Archivo:** exportá los datos (CSV) o el gráfico (PNG o PDF), o volvé a abrir un CSV exportado para analizarlo.
   **Ver > Curva de referencia** deja una curva gris de fondo para comparar antes y después de un cambio.

### Cómo leer la medición

- Los círculos huecos (y la zona gris, si activás *Ver > Sombrear zona poco confiable*) son puntos poco confiables.
  Pasá el mouse para ver el motivo: nivel por debajo de −20 dB (el detector llega a su piso, ≈ −25 dB) o baja frecuencia
  (< 700 Hz) con atenuación.
- Si una frecuencia de corte va con `*`, cae en una zona poco confiable.

## Para quien quiera reconstruir el instalador

La carpeta `construccion/` (`fra.spec`, `instalador.iss`, `construir.bat`, `requirements-build.txt`) genera el
instalador a partir del código de la aplicación (la carpeta que contiene `run.py` y `src/`). Hace falta Python e
[Inno Setup 6](https://jrsoftware.org/isinfo.php); el script instala las dependencias de la aplicación y PyInstaller
si faltan.

```
construccion\construir.bat ruta\a\la\carpeta\de\la\aplicacion
```

Empaqueta la aplicación con PyInstaller y deja `FRA_Instalador_<versión>.exe` en la raíz de este repositorio (el
`.gitignore` lo excluye: se sube como *Release*). La versión está en `construccion/instalador.iss` (`VersionApp`).
