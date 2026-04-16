Option Explicit

Dim WshShell, FSO, ProjectDir
Dim oExec, sOut, isRunning, i

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 调用批处理脚本关闭旧进程并启动新服务
WshShell.Run """" & ProjectDir & "\restart_server.bat""", 0, True

' 等待服务启动
isRunning = False
For i = 1 To 30
    WScript.Sleep 1000
    On Error Resume Next
    Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr :5055 | findstr LISTENING")
    If Err.Number = 0 Then
        Do While oExec.Status = 0
            WScript.Sleep 200
        Loop
        sOut = oExec.StdOut.ReadAll()
        If Len(sOut) > 0 And InStr(sOut, "5055") > 0 Then
            isRunning = True
            Exit For
        End If
    End If
    On Error GoTo 0
Next

If isRunning Then
    WshShell.Run "http://localhost:5055/launcher"
Else
    WshShell.Popup "Flask timeout (30s), please check manually!", 8, "YP Ads Platform", 16
End If

Set WshShell = Nothing
Set FSO      = Nothing
