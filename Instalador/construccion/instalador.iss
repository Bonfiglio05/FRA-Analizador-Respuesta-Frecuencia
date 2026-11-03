; Script de Inno Setup para el instalador de la app del FRA.
; Se compila desde construir.bat (que primero genera la carpeta FRA con PyInstaller).

#define NombreApp "FRA - Analizador de Respuesta en Frecuencia"
#define VersionApp "1.0.1"
#ifndef Origen
  #define Origen "build\dist\FRA"
#endif

[Setup]
; Identificador unico de la app: no cambiarlo entre versiones (asi una version nueva actualiza a la anterior)
AppId={{F79E7B2D-3F3E-456A-8B51-7183CE925C37}
AppName={#NombreApp}
AppVersion={#VersionApp}
DefaultDirName={autopf}\FRA
DefaultGroupName=FRA
OutputDir=..
OutputBaseFilename=FRA_Instalador_{#VersionApp}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; instala solo para el usuario actual: no pide permisos de administrador
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\FRA.exe
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "{#Origen}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\FRA"; Filename: "{app}\FRA.exe"
Name: "{autodesktop}\FRA"; Filename: "{app}\FRA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FRA.exe"; Description: "Abrir la aplicacion del FRA"; Flags: nowait postinstall skipifsilent
