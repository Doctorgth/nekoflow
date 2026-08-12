import os
import sys

# СТРОГО ПЕРВЫМ ДЕЛОМ: Устанавливаем AppUserModelID для Windows
# Это должно произойти до импорта PySide6 / Qt
if sys.platform == "win32":
    try:
        import ctypes
        # Тот же ID, что в лаунчере
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("NekoFlow.Project.V1")
    except Exception:
        pass

from src.main import main

if __name__ == "__main__":
    main()