import numpy as np
def clamped_spline_curvature(pts):
    # simplified: curvature from three consecutive waypoints
    k = []
    for i in range(1, len(pts) - 1):
        a = np.array(pts[i]) - np.array(pts[i - 1])
        b = np.array(pts[i + 1]) - np.array(pts[i])
        cross = abs(np.cross(a, b))
        k.append(cross / (np.linalg.norm(a) * np.linalg.norm(b)))
    return k