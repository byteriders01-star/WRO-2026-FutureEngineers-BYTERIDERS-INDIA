def detect_walls(raw):
    left = raw.get("left_mm", 0.0)
    right = raw.get("right_mm", 0.0)
    front = raw.get("front_mm", 0.0)
    # blind spot: <30mm reported as 0 = wall contact
    return {"left_wall_mm": left if left > 30 else 0.0,
            "right_wall_mm": right if right > 30 else 0.0,
            "front_dist_mm": front if front > 30 else 0.0,
            "wall_contact": left < 30 or right < 30 or front < 30}