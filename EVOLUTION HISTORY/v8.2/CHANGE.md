v8.2 — Crab-Walk Steering Implementation
What Changed

Today I implemented the crab-walk steering mode for our WRO 2026 robot. In this mode, all four wheels steer to the same angle, allowing the robot to move diagonally while maintaining its heading. This steering mode is useful for controlled lateral movements during alignment and positioning tasks.

The implementation is contained in steer_crab.py. The steering command assigns the same steering angle to all four wheels, and the desired velocity is decomposed into forward and lateral components:

forward_velocity = speed * cos(theta)
lateral_velocity = speed * sin(theta)

A configurable speed limit of 0.5 m/s is also applied for safe crab-walk operation.

Problem Encountered

During testing, I noticed that the IMU heading estimate became unstable whenever the robot moved sideways. Although the robot was intentionally translating laterally, the IMU correction continued applying yaw corrections, producing unnecessary heading adjustments.

Typical logs looked like this:

[IMU] WARN: Heading correction applied during crab walk
[CONTROL] INFO: Steering mode = crab_walk
[CONTROL] WARN: Unwanted yaw correction detected

The steering system itself behaved correctly, but the controller was trying to compensate for motion that was expected.

The Fix

Instead of changing the Mahony filter directly, I introduced an IMU correction mode controller. When crab-walk mode is active, the controller switches the IMU into GYRO_ONLY mode.

imu_mode_controller.set_mode(ImuCorrectionMode.GYRO_ONLY)

This disables proportional and integral correction gains while allowing the gyroscope to continue propagating orientation.

When normal steering resumes, the controller switches back to the default correction mode.

This approach keeps the steering module independent from the IMU implementation and makes switching correction strategies straightforward.

Alternatives Considered

1. Disable yaw correction inside the filter

Directly modifying the Mahony filter during crab-walk would work, but it tightly couples the steering and sensor fusion modules.

2. Adaptive correction gains

Reducing correction gains during lateral motion would provide smoother behavior but requires additional tuning and increases controller complexity.

3. Magnetometer-based yaw correction

Using the magnetometer during crab-walk was considered, but magnetic disturbances on the competition field can reduce heading accuracy.

Testing
Crab-walk steering angle correctly applied to all four wheels.
Velocity decomposition produced the expected forward and lateral motion.
IMU correction mode switched successfully between normal driving and crab-walk.
No unexpected steering corrections observed during lateral movement.
Lessons Learned

Crab-walk introduces different vehicle dynamics than conventional steering. Separating steering behavior from IMU correction logic using dedicated operating modes results in cleaner software and makes the system easier to maintain and extend.