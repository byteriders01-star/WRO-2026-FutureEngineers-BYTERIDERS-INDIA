class AntiWindupPID:
    def __init__(self, kp, ki, kd, out_min, out_max):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.out_min, self.out_max = out_min, out_max
        self.integral = 0.0; self.last = 0.0
    def update(self, err, dt):
        out = self.kp * err + self.ki * self.integral + self.kd * (err - self.last) / dt
        if out <= self.out_min or out >= self.out_max:
            pass  # freeze integral (conditional integration)
        else:
            self.integral += err * dt
        self.last = err
        return max(self.out_min, min(self.out_max, out))