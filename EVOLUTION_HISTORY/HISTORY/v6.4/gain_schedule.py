def adaptive_k(base_k, speed_pct):
    return base_k / (1.0 + 0.015 * speed_pct)