; This is the script for Inno Setup

[Setup]
AppName=Black Zero Invoicer
AppVersion=1.0
AppPublisher=Black Zero
DefaultDirName={autopf}\Black Zero Invoicer
DefaultGroupName=Black Zero Invoicer
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=Setup-BlackZeroInvoicer
SetupIconFile=logo.ico
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\BlackZeroInvoicer.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; This tells the installer to grab everything from the folder 
; PyInstaller makes and put it in the user's Program Files.
Source: "dist\BlackZeroInvoicer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; This creates the Start Menu and Desktop shortcuts
Name: "{autoprograms}\Black Zero Invoicer"; Filename: "{app}\BlackZeroInvoicer.exe"; IconFilename: "{app}\logo.ico"
Name: "{autodesktop}\Black Zero Invoicer"; Filename: "{app}\BlackZeroInvoicer.exe"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon