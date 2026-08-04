import math
from dataclasses import dataclass


@dataclass
class SteeringCommand:
    front_left: float
    front_right: float
    rear_left: float
    rear_right: float
    turning_radius: float
    mode: str


@dataclass
class SteeringLimits:
    max_angle: float
    min_turning_radius: float


def validate_steering_angle(
    angle: float,
    limits: SteeringLimits,
) -> float:
    """
    Clamp a steering angle to the configured steering limits.
    """
    return max(-limits.max_angle, min(limits.max_angle, angle))


def rad_to_servo_pulse(angle_rad: float) -> int:
    """
    Convert a steering angle (radians) to a standard servo pulse width.
    0° -> 1500 µs
    -90° -> 1000 µs
    +90° -> 2000 µs
    """
    angle_deg = math.degrees(angle_rad)
    pulse = int(1500 + (angle_deg / 90.0) * 500)
    return max(1000, min(2000, pulse))