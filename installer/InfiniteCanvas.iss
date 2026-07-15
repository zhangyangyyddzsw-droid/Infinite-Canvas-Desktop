#define MyAppName "Infinite Canvas"
#ifndef MyAppVersion
#define MyAppVersion "dev"
#endif
#define MyAppPublisher "Infinite Canvas community desktop build"
#define MyAppExeName "InfiniteCanvas.exe"
#define ProjectRoot SourcePath + "\.."

[Setup]
AppId={{7532229D-E42C-488A-888D-A74CFE887596}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\InfiniteCanvas
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile={#ProjectRoot}\LICENSE
OutputDir={#ProjectRoot}\dist-installer
OutputBaseFilename=InfiniteCanvas-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "{#ProjectRoot}\dist\InfiniteCanvas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
