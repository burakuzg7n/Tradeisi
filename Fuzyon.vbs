' Fuzyon Arena'yi PENCERESIZ baslatir ve paneli acar. Cift tiklayin.
' Zaten calisiyorsa yalniz paneli acar. Durdurmak icin: panel > Ayarlar > Servisi durdur.
Option Explicit
Dim fso, sh, ek
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
ek = ""
If WScript.Arguments.Count > 0 Then
  If LCase(WScript.Arguments(0)) = "sessiz" Then ek = " --sessiz"
End If
sh.Run "cmd /c chcp 65001 >nul & set PYTHONIOENCODING=utf-8& python -m fusion servis" & ek, 0, False
