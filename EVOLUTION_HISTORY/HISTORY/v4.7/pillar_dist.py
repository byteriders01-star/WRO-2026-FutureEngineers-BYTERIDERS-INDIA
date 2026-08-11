import math
def pillar_distance_mm(bbox_height_px, img_h, pitch_rad):
    if bbox_height_px <= 0: return 9999.0
    raw = (img_h * 150.0) / bbox_height_px
    return raw * math.cos(pitch_rad)