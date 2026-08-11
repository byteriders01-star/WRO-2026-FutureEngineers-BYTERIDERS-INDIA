import math
def compensate(raw_mm, roll_rad, pitch_rad, side):
    # laser range correction for vehicle roll/pitch
    if raw_mm <= 0: return -1.0
    if side == "front": return raw_mm * math.cos(pitch_rad)
    return raw_mm * math.cos(roll_rad)