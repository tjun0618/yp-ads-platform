Option Explicit

Dim WshShell, FSO, ProjectDir, oExec, sOut, isRunning, i, ps1Path

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)
ps1Path = ProjectDir & "\start_flask.ps1"

isRunning = False
Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr :5055 | findstr LISTENING")
Do While oExec.Status = 0
    WScript.Sleep 200
Loop
sOut = oExec.StdOut.ReadAll()
If InStr(sOut, "5055") > 0 Then isRunning = True

If Not isRunning Then
    WshShell.Run "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1Path & """", 0, False
    For i = 1 To 30
        WScript.Sleep 1000
        Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr :5055 | findstr LISTENING")
        Do While oExec.Status = 0
            WScript.Sleep 200
        Loop
        sOut = oExec.StdOut.ReadAll()
        If InStr(sOut, "5055") > 0 Then
            isRunning = True
            Exit For
        End If
    Next
End If

If isRunning Then
    WshShell.Run "http://localhost:5055/launcher"
Else
    WshShell.Popup "Flask timeout (30s), please check manually!", 8, "YP Ads Platform", 16
End If

Set WshShell = Nothing
Set FSO      = Nothing