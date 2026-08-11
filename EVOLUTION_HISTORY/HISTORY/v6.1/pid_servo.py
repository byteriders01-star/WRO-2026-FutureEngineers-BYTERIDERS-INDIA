import time
class ServoPID:
    def __init__(self):
        self.kp, self.ki, self.kd = 0.9, 0.01, 0.25
        self.integral = 0.0; self.last = 0.0
    def compute_angle(self, target, current, dt):
        err = target - current
        self.integral += err * dt
        d = (err - self.last) / dt if dt > 0 else 0.0
        self.last = err
        out = self.kp * err + self.ki * self.integral + self.kd * d
        return max(-35.0, min(35.0, out))