def parking_ready(marker, left_wall, right_wall, aligned_tol=25.0):
    if marker is None or marker["area"] < 1500: return False
    offset = (left_wall - right_wall) / 2.0
    return abs(offset) < aligned_tol, offset