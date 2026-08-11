import math
class DeadReckoning:
    def __init__(self):
        self.x = 0.0; self.y = 0.0; self.theta = 0.0
    def update(self, v_mm_s, dt):
        self.x += v_mm_s * math.cos(self.theta) * dt
        self.y += v_mm_s * math.sin(self.theta) * dt
    def pose(self):
        return {"x_mm": self.x, "y_mm": self.y, "heading_rad": self.theta}