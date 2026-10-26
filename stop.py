import os
import subprocess
import sys

def stop_bot_processes():
    print("Bot jarayonlari qidirilmoqda va to'xtatilmoqda...")
    try:
        # Taskkill by window title
        subprocess.run(['taskkill', '/FI', 'WINDOWTITLE eq EchoMusicBot*', '/T', '/F'], capture_output=True)
    except Exception:
        pass

    try:
        # Windows wmic / powershell or tasklist
        cmd = ["powershell", "-NoProfile", "-Command", 
               "Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*EchoMusicBot*' -or $_.CommandLine -like '*bot.py*' } | Stop-Process -Force"]
        subprocess.run(cmd, capture_output=True)
    except Exception:
        pass
        
    print("[MUVAFFAQIYATLI] EchoMusicBot to'xtatildi!")

if __name__ == "__main__":
    stop_bot_processes()
