#define AppName "ConectaTudo 1.1"
#define AppVersion "1.1"
#define AppExe "ConectaTudo-Windows-1.1.exe"
[Setup]
AppId={{3D729CC9-37DD-4378-B3B2-5DB920743C15}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Projeto ConectaTudo
DefaultDirName={localappdata}\Programs\ConectaTudo-1.1
DefaultGroupName=ConectaTudo 1.1
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ConectaTudo-Setup-1.1
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\ConectaTudo 1.1"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\ConectaTudo 1.1"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Criar atalho na área de trabalho"; Flags: unchecked
[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir ConectaTudo"; Flags: nowait postinstall skipifsilent
