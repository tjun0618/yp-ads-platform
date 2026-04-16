Option Explicit

Dim WshShell, oShortcut, FSO
Dim ProjectDir, VbsPath, DesktopPath, ShortcutPath

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir   = FSO.GetParentFolderName(WScript.ScriptFullName)
VbsPath      = ProjectDir & "\yi-jian-qi-dong.vbs"
DesktopPath  = WshShell.SpecialFolders("Desktop")
ShortcutPath = DesktopPath & "\YP Ads Platform.lnk"

Set oShortcut = WshShell.CreateShortcut(ShortcutPath)
oShortcut.TargetPath       = "wscript.exe"
oShortcut.Arguments        = Chr(34) & VbsPath & Chr(34)
oShortcut.WorkingDirectory = ProjectDir
oShortcut.Description      = "YP Affiliate Ads Platform"
oShortcut.WindowStyle      = 1
oShortcut.Save

MsgBox "Desktop shortcut created!" & vbCrLf & ShortcutPath, vbInformation, "Done"

Set WshShell = Nothing
Set FSO      = Nothing