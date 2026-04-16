Option Explicit

Dim WshShell, FSO, ProjectDir
Dim oExec, sOut, PID, arr

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 关闭所有 Python 进程
On Error Resume Next
WshShell.Run "taskkill /F /IM python.exe", 0, True
On Error GoTo 0

' 删除 Python 缓存目录（确保加载最新代码）
On Error Resume Next
Dim PyCacheDir
PyCacheDir = ProjectDir & "\__pycache__"
If FSO.FolderExists(PyCacheDir) Then
    FSO.DeleteFolder PyCacheDir
End If
On Error GoTo 0

' 等待端口释放
WScript.Sleep 2000

' 启动服务
WshShell.CurrentDirectory = ProjectDir
WshShell.Run "python -X utf8 ads_manager.py", 1, False

' 等待服务启动（固定等待8秒）
WScript.Sleep 8000

' 打开浏览器
On Error Resume Next
WshShell.Run "http://localhost:5055/launcher"
On Error GoTo 0

Set WshShell = Nothing
Set FSO      = Nothing
