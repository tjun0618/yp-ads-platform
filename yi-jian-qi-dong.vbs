Option Explicit

Dim WshShell, FSO, ProjectDir, oExec, sOut, pids, pid

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 切换到项目目录
WshShell.CurrentDirectory = ProjectDir

' ========================================
' Step 1: 关闭所有监听 5055 端口的进程
' ========================================
Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr :5055 | findstr LISTENING")
sOut = oExec.StdOut.ReadAll

If Len(sOut) > 0 Then
    ' 解析输出，提取 PID（最后一列）
    Dim lines, line, parts
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

' ========================================
' Step 2: 关闭所有 Python 进程
' ========================================
On Error Resume Next
WshShell.Run "taskkill /F /IM python.exe", 0, True
On Error GoTo 0

' ========================================
' Step 3: 删除 Python 缓存
' ========================================
Dim PyCacheDir
PyCacheDir = ProjectDir & "\__pycache__"
If FSO.FolderExists(PyCacheDir) Then
    On Error Resume Next
    FSO.DeleteFolder PyCacheDir
    On Error GoTo 0
End If

' ========================================
' Step 4: 等待端口释放
' ========================================
WScript.Sleep 2000

' ========================================
' Step 5: 启动服务
' ========================================
WshShell.Run "cmd.exe /k python -X utf8 ads_manager.py", 1, False

' 等待服务启动
WScript.Sleep 8000

' 打开浏览器
WshShell.Run "http://localhost:5055/launcher"

Set WshShell = Nothing
Set FSO      = Nothing
