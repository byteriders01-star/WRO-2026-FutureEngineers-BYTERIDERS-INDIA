def free_space(front_mm, mask_confidence):
    if front_mm > 0 and front_mm < 450:
        return "BLOCKED_NEAR"
    if mask_confidence < 0.3:
        return "FREE"
    return "OCCUPIED_FAR"