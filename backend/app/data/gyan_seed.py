from app.core import db

WORKSHOPS = [
    {
        "id": "ws-1",
        "title": "Organic Farming Certification Course",
        "instructor": "Dr. R. K. Sharma",
        "instructorRole": "Principal Scientist",
        "institution": "ICAR",
        "feeRupees": 499,
        "coinsDiscountAllowed": 200,
        "duration": "6 hours",
        "batchDate": "2026-10-05",
        "timing": "10:00-16:00",
        "rating": 4.7,
        "enrolledCount": 380,
        "totalSeats": 500,
        "isCertified": True,
        "certificateTitle": "ICAR Organic Farming Certificate",
        "syllabusModules": ["Soil health basics", "Composting", "Bio-pesticides", "Certification process"],
        "deliverables": ["Certificate", "Handbook", "Soil test coupon"],
    },
    {
        "id": "ws-2",
        "title": "Drip Irrigation Design Workshop",
        "instructor": "Er. A. Patil",
        "instructorRole": "Agri Engineer",
        "institution": "Mahadbt Empanelled",
        "feeRupees": 899,
        "coinsDiscountAllowed": 100,
        "duration": "4 hours",
        "batchDate": "2026-10-12",
        "timing": "09:00-13:00",
        "rating": 4.4,
        "enrolledCount": 120,
        "totalSeats": 150,
        "isCertified": False,
        "certificateTitle": "Drip Design Participation",
        "syllabusModules": ["Crop water need", "Emitter spacing", "Fertigation"],
        "deliverables": ["Design worksheet"],
    },
    {
        "id": "ws-3",
        "title": "Post-Harvest Handling Masterclass",
        "instructor": "Dr. S. Kulkarni",
        "instructorRole": "Horticulture Expert",
        "institution": "Mahabeej",
        "feeRupees": 299,
        "coinsDiscountAllowed": 150,
        "duration": "3 hours",
        "batchDate": "2026-10-20",
        "timing": "11:00-14:00",
        "rating": 4.2,
        "enrolledCount": 30,
        "totalSeats": 60,
        "isCertified": False,
        "certificateTitle": "Post-Harvest Participation",
        "syllabusModules": ["Grading", "Pre-cooling", "Packaging"],
        "deliverables": ["Checklist"],
    },
]

EXPERT_TALKS = [
    {
        "id": "talk-1",
        "expertName": "Dr. Meena Jadhav",
        "institution": "KVK Nashik",
        "topic": "Sowing-window advisory for Rabi",
        "scheduledTime": "2026-09-20T17:00:00+05:30",
        "isLive": True,
        "registeredCount": 210,
        "description": "Live Q&A on choosing the right sowing window this Rabi.",
    },
    {
        "id": "talk-2",
        "expertName": "Dr. R. K. Sharma",
        "institution": "ICAR",
        "topic": "Integrated pest management in onion",
        "scheduledTime": "2026-09-25T18:00:00+05:30",
        "isLive": False,
        "registeredCount": 140,
        "description": "IPM practices for onion thrips and purple blotch.",
    },
    {
        "id": "talk-3",
        "expertName": "Er. A. Patil",
        "institution": "Mahadbt Empanelled",
        "topic": "PMKSY subsidy documentation",
        "scheduledTime": "2026-10-02T11:00:00+05:30",
        "isLive": False,
        "registeredCount": 85,
        "description": "Step-by-step subsidy paperwork walkthrough.",
    },
]

