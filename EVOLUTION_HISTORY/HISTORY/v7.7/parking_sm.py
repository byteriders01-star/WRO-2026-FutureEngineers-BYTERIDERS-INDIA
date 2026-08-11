import time
class ParkingSM:
    def __init__(self):
        self.state = "SEARCHING"; self.t0 = 0.0
    def update(self, marker_area, aligned):
        if self.state == "SEARCHING":
            if marker_area is not None and marker_area > 1500:
                self.state = "MANEUVER"; self.t0 = time.time()
        elif self.state == "MANEUVER":
            if aligned and time.time() - self.t0 > 5.0:
                self.state = "FINISHED"
        return self.state