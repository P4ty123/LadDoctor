; Programma di installazione di LagDoctor (Inno Setup 6)
; Uso: ISCC.exe /DAppVer=5.7.0 packaging\installer.iss   (dopo PyInstaller: serve dist\LagDoctor)

#ifndef AppVer
  #define AppVer "0.0.0"
#endif

[Setup]
AppId={{8F3C2A51-6B7E-4E2D-9C1A-5D4B3E2F1A07}
AppName=LagDoctor
AppVersion={#AppVer}
AppVerName=LagDoctor {#AppVer}
AppPublisher=P4ty123
AppPublisherURL=https://github.com/P4ty123/LadDoctor
AppUpdatesURL=https://github.com/P4ty123/LadDoctor/releases
DefaultDirName={autopf}\LagDoctor
DefaultGroupName=LagDoctor
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=LagDoctor-Setup-{#AppVer}
SetupIconFile=lagdoctor.ico
UninstallDisplayIcon={app}\LagDoctor.exe
UninstallDisplayName=LagDoctor
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; durante gli aggiornamenti LagDoctor viene chiuso da solo
CloseApplications=force
RestartApplications=no

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; aggiornamento: tolgo le librerie della versione precedente prima di copiare le nuove
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\LagDoctor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\LagDoctor"; Filename: "{app}\LagDoctor.exe"
Name: "{autoprograms}\LagDoctor - Autodiagnosi (sola lettura)"; Filename: "{app}\LagDoctorHelper.exe"; Parameters: "--autodiagnosi"
Name: "{autoprograms}\LagDoctor - Ripristina tutte le modifiche"; Filename: "{app}\LagDoctorHelper.exe"; Parameters: "--ripristina"
Name: "{autodesktop}\LagDoctor"; Filename: "{app}\LagDoctor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LagDoctor.exe"; Description: "{cm:LaunchProgram,LagDoctor}"; Flags: nowait postinstall skipifsilent
; aggiornamento automatico (installazione silenziosa): riapro LagDoctor da solo
Filename: "{app}\LagDoctor.exe"; Flags: nowait; Check: IsUpdate

[UninstallRun]
Filename: "{app}\LagDoctorHelper.exe"; Parameters: "--disinstalla {code:RestoreParam}"; Flags: runhidden waituntilterminated; RunOnceId: "LagDoctorPulizia"

[Code]
var
  RestoreAll: Boolean;

function IsUpdate: Boolean;
begin
  Result := Pos('/AGGIORNAMENTO', Uppercase(GetCmdTail)) > 0;
end;

function InitializeUninstall(): Boolean;
begin
  RestoreAll := False;
  if not UninstallSilent then
    RestoreAll := MsgBox('Vuoi annullare anche tutte le modifiche fatte da LagDoctor?' + #13#10#13#10 +
      'Si = Windows torna com''era prima di LagDoctor' + #13#10 +
      'No = le ottimizzazioni applicate restano attive' + #13#10#13#10 +
      'In ogni caso la game mode viene spenta e il Timer Resolution annullato.',
      mbConfirmation, MB_YESNO) = IDYES;
  Result := True;
end;

function RestoreParam(Param: String): String;
begin
  if RestoreAll then
    Result := '--ripristina'
  else
    Result := '';
end;
