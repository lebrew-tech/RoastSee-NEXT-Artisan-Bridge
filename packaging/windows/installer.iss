#define AppName "RoastSee NEXT for Artisan"
#define AppExe "RoastSeeNEXT-Artisan.exe"
#define BuildDate GetDateTimeString("yyyy.mm.dd", "", "")

[Setup]
AppId=LeBrew.RoastSeeNEXT.Artisan
AppName={#AppName}
AppVersion={#BuildDate}
AppPublisher=LeBrew
DefaultDirName={localappdata}\Programs\RoastSeeNEXT-Artisan
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=yes
DisableProgramGroupPage=yes
AppMutex=Local\LeBrew-RoastSeeNEXT-Artisan
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\..\assets\brand\lebrew.ico
OutputDir=..\..\dist\windows
OutputBaseFilename=RoastSeeNEXT-Artisan-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Files]
Source: "..\..\dist\windows\RoastSeeNEXT-Artisan-Windows-x64\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
