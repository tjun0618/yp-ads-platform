Dim WshShell, FSO, ProjectDir

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 调用批处理脚本关闭旧进程并启动新服务（隐藏窗口）
WshShell.Run """" & ProjectDir & "\restart_server.bat""", 0, True
