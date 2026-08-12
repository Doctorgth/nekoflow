import sys
import os
import atexit
import signal
import logging

# Подавляем мусорный спам фоновых тасок aioptcp при завершении соединений
logging.getLogger("aioptcp").setLevel(logging.WARNING)

from PySide6.QtWidgets import QApplication
from src.config import ConfigManager
from src.ui.main_window import MainWindow
from src.network.route_manager import RouteManager

# Глобальный объект менеджера маршрутов для аварийного восстановления
global_route_manager = RouteManager()

def cleanup_on_exit():
    """Функция отката маршрутизации при завершении или краше приложения."""
    print("[Connecter] Запуск процедуры аварийного восстановления сетевых настроек...")
    global_route_manager.restore_routes()

def handle_exception(exc_type, exc_value, exc_traceback):
    """Глобальный перехватчик необработанных исключений."""
    print(f"[Connecter] Критический краш: {exc_value}")
    cleanup_on_exit()
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

class NullWriter:
    def write(self, text): pass
    def flush(self): pass

def main():
    # Защита от краша print() при запуске через pythonw.exe без консоли
    if sys.stdout is None: sys.stdout = NullWriter()
    if sys.stderr is None: sys.stderr = NullWriter()

    # Сообщаем Windows AppUserModelID, чтобы иконки на панели задач группировались с лаунчером
    try:
        import ctypes
        # Строго такой же ID, как в Launcher.cs
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('NekoFlow.Project.V1')
    except Exception:
        pass

    # Принудительная зачистка зависших в системе маршрутов перед запуском GUI
    RouteManager.force_cleanup_leftovers()

    # Регистрируем функции восстановления сети
    atexit.register(cleanup_on_exit)
    sys.excepthook = handle_exception

    # Регистрация сигналов завершения процесса (SIGINT, SIGTERM)
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))

    app = QApplication(sys.argv)
    
    # Помогаем Windows понять, что это часть одного проекта
    app.setApplicationName("NekoFlow")
    app.setOrganizationName("NekoFlowProject")
    
    config = ConfigManager()
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()