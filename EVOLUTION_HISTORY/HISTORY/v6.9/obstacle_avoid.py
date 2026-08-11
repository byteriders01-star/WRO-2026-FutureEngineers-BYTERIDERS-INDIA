class Avoidance:
    def __init__(self, brake_mm=180, safe_mm=450):
        self.brake_mm = brake_mm; self.safe_mm = safe_mm
    def target_speed(self, front_mm, v_normal):
        if front_mm < self.brake_mm: return 0.0
        if front_mm < self.safe_mm: return v_normal * (front_mm / self.safe_mm)
        return v_normal