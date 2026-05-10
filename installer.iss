#define AppName "Externo Browser"
#define AppVersion "1.0.0"
#define AppExe "Externo Browser.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Externo
AppPublisherURL=https://externo.browser
AppSupportURL=https://externo.browser
AppUpdatesURL=https://externo.browser
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=Externo Browser Setup
SetupIconFile=assets\logo.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
DisableProgramGroupPage=yes
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
VersionInfoVersion=1.0.0
VersionInfoCompany=Externo
VersionInfoDescription=Externo Browser Installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checked
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checked

[Files]
; Bundle the entire PyInstaller output folder — Python runtime, Qt, DLLs, everything
Source: "dist\Externo Browser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Desktop (only if task selected)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; Register as a default browser candidate (optional, can be removed)
Root: HKCU; Subkey: "Software\Externo Browser"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExe}"; Description: "Launch Externo Browser"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user data folder on uninstall (optional — comment out to keep bookmarks)
; Type: filesandordirs; Name: "{userdocs}\.externo"
