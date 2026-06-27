#define MyAppName "EchoText"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "EchoText"
#define MyAppExeName "EchoText.exe"
#ifndef SourceBuildDir
  #define SourceBuildDir "..\build\windows-dist\EchoText"
#endif
#ifndef OutputDirOverride
  #define OutputDirOverride "..\dist"
#endif

[Setup]
AppId={{D72E67BB-6D07-4D89-A627-EA93C92D6D61}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDirOverride}
OutputBaseFilename=EchoText-Setup-v0.1.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupIconFile=..\assets\branding\EchoText.ico
UninstallDisplayIcon={app}\EchoText.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\branding\EchoText.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\EchoText.ico"; IconIndex: 0
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\EchoText.ico"; IconIndex: 0

[Run]
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall delete rule name=""EchoText LAN"" >nul 2>nul & netsh advfirewall firewall add rule name=""EchoText LAN"" dir=in action=allow program=""{app}\{#MyAppExeName}"" enable=yes profile=private,public remoteip=any"; Flags: runhidden
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall delete rule name=""EchoText LAN"""; Flags: runhidden; RunOnceId: "RemoveEchoTextLanFirewallRule"
