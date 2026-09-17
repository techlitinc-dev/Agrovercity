from app.services.grading_model.base import GradeModelAdapter


class StubGradeAdapter(GradeModelAdapter):
    def scan(self, image_bytes: bytes) -> dict:
        return {"grade": "AGMARK A", "uniformityPercent": 88, "shelfLifeDays": 12, "recommendedPrice": 1650}
