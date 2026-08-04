v8.6 — Track Map and Geometry-Based Section Tracking
What Changed

I implemented track_map.py to track the robot's position on the WRO track using cumulative traveled distance. Since the approximate track geometry is known beforehand, the track is divided into logical sections:

start_straight
first_curve
mid_straight
pillar_zone
second_curve
parking_approach
parking_zone

Each section stores its start distance, end distance, and the expected robot behavior. Every control update adds the measured travel distance and determines which section the robot is currently inside.

The module also tracks lap count, section progress, and automatically resets the accumulated distance whenever the start/finish line is detected.

Errors Encountered

During repeated lap testing, small odometry errors accumulated over time.

[TRACK_MAP] INFO: Lap 1 distance = 9.28m
[TRACK_MAP] INFO: Lap 2 distance = 9.56m
[TRACK_MAP] WARN: Expected start line near 9.20m
[TRACK_MAP] INFO: Lap 3 distance = 9.85m

Although each lap only introduced a small error, after several laps the accumulated distance no longer matched the actual position on the track. This caused incorrect section selection.

The problem was not the section definitions themselves—the accumulated distance simply drifted over time due to normal odometry error.

The Fix

Whenever the downward camera detects the start/finish line, the accumulated distance is reset and a new lap begins.

if start_finish:
    self._distance_m = 0.0
    self._current_lap += 1

To reduce long-term drift, the module records the accumulated distance error at every lap reset.

After three laps, the average error is used to slightly adjust the distance calibration factor.

correction = -avg_error / self._track_length * 0.001
self._calibration_factor += correction

The calibration factor is limited to a safe range so it cannot change excessively.

Alternatives Considered
Fixed calibration

A constant wheel calibration factor is simple but cannot compensate for changing wheel slip.

Visual localization

Using cameras to determine the robot's absolute position would reduce drift, but requires significantly more computation than simple distance tracking.

External positioning

External localization systems would provide accurate positioning but require additional hardware that is unnecessary for this application.

Periodic distance reset (Chosen)

Resetting the accumulated distance at every start/finish crossing is simple, reliable, and completely removes lap-to-lap error accumulation.

Testing
Single lap tracking remained consistent.
Multi-lap testing correctly reset the accumulated distance every lap.
Section identification remained stable after repeated laps.
Calibration factor converged after several laps with small accumulated errors.
Section progress updated smoothly throughout the lap.
Lessons Learned

Any system based only on accumulated distance will eventually drift. Periodically resetting the position using a known reference point prevents the error from growing indefinitely. A small adaptive calibration also helps compensate for consistent wheel slip without introducing large corrections.