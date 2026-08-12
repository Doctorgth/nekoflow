import ctypes
import os

def is_admin() -> bool:
    """Проверяет, запущен ли текущий процесс с правами Администратора в Windows."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        # Для Linux/macOS
        return getattr(os, "geteuid", lambda: -1)() == 0