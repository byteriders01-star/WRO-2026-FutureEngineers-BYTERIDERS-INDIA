import math

class Kinematics4WSLayer:
    """
    Layer 9: Vehicle Dynamics (Single Servo 4WS Kinematic Model)
    Models the mechanical 4WS linkage driven by a single MG995 servo.
    Converts desired vehicle yaw curvature into front/rear Ackermann steering angles
    and maps them to servo angle outputs.
    """
    def __init__(self, config: dict):
        self.config = config
        self.kin_cfg = config.get("kinematics_4ws", {})

        self.wheelbase = self.kin_cfg.get("wheelbase_mm", 200.0)
        self.track_width = self.kin_cfg.get("track_width_mm", 150.0)
        self.max_servo_deg = self.kin_cfg.get("max_servo_angle_deg", 35.0)
        self.rear_ratio = self.kin_cfg.get("rear_to_front_ratio", 0.85) # kappa ratio

    def compute_steering(self, desired_steering_angle_rad: float) -> dict:
        """
        Input: Desired equivalent vehicle steering angle (rad)
        Output: Front wheel angle, rear wheel angle, turning radius, and MG995 servo command angle (deg).
        """
        # Clamp input desired steering
        max_rad = math.radians(self.max_servo_deg)
        delta_cmd = max(-max_rad, min(max_rad, desired_steering_angle_rad))

        # Single servo 4WS Kinematic Decomposition:
        # tan(delta_eff) = (tan(delta_f) - tan(delta_r)) / 2
        # Since delta_r = -kappa * delta_f:
        # tan(delta_eff) = (1 + kappa) * tan(delta_f) / 2
        # Therefore: tan(delta_f) = 2 * tan(delta_cmd) / (1 + kappa)
        
        tan_delta_f = (2.0 * math.tan(delta_cmd)) / (1.0 + self.rear_ratio)
        delta_f_rad = math.atan(tan_delta_f)
        delta_r_rad = -self.rear_ratio * delta_f_rad

        # Turning Radius (mm)
        if abs(delta_f_rad - delta_r_rad) > 1e-4:
            turning_radius_mm = self.wheelbase / (math.tan(delta_f_rad) - math.tan(delta_r_rad))
        else:
            turning_radius_mm = float('inf')

        # Servo Mapping (Direct linear mechanical linkage translation)
        servo_angle_deg = math.degrees(delta_f_rad)

        return {
            "servo_angle_deg": round(servo_angle_deg, 2),
            "front_wheel_deg": round(math.degrees(delta_f_rad), 2),
            "rear_wheel_deg": round(math.degrees(delta_r_rad), 2),
            "turning_radius_mm": round(turning_radius_mm, 1) if turning_radius_mm != float('inf') else 99999.0
        }
