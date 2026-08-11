import math
class StanleyController:
    def __init__(self, k=0.75, ks=0.1):
        self.k = k; self.ks = ks
    def compute(self, heading_err, e_crosstrack_m, v_m_s):
        cross = math.atan2(self.k * e_crosstrack_m, v_m_s + self.ks)
        return heading_err + cross