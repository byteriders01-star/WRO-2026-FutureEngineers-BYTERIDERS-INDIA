import time
class Reverse:
    def __init__(self, max_mm=200, safety_mm=100):
        self.max_mm = max_mm; self.safety = safety_mm; self.active = False; self.t0 = 0.0
    def start(self, front_mm):
        if front_mm > self.safety and not self.active:
            self.active = True; self.t0 = time.time()
        return self.active
    def update(self, elapsed_s, v_mm_s):
        if not self.active: return 0.0
        if elapsed_s * v_mm_s > self.max_mm:
            self.active = False; return 0.0
        return -30.0