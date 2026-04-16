' 无窗口静默启动 YP Affiliate Ads Platform
' 使用方法：双击此文件，Flask 将在后台静默启动，并自动打开浏览器

Option Explicit

Dim WshShell, FSO, ProjectDir, PythonExe, LauncherHtml
Dim sOut, cmd, waitResult

Set WshShell = CreateObject("WScript.Shell")
Set FSO      = CreateObject("Scripting.FileSystemObject")

' ── 项目目录（与本 .vbs 文件同目录）──
ProjectDir  = FSO.GetParentFolderName(WScript.ScriptFullName)
PythonExe   = "python"
LauncherHtml = ProjectDir & "\launcher.html"

' ── 检查服务是否已在运行 ──
Dim isRunning
isRunning = False

Dim oExec
Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr :5055 | findstr LISTENING")
Do While oExec.Status = 0
    WScript.Sleep 200
Loop
sOut = oExec.StdOut.ReadAll()
If InStr(sOut, "5055") > 0 Then isRunning = True

' ── 若未运行则启动 Flask ──
If Not isRunning Then
    cmd = "cmd /c cd /d """ & ProjectDir & """ && python -X utf8 ads_manager.py"
    WshShell.Run cmd, 0, False   ' 0 = 隐藏窗口，False = 不等待
    WScript.Sleep 4000           ' 等待 4 秒让服务就绪
End If

' ── 打开浏览器（优先用 launcher.html，其次直接打开管理界面）──
If FSO.FileExists(LauncherHtml) Then
    WshShell.Run "explorer.exe """ & LauncherHtml & """"
Else
    WshShell.Run "http://localhost:5055"
End If

Set WshShell = Nothing
Set FSO      = Nothing
