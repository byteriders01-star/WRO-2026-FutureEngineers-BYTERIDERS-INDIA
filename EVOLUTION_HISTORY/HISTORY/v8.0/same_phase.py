import math
class Kinematics4WS:
    def __init__(self, wheelbase=230.0, rear_ratio=0.85, max_deg=35.0):
        self.wheelbase = wheelbase; self.kappa = rear_ratio; self.max_deg = max_deg
    def compute(self, cmd_rad):
        cmd = max(-math.radians(self.max_deg), min(math.radians(self.max_deg), cmd_rad))
        delta_f = math.atan(2.0 * math.tan(cmd) / (1.0 + self.kappa))
        delta_r = -self.kappa * delta_f
        radius = self.wheelbase / (math.tan(delta_f) - math.tan(delta_r))
        return delta_f, delta_r, radius