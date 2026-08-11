class DirectionDetector:
    def __init__(self):
        self.direction = None; self.acc = 0.0
    def update(self, yaw_delta, front_mm):
        if self.direction: return self.direction
        if front_mm < 350:      # inside a corner
            self.acc += yaw_delta
            if abs(self.acc) > 1.0:
                self.direction = "CCW" if self.acc > 0 else "CW"
        return self.direction