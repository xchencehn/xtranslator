Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

' Get script directory and change working directory
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptPath

' Set console encoding to UTF-8 (via batch command)
' Run in background, hide window (parameter 0 means hidden window)
WshShell.Run "cmd /c chcp 65001 >nul && python translator.py", 0, False

Set WshShell = Nothing
Set fso = Nothing

