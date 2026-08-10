import time
import logging
import os
import math
from surprise import read_yaml

YAML_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "surprise_rules.yaml")

class MissionManagerLayer:
    """
    Layer 6: Mission Manager & Finite State Machine
    Manages lap counting (using accumulated UKF yaw angle), starting from the parking lot,
    surprise rules adaption (reloading config dynamically), and precision parking.
    """
    def __init__(self, config: dict):
        self.config = config
        self.reload_surprise_rules()

        # FSM State variables
        self.state = "INIT"
        self.lap_count = 0
        self.max_laps = 3
        self.lap_start_time = time.time()
        
        # Yaw accumulation for lap counting
        self.accumulated_yaw_rad = 0.0
        self.last_heading_rad = None
        
        # Stop and Go Timer
        self.stop_and_go_triggered = False
        self.stop_start_time = 0.0
        
        # Parking control variables
        self.parking_side_detected = None # "LEFT" or "RIGHT"
        self.parking_start_time = 0.0
        self.parked_time = 0.0
        self.parking_phase = 0 # 0: align/drive past, 1: reverse turn 1, 2: reverse turn 2, 3: straight align, 4: stop
        self.park_x_ref = 0.0
        self.park_y_ref = 0.0

        logging.info(f"[LAYER 6] Loaded. Sign Logic: {self.sign_logic} | Direction: {self.direction} | Start From Parking: {self.start_from_parking}")

    def reload_surprise_rules(self):
        """Loads rules from surprise_rules.yaml using surprise.py custom parser."""
        surprise_cfg = read_yaml(YAML_PATH)
        self.sign_logic = surprise_cfg.get("SIGN_LOGIC", "NORMAL")
        self.direction = surprise_cfg.get("DRIVING_DIRECTION", "CCW")
        self.narrow_mode = surprise_cfg.get("NARROW_TRACK_MODE", False)
        self.stop_and_go_enabled = surprise_cfg.get("STOP_AND_GO_ENABLED", True)
        self.stop_duration = surprise_cfg.get("STOP_DURATION_SEC", 3.0)
        self.emergency_dist = surprise_cfg.get("EMERGENCY_BRAKE_DIST_MM", 180)
        self.parking_side_cfg = surprise_cfg.get("PARKING_SIDE", "DYNAMIC").upper()
        self.start_from_parking = surprise_cfg.get("START_FROM_PARKING", True)

    def update_state(self, perception: dict, sensors: dict, localization: dict) -> dict:
        front_dist = sensors.get("front_mm", 1000.0)
        left_dist = sensors.get("left_mm", 300.0)
        right_dist = sensors.get("right_mm", 300.0)
        
        blue_marker = perception.get("blue_marker", False)
        red_pillar = perception.get("red_pillar", None)
        green_pillar = perception.get("green_pillar", None)
        magenta_block = perception.get("magenta_block", None)
        
        heading_rad = localization.get("heading_deg", 0.0) * math.pi / 180.0 # get heading from state
        
        # 1. Update Lap Counter via Yaw Accumulation
        if self.last_heading_rad is not None:
            delta_heading = math.atan2(math.sin(heading_rad - self.last_heading_rad), math.cos(heading_rad - self.last_heading_rad))
            
            # Filter out random huge jumps or resets
            if abs(delta_heading) < 0.5:
                self.accumulated_yaw_rad += delta_heading
                
            # One complete lap is ~ 2 * pi radians (6.28 rad)
            # In CCW, we turn left (+yaw). In CW, we turn right (-yaw).
            expected_yaw = 2.0 * math.pi * (self.lap_count + 1)
            if abs(self.accumulated_yaw_rad) >= expected_yaw - 0.5: # 0.5 rad tolerance
                if self.lap_count < self.max_laps:
                    self.lap_count += 1
                    logging.info(f"[LAYER 6] LAP COMPLETED! Lap count: {self.lap_count}/3. Accumulated Yaw: {math.degrees(self.accumulated_yaw_rad):.1f}°")
                    
        self.last_heading_rad = heading_rad

        # 2. Emergency Obstacle Stopping (except during manual parking phases)
        if (front_dist > 0 and front_dist < self.emergency_dist and 
            self.state not in ("EMERGENCY_BRAKE", "PARKING_MANEUVER", "PARKED")):
            logging.warning(f"[LAYER 6] EMERGENCY BRAKE! Obstacle at {front_dist} mm.")
            self.state = "EMERGENCY_BRAKE"

        # 3. State Transitions FSM
        if self.state == "INIT":
            if self.start_from_parking:
                self.state = "START_FROM_PARKING"
                self.parking_start_time = time.time()
                logging.info("[LAYER 6] State: START_FROM_PARKING — Driving out of starting slot.")
            else:
                self.state = "RUNNING"
                logging.info("[LAYER 6] State: RUNNING.")

        elif self.state == "START_FROM_PARKING":
            # Drive forward/outward to align with lane. After 1.5 seconds, merge complete.
            if time.time() - self.parking_start_time > 1.5:
                self.state = "RUNNING"
                logging.info("[LAYER 6] State: RUNNING — Merged into main track.")

        elif self.state == "RUNNING":
            # Check Stop-and-Go Blue Marker
            if blue_marker and self.stop_and_go_enabled and not self.stop_and_go_triggered:
                logging.info(f"[LAYER 6] Stop-and-Go Blue Marker! Pausing for {self.stop_duration}s.")
                self.state = "STOP_AND_GO"
                self.stop_start_time = time.time()
                self.stop_and_go_triggered = True

            # If lap 3 is nearly complete (yaw is > 2.5 laps, i.e., 5.0 * pi rad)
            elif self.lap_count >= 3 or abs(self.accumulated_yaw_rad) >= (2.5 * 2.0 * math.pi):
                self.state = "PARKING_SEARCH"
                logging.info("[LAYER 6] State: PARKING_SEARCH — Initiating search for magenta blocks.")

            elif red_pillar is not None or green_pillar is not None:
                self.state = "AVOIDING_PILLAR"

        elif self.state == "STOP_AND_GO":
            if time.time() - self.stop_start_time >= self.stop_duration:
                logging.info("[LAYER 6] Stop-and-Go complete. Resuming.")
                self.state = "RUNNING"

        elif self.state == "AVOIDING_PILLAR":
            if red_pillar is None and green_pillar is None:
                self.state = "RUNNING"

        elif self.state == "EMERGENCY_BRAKE":
            if front_dist > self.emergency_dist + 100:
                logging.info("[LAYER 6] Emergency obstacle cleared. Resuming.")
                self.state = "RUNNING"

        elif self.state == "PARKING_SEARCH":
            # Look for magenta marker blocks
            if magenta_block is not None and magenta_block["distance_est_mm"] < 600.0:
                self.state = "PARKING_APPROACH"
                self.parking_start_time = time.time()
                
                # Determine parking side: LEFT or RIGHT
                if self.parking_side_cfg in ("LEFT", "RIGHT"):
                    self.parking_side_detected = self.parking_side_cfg
                else:
                    # DYNAMIC auto-detect:
                    # If magenta block center is on left half of frame, it is on the left
                    if magenta_block["normalized_x"] < 0.0:
                        self.parking_side_detected = "LEFT"
                    else:
                        self.parking_side_detected = "RIGHT"
                
                logging.info(f"[LAYER 6] State: PARKING_APPROACH — Magenta block seen at {magenta_block['distance_est_mm']}mm. Side: {self.parking_side_detected}")

        elif self.state == "PARKING_APPROACH":
            # Slow down and align next to the block.
            # Once side distance is aligned and we start passing the block, trigger maneuver phase.
            side_dist = left_dist if self.parking_side_detected == "LEFT" else right_dist
            
            # If the side distance sensor sees a dip (wall opening) or time limit exceeded
            if (side_dist > 400.0) or (time.time() - self.parking_start_time > 3.0):
                self.state = "PARKING_MANEUVER"
                self.parking_phase = 1
                self.parking_start_time = time.time()
                logging.info("[LAYER 6] State: PARKING_MANEUVER — Executing S-turn reverse park.")

        elif self.state == "PARKING_MANEUVER":
            # Executing Ackerman S-turn reverse parallel parking maneuver
            elapsed = time.time() - self.parking_start_time
            
            if self.parking_phase == 1:
                # Phase 1: Drive forward past the parking slot slightly
                if elapsed > 1.2:
                    self.parking_phase = 2
                    self.parking_start_time = time.time()
                    logging.info("[LAYER 6] Maneuver Phase 2: Reverse steer towards wall.")
            
            elif self.parking_phase == 2:
                # Phase 2: Reverse steer fully towards the wall
                if elapsed > 1.5:
                    self.parking_phase = 3
                    self.parking_start_time = time.time()
                    logging.info("[LAYER 6] Maneuver Phase 3: Reverse steer away from wall to align.")
            
            elif self.parking_phase == 3:
                # Phase 3: Reverse steer away from the wall to swing the nose in and align parallel
                side_dist = left_dist if self.parking_side_detected == "LEFT" else right_dist
                
                # Check if parallel to wall (using UKF heading alignment near wall)
                heading_err = abs(localization.get("heading_deg", 0.0) % 90)
                is_parallel = heading_err < 5.0 or heading_err > 85.0
                
                if elapsed > 1.5 or (is_parallel and side_dist < 180.0):
                    self.parking_phase = 4
                    self.parking_start_time = time.time()
                    logging.info("[LAYER 6] Maneuver Phase 4: Center steering and secure final position.")
            
            elif self.parking_phase == 4:
                # Phase 4: Final parallel alignment and come to a complete stop
                if elapsed > 1.0:
                    self.state = "PARKED"
                    self.parked_time = time.time()
                    logging.info("[LAYER 6] State: PARKED! Full stop. Starting 15-second stationary check.")

        elif self.state == "PARKED":
            # Stationary rule verification
            stationary_time = time.time() - self.parked_time
            if stationary_time % 3.0 < 0.1: # log heartbeat
                logging.info(f"[LAYER 6] PARKED — Stationary for {stationary_time:.1f}/15.0 seconds.")

        # Determine avoidance offset for pillars (Rule 6 logic)
        avoidance_offset = 0.0
        is_reversed = (self.sign_logic == "REVERSED")
        
        if green_pillar is not None:
            avoidance_offset = -0.65 if is_reversed else 0.65
        elif red_pillar is not None:
            avoidance_offset = 0.65 if is_reversed else -0.65

        # Return status dict
        return {
            "state": self.state,
            "lap_count": self.lap_count,
            "avoidance_offset": avoidance_offset,
            "sign_logic": self.sign_logic,
            "narrow_mode": self.narrow_mode,
            "emergency_stop": (self.state in ("EMERGENCY_BRAKE", "STOP_AND_GO", "PARKED")),
            "parking_side": self.parking_side_detected,
            "parking_phase": self.parking_phase
        }
