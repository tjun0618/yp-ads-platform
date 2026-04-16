Dim WshShell, FSO

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

WshShell.CurrentDirectory = FSO.GetParentFolderName(WScript.ScriptFullName)

' 先关闭旧进程（通过端口 5055 查找并关闭）
On Error Resume Next
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -ano ^| findstr :5055 ^| findstr LISTENING') do taskkill /F /PID %a", 0, True
WScript.Sleep 2000
On Error GoTo 0

' 启动新服务
WshShell.Run "cmd /c start """" python -X utf8 ads_manager.py", 0, False
