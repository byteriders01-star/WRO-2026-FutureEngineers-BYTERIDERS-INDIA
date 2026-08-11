import math
class HeadingFusion:
    def __init__(self):
        self.yaw = 0.0; self.motion = 0.0
    def update(self, gyro_z_rad, accel_x, dt):
        self.motion = 0.9 * self.motion + 0.1 * abs(accel_x)
        trust_gyro = min(1.0, self.motion / 1.5)
        self.yaw += gyro_z_rad * dt * trust_gyro
        self.yaw = math.atan2(math.sin(self.yaw), math.cos(self.yaw))
        return self.yaw