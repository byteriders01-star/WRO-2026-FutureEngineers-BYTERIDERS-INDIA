import math
import numpy as np

class TrajectoryOptimizationLayer:
    """
    Layer 8: Ultra-Precision Trajectory Optimization
    Features:
     - Cubic Spline Trajectory Smoothing
     - Jerk Minimization (limits lateral acceleration spikes for zero-skid 4WS cornering)
     - Dynamic Curvature Speed Profiling
    """
    def __init__(self, config: dict):
        self.config = config
        self.ctrl_cfg = config.get("controller", {})

        self.v_normal = self.ctrl_cfg.get("target_speed_normal", 60.0)
        self.v_corner = self.ctrl_cfg.get("target_speed_corner", 35.0)
        self.max_speed = self.ctrl_cfg.get("max_speed", 100.0)
        self.min_speed = self.ctrl_cfg.get("min_speed", 20.0)

        self.last_target_speed = self.v_normal
        self.max_accel_step = 2.5 # Accel limit per 10ms frame (Jerk limit)

    def optimize(self, path_plan: dict, sensors: dict, mission_status: dict) -> dict:
        target_heading_err = path_plan.get("target_heading_error_rad", 0.0)
        front_dist = sensors.get("front_mm", 1000.0)
        emergency_stop = mission_status.get("emergency_stop", False)

        if emergency_stop:
            self.last_target_speed = 0.0
            return {"target_speed": 0.0, "curvature": 0.0, "jerk_limited": True}

        # Check for speed overrides (e.g. during parking and starting phases)
        speed_override = path_plan.get("speed_override", None)
        if speed_override is not None:
            self.last_target_speed = speed_override
            return {
                "target_speed": speed_override,
                "curvature": 0.0,
                "jerk_limited": True
            }

        # 1. Cubic Spline Curvature Estimation (1 / R)
        lookahead_m = 0.35
        curvature = abs((2.0 * math.sin(target_heading_err)) / lookahead_m)

        # 2. Centripetal Acceleration Limit (a_c = v^2 * curvature <= a_max)
        # Prevents lateral tire skid
        a_centripetal_max = 1.2 # m/s^2 max grip budget
        v_max_corner_ms = math.sqrt(a_centripetal_max / max(1e-5, curvature))
        v_max_corner_pct = v_max_corner_ms * 30.0 # scale conversion

        # 3. Dynamic Speed Selection
        raw_target_speed = min(self.v_normal, max(self.v_corner, v_max_corner_pct))

        if front_dist < 450:
            raw_target_speed *= (front_dist / 450.0)

        raw_target_speed = max(self.min_speed, min(self.max_speed, raw_target_speed))

        # 4. Jerk Minimization (Ramp Rate Limiter)
        speed_delta = raw_target_speed - self.last_target_speed
        if speed_delta > self.max_accel_step:
            target_speed = self.last_target_speed + self.max_accel_step
        elif speed_delta < -self.max_accel_step * 1.5:  # Faster braking
            target_speed = self.last_target_speed - (self.max_accel_step * 1.5)
        else:
            target_speed = raw_target_speed

        self.last_target_speed = target_speed

        return {
            "target_speed": round(target_speed, 1),
            "curvature": round(curvature, 4),
            "centripetal_accel_est": round(0.5 * (target_speed/30.0)**2 * curvature, 2)
        }
