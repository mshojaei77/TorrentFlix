from abc import ABC, abstractmethod

class MetadataSource(ABC):
    @abstractmethod
    def get_url(self, title: str, year: int) -> str:
        pass
    
    @abstractmethod
    def get_info(self, url: str) -> dict:
        pass
