from app.core import db

ARTICLES = [
    {"id": "tree-art-1", "title": "Timber species for marginal land", "category": "timber", "author": "Dr. R. Kulkarni", "readTime": "6 min", "summary": "Teak and sandalwood options for low-fertility plots.", "fullContent": "Marginal land can carry high-value timber if species match soil depth and rainfall. Teak suits deep red soil while subabul tolerates shallow gravel.", "benefits": ["Long-term asset", "Inter-cropping possible"], "publishedDate": "2026-08-12"},
    {"id": "tree-art-2", "title": "Fruit orchards on farm boundaries", "category": "fruit", "author": "Dr. S. Kulkarni", "readTime": "5 min", "summary": "Boundary plantations that pay for fencing.", "fullContent": "Boundary plantations of mango, aonla and lemon use land that otherwise grows weeds, and mature trees pay for the farm fence within five years.", "benefits": ["Extra income", "Windbreak"], "publishedDate": "2026-08-20"},
    {"id": "tree-art-3", "title": "Biofuel trees and the buy-back market", "category": "biofuel", "author": "Maharashtra Biodiesel Board", "readTime": "7 min", "summary": "Who buys oil-seed produce and at what rate.", "fullContent": "Oil-seed trees like Jatropha and Pongamia have assured buy-back arrangements with processing units; this article lists the current rates and contracts.", "benefits": ["Buy-back assurance", "Drought-hardy"], "publishedDate": "2026-09-01"},
    {"id": "tree-art-4", "title": "Care calendar for young plantations", "category": "care", "author": "KVK Nashik", "readTime": "4 min", "summary": "A month-wise care routine for years 1–3.", "fullContent": "Young plantations fail on care, not species. This calendar covers watering, basin shaping and protection by month.", "benefits": ["Survival rate", "Faster growth"], "publishedDate": "2026-09-08"},
]

NGOS = [
    {"id": "ngo-1", "name": "Green Maharashtra Foundation", "focusArea": "Agroforestry", "location": "Nashik, Maharashtra", "contactPhone": "+919811400001", "email": "hello@greenmaharashtra.org", "treesPlantedCount": 480000, "rating": 4.7, "servicesOffered": ["Saplings", "Plantation drive", "Maintenance training"], "providesFreeSaplings": True, "websiteUrl": "https://greenmaharashtra.org"},
    {"id": "ngo-2", "name": "Vruksha Mitr Seva", "focusArea": "Urban & rural greening", "location": "Pune, Maharashtra", "contactPhone": "+919811400002", "email": "contact@vrukshamitr.org", "treesPlantedCount": 190000, "rating": 4.4, "servicesOffered": ["Saplings at cost", "Watering guidance"], "providesFreeSaplings": False, "websiteUrl": "https://vrukshamitr.org"},
    {"id": "ngo-3", "name": "Shivar Paryavaran Sangh", "focusArea": "Watershed + trees", "location": "Dindori, Maharashtra", "contactPhone": "+919811400003", "email": "info@shivarparayavaran.org", "treesPlantedCount": 75000, "rating": 4.2, "servicesOffered": ["Bund planting", "NGO-managed nurseries"], "providesFreeSaplings": False, "websiteUrl": "https://shivarparayavaran.org"},
]

BIOFUEL_TREES = [
    {"id": "bio-1", "name": "Jatropha", "botanicalName": "Jatropha curcas", "oilContentPercent": 34.0, "gestationPeriod": "2–3 years", "expectedReturnPerAcre": "₹18,000–₹25,000/acre from year 4", "suitability": "Marginal and waste land", "uses": ["Biodiesel", "Soap"], "buyerMarket": "Maharashtra biodiesel processors, contract farming", "subsidyScheme": "MNRE biofuel promotion grant"},
    {"id": "bio-2", "name": "Pongamia", "botanicalName": "Millettia pinnata", "oilContentPercent": 30.0, "gestationPeriod": "4–5 years", "expectedReturnPerAcre": "₹15,000–₹22,000/acre from year 6", "suitability": "Roadside, bunds, saline patches", "uses": ["Biodiesel", "Oil cake fertilizer"], "buyerMarket": "State biofuel board buy-back", "subsidyScheme": "MGNREGA plantation support"},
    {"id": "bio-3", "name": "Neem", "botanicalName": "Azadirachta indica", "oilContentPercent": 45.0, "gestationPeriod": "5–7 years", "expectedReturnPerAcre": "₹20,000/acre from year 7 (seed + leaves)", "suitability": "Farm boundaries, dry land", "uses": ["Neem oil pesticide", "Pharmaceuticals"], "buyerMarket": "Neem oil cooperatives", "subsidyScheme": "State horticulture subsidy"},
    {"id": "bio-4", "name": "Mahua", "botanicalName": "Madhuca longifolia", "oilContentPercent": 44.0, "gestationPeriod": "7–8 years", "expectedReturnPerAcre": "₹24,000/acre from year 8", "suitability": "Dry deciduous zones", "uses": ["Edible oil", "Soap", "Ayurveda"], "buyerMarket": "TRIFED and local oil mills", "subsidyScheme": "Van Dhan Vikas scheme"},
]

CARE_GUIDES = [
    {"id": "care-1", "title": "Pit preparation", "stepNumber": 1, "stage": "Pre-planting", "instructions": "Dig 45×45×45 cm pits 15 days before planting and fill with topsoil + 5 kg compost.", "wateringRule": "Soak pit 24 h before planting", "fertilizerSchedule": "5 kg compost per pit", "pestProtection": "Termite treatment for the pit"},
    {"id": "care-2", "title": "Planting", "stepNumber": 2, "stage": "Planting", "instructions": "Plant in the evening, keep the graft union above soil, and stake the sapling.", "wateringRule": "10 L immediately after planting", "fertilizerSchedule": "None in month 1", "pestProtection": "Collar guard against termites"},
    {"id": "care-3", "title": "Month 1–3 care", "stepNumber": 3, "stage": "Establishment", "instructions": "Weed the basin every 15 days and replace dead saplings within 30 days.", "wateringRule": "10 L every 3 days", "fertilizerSchedule": "50 g urea per plant at month 3", "pestProtection": "Neem-oil spray at 2% monthly"},
    {"id": "care-4", "title": "Month 4–12 care", "stepNumber": 4, "stage": "Growth", "instructions": "Shape a single leader, remove side shoots below 1 m.", "wateringRule": "20 L weekly", "fertilizerSchedule": "100 g NPK 10:26:26 quarterly", "pestProtection": "Stem-borer monitoring"},
    {"id": "care-5", "title": "Year 2 onward", "stepNumber": 5, "stage": "Maturation", "instructions": "Annual pruning after fruiting and basin widening each monsoon.", "wateringRule": "40 L weekly, taper in monsoon", "fertilizerSchedule": "FYM 10 kg + 200 g NPK yearly", "pestProtection": "Annual borax/lime wash"},
]


async def seed_tree():
    if await db.query("tree_articles", [], limit=1):
        return
    for doc in ARTICLES:
        await db.set_doc("tree_articles", doc["id"], doc)
    for doc in NGOS:
        await db.set_doc("ngos", doc["id"], doc)
    for doc in BIOFUEL_TREES:
        await db.set_doc("biofuel_trees", doc["id"], doc)
    for doc in CARE_GUIDES:
        await db.set_doc("tree_care_guides", doc["id"], doc)
