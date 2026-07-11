#define MyAppName "Just DNA Lite"
#ifndef APP_VERSION
  #define APP_VERSION "0.3.15"
#endif
#define MyAppVersion APP_VERSION
#define MyAppPublisher "dna-seq"
#define MyAppURL "https://github.com/dna-seq/just-dna-lite"
#define MyAppExeName "just-dna-lite.bat"

[Setup]
AppId={{B9F4C2A1-7D3E-4A5B-8C1F-2E6D9A3B7C4D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\JustDNALite
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=JustDNALite-{#MyAppVersion}-Setup
SetupIconFile=icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; uv binary
Source: "uv.exe"; DestDir: "{app}"; Flags: ignoreversion

; Application source (excluding dev/runtime artifacts)
Source: "..\pyproject.toml"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\uv.lock"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\modules.yaml"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\.python-version"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\.env.template"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\dagster.yaml.template"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\src\*"; DestDir: "{app}\app\src"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\just-dna-pipelines\*"; DestDir: "{app}\app\just-dna-pipelines"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,.ruff_cache"
Source: "..\webui\*"; DestDir: "{app}\app\webui"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,.web,.ruff_cache,.states,.venv"
Source: "..\images\*"; DestDir: "{app}\app\images"; Flags: ignoreversion recursesubdirs createallsubdirs

; Launcher script
Source: "just-dna-lite.bat"; DestDir: "{app}"; Flags: ignoreversion

; Icon
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent shellexec

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app\.venv"
Type: filesandordirs; Name: "{app}\app\data"
Type: filesandordirs; Name: "{app}\app\.web"
Type: filesandordirs; Name: "{app}\app\.states"
