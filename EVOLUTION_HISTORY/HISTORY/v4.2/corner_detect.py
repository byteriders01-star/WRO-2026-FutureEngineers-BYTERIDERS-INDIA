import math
class CornerDetector:
    def __init__(self, threshold_deg=75):
        self.threshold = math.radians(threshold_deg)
        self.accumulated = 0.0
        self.last = 0.0
        self.corner_done = True
    def update(self, yaw, front_mm):
        d = yaw - self.last
        if d > math.pi: d -= 2 * math.pi
        if d < -math.pi: d += 2 * math.pi
        self.last = yaw
        if self.corner_done and front_mm < 350:
            self.corner_done = False
            self.accumulated = 0.0
        if not self.corner_done:
            self.accumulated += d
            if abs(self.accumulated) > self.threshold:
                self.corner_done = True
                return True
        return False