import os

from app.services.disease_model.base import DiseaseModelAdapter
from app.services.disease_model.stub import StubDiseaseAdapter

_ADAPTERS: dict[str, type[DiseaseModelAdapter]] = {"stub": StubDiseaseAdapter}


def get_disease_adapter() -> DiseaseModelAdapter:
    name = os.getenv("DISEASE_MODEL_ADAPTER", "stub")
    if name not in _ADAPTERS:
        raise ValueError(f"Unknown DISEASE_MODEL_ADAPTER: {name}")
    return _ADAPTERS[name]()
