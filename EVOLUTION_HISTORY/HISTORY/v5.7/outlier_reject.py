import numpy as np
CHI2_95 = 5.99  # 2 DOF
def gate(innovation, S, R):
    d = np.array(innovation).reshape(-1, 1)
    mahal = float((d.T @ np.linalg.inv(S + R) @ d))
    return mahal < CHI2_95