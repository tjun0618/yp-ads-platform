Option Explicit

Dim WshShell, FSO, ProjectDir
Dim oExec, sOut, PID, arr

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 关闭端口 5055 的进程
On Error Resume Next
Set oExec = WshShell.Exec("netstat -ano | findstr :5055 | findstr LISTENING")
Do While oExec.Status = 0
    WScript.Sleep 100
Loop
sOut = oExec.StdOut.ReadAll
If Len(sOut) > 0 Then
    arr = Split(Trim(sOut))
    If UBound(arr) >= 4 Then
        PID = arr(UBound(arr))
        If IsNumeric(PID) Then
            WshShell.Run "taskkill /F /PID " & PID, 0, True
        End If
    End If
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
