from app.models.advisory import PestDisease
from app.services.disease_model.base import DiseaseModelAdapter


class StubDiseaseAdapter(DiseaseModelAdapter):
    async def scan(self, image_bytes: bytes) -> list[PestDisease]:
        return [
            PestDisease(
                diseaseName="Early Blight",
                crop="Tomato",
                pathogen="Alternaria solani",
                confidence=0.87,
                symptoms="Concentric dark spots on older leaves with yellow halo",
                chemicalTreatment="Mancozeb 75% WP",
                organicTreatment="Neem oil 5%",
                dosage="2.5 g/L",
                estimatedCost=450,
            )
        ]
