Option Explicit

Dim WshShell, FSO, ProjectDir

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 关闭端口 5055 的进程
On Error Resume Next
Dim oExec, sOut, PIDs, PID
Set oExec = WshShell.Exec("netstat -ano | findstr :5055 | findstr LISTENING")
Do While oExec.Status = 0
    WScript.Sleep 100
Loop
sOut = oExec.StdOut.ReadAll
If Len(sOut) > 0 Then
    ' 简单提取最后一列的 PID
    Dim arr
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

' 等待服务启动
WScript.Sleep 5000

' 打开浏览器
WshShell.Run "http://localhost:5055/launcher"

Set WshShell = Nothing
Set FSO      = Nothing
