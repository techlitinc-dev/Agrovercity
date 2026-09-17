from abc import ABC, abstractmethod


class GradeModelAdapter(ABC):
    @abstractmethod
    def scan(self, image_bytes: bytes) -> dict:
        """Returns {grade, uniformityPercent, shelfLifeDays, recommendedPrice}."""
