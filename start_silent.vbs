Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

WshShell.CurrentDirectory = FSO.GetParentFolderName(WScript.ScriptFullName)

' 先关闭旧进程（通过端口 5055 查找）
On Error Resume Next
Dim oExec, sOut, lines, line, parts, pid
Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr :5055 | findstr LISTENING")
If Err.Number = 0 Then
    Do While oExec.Status = 0
        WScript.Sleep 200
    Loop
    sOut = oExec.StdOut.ReadAll()
    
    If Len(sOut) > 0 And InStr(sOut, "5055") > 0 Then
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
        WScript.Sleep 2000
    End If
End If
On Error GoTo 0

' 启动新服务
WshShell.Run "cmd /c start """" python -X utf8 ads_manager.py", 0, False
