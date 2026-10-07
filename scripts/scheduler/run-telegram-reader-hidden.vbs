Set ws = CreateObject("Wscript.Shell")
ws.Run "powershell -NoProfile -ExecutionPolicy Bypass -File C:\alpha\run-telegram-reader.ps1", 0, False
