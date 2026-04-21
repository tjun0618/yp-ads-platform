Option Explicit

Dim WshShell, FSO, ProjectDir, oExec, sOut, pid
Dim lines, line, parts

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ProjectDir

' Step 1: Kill processes on port 5055
Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr :5055 | findstr LISTENING")
sOut = oExec.StdOut.ReadAll

If Len(sOut) > 0 Then
    lines = Split(sOut, vbCrLf)
    For Each line In lines
        If Len(Trim(line)) > 0 Then
            parts = Split(Trim(line))
            If UBound(parts) >= 4 Then
                pid = parts(UBound(parts))
                If IsNumeric(pid) Then
                    On Error Resume Next
                    WshShell.Run "taskkill /F /PID " & pid, 0, True
                    On Error GoTo 0
                End If
            End If
        End If
    Next
End If

' Step 2: Kill all Python processes
On Error Resume Next
WshShell.Run "taskkill /F /IM python.exe", 0, True
On Error GoTo 0

' Step 3: Delete Python cache
Dim PyCacheDir
PyCacheDir = ProjectDir & "\__pycache__"
If FSO.FolderExists(PyCacheDir) Then
    On Error Resume Next
    FSO.DeleteFolder PyCacheDir
    On Error GoTo 0
End If

' Step 4: Wait for port release
WScript.Sleep 2000

' Step 5: Start Flask service
WshShell.Run "cmd.exe /k python -X utf8 ads_manager.py", 1, False

' Step 6: Wait and open browser
WScript.Sleep 8000
WshShell.Run "cmd /c start http://127.0.0.1:5055/", 0, False

Set WshShell = Nothing
Set FSO      = Nothing
