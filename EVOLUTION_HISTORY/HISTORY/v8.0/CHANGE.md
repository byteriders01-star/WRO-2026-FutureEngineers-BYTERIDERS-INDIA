v8.0 — Same-Phase Steering Implementation
What Changed

I implemented the first steering mode for the WRO robot: same-phase steering.

The implementation is contained in steer_same.py. Given a desired turning radius, the module computes a steering angle using the bicycle-model approximation:

steering_angle = atan(wheelbase / (2 * turning_radius))

The steering angle is then limited to the configured maximum steering angle before being applied equally to all four steering actuators. The resulting command is returned as a SteeringCommand object together with the requested turning radius and steering mode.

Errors Encountered

During testing, requesting very small turning radii produced steering angles larger than the mechanical steering limit.

For example:

Requested turning radius: 0.50 m
Computed steering angle: 28.6°
Maximum allowed angle: 25.0°

Without limiting the steering command, the calculated angle could exceed the physical capability of the steering mechanism.

The Fix

I introduced steering limits using the shared SteeringLimits structure.

Every computed steering angle is passed through validate_steering_angle() before generating the steering command.

angle = validate_steering_angle(angle, self.limits)

If the requested turning radius is smaller than the configured minimum turning radius, it is clamped before computing the steering angle.

turning_radius = max(
    turning_radius,
    self.config.min_turning_radius_m,
)

This guarantees that every steering command remains within the robot's mechanical limits.

Alternatives Considered
1. Reject invalid commands

Instead of clamping the turning radius, the module could reject requests below the minimum turning radius. This would make invalid requests more obvious but would require additional error handling elsewhere.

2. Compute individual wheel angles

A more advanced implementation could calculate different steering angles for each wheel. While this would better represent steering geometry, it adds unnecessary complexity for the current software architecture.

3. Fixed steering table

Another option was storing steering angles in a lookup table indexed by turning radius. This is simple but less flexible than computing the angle analytically.

Testing
Verified steering angle computation across multiple turning radii.
Confirmed steering angles never exceed the configured maximum.
Verified turning radii below the configured minimum are automatically clamped.
Confirmed all four wheels receive the same steering angle.
Verified the stop command returns zero steering for all wheels.

Lessons Learned

Even a simple steering model should always enforce mechanical limits before generating actuator commands. Clamping invalid steering requests keeps the interface predictable while protecting the steering mechanism from impossible commands.