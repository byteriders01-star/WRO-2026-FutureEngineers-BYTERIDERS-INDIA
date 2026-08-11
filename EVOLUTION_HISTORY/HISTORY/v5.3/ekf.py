import numpy as np
class EKF:
    def __init__(self):
        self.x = np.zeros((5, 1)); self.P = np.eye(5) * 10
    def predict(self, F, Q):
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q
    def update(self, H, z, R):
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ (z - H @ self.x)
        self.P = self.P - K @ S @ K.T