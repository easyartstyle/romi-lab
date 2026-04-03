#define AppName "ROMI Lab"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppPublisher "easyartstyle"
#define AppExeName "ROMILab.exe"
#define AppId "ROMILabDesktop"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ROMI Lab
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=ROMILab-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\VERSION"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить приложение"; Flags: nowait postinstall skipifsilent

