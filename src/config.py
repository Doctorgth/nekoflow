import json
import os
from typing import List, Dict, Any

CONFIG_FILE = "connecter_config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "tun",  # "tun", "socks"
    "enabled": False,
    "split_tunneling": True,
    "selected_server": "",
    "servers": [],
    "process_whitelist": []
}

class ConfigManager:
    def __init__(self, filepath: str = CONFIG_FILE):
        self.filepath = filepath
        self.data = self.load()

    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Объединяем с дефолтными значениями на случай отсутствия новых ключей
                    res = DEFAULT_CONFIG.copy()
                    res.update(data)
                    return res
            except Exception:
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    def save(self) -> None:
        tmp_file = f"{self.filepath}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            os.replace(tmp_file, self.filepath)
        except Exception as e:
            print(f"[Config] Ошибка сохранения конфигурации: {e}")
            if os.path.exists(tmp_file):
                try: os.remove(tmp_file)
                except: pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()