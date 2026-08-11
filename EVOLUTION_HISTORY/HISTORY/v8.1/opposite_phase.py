import math
def opposite_phase(cmd_rad, max_deg=40.0):
    cmd = max(-math.radians(max_deg), min(math.radians(max_deg), cmd_rad))
    delta_f = cmd
    delta_r = -0.85 * cmd
    return delta_f, delta_r