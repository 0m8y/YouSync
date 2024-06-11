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
Source: "installer.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "yousync.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "core\*"; DestDir: "{app}\core"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "gui\*"; DestDir: "{app}\gui"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\gui\assets\images\yousync.ico"

[Run]
Filename: "{app}\installer.bat"; Parameters: ""; WorkingDir: "{app}"; Flags: runascurrentuser waituntilterminated

[UninstallDelete]
Type: files; Name: "{app}\yousync.exe"
Type: files; Name: "{app}\yousync.spec"
Type: files; Name: "{app}\requirements.txt"
Type: files; Name: "{app}\installer.bat"
Type: files; Name: "{app}\core\*.*"
Type: files; Name: "{app}\gui\*.*"
Type: files; Name: "{app}\build\*.*"
Type: files; Name: "{app}\dist\*.*"
Type: dirifempty; Name: "{app}\core"
Type: dirifempty; Name: "{app}\gui"
Type: dirifempty; Name: "{app}\build"
Type: dirifempty; Name: "{app}\dist"

	
[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
    if CurUninstallStep = usUninstall then
    begin
        DelTree(ExpandConstant('{app}\core'), True, True, True);
        DelTree(ExpandConstant('{app}\gui'), True, True, True);
        DelTree(ExpandConstant('{app}\build'), True, True, True);
        DelTree(ExpandConstant('{app}\dist'), True, True, True);
    end;
end;