def is_eligible(user: dict, rules: dict) -> bool:
    if not rules:
        return True
    if "maxLandAcres" in rules and user.get("landAreaAcres", 0) > rules["maxLandAcres"]:
        return False
    if "states" in rules and rules["states"] and user.get("state") not in rules["states"]:
        return False
    if "requiresKcc" in rules and rules["requiresKcc"] and not user.get("kccLimit", 0) > 0:
        return False
    return True
