import math
class ComplementaryFilter:
    def __init__(self, alpha=0.92):
        self.alpha = alpha; self.roll = 0.0; self.pitch = 0.0
    def update(self, accel, gyro, dt):
        ax, ay, az = accel
        roll_a = math.atan2(ay, az)
        pitch_a = math.atan2(-ax, math.sqrt(ay**2 + az**2))
        self.roll = self.alpha * (self.roll + math.radians(gyro[0]) * dt) + (1 - self.alpha) * roll_a
        self.pitch = self.alpha * (self.pitch + math.radians(gyro[1]) * dt) + (1 - self.alpha) * pitch_a
        return self.roll, self.pitch