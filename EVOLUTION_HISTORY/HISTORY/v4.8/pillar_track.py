import time
class PillarTracker:
    def __init__(self, cooldown=0.5):
        self.last = None; self.last_seen = 0.0; self.cooldown = cooldown
    def update(self, det):
        if det is not None:
            self.last = det; self.last_seen = time.time()
        if time.time() - self.last_seen > self.cooldown:
            self.last = None
        return self.last