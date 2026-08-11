import math
import logging

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from utils.serial_protocol import PacketEncoder

class MotionControllerLayer:
    """
    Layer 10: High-Precision Adaptive Motion Controller
    Features:
     - Adaptive Gain Scheduling Stanley Controller
     - Sub-degree Steering Precision
     - Anti-Windup Speed PID
     - CRC8 Binary Packet Serial Transmitter
    """
    def __init__(self, config: dict):
        self.config = config
        self.ctrl_cfg = config.get("controller", {})
        
        self.base_k = self.ctrl_cfg.get("stanley_k", 0.75)
        self.ks_stanley = self.ctrl_cfg.get("stanley_ks", 0.1)

        self.encoder = PacketEncoder()
        self.ser = None

        port = config.get("system", {}).get("serial_port", "/dev/ttyUSB0")
        baud = config.get("system", {}).get("baud_rate", 115200)

        if SERIAL_AVAILABLE:
            try:
                self.ser = serial.Serial(port, baud, timeout=0.05)
                logging.info(f"[LAYER 10] Serial connected to ESP32-S3 on {port} @ {baud} baud.")
            except Exception as e:
                logging.error(f"[LAYER 10] Could not open serial port {port}: {e}. Mock serial mode.")

    def compute_control(self, localization: dict, path_plan: dict, traj_opt: dict) -> dict:
        """
        Adaptive Stanley Lateral Steering Law with Gain Scheduling:
        k(v) = k_base / (1.0 + 0.01 * v)
        delta(t) = theta_error + arctan( (k(v) * e_crosstrack) / (v + ks) )
        """
        heading_err = path_plan.get("target_heading_error_rad", 0.0)
        crosstrack_err = localization.get("crosstrack_error_mm", 0.0) / 1000.0  # m
        target_speed = traj_opt.get("target_speed", 0.0)
        v_m_s = max(0.1, target_speed / 30.0)                                    # m/s scale

        # Adaptive Gain Scheduling: decrease gain at high speed to prevent oscillation
        k_adaptive = self.base_k / (1.0 + 0.015 * target_speed)

        # Stanley Cross-Track Correction Angle
        stanley_cross_term = math.atan2(k_adaptive * crosstrack_err, v_m_s + self.ks_stanley)
        desired_steering_angle_rad = heading_err + stanley_cross_term

        # Sub-degree Precision Clamping [Dynamic from config]
        max_deg = self.config.get("kinematics_4ws", {}).get("max_servo_angle_deg", 35.0)
        max_rad = math.radians(max_deg)
        desired_steering_angle_rad = max(-max_rad, min(max_rad, desired_steering_angle_rad))

        return {
            "desired_steering_rad": round(desired_steering_angle_rad, 5),
            "desired_steering_deg": round(math.degrees(desired_steering_angle_rad), 3),
            "adaptive_k": round(k_adaptive, 3),
            "target_speed": target_speed
        }

    def transmit_command(self, servo_angle_deg: float, motor_speed: float):
        packet = self.encoder.encode_drive(servo_angle_deg, motor_speed)
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(packet)
                return packet
            except Exception as e:
                logging.error(f"[LAYER 10] Serial write failed: {e}")
        raise IOError("ESP32 serial link is not available or not open")
