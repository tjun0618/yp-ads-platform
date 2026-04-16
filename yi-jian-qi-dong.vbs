Option Explicit

Dim WshShell, FSO, ProjectDir, BatFile

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)
BatFile    = ProjectDir & "\启动服务.bat"

' 启动批处理文件（新窗口）
WshShell.CurrentDirectory = ProjectDir
WshShell.Run "cmd.exe /c """ & BatFile & """", 1, False

' 等待服务启动
WScript.Sleep 10000

' 打开浏览器
On Error Resume Next
WshShell.Run "http://localhost:5055/launcher"
On Error GoTo 0

Set WshShell = Nothing
Set FSO      = Nothing
