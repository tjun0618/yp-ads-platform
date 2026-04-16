Option Explicit

Dim WshShell, FSO, ProjectDir, ps1Path
Dim oExec, sOut, isRunning, i
Dim lines, line, parts, pid

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)
ps1Path = ProjectDir & "\start_flask.ps1"

' 先关闭旧进程（通过端口 5055 查找）
On Error Resume Next
Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr :5055 | findstr LISTENING")
If Err.Number = 0 Then
    Do While oExec.Status = 0
        WScript.Sleep 200
    Loop
    sOut = oExec.StdOut.ReadAll()
    
    If Len(sOut) > 0 And InStr(sOut, "5055") > 0 Then
        ' 提取 PID 并关闭
        lines = Split(sOut, vbCrLf)
        For Each line In lines
            If InStr(line, "5055") > 0 And Len(Trim(line)) > 0 Then
                parts = Split(Trim(line))
                If UBound(parts) >= 4 Then
                    pid = parts(UBound(parts))
                    If IsNumeric(pid) And Len(pid) > 0 Then
                        WshShell.Run "cmd /c taskkill /F /PID " & pid, 0, True
                    End If
                End If
            End If
        Next
        ' 等待端口释放
        WScript.Sleep 2000
    End If
End If
On Error GoTo 0

' 启动新服务
WshShell.Run "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1Path & """", 0, False

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
