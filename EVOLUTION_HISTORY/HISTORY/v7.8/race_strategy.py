import time
class RaceStrategy:
    def __init__(self, stop_sec=3.0, enabled=True):
        self.stop_sec = stop_sec; self.enabled = enabled
        self.triggered = False; self.t0 = 0.0; self.state = "RUN"
    def update(self, blue_marker, front_mm, brake_mm):
        if self.enabled and blue_marker and not self.triggered:
            self.state = "STOP"; self.triggered = True; self.t0 = time.time()
        if self.state == "STOP" and time.time() - self.t0 >= self.stop_sec:
            self.state = "RUN"
        if front_mm < brake_mm:
            self.state = "EMERGENCY"
        if self.state == "EMERGENCY" and front_mm > brake_mm + 100:
            self.state = "RUN"
        return self.state