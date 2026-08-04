v8.1 — Opposite-Phase Steering Implementation
What Changed

I implemented the opposite-phase steering mode for the robot.

The implementation is contained in steer_opposite.py. In this steering mode, the front wheels steer in one direction while the rear wheels steer by the same amount in the opposite direction. This reduces the turning radius and allows tighter maneuvers compared to same-phase steering.

The steering angle is calculated using the bicycle-model approximation:

steering_angle = atan(wheelbase / (2 * turning_radius))

The front wheels receive the computed steering angle while the rear wheels receive its negative value.

front_left = angle
front_right = angle
rear_left = -angle
rear_right = -angle

The module also provides a configurable maximum driving speed for opposite-phase steering through get_speed_limit().

Errors Encountered

During testing, requesting turning radii smaller than the configured minimum produced steering angles larger than the steering mechanism could safely achieve.

Example:

Requested turning radius: 0.35 m
Configured minimum radius: 0.50 m
Computed steering angle exceeded steering limit.

Without limiting the steering command, unrealistic steering requests could generate invalid actuator commands.

The Fix

I added two safeguards.

First, the requested turning radius is clamped to the configured minimum turning radius before computing the steering angle.

turning_radius = max(
    turning_radius,
    self.config.min_turning_radius_m,
)

Second, every computed steering angle is validated against the configured steering limits.

angle = validate_steering_angle(angle, self.limits)

The module also exposes a configurable maximum speed value for opposite-phase steering.

speed_limit = self.get_speed_limit()

This allows higher-level software to reduce vehicle speed whenever opposite-phase steering is active.

Alternatives Considered
1. Reject invalid turning radius requests

Instead of automatically clamping the turning radius, the function could reject values below the minimum limit and report an error. Clamping was chosen because it guarantees a valid steering command.

2. Lookup table

A lookup table mapping turning radius to steering angle would avoid runtime calculations but would be less flexible than computing the steering angle directly.

3. Vehicle-specific steering model

A more detailed steering model could account for the exact vehicle geometry and individual wheel angles. The current implementation keeps the computation simple while remaining suitable for the existing software architecture.

Testing
Verified steering commands for multiple turning radii.
Confirmed rear wheel angles are always the negative of the front wheel angles.
Verified steering angles remain within configured limits.
Confirmed turning radii below the minimum are automatically clamped.
Verified the stop command returns zero steering for all wheels.
Verified the configured speed limit is returned correctly.
Lessons Learned

Even simple steering models benefit from enforcing mechanical constraints before generating actuator commands. Separating steering computation from speed limiting also keeps the steering module focused on geometry while allowing higher-level control software to decide how fast the robot should move in each steering mode.