import os

from app.services.grading_model.base import GradeModelAdapter
from app.services.grading_model.stub import StubGradeAdapter

_ADAPTERS: dict[str, type[GradeModelAdapter]] = {"stub": StubGradeAdapter}


def get_grading_adapter() -> GradeModelAdapter:
    name = os.getenv("GRADE_MODEL_ADAPTER", "stub")
    if name not in _ADAPTERS:
        raise ValueError(f"Unknown GRADE_MODEL_ADAPTER: {name}")
    return _ADAPTERS[name]()
