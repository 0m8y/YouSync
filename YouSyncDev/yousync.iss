#define MyAppName "YouSync"
#define MyAppVersion "1.0"
#define MyAppExeName "yousync.exe"

[Setup]
AppId={{8e1eebc2-2a55-4d1c-82ed-9e384958c8ed}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=../
OutputBaseFilename=YouSyncInstaller
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
Source: "yousync.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\gui\assets\images\yousync.ico"

[UninstallDelete]
Type: files; Name: "{app}\yousync.exe"
