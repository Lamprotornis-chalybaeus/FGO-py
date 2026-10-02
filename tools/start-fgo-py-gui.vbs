Option Explicit
Dim Shell, FS, Root, PythonPath, EntryPath
Set Shell = CreateObject("WScript.Shell")
Set FS = CreateObject("Scripting.FileSystemObject")
Root = FS.GetParentFolderName(WScript.ScriptFullName)
If LCase(FS.GetFileName(Root)) = "tools" Then
  Root = FS.GetParentFolderName(FS.GetParentFolderName(Root))
End If
PythonPath = Root & "\FGO-py\.venv\Scripts\pythonw.exe"
EntryPath = Root & "\FGO-py\FGO-py\fgo.py"
If Not FS.FileExists(PythonPath) Then
  MsgBox "Python venv is missing: " & PythonPath, 16, "FGO-py"
  WScript.Quit 1
End If
Shell.CurrentDirectory = Root & "\FGO-py"
Shell.Environment("Process")("PATH") = Root & "\tools\platform-tools;" & Shell.Environment("Process")("PATH")
Shell.Run Chr(34) & PythonPath & Chr(34) & " " & Chr(34) & EntryPath & Chr(34) & " gui", 1, False
