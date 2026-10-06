Set args = WScript.Arguments
t = "run"
If args.Count > 0 Then t = args(0)
Set ws = CreateObject("Wscript.Shell")
ws.Run "powershell -ExecutionPolicy Bypass -File C:\alpha\run-auto-trading-cycle.ps1 -Task " & t, 0, False