VIDEOS = [
    {"id": "vid-1", "title": "Drip system maintenance", "instructor": "Er. A. Patil", "duration": "12:30", "views": 15200, "category": "drip", "videoUrl": "https://example.com/vid1.mp4", "summary": "Flushing, filter cleaning and emitter checks.", "keyPoints": ["Flush weekly", "Check pressure", "Clean filters"]},
    {"id": "vid-2", "title": "Drip layout for small plots", "instructor": "Er. A. Patil", "duration": "09:45", "views": 9800, "category": "drip", "videoUrl": "https://example.com/vid2.mp4", "summary": "Designing laterals for sub-acre plots.", "keyPoints": ["Mainline sizing", "Lateral length"]},
    {"id": "vid-3", "title": "Grape pruning basics", "instructor": "Dr. S. Kulkarni", "duration": "15:10", "views": 22400, "category": "pruning", "videoUrl": "https://example.com/vid3.mp4", "summary": "Cane vs spur pruning for Thompson Seedless.", "keyPoints": ["Cane selection", "Spur spacing"]},
    {"id": "vid-4", "title": "Pruning tools and care", "instructor": "Dr. S. Kulkarni", "duration": "07:20", "views": 6100, "category": "pruning", "videoUrl": "https://example.com/vid4.mp4", "summary": "Keeping secateurs sharp and disease-free.", "keyPoints": ["Sharpening", "Sterilising"]},
    {"id": "vid-5", "title": "Safe pesticide spraying", "instructor": "Dr. M. Jadhav", "duration": "11:05", "views": 18300, "category": "spray", "videoUrl": "https://example.com/vid5.mp4", "summary": "Dose, PPE and wind conditions.", "keyPoints": ["Label dose", "PPE", "Wind speed"]},
    {"id": "vid-6", "title": "Sprayer calibration", "instructor": "Dr. M. Jadhav", "duration": "08:40", "views": 7600, "category": "spray", "videoUrl": "https://example.com/vid6.mp4", "summary": "Calibrating a knapsack sprayer in 10 minutes.", "keyPoints": ["Nozzle output", "Walking speed"]},
]

BLOGS = [
    {"id": "blog-1", "title": "Reading your soil health card", "author": "Dr. R. K. Sharma", "authorRole": "Principal Scientist, ICAR", "readTimeMinutes": 6, "category": "soil", "summary": "What the numbers on your card actually mean.", "content": "Soil health cards report NPK levels, organic carbon and pH. This article walks through each number and the corrective dose it suggests.", "publishedDate": "2026-09-01", "likesCount": 124},
    {"id": "blog-2", "title": "Onion storage: from heap to hostel", "author": "Sunil Deshmukh", "authorRole": "Progressive farmer", "readTimeMinutes": 8, "category": "post-harvest", "summary": "Ventilated storage lessons from a 20-tonne operator.", "content": "Good storage starts at harvest: curing, sorting and the right ventilation ratio cut losses dramatically.", "publishedDate": "2026-08-28", "likesCount": 98},
    {"id": "blog-3", "title": "BNPL for inputs: a cautious guide", "author": "Priya Nair", "authorRole": "Agri-finance analyst", "readTimeMinutes": 5, "category": "finance", "summary": "When buy-now-pay-later helps and when it hurts.", "content": "BNPL can smooth input cash-flow, but late fees and crop-cycle mismatches are real risks.", "publishedDate": "2026-08-20", "likesCount": 76},
    {"id": "blog-4", "title": "Grapes: exporting beyond Bangladesh", "author": "Vikram Chavan", "authorRole": "Exporter", "readTimeMinutes": 7, "category": "market", "summary": "New markets and the residue-compliance bar.", "content": "EU and Gulf buyers pay better but residue limits are strict — residue testing starts at the farm.", "publishedDate": "2026-08-15", "likesCount": 64},
    {"id": "blog-5", "title": "Bakhar vs compost: cost per acre", "author": "Dr. S. Kulkarni", "authorRole": "Horticulture Expert", "readTimeMinutes": 4, "category": "soil", "summary": "Comparing nutrient value and cost per nutrient.", "content": "Per-acre nutrient cost of farmyard manure versus compost with microbial enrichment.", "publishedDate": "2026-08-10", "likesCount": 41},
    {"id": "blog-6", "title": "Weather-based spraying windows", "author": "KVK Nashik", "authorRole": "Advisory team", "readTimeMinutes": 5, "category": "advisory", "summary": "Why wind and rain windows matter more than the calendar.", "content": "Spray effectiveness depends on wind, temperature inversion and rain-fastness of the molecule.", "publishedDate": "2026-08-05", "likesCount": 55},
]


async def seed_gyan():
    if await db.query("workshops", [], limit=1):
        return
    for doc in WORKSHOPS:
        await db.set_doc("workshops", doc["id"], doc)
    for doc in EXPERT_TALKS:
        await db.set_doc("expert_talks", doc["id"], doc)
    for doc in VIDEOS:
        await db.set_doc("videos", doc["id"], doc)
    for doc in BLOGS:
        await db.set_doc("blogs", doc["id"], doc)
