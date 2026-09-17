from app.core import db

GAUSHALAS = [
    {
        "id": "gau-1", "name": "Shree Gau Seva Gaushala", "trustName": "Shree Gau Seva Trust", "address": "Dindori Road, Nashik", "district": "Nashik",
        "distanceKm": 8.5, "cowCount": 420, "breeds": ["Gir", "Khillari"], "phone": "+919811100001",
        "providesOrganicManure": True, "offersCowAdoption": False, "rating": 4.6, "facilities": ["Veterinary care", "Biogas", "Goshala store"],
    },
    {
        "id": "gau-2", "name": "Aditya Gau shala", "trustName": "Aditya Seva Sanstha", "address": "Ozar, Nashik", "district": "Nashik",
        "distanceKm": 18.0, "cowCount": 260, "breeds": ["Gir", "Sahiwal"], "phone": "+919811100002",
        "providesOrganicManure": False, "offersCowAdoption": True, "rating": 4.3, "facilities": ["Adoption program", "Gau-daan"],
    },
    {
        "id": "gau-3", "name": "Sant Gadge Gaushala", "trustName": "Sant Gadge Maharaj Trust", "address": "Pimpalgaon, Nashik", "district": "Nashik",
        "distanceKm": 24.5, "cowCount": 180, "breeds": ["Khillari"], "phone": "+919811100003",
        "providesOrganicManure": False, "offersCowAdoption": False, "rating": 4.1, "facilities": ["Shelter", "Fodder bank"],
    },
]

NURSERIES = [
    {
        "id": "nur-1", "name": "Govt Horticulture Nursery", "address": "College Road, Nashik", "district": "Nashik", "distanceKm": 5.0,
        "phone": "+919811200001", "saplingsAvailable": ["Mango", "Guava", "Aonla"], "isGovtCertified": True, "rating": 4.4,
    },
    {
        "id": "nur-2", "name": "Green Leaf Nursery", "address": "Dindori, Nashik", "district": "Nashik", "distanceKm": 14.0,
        "phone": "+919811200002", "saplingsAvailable": ["Pomegranate", "Grape rootstock"], "isGovtCertified": False, "rating": 4.2,
    },
    {
        "id": "nur-3", "name": "Shakti Plant Nursery", "address": "Pimpalgaon, Nashik", "district": "Nashik", "distanceKm": 21.0,
        "phone": "+919811200003", "saplingsAvailable": ["Mango", "Sapota", "Lemon"], "isGovtCertified": False, "rating": 4.0,
    },
]

VETS = [
    {
        "id": "vet-1", "name": "Dr. Sanjay More", "clinicName": "More Pet & Cattle Clinic", "address": "Gangapur Road, Nashik", "district": "Nashik",
        "distanceKm": 4.5, "phone": "+919811300001", "specialization": "Cattle & buffalo", "consultationFeeRupees": 500,
        "availableForFarmVisit": True, "emergencyAvailable": True, "nextAvailableSlot": "2026-09-18 09:00", "rating": 4.7,
    },
    {
        "id": "vet-2", "name": "Dr. Priya Wagh", "clinicName": "Wagh Veterinary Care", "address": "Ozar, Nashik", "district": "Nashik",
        "distanceKm": 11.0, "phone": "+919811300002", "specialization": "Small ruminants", "consultationFeeRupees": 300,
        "availableForFarmVisit": True, "emergencyAvailable": True, "nextAvailableSlot": "2026-09-18 11:00", "rating": 4.5,
    },
    {
        "id": "vet-3", "name": "Dr. Anil Bhoir", "clinicName": "Bhoir Animal Hospital", "address": "Pimpalgaon, Nashik", "district": "Nashik",
        "distanceKm": 16.5, "phone": "+919811300003", "specialization": "Poultry", "consultationFeeRupees": 400,
        "availableForFarmVisit": False, "emergencyAvailable": False, "nextAvailableSlot": "2026-09-19 10:00", "rating": 4.2,
    },
    {
        "id": "vet-4", "name": "Dr. Kavita Sonawane", "clinicName": "Sonawane Livestock Clinic", "address": "Dindori, Nashik", "district": "Nashik",
        "distanceKm": 22.0, "phone": "+919811300004", "specialization": "Cattle nutrition", "consultationFeeRupees": 800,
        "availableForFarmVisit": True, "emergencyAvailable": False, "nextAvailableSlot": "2026-09-20 15:00", "rating": 4.6,
    },
]

DAIRY_PRODUCTS = [
    {"id": "dairy-1", "name": "A2 Gir Cow Ghee", "category": "ghee", "description": "Bilona-method A2 ghee", "priceRupees": 1450, "unit": "1 L", "inStock": True, "purityCertification": "FSSAI A2 verified", "rating": 4.8},
    {"id": "dairy-2", "name": "Organic A2 Milk", "category": "milk", "description": "Farm-fresh A2 cow milk", "priceRupees": 90, "unit": "1 L", "inStock": True, "purityCertification": "FSSAI", "rating": 4.5},
    {"id": "dairy-3", "name": "Malai Paneer", "category": "paneer", "description": "Soft farm paneer", "priceRupees": 450, "unit": "1 kg", "inStock": True, "purityCertification": "FSSAI", "rating": 4.6},
    {"id": "dairy-4", "name": "Farm Butter", "category": "butter", "description": "Cultured white butter", "priceRupees": 520, "unit": "500 g", "inStock": False, "purityCertification": "FSSAI", "rating": 4.3},
    {"id": "dairy-5", "name": "A2 Curd", "category": "milk", "description": "Set curd from A2 milk", "priceRupees": 70, "unit": "500 g", "inStock": True, "purityCertification": "FSSAI", "rating": 4.4},
    {"id": "dairy-6", "name": "Ghee 500 ml", "category": "ghee", "description": "Half-litre bilona ghee", "priceRupees": 750, "unit": "500 ml", "inStock": True, "purityCertification": "FSSAI A2 verified", "rating": 4.7},
]


async def seed_livestock():
    if await db.query("gaushalas", [], limit=1):
        return
    for doc in GAUSHALAS:
        await db.set_doc("gaushalas", doc["id"], doc)
    for doc in NURSERIES:
        await db.set_doc("nurseries", doc["id"], doc)
    for doc in VETS:
        await db.set_doc("vets", doc["id"], doc)
    for doc in DAIRY_PRODUCTS:
        await db.set_doc("dairy_products", doc["id"], doc)
