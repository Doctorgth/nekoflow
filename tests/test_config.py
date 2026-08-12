import os
import pytest
from src.config import ConfigManager

TEST_CONFIG_PATH = "test_config.json"

@pytest.fixture
def config():
    if os.path.exists(TEST_CONFIG_PATH):
        os.remove(TEST_CONFIG_PATH)
    cfg = ConfigManager(TEST_CONFIG_PATH)
    yield cfg
    if os.path.exists(TEST_CONFIG_PATH):
        os.remove(TEST_CONFIG_PATH)

def test_default_config(config):
    assert config.get("mode") == "tun"
    assert isinstance(config.get("process_whitelist"), list)

def test_save_and_load(config):
    config.set("selected_server", "1.2.3.4:8080")
    assert config.get("selected_server") == "1.2.3.4:8080"

    # Создаем новый объект и проверяем чтение с диска
    new_cfg = ConfigManager(TEST_CONFIG_PATH)
    assert new_cfg.get("selected_server") == "1.2.3.4:8080"