class AdaptiveNoise:
    def __init__(self, alpha=0.1, lo=1.0, hi=100.0):
        self.alpha = alpha; self.lo = lo; self.hi = hi; self.est = 10.0
    def update(self, innovation):
        self.est += self.alpha * (abs(innovation) - self.est)
        return max(self.lo, min(self.hi, self.est))