# Ported from the persona x screen matrix (docs/overview/04-persona-screen-matrix.md §2),
# which mirrors the missing flutter-prototype/lib/state/profile_routes.dart.

ACCESS_MAP: dict[str, set[str]] = {
    "farmer": {
        "home", "mandi", "marketplace", "buyers", "advisory", "profitLoss", "water",
        "schemes", "finance", "womenFarmer", "fpo", "equipment", "landLegal", "climate",
        "postHarvest", "treePlantation", "liveChannels", "agriNews", "livestockDairy",
        "farmDiary", "referEarn", "krishiRatna", "gyanHub", "cropInsurance",
    },
    "farmLandlord": {
        "marketplace", "profitLoss", "schemes", "finance", "landLegal", "treePlantation",
        "agriNews", "farmDiary", "referEarn", "krishiRatna", "gyanHub", "cropInsurance",
    },
    "transport": {
        "marketplace", "finance", "postHarvest", "liveChannels", "agriNews",
        "referEarn", "krishiRatna", "gyanHub",
    },
    "seller": {
        "mandi", "marketplace", "buyers", "profitLoss", "finance", "postHarvest",
        "treePlantation", "agriNews", "livestockDairy", "referEarn", "krishiRatna", "gyanHub",
    },
    "equipmentRental": {
        "profitLoss", "finance", "equipment", "liveChannels", "agriNews",
        "referEarn", "krishiRatna", "gyanHub",
    },
    "broker": {
        "mandi", "buyers", "profitLoss", "finance", "liveChannels", "agriNews",
        "referEarn", "krishiRatna", "gyanHub",
    },
}

DEFAULT_HOME: dict[str, str] = {
    "farmer": "home",
    "farmLandlord": "landlordHome",
    "transport": "transportHome",
    "seller": "sellerHome",
    "equipmentRental": "equipmentOwnerHome",
    "broker": "brokerHome",
}
