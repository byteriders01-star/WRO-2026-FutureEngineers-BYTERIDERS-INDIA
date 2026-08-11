import math

class PathPlannerLayer:
    """
    Layer 7: Path Planning
    Generates target trajectory centerline and obstacle avoidance paths.
    """
    def __init__(self, config: dict):
        self.config = config

    def plan_path(self, localization: dict, mission_status: dict) -> dict:
        crosstrack_err = localization.get("crosstrack_error_mm", 0.0)
        avoidance_offset = mission_status.get("avoidance_offset", 0.0) # [-1.0, 1.0]
        narrow_mode = mission_status.get("narrow_mode", False)

        # Baseline desired cross-track offset from wall center (0 = middle)
        # Apply higher centering weight if in narrow 600mm track mode
        gain = 1.8 if narrow_mode else 1.0

        target_crosstrack_offset_mm = (avoidance_offset * 120.0) - (crosstrack_err * gain)

        # Target Heading Angle Error (rad)
        target_heading_error_rad = math.atan2(target_crosstrack_offset_mm, 350.0)

        return {
            "target_crosstrack_offset_mm": round(target_crosstrack_offset_mm, 2),
            "target_heading_error_rad": round(target_heading_error_rad, 4),
            "target_heading_error_deg": round(math.degrees(target_heading_error_rad), 2)
        }
