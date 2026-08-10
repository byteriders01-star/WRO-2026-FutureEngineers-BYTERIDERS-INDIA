import math

class PathPlannerLayer:
    """
    Layer 7: Path Planning
    Generates target trajectory centerline, obstacle avoidance paths,
    and manages state-specific steering/speed overrides for starting and parking.
    """
    def __init__(self, config: dict):
        self.config = config

    def plan_path(self, localization: dict, mission_status: dict) -> dict:
        state = mission_status.get("state", "RUNNING")
        parking_side = mission_status.get("parking_side", "RIGHT")
        parking_phase = mission_status.get("parking_phase", 0)

        # Default: no overrides
        steering_override_rad = None
        speed_override = None

        if state == "START_FROM_PARKING":
            # If starting inside parking, steer out away from the wall
            # If parking side is LEFT, steer RIGHT (positive); if RIGHT, steer LEFT (negative)
            dir_mult = 1.0 if parking_side == "LEFT" else -1.0
            steering_override_rad = dir_mult * math.radians(20.0)
            speed_override = 35.0

        elif state == "PARKING_MANEUVER":
            # Parallel parking Ackerman phase overrides
            dir_mult = 1.0 if parking_side == "LEFT" else -1.0
            
            if parking_phase == 1:
                # Phase 1: Drive forward straight past the slot
                steering_override_rad = 0.0
                speed_override = 25.0
            elif parking_phase == 2:
                # Phase 2: Reverse steer towards wall
                # Driving reverse: positive steer turns wheels right, swinging rear left (towards left wall)
                steering_override_rad = dir_mult * math.radians(35.0)
                speed_override = -22.0
            elif parking_phase == 3:
                # Phase 3: Reverse steer away from wall
                steering_override_rad = -dir_mult * math.radians(35.0)
                speed_override = -18.0
            elif parking_phase == 4:
                # Phase 4: Straight align slow
                steering_override_rad = 0.0
                speed_override = -12.0
            else:
                steering_override_rad = 0.0
                speed_override = 0.0

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
            "target_heading_error_deg": round(math.degrees(target_heading_error_rad), 2),
            "steering_override_rad": steering_override_rad,
            "speed_override": speed_override
        }
