Option Explicit

Dim WshShell, FSO, ProjectDir

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 切换到项目目录
WshShell.CurrentDirectory = ProjectDir

' 启动服务（新窗口）
WshShell.Run "cmd.exe /k python -X utf8 ads_manager.py", 1, False

' 等待服务启动
WScript.Sleep 8000

' 打开浏览器
WshShell.Run "http://localhost:5055/launcher"

Set WshShell = Nothing
Set FSO      = Nothing
