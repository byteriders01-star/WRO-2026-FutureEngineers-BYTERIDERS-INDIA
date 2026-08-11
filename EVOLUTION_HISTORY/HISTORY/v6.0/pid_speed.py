class PID:
    def __init__(self, kp, ki, kd):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.integral = 0.0; self.last_err = 0.0
    def update(self, err, dt):
        self.integral = max(-30, min(30, self.integral + err * dt))
        deriv = (err - self.last_err) / dt if dt > 0 else 0.0
        self.last_err = err
        return self.kp * err + self.ki * self.integral + self.kd * deriv