import math, time
class LapCounter:
    def __init__(self, total=3, yaw_thresh=5.5, start_radius=800.0, cooldown=15.0):
        self.total = total; self.yaw_thresh = yaw_thresh
        self.radius = start_radius; self.cooldown = cooldown
        self.laps = 0; self.acc_yaw = 0.0; self.last_h = 0.0
        self.cool_until = 0.0
    def update(self, heading, x, y, sx, sy):
        d = heading - self.last_h
        if d > math.pi: d -= 2 * math.pi
        if d < -math.pi: d += 2 * math.pi
        self.last_h = heading; self.acc_yaw += d
        dist = math.hypot(x - sx, y - sy)
        if abs(self.acc_yaw) > self.yaw_thresh and dist < self.radius and time.time() > self.cool_until:
            self.laps += 1; self.acc_yaw = 0.0; self.cool_until = time.time() + self.cooldown
        return self.laps