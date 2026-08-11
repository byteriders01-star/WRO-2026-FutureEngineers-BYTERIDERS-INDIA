import math
class CheckpointMgr:
    def __init__(self):
        self.start = None
    def init(self, x, y): self.start = (x, y)
    def near_start(self, x, y, radius=800.0):
        if not self.start: return False
        return math.hypot(x - self.start[0], y - self.start[1]) < radius