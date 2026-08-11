import time
import logging
import math

class SurpriseRuleAdapter:
    """
    Handles 'Day-of-Competition' rule changes.
    Maps high-level intents (e.g., 'avoid_red') to physical actions.
    """
    def __init__(self, surprise_cfg: dict):
        self.cfg = surprise_cfg
        self.sign_logic = self.cfg.get("SIGN_LOGIC", "NORMAL")
        self.direction = self.cfg.get("DRIVING_DIRECTION", "CCW")
    
    def get_avoidance_direction(self, color: str) -> str:
        """Returns 'LEFT' or 'RIGHT' based on color and current logic."""
        is_reversed = (self.sign_logic.upper() == "REVERSED")
        if color == "green":
            return "RIGHT" if is_reversed else "LEFT"
        elif color == "red":
            return "LEFT" if is_reversed else "RIGHT"
        return "CENTER"

class MissionManagerLayer:
    """
    Layer 6: Mission Manager & State Machine
    Handles mission progression, lap count, and implements the WRO 2026 Rule 6 Surprise Rules Adapter.
    """
    def __init__(self, config: dict):
        self.config = config
        self.surprise_cfg = config.get("surprise_rules", {})
        self.adapter = SurpriseRuleAdapter(self.surprise_cfg)

        # State Machine States: INIT -> RUNNING -> SEARCHING_PARKING -> PARKING_MANEUVER -> FINISHED
        self.state = "INIT"
        self.lap_count = 0
        self.max_laps = 3
        
        # Robust Lap Counting
        self.last_heading = 0.0
        self.accumulated_yaw_rad = 0.0
        self.lap_cooldown_start = 0.0
        self.start_zone_x = 0.0
        self.start_zone_y = 0.0
        
        # Stop and Go Timer
        self.stop_and_go_triggered = False
        self.stop_start_time = 0.0
        self.finish_time = 0.0

        # Surprise Rule Parameters
        self.narrow_mode = self.surprise_cfg.get("NARROW_TRACK_MODE", False)
        self.emergency_dist = self.surprise_cfg.get("EMERGENCY_BRAKE_DIST_MM", 180)

        logging.info(f"[LAYER 6] Mission Manager Loaded. Logic: {self.adapter.sign_logic} | Dir: {self.adapter.direction}")

    def update_state(self, perception: dict, sensors: dict, localization: dict) -> dict:
        front_dist = sensors.get("front_mm", 1000.0)
        blue_marker = perception.get("blue_marker", False)
        magenta_marker = perception.get("magenta_marker", None)
        red_pillar = perception.get("red_pillar", None)
        green_pillar = perception.get("green_pillar", None)

        heading_rad = localization.get("heading_rad", 0.0)
        x_mm = localization.get("x_mm", 0.0)
        y_mm = localization.get("y_mm", 0.0)

        # 1. Robust Lap Calculation (Heading Integration + Proximity)
        delta_h = heading_rad - self.last_heading
        if delta_h > math.pi: delta_h -= 2*math.pi
        if delta_h < -math.pi: delta_h += 2*math.pi
        self.accumulated_yaw_rad += delta_h
        self.last_heading = heading_rad

        # Check for lap completion (Approx 360 deg turn + back at start zone)
        # 6.28 rad = 360 deg. Use 5.5 as threshold for noise/slip.
        dist_to_start = math.sqrt((x_mm - self.start_zone_x)**2 + (y_mm - self.start_zone_y)**2)
        
        if abs(self.accumulated_yaw_rad) > 5.5 and dist_to_start < 800:
            if time.time() - self.lap_cooldown_start > 15.0: # Cooldown to prevent double counts
                self.lap_count += 1
                self.accumulated_yaw_rad = 0.0
                self.lap_cooldown_start = time.time()
                logging.info(f"[LAYER 6] LAP {self.lap_count} COMPLETE!")

        # 2. Emergency Braking Rule Check
        if front_dist > 0 and front_dist < self.emergency_dist and self.state not in ["EMERGENCY_BRAKE", "PARKING_MANEUVER", "FINISHED"]:
            logging.warning(f"[LAYER 6] EMERGENCY BRAKE TRIGGERED! Obstacle at {front_dist} mm.")
            self.state = "EMERGENCY_BRAKE"

        # 3. State Machine Transitions
        if self.state == "INIT":
            self.state = "RUNNING"
            self.start_zone_x, self.start_zone_y = x_mm, y_mm

        elif self.state == "RUNNING":
            if self.lap_count >= self.max_laps:
                self.state = "SEARCHING_PARKING"
                logging.info("[LAYER 6] 3 Laps complete. Searching for parking...")

            elif blue_marker and self.surprise_cfg.get("STOP_AND_GO_ENABLED", True) and not self.stop_and_go_triggered:
                self.state = "STOP_AND_GO"
                self.stop_start_time = time.time()
                self.stop_and_go_triggered = True

        elif self.state == "SEARCHING_PARKING":
            if magenta_marker is not None and magenta_marker["area"] > 1500:
                self.state = "PARKING_MANEUVER"
                self.stop_start_time = time.time()
                logging.info("[LAYER 6] Magenta marker detected! Initiating Parallel Park.")

        elif self.state == "PARKING_MANEUVER":
            # Mandatory 15-second stationary rule handler
            elapsed = time.time() - self.stop_start_time
            if elapsed > 5.0: # Assume parked after 5s maneuver
                self.state = "FINISHED"
                self.finish_time = time.time()
                logging.info("[LAYER 6] PARKING COMPLETE. Holding for 15s stationary rule.")

        elif self.state == "STOP_AND_GO":
            if time.time() - self.stop_start_time >= self.surprise_cfg.get("STOP_DURATION_SEC", 3.0):
                self.state = "RUNNING"

        elif self.state == "EMERGENCY_BRAKE":
            if front_dist > self.emergency_dist + 100:
                self.state = "RUNNING"

        # 4. Determine Pillar Avoidance Offset Direction via Adapter
        avoidance_offset = 0.0
        if green_pillar is not None:
            direction = self.adapter.get_avoidance_direction("green")
            avoidance_offset = 0.6 if direction == "LEFT" else -0.6
        elif red_pillar is not None:
            direction = self.adapter.get_avoidance_direction("red")
            avoidance_offset = 0.6 if direction == "LEFT" else -0.6

        return {
            "state": self.state,
            "lap_count": self.lap_count,
            "avoidance_offset": avoidance_offset,
            "narrow_mode": self.narrow_mode,
            "emergency_stop": (self.state in ["EMERGENCY_BRAKE", "STOP_AND_GO", "FINISHED"]),
            "is_parking": (self.state == "PARKING_MANEUVER")
        }
