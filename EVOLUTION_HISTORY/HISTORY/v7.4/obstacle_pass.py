import time
class PassStrategy:
    def __init__(self, cooldown=0.5):
        self.offset = 0.0; self.locked = False; self.until = 0.0
    def update(self, pillar_side, dist_mm):
        if not self.locked and pillar_side is not None:
            self.offset = 0.6 if pillar_side == "left" else -0.6
            self.locked = True; self.until = time.time() + 1.0
        if self.locked and time.time() > self.until and dist_mm > 500:
            self.locked = False; self.offset = 0.0
        return self.offset