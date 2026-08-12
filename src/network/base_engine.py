from abc import ABC, abstractmethod
from typing import List

class BaseNetworkEngine(ABC):
    """Абстрактный класс сетевого движка."""

    def __init__(self):
        self.is_running = False
        self.split_tunneling = False
        self.whitelist: List[str] = []

    def configure_split_tunneling(self, enabled: bool, whitelist: List[str]) -> None:
        self.split_tunneling = enabled
        self.whitelist = [p.lower() for p in whitelist]

    @abstractmethod
    def start(self) -> bool:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass